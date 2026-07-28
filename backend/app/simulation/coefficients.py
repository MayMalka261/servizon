"""Loads and merges the simulation coefficients."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True, slots=True)
class Coefficients:
    """Resolved coefficients for one center type."""

    deflection: dict[str, float]
    aht: dict[str, float]
    fcr: dict[str, float]
    repeat_factor: float
    satisfaction: dict[str, float]
    queue_tolerance_at_min: float
    queue_tolerance_at_max: float
    hours_flattening: float


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Merge `override` into a copy of `base`, recursing into nested dicts.

    Overrides are partial by design: a center type states only what differs.
    """
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


@lru_cache(maxsize=8)
def _load_raw(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Coefficients file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict) or "default" not in data:
        raise ValueError(f"{path}: expected a mapping with a 'default' key")
    return data


def load_coefficients(path: Path, center_type: str) -> Coefficients:
    raw = _load_raw(path)
    resolved = raw["default"]
    override = (raw.get("by_center_type") or {}).get(center_type)
    if override:
        resolved = _deep_merge(resolved, override)

    return Coefficients(
        deflection=dict(resolved["deflection"]),
        aht=dict(resolved["aht"]),
        fcr=dict(resolved["fcr"]),
        repeat_factor=float(resolved["repeat"]["factor"]),
        satisfaction=dict(resolved["satisfaction"]),
        queue_tolerance_at_min=float(resolved["queue"]["tolerance_at_min"]),
        queue_tolerance_at_max=float(resolved["queue"]["tolerance_at_max"]),
        hours_flattening=float(resolved["workforce"]["hours_flattening"]),
    )
