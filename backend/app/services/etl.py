"""Turns the four raw tables into per-center snapshots.

Everything downstream — the API, the engine, the UI — consumes the output of
this module and never touches a raw frame. That is what makes the data source
swappable.

The transformation is deliberately conservative: it aggregates, it fits two
parameters (caller patience and queue size) that the source tables do not carry
directly, and it does nothing else. No imputation of missing centers, no
smoothing that would hide a real operational problem.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime

import numpy as np
import pandas as pd

from app.domain.enums import (
    CENTER_TYPE_LABELS,
    DIGITAL_CHANNELS,
    DISTRICT_LABELS,
    SIZE_LABELS,
    STATUS_LABELS,
    CenterSize,
    CenterStatus,
    CenterType,
    ChannelKind,
    District,
    LeverId,
)
from app.domain.models import (
    BaselineMetrics,
    KpiValue,
    LeverBounds,
    ServiceCenter,
    Snapshot,
    TrendPoint,
)
from app.simulation.coefficients import Coefficients
from app.simulation.engine import evaluate, extract_kpi
from app.simulation.erlang import fit_patience
from app.simulation.kpis import KPI_DEFINITIONS
from app.simulation.levers import to_display_units

#: How much recent history feeds the baseline. Long enough to average out a bad
#: day, short enough that a change made three weeks ago is not still dominating.
BASELINE_WINDOW_DAYS = 14
#: Length of the trend line shown on the simulation screen.
TREND_DAYS = 28

#: Policy default for the maximum acceptable abandonment rate. The source
#: tables do not carry a target, so it lives here until they do.
DEFAULT_ABANDONMENT_TARGET = 0.05

_SIZE_THRESHOLDS: tuple[tuple[int, CenterSize], ...] = (
    (35, CenterSize.SMALL),
    (75, CenterSize.MEDIUM),
)

#: Resolves a center type to its tuned coefficients. Injected so the ETL does
#: not need to know where the coefficients file lives.
CoefficientsResolver = Callable[[str], Coefficients]


class EtlError(RuntimeError):
    """Raised when the incoming data cannot produce a usable dataset."""


def _classify_size(headcount: int) -> CenterSize:
    for threshold, size in _SIZE_THRESHOLDS:
        if headcount < threshold:
            return size
    return CenterSize.LARGE


def _classify_status(sla: float, abandonment: float, raw_status: str) -> CenterStatus:
    """Derive operational health from live KPIs.

    The source table only flags hard outages; everything short of that is
    inferred, so the centers grid reflects reality rather than a field somebody
    last updated months ago.
    """
    if raw_status and raw_status.strip().lower() == "offline":
        return CenterStatus.OFFLINE
    if sla < 0.70 or abandonment > 0.12:
        return CenterStatus.CRITICAL
    if sla < 0.85 or abandonment > 0.07:
        return CenterStatus.STRAINED
    return CenterStatus.ACTIVE


def _weighted_mean(values: pd.Series, weights: pd.Series, default: float) -> float:
    total = float(weights.sum())
    if total <= 0 or values.empty:
        return default
    result = float((values * weights).sum() / total)
    return result if np.isfinite(result) else default


def _snapshot_id(center_id: str, captured_at: datetime, fingerprint: str) -> str:
    """Stable identifier for one baseline.

    Derived from the content, so a refresh that changes nothing keeps the same
    id and the client is not told its scenario is stale for no reason.
    """
    digest = hashlib.sha256(f"{center_id}|{fingerprint}".encode()).hexdigest()[:12]
    return f"snap_{center_id}_{digest}"


def build_dataset(
    *,
    centers: pd.DataFrame,
    interactions: pd.DataFrame,
    staffing: pd.DataFrame,
    channels: pd.DataFrame,
    coefficients_for: CoefficientsResolver,
) -> tuple[dict[str, ServiceCenter], dict[str, Snapshot]]:
    """Build the center directory and one snapshot per center."""
    if centers.empty:
        raise EtlError("centers table is empty")
    if interactions.empty:
        raise EtlError("interactions table is empty")

    captured_at = datetime.now(UTC)

    interactions = interactions.dropna(subset=["ts_bucket"]).copy()
    staffing = staffing.dropna(subset=["ts_bucket"]).copy()
    if interactions.empty:
        raise EtlError("interactions table has no usable timestamps")

    latest = interactions["ts_bucket"].max()
    baseline_from = latest - pd.Timedelta(days=BASELINE_WINDOW_DAYS)
    trend_from = latest - pd.Timedelta(days=TREND_DAYS)

    recent_interactions = interactions[interactions["ts_bucket"] >= baseline_from]
    recent_staffing = staffing[staffing["ts_bucket"] >= baseline_from]
    trend_interactions = interactions[interactions["ts_bucket"] >= trend_from]

    interactions_by_center = dict(tuple(recent_interactions.groupby("center_id", sort=False)))
    staffing_by_center = dict(tuple(recent_staffing.groupby("center_id", sort=False)))
    trend_by_center = dict(tuple(trend_interactions.groupby("center_id", sort=False)))
    channels_by_center = dict(tuple(channels.groupby("center_id", sort=False)))

    directory: dict[str, ServiceCenter] = {}
    snapshots: dict[str, Snapshot] = {}

    for row in centers.itertuples(index=False):
        center_id = str(row.center_id)
        center_interactions = interactions_by_center.get(center_id)
        if center_interactions is None or center_interactions.empty:
            # A center with no recent traffic is not an error; it simply has
            # nothing to simulate. Skipping keeps it out of the grid rather
            # than showing a card full of zeroes.
            continue

        baseline, observed = _build_baseline(
            interactions=center_interactions,
            staffing=staffing_by_center.get(center_id, pd.DataFrame()),
            channels=channels_by_center.get(center_id, pd.DataFrame()),
            working_hours=float(row.working_hours_per_day),
        )

        center_type = CenterType(str(row.center_type))
        coefficients = coefficients_for(center_type.value)

        values = evaluate(baseline, coefficients, {})
        kpis = tuple(
            KpiValue(
                id=definition.id,
                label=definition.label,
                value=round(extract_kpi(definition.id, values, baseline, {}), 4),
                format=definition.format,
                direction=definition.direction,
            )
            for definition in KPI_DEFINITIONS
        )

        status = _classify_status(
            sla=float(values["service_level"]),
            abandonment=float(values["abandonment"]),
            raw_status=str(row.status),
        )
        size = _classify_size(int(row.headcount))
        district = District(str(row.district))

        enabled_channels = _enabled_channels(channels_by_center.get(center_id, pd.DataFrame()))

        directory[center_id] = ServiceCenter(
            id=center_id,
            name=str(row.center_name),
            center_type=center_type,
            center_type_label=CENTER_TYPE_LABELS[center_type],
            district=district,
            district_label=DISTRICT_LABELS[district],
            status=status,
            status_label=STATUS_LABELS[status],
            size=size,
            size_label=SIZE_LABELS[size],
            headcount=int(row.headcount),
            channels=enabled_channels,
            working_hours_per_day=float(row.working_hours_per_day),
            daily_contacts=int(round(baseline.daily_contacts)),
            sla_pct=round(float(values["service_level"]) * 100, 1),
            abandonment_pct=round(float(values["abandonment"]) * 100, 1),
        )

        trend = _build_trend(trend_by_center.get(center_id, pd.DataFrame()))
        fingerprint = _fingerprint(baseline, observed)

        snapshots[center_id] = Snapshot(
            id=_snapshot_id(center_id, captured_at, fingerprint),
            center_id=center_id,
            captured_at=captured_at,
            baseline=baseline,
            kpis=kpis,
            trend=trend,
            lever_defaults=_lever_defaults(baseline),
            lever_bounds=_lever_bounds(baseline),
        )

    if not directory:
        raise EtlError("no center produced a usable snapshot")

    return directory, snapshots


def _enabled_channels(channels: pd.DataFrame) -> tuple[ChannelKind, ...]:
    if channels.empty:
        return (ChannelKind.PHONE,)
    active = channels[channels["enabled"]]
    result: list[ChannelKind] = []
    for name in active["channel"].tolist():
        try:
            result.append(ChannelKind(str(name)))
        except ValueError:
            continue
    return tuple(result) or (ChannelKind.PHONE,)


def _build_baseline(
    *,
    interactions: pd.DataFrame,
    staffing: pd.DataFrame,
    channels: pd.DataFrame,
    working_hours: float,
) -> tuple[BaselineMetrics, dict[str, float]]:
    """Aggregate one center's recent history into engine inputs."""
    offered = interactions["offered"].fillna(0.0)
    days = max(interactions["ts_bucket"].dt.normalize().nunique(), 1)

    daily_contacts = float(offered.sum()) / days

    # Peak hour: average across days of each day's busiest hour, so a single
    # freak hour does not define the center's capacity requirement.
    #
    # `peak_hour_timestamps` is kept because staffing has to be sampled from
    # exactly these hours. Averaging volume across all days while sampling
    # staffing from only the busiest ones compares an average day's demand
    # against a peak day's roster, which flatters every center by 10-20% and
    # makes a strained site look healthy.
    hourly = (
        interactions.assign(hour=interactions["ts_bucket"].dt.floor("h"))
        .groupby("hour", sort=False)["offered"]
        .sum()
        .sort_index()
    )
    if hourly.empty:
        peak_hour_contacts = daily_contacts / max(working_hours, 1.0)
        peak_hour_timestamps = pd.DatetimeIndex([])
    else:
        peak_hour_timestamps = pd.DatetimeIndex(
            hourly.groupby(hourly.index.normalize()).idxmax().to_numpy()
        )
        peak_hour_contacts = float(hourly.loc[peak_hour_timestamps].mean())

    phone = interactions[interactions["channel"] == ChannelKind.PHONE.value]
    phone_offered = phone["offered"].fillna(0.0) if not phone.empty else pd.Series(dtype="float64")

    aht_sec = _weighted_mean(
        interactions["aht_sec"].fillna(0.0), offered, default=300.0
    )
    observed_wait = (
        _weighted_mean(phone["wait_sec"].fillna(0.0), phone_offered, default=60.0)
        if not phone.empty
        else 60.0
    )
    observed_abandonment = (
        float(phone["abandoned"].sum() / max(phone["offered"].sum(), 1e-9))
        if not phone.empty
        else 0.03
    )

    handled_total = float(interactions["handled"].sum())
    resolved_total = float(interactions["resolved_first_contact"].sum())
    fcr = resolved_total / handled_total if handled_total > 0 else 0.75

    # Digital adoption is the share of contacts arriving on a non-phone channel.
    digital_names = {c.value for c in DIGITAL_CHANNELS}
    digital_offered = float(interactions[interactions["channel"].isin(digital_names)]["offered"].sum())
    total_offered = float(offered.sum())
    digital_adoption = digital_offered / total_offered if total_offered > 0 else 0.0

    # Staffing at the peak hour, not the daily mean — that is the number the
    # queueing model needs.
    if staffing.empty:
        agents_scheduled = max(peak_hour_contacts * aht_sec / 3600.0 * 1.3, 1.0)
        shrinkage = 0.28
        sla_target_sec = 90.0
    else:
        staff_hourly = (
            staffing.assign(hour=staffing["ts_bucket"].dt.floor("h"))
            .groupby("hour", sort=False)["agents_scheduled"]
            .mean()
            .sort_index()
        )
        # Sample the roster from the very hours that produced the peak volume.
        aligned = (
            staff_hourly.reindex(peak_hour_timestamps).dropna()
            if len(peak_hour_timestamps)
            else pd.Series(dtype="float64")
        )
        agents_scheduled = float(aligned.mean()) if not aligned.empty else float(staff_hourly.max())
        agents_scheduled = max(agents_scheduled, 1.0)
        shrinkage = float(np.clip(staffing["shrinkage_pct"].mean() / 100.0, 0.05, 0.6))
        sla_target_sec = float(staffing["sla_target_sec"].dropna().median() or 90.0)

    config = _channel_config(channels, interactions)

    # Queue size via Little's law on observed waiting — the source tables carry
    # no queue-depth column, so it is reconstructed from what they do carry.
    queue_size = max(peak_hour_contacts * (observed_wait / 3600.0), 1.0)

    baseline = BaselineMetrics(
        daily_contacts=max(daily_contacts, 0.0),
        peak_hour_contacts=max(peak_hour_contacts, 0.0),
        aht_sec=max(aht_sec, 15.0),
        agents_scheduled=agents_scheduled,
        shrinkage=shrinkage,
        working_hours_per_day=working_hours,
        digital_adoption=float(np.clip(digital_adoption, 0.0, 1.0)),
        self_service_rate=config["self_service_rate"],
        automation_level=config["automation_level"],
        agent_ai_usage=config["agent_ai_usage"],
        customer_ai_usage=config["customer_ai_usage"],
        knowledge_base_quality=config["knowledge_base_quality"],
        fcr=float(np.clip(fcr, 0.05, 0.99)),
        sla_target_sec=max(sla_target_sec, 10.0),
        abandonment_target=DEFAULT_ABANDONMENT_TARGET,
        queue_size=queue_size,
        patience_sec=fit_patience(
            observed_abandonment=observed_abandonment,
            observed_asa_sec=observed_wait,
        ),
    )

    observed = {
        "observed_wait_sec": observed_wait,
        "observed_abandonment": observed_abandonment,
    }
    return baseline, observed


