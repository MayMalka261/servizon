"""The simulation executor.

Runs the rule graph twice — once with the levers untouched to establish the
current state, once with the user's scenario — and reports the difference.
Deriving "current" from the same engine rather than from stored numbers is what
guarantees the comparison is apples to apples.

Two properties this module is built to hold, both covered by tests:

  * **Deterministic.** No randomness anywhere. The same snapshot and levers
    always produce byte-identical output.
  * **Non-mutating.** The snapshot and its baseline are frozen models and the
    engine only ever reads them. A simulation cannot damage live data.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from pathlib import Path

from app.domain.enums import Direction, KpiId, LeverId, SimulationTab
from app.domain.models import (
    BaselineMetrics,
    LeverBounds,
    SimulatedKpi,
    SimulationResult,
    Snapshot,
    WaterfallStep,
)
from app.simulation import rules as R
from app.simulation.coefficients import Coefficients, load_coefficients
from app.simulation.kpis import KPIS_BY_ID, kpis_for_tab
from app.simulation.levers import LEVERS_BY_ID, to_model_units
from app.simulation.recommendations import build_recommendations


class RuleGraphError(RuntimeError):
    """Raised when the rule graph cannot be ordered — a cycle or a missing producer."""


def _topological_order(rule_set: tuple[R.Rule, ...]) -> tuple[R.Rule, ...]:
    """Kahn's algorithm over the rules' declared inputs and outputs.

    Ordering is derived from the declarations rather than from the order rules
    happen to appear in the registry, so inserting a rule in the middle of the
    file cannot silently break the chain.
    """
    producer: dict[str, str] = {}
    for rule in rule_set:
        for output in rule.outputs:
            if output in producer:
                raise RuleGraphError(
                    f"value {output!r} is produced by both {producer[output]!r} and {rule.id!r}"
                )
            producer[output] = rule.id

    by_id = {rule.id: rule for rule in rule_set}
    dependencies: dict[str, set[str]] = {}
    for rule in rule_set:
        deps: set[str] = set()
        for required in rule.inputs:
            source = producer.get(required)
            if source is None:
                raise RuleGraphError(f"rule {rule.id!r} needs {required!r}, which no rule produces")
            deps.add(source)
        dependencies[rule.id] = deps

    ordered: list[R.Rule] = []
    # Sorting the ready set keeps execution order stable across runs, which
    # matters for reproducibility even though the results are order-independent.
    ready = sorted(rid for rid, deps in dependencies.items() if not deps)
    remaining = {rid: set(deps) for rid, deps in dependencies.items()}

    while ready:
        current = ready.pop(0)
        ordered.append(by_id[current])
        remaining.pop(current, None)
        newly_ready = []
        for rid, deps in remaining.items():
            if current in deps:
                deps.discard(current)
                if not deps:
                    newly_ready.append(rid)
        ready = sorted(ready + newly_ready)

    if len(ordered) != len(rule_set):
        stuck = sorted(set(by_id) - {rule.id for rule in ordered})
        raise RuleGraphError(f"cycle detected in rule graph involving {stuck}")

    return tuple(ordered)


#: Computed once at import; the graph is static.
ORDERED_RULES: tuple[R.Rule, ...] = _topological_order(R.RULES)


def evaluate(
    baseline: BaselineMetrics,
    coefficients: Coefficients,
    levers: dict[LeverId, float],
) -> dict[str, float]:
    """Run every rule in dependency order and return the accumulated values."""
    ctx = R.RuleContext(baseline=baseline, coefficients=coefficients, levers=dict(levers))
    for rule in ORDERED_RULES:
        ctx.values.update(rule.fn(ctx))
    return ctx.values


# --------------------------------------------------------------------------
# KPI extraction
# --------------------------------------------------------------------------

#: KPI -> the rule output that carries it.
_KPI_SOURCES: dict[KpiId, str] = {
    KpiId.INCOMING_CALLS: R.V_AGENT_CONTACTS,
    KpiId.AVERAGE_WAITING_TIME: R.V_ASA,
    KpiId.ABANDONMENT_RATE: R.V_ABANDONMENT,
    KpiId.SLA: R.V_SLA,
    KpiId.CUSTOMER_SATISFACTION: R.V_SATISFACTION,
    KpiId.FCR: R.V_EFFECTIVE_FCR,
    KpiId.AHT: R.V_EFFECTIVE_AHT,
    KpiId.OCCUPANCY: R.V_OCCUPANCY,
    KpiId.UTILIZATION: R.V_UTILIZATION,
    KpiId.QUEUE_LENGTH: R.V_QUEUE_LENGTH,
    KpiId.REQUIRED_AGENTS: R.V_REQUIRED_AGENTS,
    KpiId.AI_USAGE: R.V_AI_USAGE,
}


def extract_kpi(
    kpi_id: KpiId,
    values: dict[str, float],
    baseline: BaselineMetrics,
    levers: dict[LeverId, float],
) -> float:
    """Pull one KPI out of a completed run."""
    if kpi_id is KpiId.DIGITAL_ADOPTION:
        return levers.get(LeverId.DIGITAL_ADOPTION, baseline.digital_adoption)
    source = _KPI_SOURCES.get(kpi_id)
    if source is None:  # pragma: no cover - registry and sources are kept in sync
        raise KeyError(f"no rule output mapped for KPI {kpi_id}")
    return values[source]


def _round_for_display(kpi_id: KpiId, value: float) -> float:
    """Round to the precision the UI shows, before deltas are computed.

    Otherwise a card can read "500 -> 500" while the delta badge insists
    something changed, which destroys trust in the whole tool.
    """
    definition = KPIS_BY_ID[kpi_id]
    if kpi_id in (KpiId.INCOMING_CALLS, KpiId.REQUIRED_AGENTS):
        return float(round(value))
    if definition.format.value == "percent":
        return round(value, 4)
    if definition.format.value == "duration":
        return float(round(value))
    return round(value, 2)


def _build_simulated_kpi(kpi_id: KpiId, current: float, scenario: float) -> SimulatedKpi:
    definition = KPIS_BY_ID[kpi_id]
    current = _round_for_display(kpi_id, current)
    scenario = _round_for_display(kpi_id, scenario)
    difference = scenario - current
    percentage = (difference / current * 100.0) if current != 0 else 0.0

    if abs(difference) < 1e-9 or definition.direction is Direction.NEUTRAL:
        # A neutral KPI still reports its trend arrow; it just never claims the
        # movement is good or bad.
        trend = 0 if abs(difference) < 1e-9 else (1 if difference > 0 else -1)
        is_improvement = False
    else:
        trend = 1 if difference > 0 else -1
        improving_up = definition.direction is Direction.HIGHER_IS_BETTER
        is_improvement = (difference > 0) == improving_up

    return SimulatedKpi(
        id=kpi_id,
        label=definition.label,
        format=definition.format,
        direction=definition.direction,
        current=current,
        scenario=scenario,
        difference=round(difference, 4),
        percentage=round(percentage, 2),
        trend=trend,
        is_improvement=is_improvement,
    )


# --------------------------------------------------------------------------
# Lever resolution
# --------------------------------------------------------------------------


def _effective_bounds(lever_id: LeverId, snapshot: Snapshot) -> LeverBounds:
    definition = LEVERS_BY_ID[lever_id]
    override = snapshot.lever_bounds.get(lever_id)
    if override is not None:
        return override
    return LeverBounds(min=definition.min, max=definition.max, step=definition.step)


def resolve_levers(
    snapshot: Snapshot,
    requested: dict[LeverId, float],
    tab: SimulationTab,
) -> tuple[dict[LeverId, float], dict[LeverId, float]]:
    """Clamp and convert the requested lever values.

    Returns `(display_values, model_values)`. Display values are echoed back so
    the UI can snap a slider that was dragged out of range instead of silently
    disagreeing with the server.

    Levers that do not belong to the active tab are dropped rather than
    rejected — switching tabs with a scenario open is a normal thing to do.
    """
    display: dict[LeverId, float] = {}
    model: dict[LeverId, float] = {}

    for lever_id, raw in requested.items():
        definition = LEVERS_BY_ID.get(lever_id)
        if definition is None or tab not in definition.tabs:
            continue
        bounds = _effective_bounds(lever_id, snapshot)
        clamped = max(bounds.min, min(bounds.max, float(raw)))
        display[lever_id] = clamped

        # A lever sitting exactly on its default is left out of the model so
        # the engine reads the precise baseline instead.
        #
        # `lever_defaults` are rounded for display — headcount to whole agents,
        # AHT to whole seconds. Feeding those rounded figures back as a
        # scenario re-runs the model on inputs that differ slightly from
        # reality, and near the Erlang C cliff half an agent moves the service
        # level by points. The visible symptom is a center reporting a change
        # when the user has touched nothing, which is fatal to trust in the
        # tool. Saved scenarios store every lever, so this has to be handled
        # here rather than only by the client sending a partial payload.
        default = snapshot.lever_defaults.get(lever_id)
        if default is not None and math.isclose(clamped, default, rel_tol=1e-9, abs_tol=1e-9):
            continue

        model[lever_id] = to_model_units(lever_id, clamped)

    return display, model


def _moved_levers(
    snapshot: Snapshot, display: dict[LeverId, float]
) -> dict[LeverId, tuple[float, float]]:
    """Levers whose value differs from the center's current position."""
    moved: dict[LeverId, tuple[float, float]] = {}
    for lever_id, value in display.items():
        default = snapshot.lever_defaults.get(lever_id)
        if default is None:
            continue
        if abs(value - default) > 1e-9:
            moved[lever_id] = (default, value)
    return moved


