"""Pydantic models forming the API contract.

These types are mirrored in `frontend/src/types/api.ts`. When one changes the
other must change with it.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import (
    CenterSize,
    CenterStatus,
    CenterType,
    ChannelKind,
    Direction,
    District,
    KpiFormat,
    KpiId,
    LeverId,
    Severity,
    SimulationTab,
)


class Frozen(BaseModel):
    """Immutable base.

    Snapshots must never be mutated in place — a simulation runs against a
    copy and the live data stays untouched. Freezing the models makes that a
    type-level guarantee rather than a convention someone can forget.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")


# ---------------------------------------------------------------------------
# Service centers
# ---------------------------------------------------------------------------


class ServiceCenter(Frozen):
    id: str
    name: str
    center_type: CenterType
    center_type_label: str
    district: District
    district_label: str
    status: CenterStatus
    status_label: str
    size: CenterSize
    size_label: str
    headcount: int = Field(ge=0)
    channels: tuple[ChannelKind, ...]
    working_hours_per_day: float = Field(gt=0, le=24)
    #: Headline numbers so the centers grid can render without extra requests.
    daily_contacts: int = Field(ge=0)
    sla_pct: float = Field(ge=0, le=100)
    abandonment_pct: float = Field(ge=0, le=100)


class CenterFilters(BaseModel):
    """Query parameters for the centers list."""

    search: str | None = None
    center_type: CenterType | None = None
    district: District | None = None
    status: CenterStatus | None = None
    size: CenterSize | None = None


# ---------------------------------------------------------------------------
# Baseline + snapshot
# ---------------------------------------------------------------------------


class BaselineMetrics(Frozen):
    """Raw operational inputs the simulation engine reasons about.

    All rates are fractions in [0, 1]; all durations are seconds.
    """

    daily_contacts: float = Field(ge=0)
    #: Contacts during the busiest hour — Erlang C is a steady-state model, so
    #: it is applied to the peak hour rather than a daily average.
    peak_hour_contacts: float = Field(ge=0)
    aht_sec: float = Field(gt=0)
    agents_scheduled: float = Field(ge=0)
    shrinkage: float = Field(ge=0, lt=1)
    working_hours_per_day: float = Field(gt=0, le=24)
    digital_adoption: float = Field(ge=0, le=1)
    self_service_rate: float = Field(ge=0, le=1)
    automation_level: float = Field(ge=0, le=1)
    agent_ai_usage: float = Field(ge=0, le=1)
    customer_ai_usage: float = Field(ge=0, le=1)
    knowledge_base_quality: float = Field(ge=0, le=1)
    fcr: float = Field(ge=0, le=1)
    sla_target_sec: float = Field(gt=0)
    abandonment_target: float = Field(ge=0, le=1)
    queue_size: float = Field(ge=0)
    #: Mean caller patience in seconds, fitted from observed abandonment.
    patience_sec: float = Field(gt=0)


class KpiValue(Frozen):
    """A single metric in its current (unsimulated) state."""

    id: KpiId
    label: str
    value: float
    format: KpiFormat
    direction: Direction


class TrendPoint(Frozen):
    """One bucket of the historical trend line."""

    label: str
    value: float


class LeverBounds(Frozen):
    """Per-center range for a lever whose scale depends on the center."""

    min: float
    max: float
    step: float


class Snapshot(Frozen):
    """An immutable point-in-time copy of a center's data.

    Every simulation is tagged with the `id` it ran against so results from
    two different baselines can never be silently compared.
    """

    id: str
    center_id: str
    captured_at: datetime
    baseline: BaselineMetrics
    kpis: tuple[KpiValue, ...]
    #: Observed daily volume per tab. Split by channel so each tab's chart
    #: compares its own history against its own projection — drawing a
    #: phone-only scenario line across all-channel history would overstate the
    #: deflection every time.
    trend: dict[SimulationTab, tuple[TrendPoint, ...]]
    #: Per-center starting position of each lever, in display units.
    lever_defaults: dict[LeverId, float]
    #: Overrides for levers whose range scales with the center's size.
    lever_bounds: dict[LeverId, LeverBounds]


# ---------------------------------------------------------------------------
# Levers
# ---------------------------------------------------------------------------


class LeverDefinition(Frozen):
    """Metadata describing one lever.

    Bounds live on the server so the UI cannot drift out of range.
    """

    id: LeverId
    label: str
    tooltip: str
    unit: str
    min: float
    max: float
    step: float
    tabs: tuple[SimulationTab, ...]
    group: str
    group_label: str
    #: When true, `min`/`max` above are only fallbacks — the real bounds scale
    #: with the center and arrive per-snapshot in `Snapshot.lever_bounds`.
    #: Headcount has no meaningful global range: 85 agents is generous for one
    #: center and a skeleton crew for another.
    dynamic_bounds: bool = False
    #: Optional parent, used to nest AI sub-levers under "AI Usage".
    parent: LeverId | None = None


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------


class SimulationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    center_id: str
    tab: SimulationTab = SimulationTab.PHONE_CENTER
    #: Only levers the user actually moved. Anything absent falls back to the
    #: snapshot default, so a partial payload is always valid.
    levers: dict[LeverId, float] = Field(default_factory=dict)
    #: Snapshot the client believes it is simulating against. When the
    #: background refresh has moved on, the server recomputes against the
    #: current snapshot and flags it via `snapshot_changed`.
    snapshot_id: str | None = None


class SimulatedKpi(Frozen):
    """A metric before and after the scenario."""

    id: KpiId
    label: str
    format: KpiFormat
    direction: Direction
    current: float
    scenario: float
    difference: float
    percentage: float
    #: -1 down, 0 flat, +1 up.
    trend: int
    #: True when the movement is in the desirable direction for this KPI.
    is_improvement: bool


class Recommendation(Frozen):
    id: str
    severity: Severity
    title: str
    body: str


class WaterfallStep(Frozen):
    """Attribution of the scenario delta to each lever the user moved."""

    lever: LeverId
    label: str
    contribution: float


class SimulationResult(Frozen):
    center_id: str
    snapshot_id: str
    tab: SimulationTab
    computed_at: datetime
    #: Echoed back after clamping, so the UI can correct out-of-range input.
    levers: dict[LeverId, float]
    kpis: tuple[SimulatedKpi, ...]
    recommendations: tuple[Recommendation, ...]
    waterfall: tuple[WaterfallStep, ...]
    #: Set when the client's `snapshot_id` was stale.
    snapshot_changed: bool = False


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------


class ScenarioCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    center_id: str
    name: str = Field(min_length=1, max_length=80)
    tab: SimulationTab
    levers: dict[LeverId, float]
    notes: str | None = Field(default=None, max_length=500)


class ScenarioUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=80)
    levers: dict[LeverId, float] | None = None
    notes: str | None = Field(default=None, max_length=500)


class Scenario(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    center_id: str
    name: str
    tab: SimulationTab
    levers: dict[LeverId, float]
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class CompareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    center_id: str
    scenario_ids: list[str] = Field(min_length=1, max_length=3)


class CompareColumn(Frozen):
    scenario_id: str
    name: str
    kpis: tuple[SimulatedKpi, ...]


class CompareResult(Frozen):
    center_id: str
    snapshot_id: str
    columns: tuple[CompareColumn, ...]
    #: KPI id -> scenario id that scores best on it.
    winners: dict[KpiId, str]


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class HealthStatus(Frozen):
    status: str
    data_source: str
    centers_loaded: int
    last_refresh: datetime | None
    next_refresh: datetime | None
    refresh_minutes: int
