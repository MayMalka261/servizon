"""Erlang C, checked against values that can be verified independently."""

from __future__ import annotations

import math
from itertools import pairwise

import pytest

from app.simulation.erlang import (
    abandonment_rate,
    erlang_b,
    erlang_c,
    fit_patience,
    required_agents,
    solve_queue,
)


class TestErlangB:
    def test_single_server_matches_closed_form(self) -> None:
        # For N=1, B = a / (1 + a).
        for traffic in (0.5, 1.0, 2.5, 10.0):
            assert erlang_b(1, traffic) == pytest.approx(traffic / (1 + traffic))

    def test_no_traffic_means_no_blocking(self) -> None:
        assert erlang_b(10, 0.0) == 0.0

    def test_blocking_falls_as_servers_are_added(self) -> None:
        values = [erlang_b(n, 10.0) for n in range(1, 25)]
        assert all(later < earlier for earlier, later in pairwise(values))

    def test_stable_at_large_agent_counts(self) -> None:
        """The closed form overflows here; the recursion must not."""
        result = erlang_b(500, 400.0)
        assert math.isfinite(result)
        assert 0.0 <= result <= 1.0


def _erlang_c_direct(agents: int, traffic: float) -> float:
    """Erlang C from its defining summation, for cross-checking.

    Deliberately a different algorithm from the production one: the
    implementation derives C from the Erlang B recursion for numerical
    stability, so validating it against factorials catches an error in that
    derivation. Only usable for small N, where the factorials stay finite —
    which is exactly why it is not the implementation.
    """
    numerator = (traffic**agents / math.factorial(agents)) * (agents / (agents - traffic))
    tail = sum(traffic**k / math.factorial(k) for k in range(agents))
    return numerator / (tail + numerator)


class TestErlangC:
    @pytest.mark.parametrize(
        ("agents", "traffic"),
        [(8, 6.0), (5, 3.0), (12, 9.5), (20, 14.0), (3, 1.0), (15, 2.5)],
    )
    def test_matches_the_defining_summation(self, agents: int, traffic: float) -> None:
        assert erlang_c(agents, traffic) == pytest.approx(
            _erlang_c_direct(agents, traffic), rel=1e-9
        )

    def test_known_hand_computed_value(self) -> None:
        """A=6 erlangs across 8 agents.

        Erlang B recursion gives B = 0.1218758; with rho = 0.75,
        C = B / (1 - rho(1 - B)) = 0.3569811.
        """
        assert erlang_b(8, 6.0) == pytest.approx(0.1218758, abs=1e-7)
        assert erlang_c(8, 6.0) == pytest.approx(0.3569811, abs=1e-7)

    def test_saturated_system_always_waits(self) -> None:
        assert erlang_c(5, 5.0) == 1.0
        assert erlang_c(5, 9.0) == 1.0

    def test_bounded_to_probability(self) -> None:
        for agents in range(1, 40):
            value = erlang_c(agents, 12.0)
            assert 0.0 <= value <= 1.0


class TestSolveQueue:
    def test_known_service_level(self) -> None:
        """100 calls/hr, 180s AHT -> 5 erlangs. 8 agents, 20s target."""
        outcome = solve_queue(calls_per_hour=100.0, aht_sec=180.0, agents=8.0, sla_target_sec=20.0)
        assert outcome.occupancy == pytest.approx(5.0 / 8.0)
        assert 0.7 < outcome.service_level < 0.95
        assert 0 < outcome.asa_sec < 60
        assert not outcome.is_overloaded

    def test_overload_is_reported_not_raised(self) -> None:
        outcome = solve_queue(
            calls_per_hour=1000.0, aht_sec=300.0, agents=10.0, sla_target_sec=60.0
        )
        assert outcome.is_overloaded
        assert outcome.service_level == 0.0
        assert math.isfinite(outcome.asa_sec)

    def test_adding_agents_never_hurts(self) -> None:
        previous = -1.0
        for agents in range(10, 45):
            outcome = solve_queue(
                calls_per_hour=200.0, aht_sec=300.0, agents=float(agents), sla_target_sec=60.0
            )
            assert outcome.service_level >= previous - 1e-9
            previous = outcome.service_level

    def test_idle_center(self) -> None:
        outcome = solve_queue(calls_per_hour=0.0, aht_sec=300.0, agents=5.0, sla_target_sec=60.0)
        assert outcome.service_level == 1.0
        assert outcome.asa_sec == 0.0

    def test_rejects_nonsense_aht(self) -> None:
        with pytest.raises(ValueError):
            solve_queue(calls_per_hour=10.0, aht_sec=0.0, agents=5.0, sla_target_sec=60.0)


class TestRequiredAgents:
    def test_meets_the_target_it_returns(self) -> None:
        needed = required_agents(
            calls_per_hour=200.0,
            aht_sec=300.0,
            sla_target_sec=60.0,
            target_service_level=0.85,
        )
        outcome = solve_queue(
            calls_per_hour=200.0, aht_sec=300.0, agents=float(needed), sla_target_sec=60.0
        )
        assert outcome.service_level >= 0.85

    def test_is_minimal(self) -> None:
        needed = required_agents(
            calls_per_hour=200.0,
            aht_sec=300.0,
            sla_target_sec=60.0,
            target_service_level=0.85,
        )
        one_fewer = solve_queue(
            calls_per_hour=200.0, aht_sec=300.0, agents=float(needed - 1), sla_target_sec=60.0
        )
        assert one_fewer.service_level < 0.85

    def test_scales_with_demand(self) -> None:
        small = required_agents(
            calls_per_hour=100.0, aht_sec=300.0, sla_target_sec=60.0, target_service_level=0.9
        )
        large = required_agents(
            calls_per_hour=400.0, aht_sec=300.0, sla_target_sec=60.0, target_service_level=0.9
        )
        assert large > small
        # Square-root staffing: quadrupling demand needs less than 4x the
        # agents, because the buffer grows with the root of the load.
        assert large < small * 4


class TestAbandonment:
    def test_no_wait_no_abandonment(self) -> None:
        assert abandonment_rate(asa_sec=0.0, patience_sec=180.0) == 0.0

    def test_rises_with_waiting(self) -> None:
        values = [abandonment_rate(asa_sec=w, patience_sec=180.0) for w in (10, 60, 120, 300)]
        assert all(later > earlier for earlier, later in pairwise(values))

    def test_patience_reduces_abandonment(self) -> None:
        impatient = abandonment_rate(asa_sec=90.0, patience_sec=60.0)
        patient = abandonment_rate(asa_sec=90.0, patience_sec=400.0)
        assert patient < impatient

    def test_patience_fit_round_trips(self) -> None:
        """Fitting patience from an observation must reproduce that observation."""
        fitted = fit_patience(observed_abandonment=0.12, observed_asa_sec=90.0)
        assert abandonment_rate(asa_sec=90.0, patience_sec=fitted) == pytest.approx(0.12, abs=1e-6)

    def test_patience_fit_handles_degenerate_input(self) -> None:
        assert fit_patience(observed_abandonment=0.0, observed_asa_sec=0.0) > 0
        assert fit_patience(observed_abandonment=1.0, observed_asa_sec=50.0) > 0