# --------------------------------------------------------------------------
# Public entry point
# --------------------------------------------------------------------------


class SimulationEngine:
    """Stateless. Safe to share across requests and threads."""

    def __init__(self, coefficients_path: Path) -> None:
        self._coefficients_path = coefficients_path

    def coefficients_for(self, center_type: str) -> Coefficients:
        return load_coefficients(self._coefficients_path, center_type)

    def run(
        self,
        snapshot: Snapshot,
        center_type: str,
        tab: SimulationTab,
        requested_levers: dict[LeverId, float],
        *,
        snapshot_changed: bool = False,
    ) -> SimulationResult:
        coefficients = self.coefficients_for(center_type)
        baseline = snapshot.baseline

        display, model = resolve_levers(snapshot, requested_levers, tab)

        # The current state is the same engine with nothing moved, so the left
        # column of every card is produced by the identical code path as the
        # right one.
        current_values = evaluate(baseline, coefficients, {})
        scenario_values = evaluate(baseline, coefficients, model)

        kpis = tuple(
            _build_simulated_kpi(
                definition.id,
                extract_kpi(definition.id, current_values, baseline, {}),
                extract_kpi(definition.id, scenario_values, baseline, model),
            )
            for definition in kpis_for_tab(tab)
        )

        moved = _moved_levers(snapshot, display)
        waterfall = self._waterfall(baseline, coefficients, model, moved, tab)

        recommendations = build_recommendations(
            kpis=kpis,
            moved_levers=moved,
            baseline=baseline,
            scenario_values=scenario_values,
            levers=display,
        )

        return SimulationResult(
            center_id=snapshot.center_id,
            snapshot_id=snapshot.id,
            tab=tab,
            computed_at=datetime.now(UTC),
            levers=display,
            kpis=kpis,
            recommendations=recommendations,
            waterfall=waterfall,
            snapshot_changed=snapshot_changed,
        )

    def _waterfall(
        self,
        baseline: BaselineMetrics,
        coefficients: Coefficients,
        model_levers: dict[LeverId, float],
        moved: dict[LeverId, tuple[float, float]],
        tab: SimulationTab,
    ) -> tuple[WaterfallStep, ...]:
        """Attribute the change in contact volume to each lever the user moved.

        Each lever is re-run alone against the baseline. Interaction effects
        are therefore excluded, which is the standard simplification for a
        waterfall — the bars show each lever's own contribution, and the
        combined result on the KPI cards is the authoritative total.
        """
        if not moved:
            return ()

        base_volume = evaluate(baseline, coefficients, {})[R.V_AGENT_CONTACTS]
        steps: list[WaterfallStep] = []

        for lever_id in moved:
            if lever_id not in model_levers:
                continue
            solo = evaluate(baseline, coefficients, {lever_id: model_levers[lever_id]})
            contribution = solo[R.V_AGENT_CONTACTS] - base_volume
            if abs(contribution) < 0.5:
                continue
            steps.append(
                WaterfallStep(
                    lever=lever_id,
                    label=LEVERS_BY_ID[lever_id].label,
                    contribution=round(contribution, 1),
                )
            )

        steps.sort(key=lambda step: abs(step.contribution), reverse=True)
        return tuple(steps)
