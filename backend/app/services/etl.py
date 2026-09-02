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
    SimulationTab,
)
from app.domain.models import (
    BaselineMetrics,
    KpiValue,
    LeverBounds,
    ServiceCenter,
    Snapshot,
    TrendPoint,
    TrendSeries,
)
from app.services.snapshot_store import CenterHistory
from app.simulation import rules as R
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
) -> tuple[dict[str, ServiceCenter], dict[str, Snapshot], dict[str, CenterHistory]]:
    """Build the center directory, one snapshot per center, and the raw
    per-center history (trend window) behind it."""
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
    # Whole calendar days, not a raw timestamp cutoff: `latest` carries a
    # time-of-day, and slicing `latest - N days` chops the boundary day in
    # half. Averaging a nearly-empty half-day in with N-1 full days understates
    # the window by however much traffic that missing half-day would have had
    # — enough, in practice, to make a 7-day window look busier than the
    # 14-day one it is nested inside, which is what a date-range comparison
    # would otherwise flag as nonsensical.
    latest_day = latest.normalize()
    baseline_from = latest_day - pd.Timedelta(days=BASELINE_WINDOW_DAYS - 1)
    trend_from = latest_day - pd.Timedelta(days=TREND_DAYS - 1)

    recent_interactions = interactions[interactions["ts_bucket"] >= baseline_from]
    recent_staffing = staffing[staffing["ts_bucket"] >= baseline_from]
    trend_interactions = interactions[interactions["ts_bucket"] >= trend_from]
    #: Staffing over the same window as the trend, so a date range picked
    #: anywhere on the trend chart has a matching roster to compute against —
    #: not just the narrower window the default baseline uses.
    trend_staffing = staffing[staffing["ts_bucket"] >= trend_from]

    interactions_by_center = dict(tuple(recent_interactions.groupby("center_id", sort=False)))
    staffing_by_center = dict(tuple(recent_staffing.groupby("center_id", sort=False)))
    trend_by_center = dict(tuple(trend_interactions.groupby("center_id", sort=False)))
    trend_staffing_by_center = dict(tuple(trend_staffing.groupby("center_id", sort=False)))
    channels_by_center = dict(tuple(channels.groupby("center_id", sort=False)))

    directory: dict[str, ServiceCenter] = {}
    snapshots: dict[str, Snapshot] = {}
    history: dict[str, CenterHistory] = {}

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

        baseline = _recalibrate_patience(baseline, coefficients, observed)
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

        history[center_id] = CenterHistory(
            interactions=trend_by_center.get(center_id, pd.DataFrame()),
            staffing=trend_staffing_by_center.get(center_id, pd.DataFrame()),
            channels=channels_by_center.get(center_id, pd.DataFrame()),
            working_hours=float(row.working_hours_per_day),
            center_type=center_type.value,
        )

    if not directory:
        raise EtlError("no center produced a usable snapshot")

    return directory, snapshots, history


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

    aht_sec = _weighted_mean(interactions["aht_sec"].fillna(0.0), offered, default=300.0)
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
    digital_offered = float(
        interactions[interactions["channel"].isin(digital_names)]["offered"].sum()
    )
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


def build_baseline_for_range(
    history: CenterHistory,
    coefficients: Coefficients,
    date_from: str | None,
    date_to: str | None,
) -> BaselineMetrics | None:
    """Recompute a center's baseline from a caller-chosen slice of its history.

    Reuses the exact same aggregation the live baseline goes through — the
    only difference is which rows of the already-loaded trend window are fed
    in. Returns `None` when the window has no data (out of range, or the two
    bounds cross), so the caller can fall back to the live baseline rather
    than serve a made-up state.
    """
    interactions = history.interactions
    staffing = history.staffing

    if date_from:
        start = pd.Timestamp(date_from)
        interactions = interactions[interactions["ts_bucket"] >= start]
        staffing = staffing[staffing["ts_bucket"] >= start]
    if date_to:
        # Inclusive of the entire end day.
        end = pd.Timestamp(date_to) + pd.Timedelta(days=1)
        interactions = interactions[interactions["ts_bucket"] < end]
        staffing = staffing[staffing["ts_bucket"] < end]

    if interactions.empty:
        return None

    baseline, observed = _build_baseline(
        interactions=interactions,
        staffing=staffing,
        channels=history.channels,
        working_hours=history.working_hours,
    )
    return _recalibrate_patience(baseline, coefficients, observed)


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
        key: float(
            np.clip(
                _weighted_mean(active[key].fillna(default), active["weight"], default), 0.0, 1.0
            )
        )
        for key, default in defaults.items()
    }


