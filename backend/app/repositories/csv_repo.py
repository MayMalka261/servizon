"""CSV-backed repository, used during development.

Reads the seed files produced by `scripts/generate_seed.py` and coerces every
column to the dtype declared in `schema.py`, so downstream code sees exactly
the same frames it would get from the SQL implementation.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.repositories.base import ServiceDataRepository
from app.repositories.schema import (
    CENTERS_COLUMNS,
    CHANNELS_COLUMNS,
    INTERACTIONS_COLUMNS,
    STAFFING_COLUMNS,
)


def _coerce(frame: pd.DataFrame, schema: dict[str, str], source: str) -> pd.DataFrame:
    """Apply the declared schema, failing loudly on a missing column.

    A silent NaN column here would surface much later as a nonsensical KPI, so
    the contract is enforced at the boundary.
    """
    missing = set(schema) - set(frame.columns)
    if missing:
        raise ValueError(f"{source}: missing required columns {sorted(missing)}")

    out = frame.loc[:, list(schema)].copy()
    for column, dtype in schema.items():
        if dtype.startswith("datetime"):
            out[column] = pd.to_datetime(out[column], errors="coerce")
        elif dtype == "bool":
            out[column] = (
                out[column].astype("string").str.strip().str.lower().isin({"true", "1", "yes"})
            )
        elif dtype.startswith(("int", "float")):
            out[column] = pd.to_numeric(out[column], errors="coerce").astype(dtype)
        else:
            out[column] = out[column].astype("string").str.strip()
    return out


class CsvRepository(ServiceDataRepository):
    name = "csv"

    def __init__(self, seed_dir: Path) -> None:
        self._dir = seed_dir

    def _read(self, filename: str, schema: dict[str, str]) -> pd.DataFrame:
        path = self._dir / filename
        if not path.exists():
            raise FileNotFoundError(
                f"Seed file not found: {path}. Run `python scripts/generate_seed.py` first."
            )
        return _coerce(pd.read_csv(path, encoding="utf-8"), schema, filename)

    def load_centers(self) -> pd.DataFrame:
        return self._read("centers.csv", CENTERS_COLUMNS)

    def load_interactions(self) -> pd.DataFrame:
        return self._read("interactions.csv", INTERACTIONS_COLUMNS)

    def load_staffing(self) -> pd.DataFrame:
        return self._read("staffing.csv", STAFFING_COLUMNS)

    def load_channels(self) -> pd.DataFrame:
        return self._read("channels.csv", CHANNELS_COLUMNS)

    def health_check(self) -> bool:
        return all(
            (self._dir / name).exists()
            for name in ("centers.csv", "interactions.csv", "staffing.csv", "channels.csv")
        )
