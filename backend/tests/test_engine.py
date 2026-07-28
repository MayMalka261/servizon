"""The properties the simulation engine must hold.

Determinism, non-mutation and directionality are the three things a
decision-support tool cannot get wrong: a manager who sees two different
answers to the same question, or who suspects the tool touched live data, will
stop using it — correctly.
"""

from __future__ import annotations

import pytest

from app.domain.enums import Direction, KpiId, LeverId, SimulationTab
from app.domain.models import BaselineMetrics, Snapshot
from app.simulation import rules as R
from app.simulation.engine import (
    ORDERED_RULES,
    RuleGraphError,
    SimulationEngine,
    _topological_order,
    evaluate,
    resolve_levers,
)

CENTER_TYPE = "technical_support"


def _kpi(result, kpi_id: KpiId):
    return next(k for k in result.kpis if k.id is kpi_id)


class TestRuleGraph:
    def test_every_rule_is_ordered(self) -> None:
        assert len(ORDERED_RULES) == len(R.RULES)

    def test_dependencies_come_first(self) -> None:
        produced: set[str] = set()
        for rule in ORDERED_RULES:
            missing = set(rule.inputs) - produced
            assert not missing, f"{rule.id} runs before {missing} exist"
            produced.update(rule.outputs)

    def test_cycle_is_rejected(self) -> None:
        cyclic = (
            R.Rule(id="a", label="a", inputs=("y",), outputs=("x",), fn=lambda ctx: {}),
            R.Rule(id="b", label="b", inputs=("x",), outputs=("y",), fn=lambda ctx: {}),
        )
        with pytest.raises(RuleGraphError, match="cycle"):
            _topological_order(cyclic)

    def test_missing_producer_is_rejected(self) -> None:
        broken = (
            R.Rule(id="a", label="a", inputs=("nope",), outputs=("x",), fn=lambda ctx: {}),
        )
        with pytest.raises(RuleGraphError, match="no rule produces"):
            _topological_order(broken)

    def test_duplicate_producer_is_rejected(self) -> None:
        duplicated = (
            R.Rule(id="a", label="a", inputs=(), outputs=("x",), fn=lambda ctx: {}),
            R.Rule(id="b", label="b", inputs=(), outputs=("x",), fn=lambda ctx: {}),
        )
        with pytest.raises(RuleGraphError, match="produced by both"):
            _topological_order(duplicated)


class TestDeterminism:
    def test_identical_inputs_give_identical_output(
        self, engine: SimulationEngine, snapshot: Snapshot
    ) -> None:
        levers = {LeverId.DIGITAL_ADOPTION: 62.0, LeverId.AGENT_AI: 55.0}
        first = engine.run(snapshot, CENTER_TYPE, SimulationTab.PHONE_CENTER, dict(levers))
        second = engine.run(snapshot, CENTER_TYPE, SimulationTab.PHONE_CENTER, dict(levers))
        assert first.kpis == second.kpis
        assert first.waterfall == second.waterfall
        assert first.levers == second.levers

    def test_repeated_runs_are_stable(
        self, engine: SimulationEngine, snapshot: Snapshot
    ) -> None:
        levers = {LeverId.WORKFORCE_CAPACITY: 70.0}
        results = {
            tuple((k.id, k.scenario) for k in
                  engine.run(snapshot, CENTER_TYPE, SimulationTab.PHONE_CENTER, dict(levers)).kpis)
            for _ in range(15)
        }
        assert len(results) == 1

    def test_lever_order_does_not_matter(
        self, engine: SimulationEngine, snapshot: Snapshot
    ) -> None:
        forwards = {LeverId.DIGITAL_ADOPTION: 60.0, LeverId.AGENT_AI: 50.0}
        backwards = {LeverId.AGENT_AI: 50.0, LeverId.DIGITAL_ADOPTION: 60.0}
        a = engine.run(snapshot, CENTER_TYPE, SimulationTab.PHONE_CENTER, forwards)
        b = engine.run(snapshot, CENTER_TYPE, SimulationTab.PHONE_CENTER, backwards)
        assert a.kpis == b.kpis