def _channel_config(channels: pd.DataFrame, interactions: pd.DataFrame) -> dict[str, float]:
    """Volume-weighted average of the per-channel configuration.

    Weighting by traffic matters: a fully automated channel handling 2% of
    contacts should not read as though the whole center is automated.
    """
    defaults = {
        "self_service_rate": 0.25,
        "automation_level": 0.20,
        "agent_ai_usage": 0.25,
        "customer_ai_usage": 0.25,
        "knowledge_base_quality": 0.55,
    }
    if channels.empty:
        return defaults

    volume = interactions.groupby("channel", sort=False)["offered"].sum()
    active = channels[channels["enabled"]].copy()
    if active.empty:
        return defaults

    active["weight"] = active["channel"].map(volume).fillna(0.0)
    if float(active["weight"].sum()) <= 0:
        active["weight"] = 1.0

    return {
        key: float(np.clip(_weighted_mean(active[key].fillna(default), active["weight"], default), 0.0, 1.0))
        for key, default in defaults.items()
    }


def _build_trend(interactions: pd.DataFrame) -> tuple[TrendPoint, ...]:
    if interactions.empty:
        return ()
    daily = (
        interactions.assign(day=interactions["ts_bucket"].dt.normalize())
        .groupby("day", sort=True)["offered"]
        .sum()
    )
    return tuple(
        TrendPoint(label=day.strftime("%d/%m"), value=round(float(value), 1))
        for day, value in daily.items()
    )