def _recalibrate_patience(
    baseline: BaselineMetrics,
    coefficients: Coefficients,
    observed: dict[str, float],
) -> BaselineMetrics:
    """Re-fit caller patience so the model reproduces observed abandonment.

    The first fit inverts the abandonment formula using the *observed* waiting
    time. But the engine never sees that number: it computes abandonment from
    the ASA that Erlang C predicts, which is a different figure. The result was
    a baseline that disagreed with its own history — SC-111 reported 20.6%
    against 48% actually observed. Harmless while nothing plotted the history,
    and immediately visible once a trend chart sits beside the card.

    Patience does not influence ASA (that comes from arrival rate, handle time
    and staffing alone), so one extra pass is enough: evaluate to obtain the
    model's ASA and queue tolerance, then solve

        observed = 1 - exp(-ASA_model / (patience * tolerance))

    for patience. Abandonment then matches observation at baseline by
    construction, and every scenario moves away from a truthful starting point.
    """
    target = observed.get("observed_abandonment", 0.0)
    # Nothing to fit against at the extremes: no abandonment gives infinite
    # patience, total abandonment gives zero.
    if not 1e-4 < target < 0.95:
        return baseline

    values = evaluate(baseline, coefficients, {})
    asa = float(values[R.V_ASA])
    tolerance = float(values[R.V_QUEUE_TOLERANCE])
    if asa <= 0 or tolerance <= 0:
        return baseline

    patience = -asa / (tolerance * np.log(1.0 - target))
    if not np.isfinite(patience) or patience <= 0:
        return baseline

    return baseline.model_copy(update={"patience_sec": float(np.clip(patience, 20.0, 900.0))})


def _points(index: pd.Index, values: pd.Series, digits: int) -> tuple[TrendPoint, ...]:
    return tuple(
        TrendPoint(
            date=day.strftime("%Y-%m-%d"),
            label=day.strftime("%d/%m"),
            value=round(float(value), digits),
        )
        for day, value in zip(index, values, strict=True)
    )


def _build_trend(
    interactions: pd.DataFrame,
) -> dict[SimulationTab, TrendSeries]:
    """Observed daily history, split the same way the tabs are.

    The phone series is what the queueing model projects against; the digital
    series is what the deflection metrics project against. Keeping them apart
    means neither chart draws a scenario line across history it does not
    describe.

    Abandonment and handle time are ratios, so they are aggregated as daily
    totals divided by daily totals — never as a mean of per-bucket rates, which
    would weight a quiet 03:00 bucket the same as the peak hour and flatten the
    very variation the chart exists to show.
    """
    if interactions.empty:
        return {tab: TrendSeries() for tab in SimulationTab}

    digital_names = {c.value for c in DIGITAL_CHANNELS}
    frames = {
        SimulationTab.PHONE_CENTER: interactions[
            interactions["channel"] == ChannelKind.PHONE.value
        ],
        SimulationTab.DIGITAL_CHANNELS: interactions[
            interactions["channel"].isin(digital_names)
        ],
    }

    series: dict[SimulationTab, TrendSeries] = {}
    for tab, frame in frames.items():
        if frame.empty:
            series[tab] = TrendSeries()
            continue

        daily = frame.assign(day=frame["ts_bucket"].dt.normalize()).groupby("day", sort=True)
        offered = daily["offered"].sum()
        abandoned = daily["abandoned"].sum()
        # Volume-weighted: sum(aht * offered) / sum(offered).
        weighted_aht = daily.apply(
            lambda g: float((g["aht_sec"].fillna(0.0) * g["offered"].fillna(0.0)).sum()),
            include_groups=False,
        )

        safe_offered = offered.replace(0.0, np.nan)
        series[tab] = TrendSeries(
            volume=_points(offered.index, offered, 1),
            abandonment=_points(
                offered.index, (abandoned / safe_offered).fillna(0.0), 4
            ),
            aht=_points(offered.index, (weighted_aht / safe_offered).fillna(0.0), 1),
        )
    return series


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