class TestNonMutation:
    def test_snapshot_is_frozen(self, snapshot: Snapshot) -> None:
        with pytest.raises(Exception):
            snapshot.baseline.daily_contacts = 1.0  # type: ignore[misc]

    def test_baseline_unchanged_after_many_runs(
        self, engine: SimulationEngine, snapshot: Snapshot
    ) -> None:
        """The core guarantee: simulating never touches the live snapshot."""
        before = snapshot.baseline.model_dump()
        before_defaults = dict(snapshot.lever_defaults)

        for adoption in range(0, 101, 5):
            engine.run(
                snapshot,
                CENTER_TYPE,
                SimulationTab.PHONE_CENTER,
                {LeverId.DIGITAL_ADOPTION: float(adoption), LeverId.AGENT_AI: 80.0},
            )

        assert snapshot.baseline.model_dump() == before
        assert dict(snapshot.lever_defaults) == before_defaults

    def test_context_values_do_not_leak_between_runs(
        self, baseline: BaselineMetrics, coefficients
    ) -> None:
        first = evaluate(baseline, coefficients, {LeverId.DIGITAL_ADOPTION: 0.9})
        second = evaluate(baseline, coefficients, {})
        assert second[R.V_DEFLECTION] == pytest.approx(1.0)
        assert first[R.V_AGENT_CONTACTS] < second[R.V_AGENT_CONTACTS]


class TestBaselineIdentity:
    def test_empty_scenario_reproduces_current_state(
        self, engine: SimulationEngine, snapshot: Snapshot
    ) -> None:
        """With nothing moved, every KPI's scenario must equal its current."""
        result = engine.run(snapshot, CENTER_TYPE, SimulationTab.PHONE_CENTER, {})
        for kpi in result.kpis:
            assert kpi.scenario == kpi.current, kpi.id
            assert kpi.difference == 0
            assert kpi.trend == 0

    def test_setting_levers_to_their_defaults_changes_nothing(
        self, engine: SimulationEngine, snapshot: Snapshot
    ) -> None:
        result = engine.run(
            snapshot,
            CENTER_TYPE,
            SimulationTab.PHONE_CENTER,
            dict(snapshot.lever_defaults),
        )
        for kpi in result.kpis:
            assert kpi.difference == pytest.approx(0.0, abs=1e-6), kpi.id
        assert result.waterfall == ()

    def test_incoming_calls_matches_observed_volume(
        self, engine: SimulationEngine, snapshot: Snapshot
    ) -> None:
        """No double counting of repeat contacts against the observed baseline."""
        result = engine.run(snapshot, CENTER_TYPE, SimulationTab.PHONE_CENTER, {})
        calls = _kpi(result, KpiId.INCOMING_CALLS)
        assert calls.current == pytest.approx(snapshot.baseline.daily_contacts, rel=0.001)


