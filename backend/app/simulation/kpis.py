"""KPI metadata: labels, formatting and which direction counts as good.

`direction` is what lets the UI colour a delta correctly without hardcoding a
list of "metrics where down is good" — falling abandonment is an improvement,
falling SLA is not.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.enums import Direction, KpiFormat, KpiId, SimulationTab


@dataclass(frozen=True, slots=True)
class KpiDefinition:
    id: KpiId
    label: str
    format: KpiFormat
    direction: Direction
    tabs: tuple[SimulationTab, ...]
    #: Rendering order, per tab. A metric shown on both tabs does not
    #: necessarily belong in the same position on each — first-contact
    #: resolution leads the digital story and closes the phone one.
    order: dict[SimulationTab, int]


_BOTH = (SimulationTab.DIGITAL_CHANNELS, SimulationTab.PHONE_CENTER)
_PHONE = (SimulationTab.PHONE_CENTER,)
_DIGITAL = (SimulationTab.DIGITAL_CHANNELS,)
#: Computed by the engine but not surfaced on either tab. Kept in the registry
#: because the rule graph and the recommendations still read these values.
_HIDDEN: tuple[SimulationTab, ...] = ()

KPI_DEFINITIONS: tuple[KpiDefinition, ...] = (
    # -- phone center: the queue -------------------------------------------
    KpiDefinition(
        KpiId.INCOMING_CALLS,
        "כמות שיחות",
        KpiFormat.NUMBER,
        Direction.LOWER_IS_BETTER,
        _PHONE,
        {tab: 10 for tab in _PHONE},
    ),
    KpiDefinition(
        KpiId.AVERAGE_WAITING_TIME,
        "ממוצע זמן המתנה",
        KpiFormat.DURATION,
        Direction.LOWER_IS_BETTER,
        _PHONE,
        {tab: 20 for tab in _PHONE},
    ),
    KpiDefinition(
        KpiId.ABANDONMENT_RATE,
        "אחוז נטישה",
        KpiFormat.PERCENT,
        Direction.LOWER_IS_BETTER,
        _PHONE,
        {tab: 30 for tab in _PHONE},
    ),
    KpiDefinition(
        KpiId.SLA,
        "עמידה ב-SLA",
        KpiFormat.PERCENT,
        Direction.HIGHER_IS_BETTER,
        _PHONE,
        {tab: 40 for tab in _PHONE},
    ),
    KpiDefinition(
        KpiId.REQUIRED_AGENTS,
        "כמות נציגים",
        KpiFormat.NUMBER,
        Direction.LOWER_IS_BETTER,
        _PHONE,
        {tab: 50 for tab in _PHONE},
    ),
    KpiDefinition(
        KpiId.AHT,
        "זמן טיפול ממוצע לנציג",
        KpiFormat.DURATION,
        Direction.LOWER_IS_BETTER,
        _PHONE,
        {tab: 60 for tab in _PHONE},
    ),
    # -- digital channels: deflection --------------------------------------
    KpiDefinition(
        KpiId.DIGITAL_CONTACTS,
        "כמות פניות",
        KpiFormat.NUMBER,
        Direction.HIGHER_IS_BETTER,
        _DIGITAL,
        {tab: 10 for tab in _DIGITAL},
    ),
    KpiDefinition(
        KpiId.CUSTOMER_SATISFACTION,
        "שביעות רצון",
        KpiFormat.PERCENT,
        Direction.HIGHER_IS_BETTER,
        _DIGITAL,
        {tab: 30 for tab in _DIGITAL},
    ),
    KpiDefinition(
        KpiId.AHT_DIGITAL,
        "זמן טיפול בפנייה",
        KpiFormat.DURATION,
        Direction.LOWER_IS_BETTER,
        _DIGITAL,
        {tab: 40 for tab in _DIGITAL},
    ),
    # -- cross-channel outcomes --------------------------------------------
    #: "מדד פינג פונג": a contact closed by the first agent scores 1. Rising is
    #: better — every unresolved contact comes back as another one.
    KpiDefinition(
        KpiId.FCR,
        "סגירת פנייה בפעם הראשונה",
        KpiFormat.PERCENT,
        Direction.HIGHER_IS_BETTER,
        _BOTH,
        # Second on the digital tab, last on the phone tab.
        {SimulationTab.DIGITAL_CHANNELS: 20, SimulationTab.PHONE_CENTER: 70},
    ),
    # -- computed but not displayed ----------------------------------------
    KpiDefinition(
        KpiId.OCCUPANCY, "תפוסת נציגים", KpiFormat.PERCENT, Direction.NEUTRAL, _HIDDEN, {}
    ),
    KpiDefinition(
        KpiId.UTILIZATION, "ניצולת משמרת", KpiFormat.PERCENT, Direction.NEUTRAL, _HIDDEN, {}
    ),
    KpiDefinition(
        KpiId.QUEUE_LENGTH,
        "אורך תור ממוצע",
        KpiFormat.NUMBER,
        Direction.LOWER_IS_BETTER,
        _HIDDEN,
        {tab: 920 for tab in _HIDDEN},
    ),
    KpiDefinition(
        KpiId.CONTAINMENT_RATE,
        "שיעור הכלה דיגיטלי",
        KpiFormat.PERCENT,
        Direction.HIGHER_IS_BETTER,
        _HIDDEN,
        {tab: 930 for tab in _HIDDEN},
    ),
    KpiDefinition(
        KpiId.ESCALATED_CONTACTS,
        "פניות שהועברו לנציג",
        KpiFormat.NUMBER,
        Direction.LOWER_IS_BETTER,
        _HIDDEN,
        {tab: 940 for tab in _HIDDEN},
    ),
    KpiDefinition(
        KpiId.DIGITAL_ADOPTION,
        "אחוז פניות דיגיטליות",
        KpiFormat.PERCENT,
        Direction.HIGHER_IS_BETTER,
        _HIDDEN,
        {tab: 950 for tab in _HIDDEN},
    ),
    KpiDefinition(
        KpiId.SELF_SERVICE_RATE,
        "שיעור שירות עצמי",
        KpiFormat.PERCENT,
        Direction.HIGHER_IS_BETTER,
        _HIDDEN,
        {tab: 960 for tab in _HIDDEN},
    ),
    KpiDefinition(
        KpiId.AUTOMATION_LEVEL,
        "רמת אוטומציה",
        KpiFormat.PERCENT,
        Direction.HIGHER_IS_BETTER,
        _HIDDEN,
        {tab: 970 for tab in _HIDDEN},
    ),
    KpiDefinition(
        KpiId.CUSTOMER_AI_USAGE,
        "שימוש לקוח ב-AI",
        KpiFormat.PERCENT,
        Direction.HIGHER_IS_BETTER,
        _HIDDEN,
        {tab: 980 for tab in _HIDDEN},
    ),
    KpiDefinition(
        KpiId.AGENT_AI_USAGE,
        "שימוש נציג ב-AI",
        KpiFormat.PERCENT,
        Direction.HIGHER_IS_BETTER,
        _HIDDEN,
        {tab: 990 for tab in _HIDDEN},
    ),
)

KPIS_BY_ID: dict[KpiId, KpiDefinition] = {kpi.id: kpi for kpi in KPI_DEFINITIONS}


def kpis_for_tab(tab: SimulationTab) -> tuple[KpiDefinition, ...]:
    return tuple(sorted((k for k in KPI_DEFINITIONS if tab in k.tabs), key=lambda k: k.order[tab]))