def _lever_defaults(baseline: BaselineMetrics) -> dict[LeverId, float]:
    """Where each lever sits for this center today, in display units."""
    model_values: dict[LeverId, float] = {
        LeverId.DIGITAL_ADOPTION: baseline.digital_adoption,
        LeverId.SELF_SERVICE_RATE: baseline.self_service_rate,
        LeverId.AUTOMATION_LEVEL: baseline.automation_level,
        LeverId.AGENT_AI: baseline.agent_ai_usage,
        LeverId.CUSTOMER_AI: baseline.customer_ai_usage,
        LeverId.KNOWLEDGE_BASE_QUALITY: baseline.knowledge_base_quality,
        LeverId.FIRST_CALL_RESOLUTION: baseline.fcr,
        LeverId.ABANDONMENT_TARGET: baseline.abandonment_target,
        LeverId.WORKFORCE_CAPACITY: round(baseline.agents_scheduled),
        LeverId.WORKING_HOURS: baseline.working_hours_per_day,
        LeverId.AVERAGE_HANDLE_TIME: round(baseline.aht_sec),
        LeverId.SLA_TARGET: baseline.sla_target_sec,
        LeverId.QUEUE_SIZE: round(baseline.queue_size),
    }
    return {
        lever_id: round(to_display_units(lever_id, value), 2)
        for lever_id, value in model_values.items()
    }