class TestDirectionality:
    """Each lever must move the chain the way the model claims it does."""

    def test_digital_adoption_chain(
        self, engine: SimulationEngine, snapshot: Snapshot
    ) -> None:
        result = engine.run(
            snapshot, CENTER_TYPE, SimulationTab.PHONE_CENTER, {LeverId.DIGITAL_ADOPTION: 70.0}
        )
        assert _kpi(result, KpiId.INCOMING_CALLS).difference < 0
        assert _kpi(result, KpiId.AVERAGE_WAITING_TIME).difference < 0
        assert _kpi(result, KpiId.ABANDONMENT_RATE).difference < 0
        assert _kpi(result, KpiId.SLA).difference > 0
        assert _kpi(result, KpiId.CUSTOMER_SATISFACTION).difference > 0

    def test_workforce_capacity_chain(
        self, engine: SimulationEngine, snapshot: Snapshot
    ) -> None:
        result = engine.run(
            snapshot, CENTER_TYPE, SimulationTab.PHONE_CENTER, {LeverId.WORKFORCE_CAPACITY: 80.0}
        )
        assert _kpi(result, KpiId.AVERAGE_WAITING_TIME).difference < 0
        assert _kpi(result, KpiId.SLA).difference > 0
        assert _kpi(result, KpiId.OCCUPANCY).difference < 0
        # Volume is unaffected by how many people answer the phone.
        assert _kpi(result, KpiId.INCOMING_CALLS).difference == 0

    def test_cutting_workforce_degrades_service(
        self, engine: SimulationEngine, snapshot: Snapshot
    ) -> None:
        result = engine.run(
            snapshot, CENTER_TYPE, SimulationTab.PHONE_CENTER, {LeverId.WORKFORCE_CAPACITY: 35.0}
        )
        assert _kpi(result, KpiId.SLA).difference < 0
        assert _kpi(result, KpiId.ABANDONMENT_RATE).difference > 0

    def test_agent_ai_shortens_handling_and_lifts_resolution(
        self, engine: SimulationEngine, snapshot: Snapshot
    ) -> None:
        result = engine.run(
            snapshot, CENTER_TYPE, SimulationTab.PHONE_CENTER, {LeverId.AGENT_AI: 80.0}
        )
        assert _kpi(result, KpiId.AHT).difference < 0
        assert _kpi(result, KpiId.FCR).difference > 0
        assert _kpi(result, KpiId.SLA).difference > 0

    def test_lower_fcr_creates_repeat_volume(
        self, engine: SimulationEngine, snapshot: Snapshot
    ) -> None:
        """Unresolved contacts come back — resolution is a volume lever."""
        result = engine.run(
            snapshot,
            CENTER_TYPE,
            SimulationTab.PHONE_CENTER,
            {LeverId.FIRST_CALL_RESOLUTION: 45.0},
        )
        assert _kpi(result, KpiId.INCOMING_CALLS).difference > 0

    def test_longer_handle_time_degrades_service(
        self, engine: SimulationEngine, snapshot: Snapshot
    ) -> None:
        result = engine.run(
            snapshot,
            CENTER_TYPE,
            SimulationTab.PHONE_CENTER,
            {LeverId.AVERAGE_HANDLE_TIME: 480.0},
        )
        assert _kpi(result, KpiId.SLA).difference < 0
        assert _kpi(result, KpiId.OCCUPANCY).difference > 0

    def test_tightening_sla_target_lowers_attainment(
        self, engine: SimulationEngine, snapshot: Snapshot
    ) -> None:
        """A stricter target does not change reality, only the score against it."""
        result = engine.run(
            snapshot, CENTER_TYPE, SimulationTab.PHONE_CENTER, {LeverId.SLA_TARGET: 20.0}
        )
        assert _kpi(result, KpiId.SLA).difference < 0
        assert _kpi(result, KpiId.AVERAGE_WAITING_TIME).difference == 0

    def test_extending_hours_flattens_the_peak(
        self, engine: SimulationEngine, snapshot: Snapshot
    ) -> None:
        result = engine.run(
            snapshot, CENTER_TYPE, SimulationTab.PHONE_CENTER, {LeverId.WORKING_HOURS: 24.0}
        )
        assert _kpi(result, KpiId.SLA).difference > 0
        assert _kpi(result, KpiId.INCOMING_CALLS).difference == 0


class TestCompounding:
    def test_effects_accumulate(self, engine: SimulationEngine, snapshot: Snapshot) -> None:
        alone = engine.run(
            snapshot, CENTER_TYPE, SimulationTab.PHONE_CENTER, {LeverId.DIGITAL_ADOPTION: 60.0}
        )
        together = engine.run(
            snapshot,
            CENTER_TYPE,
            SimulationTab.PHONE_CENTER,
            {LeverId.DIGITAL_ADOPTION: 60.0, LeverId.SELF_SERVICE_RATE: 55.0},
        )
        assert (
            _kpi(together, KpiId.INCOMING_CALLS).scenario
            < _kpi(alone, KpiId.INCOMING_CALLS).scenario
        )

    def test_deflection_never_drives_volume_negative(
        self, engine: SimulationEngine, snapshot: Snapshot
    ) -> None:
        """Four deflection levers at maximum must compose, not overshoot."""
        result = engine.run(
            snapshot,
            CENTER_TYPE,
            SimulationTab.PHONE_CENTER,
            {
                LeverId.DIGITAL_ADOPTION: 100.0,
                LeverId.SELF_SERVICE_RATE: 100.0,
                LeverId.CUSTOMER_AI: 100.0,
                LeverId.AUTOMATION_LEVEL: 100.0,
            },
        )
        assert _kpi(result, KpiId.INCOMING_CALLS).scenario > 0


