"""The rule graph.

Each rule is a small pure function declaring what it reads and what it writes.
The engine sorts them topologically and runs them, so adding a metric means
adding a rule — never editing the executor. Effects compound naturally because
every rule reads the outputs of the ones before it.

Causal chain, top to bottom:

    levers -> effective AHT / FCR
           -> deflected contact volume
           -> repeat contacts from unresolved cases
           -> peak-hour load
           -> Erlang C  ->  waiting time, SLA, occupancy, queue length
           -> abandonment
           -> customer satisfaction

Nothing writes waiting time or SLA directly. They fall out of the queueing
model, which is what keeps the results consistent when several levers move at
once.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Final

from app.domain.enums import LeverId
from app.domain.models import BaselineMetrics
from app.simulation.coefficients import Coefficients
from app.simulation.erlang import (
    abandonment_rate,
    required_agents,
    solve_queue,
)

# --- value keys -----------------------------------------------------------
# Intermediate values flowing between rules. Kept as constants so a typo is a
# NameError at import time rather than a silently missing dependency.

V_EFFECTIVE_AHT: Final = "effective_aht_sec"
V_EFFECTIVE_FCR: Final = "effective_fcr"
V_DEFLECTION: Final = "deflection_factor"
V_AGENT_CONTACTS: Final = "agent_contacts_daily"
V_TOTAL_CONTACTS: Final = "total_contacts_daily"
V_PEAK_SHARE: Final = "peak_share"
V_PEAK_CALLS: Final = "peak_calls_per_hour"
V_PRODUCTIVE_AGENTS: Final = "productive_agents"
V_PROB_WAIT: Final = "probability_wait"
V_ASA: Final = "asa_sec"
V_SLA: Final = "service_level"
V_OCCUPANCY: Final = "occupancy"
V_QUEUE_LENGTH: Final = "queue_length"
V_OVERLOADED: Final = "is_overloaded"
V_ABANDONMENT: Final = "abandonment"
V_SATISFACTION: Final = "satisfaction"
V_REQUIRED_AGENTS: Final = "required_agents"
V_UTILIZATION: Final = "utilization"
V_QUEUE_TOLERANCE: Final = "queue_tolerance"
V_AI_USAGE: Final = "ai_usage"

# --- satisfaction reference points ---------------------------------------
# The service quality a caller treats as unremarkable. Scoring against fixed
# points rather than each center's own history is what lets satisfaction differ
# between a healthy center and a struggling one.
REF_SLA: Final = 0.85
REF_FCR: Final = 0.75
REF_ABANDONMENT: Final = 0.05
REF_ASA_SEC: Final = 60.0


@dataclass(slots=True)
class RuleContext:
    """Everything a rule may read.

    `baseline` and `levers` are inputs; `values` accumulates rule output. The
    baseline is never written to — that is the guarantee that a simulation
    cannot corrupt the live snapshot it ran against.
    """

    baseline: BaselineMetrics
    coefficients: Coefficients
    #: Lever values in model units — fractions for rates, seconds, headcount.
    levers: dict[LeverId, float]
    values: dict[str, float] = field(default_factory=dict)

    def lever(self, lever_id: LeverId, fallback: float) -> float:
        return self.levers.get(lever_id, fallback)

    def value(self, key: str) -> float:
        return self.values[key]


@dataclass(frozen=True, slots=True)
class Rule:
    id: str
    label: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    fn: Callable[[RuleContext], dict[str, float]]


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


# --- rule implementations -------------------------------------------------


def _rule_effective_aht(ctx: RuleContext) -> dict[str, float]:
    """Agent AI and a good knowledge base shorten handle time."""
    base = ctx.lever(LeverId.AVERAGE_HANDLE_TIME, ctx.baseline.aht_sec)
    agent_ai = ctx.lever(LeverId.AGENT_AI, ctx.baseline.agent_ai_usage)
    kb = ctx.lever(LeverId.KNOWLEDGE_BASE_QUALITY, ctx.baseline.knowledge_base_quality)

    # Deltas versus the baseline, so the AHT lever itself stays the anchor and
    # the assist levers only express change from where the center is today.
    d_agent_ai = agent_ai - ctx.baseline.agent_ai_usage
    d_kb = kb - ctx.baseline.knowledge_base_quality

    reduction = (
        d_agent_ai * ctx.coefficients.aht["agent_ai"]
        + d_kb * ctx.coefficients.aht["knowledge_base_quality"]
    )
    effective = base * (1.0 - _clamp(reduction, -0.6, 0.6))
    return {V_EFFECTIVE_AHT: max(effective, 15.0)}


def _rule_effective_fcr(ctx: RuleContext) -> dict[str, float]:
    """AI assistance and knowledge quality raise first-contact resolution."""
    base = ctx.lever(LeverId.FIRST_CALL_RESOLUTION, ctx.baseline.fcr)
    agent_ai = ctx.lever(LeverId.AGENT_AI, ctx.baseline.agent_ai_usage)
    kb = ctx.lever(LeverId.KNOWLEDGE_BASE_QUALITY, ctx.baseline.knowledge_base_quality)

    d_agent_ai = agent_ai - ctx.baseline.agent_ai_usage
    d_kb = kb - ctx.baseline.knowledge_base_quality

    gain = (
        d_agent_ai * ctx.coefficients.fcr["agent_ai"]
        + d_kb * ctx.coefficients.fcr["knowledge_base_quality"]
    )
    return {V_EFFECTIVE_FCR: _clamp(base + gain, 0.10, 0.99)}


def _rule_deflection(ctx: RuleContext) -> dict[str, float]:
    """How much contact volume never reaches an agent.

    Multiplicative composition. Adding the four levers would let them sum past
    100% and drive volume negative; multiplying survivors means each lever
    deflects a share of whatever the previous ones left behind, which is both
    bounded and closer to how these programmes actually stack.
    """
    coefficients = ctx.coefficients.deflection
    pairs = (
        (LeverId.DIGITAL_ADOPTION, ctx.baseline.digital_adoption, "digital_adoption"),
        (LeverId.SELF_SERVICE_RATE, ctx.baseline.self_service_rate, "self_service_rate"),
        (LeverId.CUSTOMER_AI, ctx.baseline.customer_ai_usage, "customer_ai"),
        (LeverId.AUTOMATION_LEVEL, ctx.baseline.automation_level, "automation_level"),
    )

    survival = 1.0
    for lever_id, baseline_value, key in pairs:
        delta = ctx.lever(lever_id, baseline_value) - baseline_value
        survival *= 1.0 - _clamp(delta * coefficients[key], -0.85, 0.85)

    return {V_DEFLECTION: _clamp(survival, 0.05, 3.0)}


def _rule_contact_volume(ctx: RuleContext) -> dict[str, float]:
    """Daily contacts reaching an agent, including repeats.

    Unresolved contacts come back. That feedback is what makes first-contact
    resolution a volume lever and not just a quality metric.

    The repeat multiplier is expressed *relative to the baseline*, because the
    observed volume already contains today's repeat calls. Applying the raw
    multiplier on top of it would count them twice and inflate every center's
    load by 20-30% — enough to push a healthy center over the Erlang cliff and
    report a meltdown that is not happening.
    """
    deflected = ctx.baseline.daily_contacts * ctx.value(V_DEFLECTION)

    factor = ctx.coefficients.repeat_factor
    repeats_scenario = 1.0 + (1.0 - ctx.value(V_EFFECTIVE_FCR)) * factor
    repeats_baseline = 1.0 + (1.0 - ctx.baseline.fcr) * factor

    total = max(deflected * (repeats_scenario / max(repeats_baseline, 1e-6)), 0.0)
    return {V_AGENT_CONTACTS: total, V_TOTAL_CONTACTS: ctx.baseline.daily_contacts}


def _rule_peak_load(ctx: RuleContext) -> dict[str, float]:
    """Contacts arriving in the busiest hour.

    Erlang C is a steady-state model; feeding it a daily average would hide the
    peak that actually breaks the service level. Extending opening hours
    spreads the same demand wider and flattens that peak.
    """
    baseline_share = (
        ctx.baseline.peak_hour_contacts / ctx.baseline.daily_contacts
        if ctx.baseline.daily_contacts > 0
        else 0.0
    )
    hours = ctx.lever(LeverId.WORKING_HOURS, ctx.baseline.working_hours_per_day)
    hours = max(hours, 1.0)
    ratio = ctx.baseline.working_hours_per_day / hours
    share = baseline_share * (ratio**ctx.coefficients.hours_flattening)
    share = _clamp(share, 0.005, 1.0)

    return {
        V_PEAK_SHARE: share,
        V_PEAK_CALLS: ctx.value(V_AGENT_CONTACTS) * share,
    }


def _rule_productive_agents(ctx: RuleContext) -> dict[str, float]:
    """Agents actually available to take contacts during the peak hour."""
    scheduled = ctx.lever(LeverId.WORKFORCE_CAPACITY, ctx.baseline.agents_scheduled)
    productive = max(scheduled, 0.0) * (1.0 - ctx.baseline.shrinkage)
    return {V_PRODUCTIVE_AGENTS: max(productive, 0.0)}


def _rule_queue(ctx: RuleContext) -> dict[str, float]:
    """Erlang C. Waiting time, service level, occupancy and queue length."""
    sla_target = ctx.lever(LeverId.SLA_TARGET, ctx.baseline.sla_target_sec)
    outcome = solve_queue(
        calls_per_hour=ctx.value(V_PEAK_CALLS),
        aht_sec=ctx.value(V_EFFECTIVE_AHT),
        agents=ctx.value(V_PRODUCTIVE_AGENTS),
        sla_target_sec=max(sla_target, 1.0),
    )
    return {
        V_PROB_WAIT: outcome.probability_wait,
        V_ASA: outcome.asa_sec,
        V_SLA: outcome.service_level,
        V_OCCUPANCY: outcome.occupancy,
        V_QUEUE_LENGTH: outcome.queue_length,
        V_OVERLOADED: 1.0 if outcome.is_overloaded else 0.0,
    }


def _rule_queue_tolerance(ctx: RuleContext) -> dict[str, float]:
    """Translate the queue-size policy into a patience multiplier.

    A short, declared queue keeps callers on the line; an unbounded one makes
    them give up sooner.
    """
    baseline_queue = max(ctx.baseline.queue_size, 1.0)
    queue = max(ctx.lever(LeverId.QUEUE_SIZE, baseline_queue), 1.0)
    # Ratio versus baseline, mapped onto the configured tolerance band.
    ratio = _clamp(queue / baseline_queue, 0.25, 3.0)
    low = ctx.coefficients.queue_tolerance_at_min
    high = ctx.coefficients.queue_tolerance_at_max
    # ratio 0.25 -> low (more patient), ratio 3.0 -> high (less patient)
    position = (ratio - 0.25) / (3.0 - 0.25)
    return {V_QUEUE_TOLERANCE: low + (high - low) * position}


def _rule_abandonment(ctx: RuleContext) -> dict[str, float]:
    """Callers who hang up before an agent picks up."""
    rate = abandonment_rate(
        asa_sec=ctx.value(V_ASA),
        patience_sec=ctx.baseline.patience_sec,
        queue_tolerance=ctx.value(V_QUEUE_TOLERANCE),
    )
    return {V_ABANDONMENT: rate}


def _rule_satisfaction(ctx: RuleContext) -> dict[str, float]:
    """Composite CSAT.

    Scored against fixed industry reference points rather than against the
    center's own baseline. That choice matters twice over:

      * A center already running at 50% SLA reports genuinely low satisfaction
        instead of a flat "average" that only moves when you touch a lever.
      * Because the reference points are constant, a scenario with nothing
        moved reproduces today's number exactly — no drift, no special case.

    The earlier formulation anchored on a constant and added deltas measured
    against slightly different assumptions on each side, which made every
    center report the same starting satisfaction and then saturate at the clamp
    the moment anything improved.
    """
    weights = ctx.coefficients.satisfaction
    reference = float(weights.get("wait_reference_sec", 180.0))

    score = (
        float(weights["base"])
        + (ctx.value(V_SLA) - REF_SLA) * float(weights["sla_weight"])
        + (ctx.value(V_EFFECTIVE_FCR) - REF_FCR) * float(weights["fcr_weight"])
        - (ctx.value(V_ABANDONMENT) - REF_ABANDONMENT) * float(weights["abandonment_weight"])
        - ((ctx.value(V_ASA) - REF_ASA_SEC) / reference) * float(weights["wait_weight"])
    )
    return {V_SATISFACTION: _clamp(score, 0.05, 0.99)}


def _rule_required_agents(ctx: RuleContext) -> dict[str, float]:
    """Headcount needed to hit the abandonment-implied service target.

    The target service level is derived from the abandonment target the user
    set, so the two targets stay coherent rather than contradicting each other.
    """
    abandonment_target = ctx.lever(LeverId.ABANDONMENT_TARGET, ctx.baseline.abandonment_target)
    target_service_level = _clamp(1.0 - abandonment_target * 3.0, 0.50, 0.98)
    sla_target = ctx.lever(LeverId.SLA_TARGET, ctx.baseline.sla_target_sec)

    needed = required_agents(
        calls_per_hour=ctx.value(V_PEAK_CALLS),
        aht_sec=ctx.value(V_EFFECTIVE_AHT),
        sla_target_sec=max(sla_target, 1.0),
        target_service_level=target_service_level,
    )
    # Report the scheduled headcount required, i.e. add shrinkage back.
    scheduled_equivalent = needed / max(1.0 - ctx.baseline.shrinkage, 0.05)
    return {V_REQUIRED_AGENTS: round(scheduled_equivalent)}


def _rule_utilization(ctx: RuleContext) -> dict[str, float]:
    """Share of the paid shift spent on contacts.

    Occupancy measures time on the phone against time logged in; utilisation
    measures it against the full rostered shift, so shrinkage counts against it.
    """
    return {V_UTILIZATION: ctx.value(V_OCCUPANCY) * (1.0 - ctx.baseline.shrinkage)}


def _rule_ai_usage(ctx: RuleContext) -> dict[str, float]:
    """Headline AI figure: the mean of the agent-side and customer-side rates."""
    agent_ai = ctx.lever(LeverId.AGENT_AI, ctx.baseline.agent_ai_usage)
    customer_ai = ctx.lever(LeverId.CUSTOMER_AI, ctx.baseline.customer_ai_usage)
    return {V_AI_USAGE: (agent_ai + customer_ai) / 2.0}


# --- registry -------------------------------------------------------------

RULES: tuple[Rule, ...] = (
    Rule(
        id="effective_aht",
        label="זמן טיפול אפקטיבי",
        inputs=(),
        outputs=(V_EFFECTIVE_AHT,),
        fn=_rule_effective_aht,
    ),
    Rule(
        id="effective_fcr",
        label="פתרון בפנייה ראשונה אפקטיבי",
        inputs=(),
        outputs=(V_EFFECTIVE_FCR,),
        fn=_rule_effective_fcr,
    ),
    Rule(
        id="deflection",
        label="הסטת נפח מהנציגים",
        inputs=(),
        outputs=(V_DEFLECTION,),
        fn=_rule_deflection,
    ),
    Rule(
        id="contact_volume",
        label="נפח פניות לנציג",
        inputs=(V_DEFLECTION, V_EFFECTIVE_FCR),
        outputs=(V_AGENT_CONTACTS, V_TOTAL_CONTACTS),
        fn=_rule_contact_volume,
    ),
    Rule(
        id="peak_load",
        label="עומס שעת שיא",
        inputs=(V_AGENT_CONTACTS,),
        outputs=(V_PEAK_SHARE, V_PEAK_CALLS),
        fn=_rule_peak_load,
    ),
    Rule(
        id="productive_agents",
        label="נציגים זמינים בפועל",
        inputs=(),
        outputs=(V_PRODUCTIVE_AGENTS,),
        fn=_rule_productive_agents,
    ),
    Rule(
        id="queue",
        label="מודל התור (Erlang C)",
        inputs=(V_PEAK_CALLS, V_EFFECTIVE_AHT, V_PRODUCTIVE_AGENTS),
        outputs=(V_PROB_WAIT, V_ASA, V_SLA, V_OCCUPANCY, V_QUEUE_LENGTH, V_OVERLOADED),
        fn=_rule_queue,
    ),
    Rule(
        id="queue_tolerance",
        label="סבלנות מול גודל התור",
        inputs=(),
        outputs=(V_QUEUE_TOLERANCE,),
        fn=_rule_queue_tolerance,
    ),
    Rule(
        id="abandonment",
        label="שיעור נטישה",
        inputs=(V_ASA, V_QUEUE_TOLERANCE),
        outputs=(V_ABANDONMENT,),
        fn=_rule_abandonment,
    ),
    Rule(
        id="satisfaction",
        label="שביעות רצון",
        inputs=(V_SLA, V_EFFECTIVE_FCR, V_ABANDONMENT, V_ASA),
        outputs=(V_SATISFACTION,),
        fn=_rule_satisfaction,
    ),
    Rule(
        id="required_agents",
        label="מצבת נדרשת",
        inputs=(V_PEAK_CALLS, V_EFFECTIVE_AHT),
        outputs=(V_REQUIRED_AGENTS,),
        fn=_rule_required_agents,
    ),
    Rule(
        id="utilization",
        label="ניצולת",
        inputs=(V_OCCUPANCY,),
        outputs=(V_UTILIZATION,),
        fn=_rule_utilization,
    ),
    Rule(
        id="ai_usage",
        label="שימוש כולל ב-AI",
        inputs=(),
        outputs=(V_AI_USAGE,),
        fn=_rule_ai_usage,
    ),
)
