"""Erlang C queueing model.

This is the analytical core of the simulation. Using a standard workforce-
management model rather than invented multipliers means every number the tool
produces can be defended to an operations officer, and it reproduces the
non-linear cliff real service centers fall off: adding two agents to a strained
center helps enormously, adding two more to a comfortable one barely registers.

Assumptions, stated plainly because they bound where the results are valid:
  * Poisson arrivals, exponential handle times, agents interchangeable.
  * Steady state within the modelled interval — hence it is applied to the
    peak hour, not to a daily average that would smooth the peak away.
  * Callers who abandon are modelled separately (Erlang A style patience),
    not inside the Erlang C waiting-time expression itself.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

#: Beyond this the queue is unbounded in practice; clamping keeps the numbers
#: presentable instead of returning infinities to the UI.
MAX_WAIT_SEC = 3600.0


@dataclass(frozen=True, slots=True)
class QueueOutcome:
    """Steady-state behaviour of the queue for one set of inputs."""

    #: Probability an arriving contact has to wait at all.
    probability_wait: float
    #: Average speed of answer, seconds.
    asa_sec: float
    #: Fraction of contacts answered within the SLA target.
    service_level: float
    #: Share of agent time spent on contacts, 0-1. Above ~0.9 is unsustainable.
    occupancy: float
    #: Expected number of contacts waiting in queue.
    queue_length: float
    #: True when demand exceeds capacity and the queue grows without bound.
    is_overloaded: bool


def erlang_b(agents: float, traffic: float) -> float:
    """Blocking probability, computed by the numerically stable recursion.

    The closed form overflows for realistic agent counts; this recursion does
    not, which is why it is the standard implementation.
    """
    if traffic <= 0:
        return 0.0
    n = max(int(math.floor(agents)), 0)
    inv = 1.0
    for i in range(1, n + 1):
        inv = 1.0 + inv * i / traffic
    return 1.0 / inv if inv > 0 else 1.0


def erlang_c(agents: float, traffic: float) -> float:
    """Probability of waiting, derived from Erlang B."""
    if agents <= 0:
        return 1.0
    if traffic <= 0:
        return 0.0
    utilisation = traffic / agents
    if utilisation >= 1.0:
        return 1.0
    b = erlang_b(agents, traffic)
    denominator = 1.0 - utilisation * (1.0 - b)
    if denominator <= 0:
        return 1.0
    return min(b / denominator, 1.0)


def solve_queue(
    *,
    calls_per_hour: float,
    aht_sec: float,
    agents: float,
    sla_target_sec: float,
) -> QueueOutcome:
    """Run the model for one interval.

    `agents` is the productive count — shrinkage must already be removed by the
    caller, because an agent in a briefing is not answering the phone.
    """
    if aht_sec <= 0:
        raise ValueError("aht_sec must be positive")

    # Offered traffic in erlangs: concurrent contacts in progress on average.
    traffic = max(calls_per_hour, 0.0) * aht_sec / 3600.0
    productive = max(agents, 0.0)

    if traffic <= 0:
        return QueueOutcome(0.0, 0.0, 1.0, 0.0, 0.0, False)

    if productive <= traffic:
        # Demand at or above capacity. The queue diverges, so report the
        # clamped worst case rather than an infinity the UI cannot render.
        return QueueOutcome(
            probability_wait=1.0,
            asa_sec=MAX_WAIT_SEC,
            service_level=0.0,
            occupancy=1.0,
            queue_length=max(calls_per_hour * (MAX_WAIT_SEC / 3600.0), 0.0),
            is_overloaded=True,
        )

    p_wait = erlang_c(productive, traffic)
    spare = productive - traffic

    asa = p_wait * aht_sec / spare
    asa = min(asa, MAX_WAIT_SEC)

    service_level = 1.0 - p_wait * math.exp(-spare * sla_target_sec / aht_sec)
    service_level = min(max(service_level, 0.0), 1.0)

    occupancy = min(traffic / productive, 1.0)
    queue_length = p_wait * traffic / spare

    return QueueOutcome(
        probability_wait=p_wait,
        asa_sec=asa,
        service_level=service_level,
        occupancy=occupancy,
        queue_length=queue_length,
        is_overloaded=False,
    )


def required_agents(
    *,
    calls_per_hour: float,
    aht_sec: float,
    sla_target_sec: float,
    target_service_level: float,
    max_agents: int = 5000,
) -> int:
    """Smallest productive headcount meeting the service level target."""
    traffic = max(calls_per_hour, 0.0) * aht_sec / 3600.0
    if traffic <= 0:
        return 0

    # Start just above the point of stability and walk up; the service level is
    # monotonic in agent count, so the first hit is the minimum.
    n = max(int(math.floor(traffic)) + 1, 1)
    while n <= max_agents:
        outcome = solve_queue(
            calls_per_hour=calls_per_hour,
            aht_sec=aht_sec,
            agents=float(n),
            sla_target_sec=sla_target_sec,
        )
        if outcome.service_level >= target_service_level:
            return n
        n += 1
    return max_agents


def abandonment_rate(*, asa_sec: float, patience_sec: float, queue_tolerance: float = 1.0) -> float:
    """Share of contacts that hang up before being answered.

    Exponential patience: the longer the expected wait relative to how long
    callers will tolerate, the more of them leave. `queue_tolerance` scales
    patience to reflect queue-size policy — a caller told they are 3rd in line
    waits longer than one facing an unbounded queue.
    """
    if asa_sec <= 0:
        return 0.0
    effective_patience = max(patience_sec * max(queue_tolerance, 0.1), 1.0)
    return min(max(1.0 - math.exp(-asa_sec / effective_patience), 0.0), 1.0)


def fit_patience(*, observed_abandonment: float, observed_asa_sec: float) -> float:
    """Recover mean caller patience from observed history.

    Inverts `abandonment_rate` so each center's model is calibrated to its own
    callers instead of a shared constant. Falls back to a sane default when the
    history is too clean to fit against.
    """
    default = 180.0
    if observed_asa_sec <= 0:
        return default
    rate = min(max(observed_abandonment, 1e-4), 0.95)
    patience = -observed_asa_sec / math.log(1.0 - rate)
    if not math.isfinite(patience) or patience <= 0:
        return default
    return min(max(patience, 20.0), 900.0)