class TestLeverResolution:
    def test_values_are_clamped_to_bounds(self, snapshot: Snapshot) -> None:
        display, _ = resolve_levers(
            snapshot,
            {LeverId.DIGITAL_ADOPTION: 999.0, LeverId.AGENT_AI: -40.0},
            SimulationTab.PHONE_CENTER,
        )
        assert display[LeverId.DIGITAL_ADOPTION] == 100.0
        assert display[LeverId.AGENT_AI] == 0.0

    def test_per_center_bounds_win(self, snapshot: Snapshot) -> None:
        display, _ = resolve_levers(
            snapshot, {LeverId.WORKFORCE_CAPACITY: 5000.0}, SimulationTab.PHONE_CENTER
        )
        assert display[LeverId.WORKFORCE_CAPACITY] == 138.0

    def test_percent_levers_convert_to_fractions(self, snapshot: Snapshot) -> None:
        _, model = resolve_levers(
            snapshot, {LeverId.DIGITAL_ADOPTION: 65.0}, SimulationTab.PHONE_CENTER
        )
        assert model[LeverId.DIGITAL_ADOPTION] == pytest.approx(0.65)

    def test_absolute_levers_pass_through(self, snapshot: Snapshot) -> None:
        _, model = resolve_levers(
            snapshot, {LeverId.AVERAGE_HANDLE_TIME: 240.0}, SimulationTab.PHONE_CENTER
        )
        assert model[LeverId.AVERAGE_HANDLE_TIME] == 240.0

    def test_levers_outside_the_tab_are_dropped(self, snapshot: Snapshot) -> None:
        """Switching tabs mid-scenario is normal, not an error."""
        display, _ = resolve_levers(
            snapshot,
            {LeverId.QUEUE_SIZE: 30.0, LeverId.DIGITAL_ADOPTION: 60.0},
            SimulationTab.DIGITAL_CHANNELS,
        )
        assert LeverId.QUEUE_SIZE not in display
        assert LeverId.DIGITAL_ADOPTION in display


class TestKpiPresentation:
    def test_neutral_kpis_never_claim_improvement(
        self, engine: SimulationEngine, snapshot: Snapshot
    ) -> None:
        result = engine.run(
            snapshot, CENTER_TYPE, SimulationTab.PHONE_CENTER, {LeverId.WORKFORCE_CAPACITY: 80.0}
        )
        occupancy = _kpi(result, KpiId.OCCUPANCY)
        assert occupancy.direction is Direction.NEUTRAL
        assert occupancy.is_improvement is False
        assert occupancy.trend == -1

    def test_rounded_values_agree_with_the_delta(
        self, engine: SimulationEngine, snapshot: Snapshot
    ) -> None:
        """A card must never read 500 -> 500 next to a non-zero delta."""
        for adoption in (46.0, 47.0, 48.0, 50.0, 55.0):
            result = engine.run(
                snapshot,
                CENTER_TYPE,
                SimulationTab.PHONE_CENTER,
                {LeverId.DIGITAL_ADOPTION: adoption},
            )
            for kpi in result.kpis:
                assert kpi.difference == pytest.approx(kpi.scenario - kpi.current, abs=1e-4)
                if kpi.scenario == kpi.current:
                    assert kpi.trend == 0

    def test_percentages_are_finite_against_zero_baseline(
        self, engine: SimulationEngine, snapshot: Snapshot
    ) -> None:
        result = engine.run(
            snapshot, CENTER_TYPE, SimulationTab.PHONE_CENTER, {LeverId.WORKFORCE_CAPACITY: 130.0}
        )
        for kpi in result.kpis:
            assert kpi.percentage == kpi.percentage  # not NaN
            assert abs(kpi.percentage) < 1e6


class TestWaterfall:
    def test_only_moved_levers_appear(
        self, engine: SimulationEngine, snapshot: Snapshot
    ) -> None:
        result = engine.run(
            snapshot,
            CENTER_TYPE,
            SimulationTab.PHONE_CENTER,
            {LeverId.DIGITAL_ADOPTION: 70.0, LeverId.SLA_TARGET: 60.0},
        )
        levers = {step.lever for step in result.waterfall}
        assert LeverId.DIGITAL_ADOPTION in levers
        # SLA target was left at its default and does not move volume.
        assert LeverId.SLA_TARGET not in levers

    def test_ordered_by_magnitude(self, engine: SimulationEngine, snapshot: Snapshot) -> None:
        result = engine.run(
            snapshot,
            CENTER_TYPE,
            SimulationTab.PHONE_CENTER,
            {
                LeverId.DIGITAL_ADOPTION: 75.0,
                LeverId.SELF_SERVICE_RATE: 35.0,
                LeverId.AUTOMATION_LEVEL: 30.0,
            },
        )
        magnitudes = [abs(step.contribution) for step in result.waterfall]
        assert magnitudes == sorted(magnitudes, reverse=True)


class TestSnapshotStaleness:
    def test_flag_is_raised_when_client_is_behind(
        self, engine: SimulationEngine, snapshot: Snapshot
    ) -> None:
        result = engine.run(
            snapshot,
            CENTER_TYPE,
            SimulationTab.PHONE_CENTER,
            {LeverId.DIGITAL_ADOPTION: 60.0},
            snapshot_changed=True,
        )
        assert result.snapshot_changed
        # The scenario is still evaluated — the user's work is never discarded.
        assert result.kpis
        assert result.snapshot_id == snapshot.id