def _lever_bounds(baseline: BaselineMetrics) -> dict[LeverId, LeverBounds]:
    """Ranges for the levers whose scale depends on the center's size."""
    agents = max(round(baseline.agents_scheduled), 1)
    queue = max(round(baseline.queue_size), 1)
    return {
        LeverId.WORKFORCE_CAPACITY: LeverBounds(
            min=max(1.0, float(round(agents * 0.4))),
            max=float(round(agents * 2.5)),
            step=1.0,
        ),
        LeverId.QUEUE_SIZE: LeverBounds(
            min=max(1.0, float(round(queue * 0.25))),
            max=float(round(max(queue * 3.0, 10))),
            step=1.0,
        ),
    }


def _fingerprint(baseline: BaselineMetrics, observed: dict[str, float]) -> str:
    """Content hash of the baseline, used to keep snapshot ids stable."""
    parts = [
        f"{baseline.daily_contacts:.3f}",
        f"{baseline.peak_hour_contacts:.3f}",
        f"{baseline.aht_sec:.3f}",
        f"{baseline.agents_scheduled:.3f}",
        f"{baseline.shrinkage:.4f}",
        f"{baseline.digital_adoption:.5f}",
        f"{baseline.fcr:.5f}",
        f"{observed['observed_wait_sec']:.3f}",
    ]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]
