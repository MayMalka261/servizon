"""Recommendations must never contradict the KPI cards beside them."""

from __future__ import annotations

from app.domain.enums import LeverId, Severity, SimulationTab
from app.domain.models import Snapshot
from app.simulation.engine import SimulationEngine

CENTER_TYPE = "technical_support"


def _ids(result) -> set[str]:
    return {rec.id for rec in result.recommendations}


class TestStaffingGap:
    def test_added_capacity_is_not_reported_as_a_shortfall(
        self, engine: SimulationEngine, snapshot: Snapshot
    ) -> None:
        """The gap is measured against the scenario's roster, not today's.

        Telling a user who just added fifteen agents that they are still six
        short contradicts the SLA card next to it, and one visible
        contradiction is enough to make the whole panel untrustworthy.
        """
        result = engine.run(
            snapshot,
            CENTER_TYPE,
            SimulationTab.PHONE_CENTER,
            {LeverId.WORKFORCE_CAPACITY: 130.0},
        )

        required = next(k for k in result.kpis if k.id.value == "required_agents")
        assert required.scenario < 130

        assert "staffing_shortfall" not in _ids(result)

    def test_genuine_shortfall_is_still_reported(
        self, engine: SimulationEngine, snapshot: Snapshot
    ) -> None:
        result = engine.run(
            snapshot,
            CENTER_TYPE,
            SimulationTab.PHONE_CENTER,
            {LeverId.WORKFORCE_CAPACITY: 30.0},
        )
        assert "staffing_shortfall" in _ids(result)

    def test_surplus_is_reported_against_the_scenario(
        self, engine: SimulationEngine, snapshot: Snapshot
    ) -> None:
        result = engine.run(
            snapshot,
            CENTER_TYPE,
            SimulationTab.PHONE_CENTER,
            {LeverId.WORKFORCE_CAPACITY: 130.0},
        )
        assert "staffing_surplus" in _ids(result)


class TestConsistency:
    def test_untouched_scenario_says_so(self, engine: SimulationEngine, snapshot: Snapshot) -> None:
        result = engine.run(snapshot, CENTER_TYPE, SimulationTab.PHONE_CENTER, {})
        assert _ids(result) == {"idle"}

    def test_improving_scenario_is_not_flagged_as_a_problem(
        self, engine: SimulationEngine, snapshot: Snapshot
    ) -> None:
        result = engine.run(
            snapshot,
            CENTER_TYPE,
            SimulationTab.PHONE_CENTER,
            {LeverId.DIGITAL_ADOPTION: 70.0, LeverId.WORKFORCE_CAPACITY: 75.0},
        )
        headline = next(rec for rec in result.recommendations if rec.id == "headline")
        assert headline.severity is Severity.POSITIVE

    def test_every_recommendation_has_readable_text(
        self, engine: SimulationEngine, snapshot: Snapshot
    ) -> None:
        """Guards against template holes like a missing space between words."""
        for adoption in (55.0, 70.0, 90.0):
            result = engine.run(
                snapshot,
                CENTER_TYPE,
                SimulationTab.PHONE_CENTER,
                {LeverId.DIGITAL_ADOPTION: adoption},
            )
            for rec in result.recommendations:
                assert rec.title.strip()
                assert rec.body.strip()
                assert "  " not in rec.body, f"double space in {rec.id}"
                assert not rec.body.startswith(" ")
                # A Hebrew verb running straight into the next word is the
                # signature of a broken f-string join.
                assert "לשפרעמידה" not in rec.body
                assert "None" not in rec.body

    def test_overload_outranks_everything(
        self, engine: SimulationEngine, snapshot: Snapshot
    ) -> None:
        result = engine.run(
            snapshot,
            CENTER_TYPE,
            SimulationTab.PHONE_CENTER,
            {LeverId.WORKFORCE_CAPACITY: 22.0},
        )
        assert result.recommendations[0].severity is Severity.CRITICAL
