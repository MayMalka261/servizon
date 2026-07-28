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
    #: Rendering order within a tab.
    order: int


_BOTH = (SimulationTab.DIGITAL_CHANNELS, SimulationTab.PHONE_CENTER)
_PHONE = (SimulationTab.PHONE_CENTER,)

KPI_DEFINITIONS: tuple[KpiDefinition, ...] = (
    KpiDefinition(
        KpiId.INCOMING_CALLS, "נפח שיחות נכנסות", KpiFormat.NUMBER, Direction.LOWER_IS_BETTER, _BOTH, 10
    ),
    KpiDefinition(
        KpiId.ABANDONMENT_RATE, "שיעור נטישה", KpiFormat.PERCENT, Direction.LOWER_IS_BETTER, _BOTH, 20
    ),
    KpiDefinition(
        KpiId.AVERAGE_WAITING_TIME,
        "ממוצע זמן המתנה",
        KpiFormat.DURATION,
        Direction.LOWER_IS_BETTER,
        _BOTH,
        30,
    ),
    KpiDefinition(
        KpiId.SLA, "עמידה ב-SLA", KpiFormat.PERCENT, Direction.HIGHER_IS_BETTER, _BOTH, 40
    ),
    KpiDefinition(
        KpiId.CUSTOMER_SATISFACTION,
        "שביעות רצון לקוחות",
        KpiFormat.PERCENT,
        Direction.HIGHER_IS_BETTER,
        _BOTH,
        50,
    ),
    KpiDefinition(
        KpiId.FCR, "פתרון בפנייה ראשונה", KpiFormat.PERCENT, Direction.HIGHER_IS_BETTER, _BOTH, 60
    ),
    KpiDefinition(
        KpiId.AHT, "זמן טיפול ממוצע", KpiFormat.DURATION, Direction.LOWER_IS_BETTER, _BOTH, 70
    ),
    # Occupancy and utilisation have a healthy band, not a direction — see the
    # note on Direction.NEUTRAL.
    KpiDefinition(
        KpiId.OCCUPANCY, "תפוסת נציגים", KpiFormat.PERCENT, Direction.NEUTRAL, _PHONE, 80
    ),
    KpiDefinition(
        KpiId.UTILIZATION, "ניצולת משמרת", KpiFormat.PERCENT, Direction.NEUTRAL, _PHONE, 90
    ),
    KpiDefinition(
        KpiId.QUEUE_LENGTH, "אורך תור ממוצע", KpiFormat.NUMBER, Direction.LOWER_IS_BETTER, _PHONE, 100
    ),
    KpiDefinition(
        KpiId.REQUIRED_AGENTS,
        "מצבת נציגים נדרשת",
        KpiFormat.NUMBER,
        Direction.LOWER_IS_BETTER,
        _BOTH,
        110,
    ),
    KpiDefinition(
        KpiId.DIGITAL_ADOPTION, "אימוץ דיגיטלי", KpiFormat.PERCENT, Direction.HIGHER_IS_BETTER, _BOTH, 120
    ),
    KpiDefinition(
        KpiId.AI_USAGE, "שימוש ב-AI", KpiFormat.PERCENT, Direction.HIGHER_IS_BETTER, _BOTH, 130
    ),
)

KPIS_BY_ID: dict[KpiId, KpiDefinition] = {kpi.id: kpi for kpi in KPI_DEFINITIONS}


def kpis_for_tab(tab: SimulationTab) -> tuple[KpiDefinition, ...]:
    return tuple(sorted((k for k in KPI_DEFINITIONS if tab in k.tabs), key=lambda k: k.order))
