"""The properties the simulation engine must hold.

Determinism, non-mutation and directionality are the three things a
decision-support tool cannot get wrong: a manager who sees two different
answers to the same question, or who suspects the tool touched live data, will
stop using it — correctly.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.domain.enums import Direction, KpiId, LeverId, SimulationTab
from app.domain.models import BaselineMetrics, Snapshot, TrendSeries
from app.simulation import rules as R
from app.simulation.engine import (
    ORDERED_RULES,
    RuleGraphError,
    SimulationEngine,
    _build_simulated_kpi,
    _topological_order,
    evaluate,
    resolve_levers,
)
from app.simulation.kpis import kpis_for_tab
from app.simulation.levers import levers_for_tab, to_model_units

CENTER_TYPE = "technical_support"


def _kpi(result, kpi_id: KpiId):
    return next(k for k in result.kpis if k.id is kpi_id)


def _values(
    engine: SimulationEngine,
    snapshot: Snapshot,
    levers: dict[LeverId, float],
) -> tuple[dict[str, float], dict[str, float]]:
    """Baseline and scenario rule-graph outputs, bypassing tab curation.

    `engine.run` returns only the KPIs the requested tab displays, which is a
    presentation decision. Model properties are asserted against the graph
    itself so that curating the interface can never silently disable a test of
    the mathematics.
    """
    coefficients = engine.coefficients_for(CENTER_TYPE)
    model = {lever: to_model_units(lever, value) for lever, value in levers.items()}
    return (
        evaluate(snapshot.baseline, coefficients, {}),
        evaluate(snapshot.baseline, coefficients, model),
    )


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
        broken = (R.Rule(id="a", label="a", inputs=("nope",), outputs=("x",), fn=lambda ctx: {}),)
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

    def test_repeated_runs_are_stable(self, engine: SimulationEngine, snapshot: Snapshot) -> None:
        levers = {LeverId.WORKFORCE_CAPACITY: 70.0}
        results = {
            tuple(
                (k.id, k.scenario)
                for k in engine.run(
                    snapshot, CENTER_TYPE, SimulationTab.PHONE_CENTER, dict(levers)
                ).kpis
            )
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
        """Immutability is enforced by the type system, not by convention."""
        with pytest.raises(ValidationError):
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

    def test_rounded_defaults_do_not_fabricate_a_change(
        self, engine: SimulationEngine, baseline: BaselineMetrics
    ) -> None:
        """Replaying the displayed defaults must reproduce the current state.

        `lever_defaults` are rounded for display — whole agents, whole seconds.
        A client that echoes them back (and every saved scenario does, since it
        stores all levers) must not have those rounded figures fed into the
        model: near the Erlang C cliff, half an agent is worth points of SLA,
        and the user sees the tool report a change to a scenario they never
        touched.

        The baseline here deliberately carries the awkward fractional values
        real ETL output has, which is exactly what the tidy round numbers in
        the shared fixture failed to catch.
        """
        from datetime import UTC, datetime

        awkward = baseline.model_copy(
            update={
                "agents_scheduled": 67.62,
                "aht_sec": 328.47,
                "fcr": 0.666403,
                "digital_adoption": 0.451192,
                "queue_size": 42.8,
            }
        )
        # Occupancy in the high nineties — the regime where the rounding error
        # actually bites.
        awkward = awkward.model_copy(update={"peak_hour_contacts": 690.0})

        rounded_defaults = {
            LeverId.WORKFORCE_CAPACITY: float(round(awkward.agents_scheduled)),
            LeverId.AVERAGE_HANDLE_TIME: float(round(awkward.aht_sec)),
            LeverId.FIRST_CALL_RESOLUTION: round(awkward.fcr * 100, 2),
            LeverId.DIGITAL_ADOPTION: round(awkward.digital_adoption * 100, 2),
            LeverId.QUEUE_SIZE: float(round(awkward.queue_size)),
        }

        rounded_snapshot = Snapshot(
            id="snap_rounded",
            center_id="SC-ROUND",
            captured_at=datetime.now(UTC),
            baseline=awkward,
            kpis=(),
            trend={tab: TrendSeries() for tab in SimulationTab},
            lever_defaults=rounded_defaults,
            lever_bounds={},
        )

        result = engine.run(
            rounded_snapshot,
            CENTER_TYPE,
            SimulationTab.PHONE_CENTER,
            dict(rounded_defaults),
        )

        for kpi in result.kpis:
            assert kpi.difference == 0, f"{kpi.id} moved without the user touching anything"
            assert kpi.trend == 0, kpi.id
        assert result.waterfall == ()

    def test_incoming_calls_matches_observed_volume(
        self, engine: SimulationEngine, snapshot: Snapshot
    ) -> None:
        """No double counting of repeat contacts against the observed baseline."""
        result = engine.run(snapshot, CENTER_TYPE, SimulationTab.PHONE_CENTER, {})
        calls = _kpi(result, KpiId.INCOMING_CALLS)
        assert calls.current == pytest.approx(snapshot.baseline.daily_contacts, rel=0.001)


class TestDirectionality:
    """Each lever must move the chain the way the model claims it does.

    These read rule-graph outputs rather than the KPI list `engine.run`
    returns. Directionality is a property of the model; which cards a tab
    chooses to show is a presentation decision, and the two should not be able
    to break each other.
    """

    def test_digital_adoption_chain(self, engine: SimulationEngine, snapshot: Snapshot) -> None:
        base, scenario = _values(engine, snapshot, {LeverId.DIGITAL_ADOPTION: 70.0})
        assert scenario[R.V_AGENT_CONTACTS] < base[R.V_AGENT_CONTACTS]
        assert scenario[R.V_ASA] < base[R.V_ASA]
        assert scenario[R.V_ABANDONMENT] < base[R.V_ABANDONMENT]
        assert scenario[R.V_SLA] > base[R.V_SLA]
        assert scenario[R.V_SATISFACTION] > base[R.V_SATISFACTION]

    def test_workforce_capacity_chain(self, engine: SimulationEngine, snapshot: Snapshot) -> None:
        base, scenario = _values(engine, snapshot, {LeverId.WORKFORCE_CAPACITY: 80.0})
        assert scenario[R.V_ASA] < base[R.V_ASA]
        assert scenario[R.V_SLA] > base[R.V_SLA]
        assert scenario[R.V_OCCUPANCY] < base[R.V_OCCUPANCY]
        # Volume is unaffected by how many people answer the phone.
        assert scenario[R.V_AGENT_CONTACTS] == pytest.approx(base[R.V_AGENT_CONTACTS])

    def test_cutting_workforce_degrades_service(
        self, engine: SimulationEngine, snapshot: Snapshot
    ) -> None:
        base, scenario = _values(engine, snapshot, {LeverId.WORKFORCE_CAPACITY: 35.0})
        assert scenario[R.V_SLA] < base[R.V_SLA]
        assert scenario[R.V_ABANDONMENT] > base[R.V_ABANDONMENT]

    def test_agent_ai_shortens_handling_and_lifts_resolution(
        self, engine: SimulationEngine, snapshot: Snapshot
    ) -> None:
        base, scenario = _values(engine, snapshot, {LeverId.AGENT_AI: 80.0})
        assert scenario[R.V_EFFECTIVE_AHT] < base[R.V_EFFECTIVE_AHT]
        assert scenario[R.V_EFFECTIVE_FCR] > base[R.V_EFFECTIVE_FCR]
        assert scenario[R.V_SLA] > base[R.V_SLA]

    def test_lower_fcr_creates_repeat_volume(
        self, engine: SimulationEngine, snapshot: Snapshot
    ) -> None:
        """Unresolved contacts come back — resolution is a volume lever."""
        base, scenario = _values(engine, snapshot, {LeverId.FIRST_CALL_RESOLUTION: 45.0})
        assert scenario[R.V_AGENT_CONTACTS] > base[R.V_AGENT_CONTACTS]

    def test_longer_handle_time_degrades_service(
        self, engine: SimulationEngine, snapshot: Snapshot
    ) -> None:
        base, scenario = _values(engine, snapshot, {LeverId.AVERAGE_HANDLE_TIME: 480.0})
        assert scenario[R.V_SLA] < base[R.V_SLA]
        assert scenario[R.V_OCCUPANCY] > base[R.V_OCCUPANCY]

    def test_tightening_sla_target_lowers_attainment(
        self, engine: SimulationEngine, snapshot: Snapshot
    ) -> None:
        """A stricter target does not change reality, only the score against it."""
        base, scenario = _values(engine, snapshot, {LeverId.SLA_TARGET: 20.0})
        assert scenario[R.V_SLA] < base[R.V_SLA]
        assert scenario[R.V_ASA] == pytest.approx(base[R.V_ASA])

    def test_extending_hours_flattens_the_peak(
        self, engine: SimulationEngine, snapshot: Snapshot
    ) -> None:
        base, scenario = _values(engine, snapshot, {LeverId.WORKING_HOURS: 24.0})
        assert scenario[R.V_SLA] > base[R.V_SLA]
        assert scenario[R.V_AGENT_CONTACTS] == pytest.approx(base[R.V_AGENT_CONTACTS])


class TestCompounding:
    def test_effects_accumulate(self, engine: SimulationEngine, snapshot: Snapshot) -> None:
        """Two deflection levers must beat either one alone."""
        _, alone = _values(engine, snapshot, {LeverId.DIGITAL_ADOPTION: 60.0})
        _, together = _values(
            engine,
            snapshot,
            {LeverId.DIGITAL_ADOPTION: 60.0, LeverId.SELF_SERVICE_RATE: 55.0},
        )
        assert together[R.V_AGENT_CONTACTS] < alone[R.V_AGENT_CONTACTS]

    def test_deflection_never_drives_volume_negative(
        self, engine: SimulationEngine, snapshot: Snapshot
    ) -> None:
        """Four deflection levers at maximum must compose, not overshoot."""
        _, scenario = _values(
            engine,
            snapshot,
            {
                LeverId.DIGITAL_ADOPTION: 100.0,
                LeverId.SELF_SERVICE_RATE: 100.0,
                LeverId.CUSTOMER_AI: 100.0,
                LeverId.AUTOMATION_LEVEL: 100.0,
            },
        )
        assert scenario[R.V_AGENT_CONTACTS] > 0


class TestLeverResolution:
    def test_values_are_clamped_to_bounds(self, snapshot: Snapshot) -> None:
        display, _ = resolve_levers(
            snapshot,
            {LeverId.DIGITAL_ADOPTION: 999.0, LeverId.AVERAGE_HANDLE_TIME: -40.0},
            SimulationTab.PHONE_CENTER,
        )
        assert display[LeverId.DIGITAL_ADOPTION] == 100.0
        assert display[LeverId.AVERAGE_HANDLE_TIME] == 30.0

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
    def test_neutral_kpis_never_claim_improvement(self) -> None:
        """A metric with a healthy band reports movement but never a verdict.

        Asserted on the presenter directly: occupancy is currently computed but
        not shown on either tab, and this guarantee has to survive that.
        """
        occupancy = _build_simulated_kpi(KpiId.OCCUPANCY, 0.96, 0.80)
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
    def test_only_moved_levers_appear(self, engine: SimulationEngine, snapshot: Snapshot) -> None:
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


class TestTabsAreDistinct:
    """The two tabs must answer different questions.

    They once shared ten of thirteen KPIs, so switching tabs looked like it did
    nothing — and the digital tab led with "incoming calls" and "required
    agents", phone concepts a digital manager cannot act on.
    """

    def test_kpi_sets_overlap_only_where_intended(self) -> None:
        phone = {k.id for k in kpis_for_tab(SimulationTab.PHONE_CENTER)}
        digital = {k.id for k in kpis_for_tab(SimulationTab.DIGITAL_CHANNELS)}

        # First-contact resolution is the one metric both tabs report: it is
        # the same question about the same contact whichever way it arrived.
        assert phone & digital == {KpiId.FCR}
        assert phone and digital

    def test_queue_metrics_stay_off_the_digital_tab(self) -> None:
        digital = {k.id for k in kpis_for_tab(SimulationTab.DIGITAL_CHANNELS)}
        for phone_only in (
            KpiId.INCOMING_CALLS,
            KpiId.AVERAGE_WAITING_TIME,
            KpiId.ABANDONMENT_RATE,
            KpiId.SLA,
            KpiId.REQUIRED_AGENTS,
        ):
            assert phone_only not in digital

    def test_phone_tab_excludes_digital_volume(self) -> None:
        phone = {k.id for k in kpis_for_tab(SimulationTab.PHONE_CENTER)}
        assert KpiId.DIGITAL_CONTACTS not in phone

    def test_hidden_kpis_reach_neither_tab(self) -> None:
        """Still computed for the rule graph, deliberately not displayed."""
        shown = {k.id for k in kpis_for_tab(SimulationTab.PHONE_CENTER)} | {
            k.id for k in kpis_for_tab(SimulationTab.DIGITAL_CHANNELS)
        }
        for hidden in (
            KpiId.OCCUPANCY,
            KpiId.UTILIZATION,
            KpiId.QUEUE_LENGTH,
            KpiId.CONTAINMENT_RATE,
            KpiId.ESCALATED_CONTACTS,
        ):
            assert hidden not in shown

    def test_filters_are_the_same_four_on_both_tabs(self) -> None:
        """The panel is a fixed set of filters, not a per-tab lever family."""
        expected = {
            LeverId.DIGITAL_ADOPTION,
            LeverId.WORKFORCE_CAPACITY,
            LeverId.AVERAGE_HANDLE_TIME,
            LeverId.SLA_TARGET,
        }
        for tab in SimulationTab:
            assert {lever.id for lever in levers_for_tab(tab)} == expected, tab

    def test_hidden_levers_are_dropped_from_a_request(self, snapshot: Snapshot) -> None:
        """A lever off the panel must not be steerable through the API."""
        display, _ = resolve_levers(
            snapshot,
            {LeverId.QUEUE_SIZE: 30.0, LeverId.DIGITAL_ADOPTION: 60.0},
            SimulationTab.PHONE_CENTER,
        )
        assert LeverId.QUEUE_SIZE not in display
        assert LeverId.DIGITAL_ADOPTION in display

    def test_each_tab_produces_its_own_kpis(
        self, engine: SimulationEngine, snapshot: Snapshot
    ) -> None:
        phone = engine.run(
            snapshot, CENTER_TYPE, SimulationTab.PHONE_CENTER, {LeverId.DIGITAL_ADOPTION: 60.0}
        )
        digital = engine.run(
            snapshot, CENTER_TYPE, SimulationTab.DIGITAL_CHANNELS, {LeverId.DIGITAL_ADOPTION: 60.0}
        )
        assert {k.id for k in phone.kpis} != {k.id for k in digital.kpis}

    def test_both_tabs_always_recommend_something(
        self, engine: SimulationEngine, snapshot: Snapshot
    ) -> None:
        """A tab with an empty recommendations panel looks broken."""
        for tab in SimulationTab:
            result = engine.run(snapshot, CENTER_TYPE, tab, {LeverId.DIGITAL_ADOPTION: 62.0})
            assert result.recommendations, tab
            assert all(rec.body.strip() for rec in result.recommendations), tab

    def test_handle_time_is_reported_on_both_tabs(
        self, engine: SimulationEngine, snapshot: Snapshot
    ) -> None:
        """Same underlying value, each tab's own wording."""
        phone = engine.run(
            snapshot, CENTER_TYPE, SimulationTab.PHONE_CENTER, {LeverId.AVERAGE_HANDLE_TIME: 240.0}
        )
        digital = engine.run(
            snapshot,
            CENTER_TYPE,
            SimulationTab.DIGITAL_CHANNELS,
            {LeverId.AVERAGE_HANDLE_TIME: 240.0},
        )
        assert _kpi(phone, KpiId.AHT).scenario == _kpi(digital, KpiId.AHT_DIGITAL).scenario
