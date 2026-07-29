"""Rule-based recommendations, in Hebrew.

Deliberately not generative. Every sentence is assembled from numbers the
engine actually produced, so a recommendation can always be traced back to the
computation behind it — which is the whole point in a decision-support tool.
"""

from __future__ import annotations

from app.domain.enums import KpiId, LeverId, Severity
from app.domain.models import BaselineMetrics, Recommendation, SimulatedKpi
from app.simulation import rules as R
from app.simulation.levers import LEVERS_BY_ID, is_percent_lever

#: Occupancy above this is unsustainable — agents burn out and attrition rises.
OCCUPANCY_CEILING = 0.90
#: Below this the roster is oversized for the demand.
OCCUPANCY_FLOOR = 0.55


def _format_number(value: float) -> str:
    return f"{round(value):,}"


def _format_points(value: float) -> str:
    """Percentage-point movement, e.g. 0.043 -> '4.3'."""
    return f"{abs(value) * 100:.1f}".rstrip("0").rstrip(".")


def _format_lever_delta(lever_id: LeverId, before: float, after: float) -> str:
    unit = LEVERS_BY_ID[lever_id].unit
    delta = after - before
    verb = "הגדלת" if delta > 0 else "הקטנת"
    if is_percent_lever(lever_id):
        magnitude = f"{abs(delta):.0f} נקודות האחוז"
    else:
        magnitude = f"{abs(delta):,.0f} {unit}"
    return f"{verb} {LEVERS_BY_ID[lever_id].label} ב-{magnitude}"


def _by_id(kpis: tuple[SimulatedKpi, ...]) -> dict[KpiId, SimulatedKpi]:
    return {kpi.id: kpi for kpi in kpis}


def build_recommendations(
    *,
    kpis: tuple[SimulatedKpi, ...],
    moved_levers: dict[LeverId, tuple[float, float]],
    baseline: BaselineMetrics,
    scenario_values: dict[str, float],
    levers: dict[LeverId, float],
) -> tuple[Recommendation, ...]:
    if not moved_levers:
        return (
            Recommendation(
                id="idle",
                severity=Severity.INFO,
                title="לא הוגדר תרחיש",
                body="הזז מנוף תפעולי אחד או יותר כדי לראות את ההשפעה הצפויה על מדדי השירות.",
            ),
        )

    indexed = _by_id(kpis)
    found: list[Recommendation] = []

    found.extend(_headline(indexed, moved_levers))
    found.extend(_capacity_warnings(indexed, scenario_values, baseline))
    found.extend(_target_checks(indexed, baseline, levers))
    found.extend(_staffing_gap(indexed, baseline, levers))

    order = {
        Severity.CRITICAL: 0,
        Severity.WARNING: 1,
        Severity.POSITIVE: 2,
        Severity.INFO: 3,
    }
    found.sort(key=lambda rec: order[rec.severity])
    return tuple(found[:6])


def _headline(
    indexed: dict[KpiId, SimulatedKpi],
    moved: dict[LeverId, tuple[float, float]],
) -> list[Recommendation]:
    """The main sentence: what was moved, and what it is expected to do."""
    calls = indexed.get(KpiId.INCOMING_CALLS)
    sla = indexed.get(KpiId.SLA)
    wait = indexed.get(KpiId.AVERAGE_WAITING_TIME)
    if calls is None:
        return []

    # Name the levers actually moved, largest movement first.
    described = sorted(
        moved.items(),
        key=lambda item: abs(item[1][1] - item[1][0]),
        reverse=True,
    )[:2]
    phrases = [
        _format_lever_delta(lever_id, before, after) for lever_id, (before, after) in described
    ]
    subject = " ו".join(phrases) if len(phrases) > 1 else phrases[0]

    effects: list[str] = []
    if abs(calls.percentage) >= 0.5:
        direction = "להפחית" if calls.difference < 0 else "להגדיל"
        effects.append(f"{direction} את נפח הפניות בכ-{abs(calls.percentage):.0f}%")
    if sla is not None and abs(sla.difference) >= 0.005:
        phrase = "לשפר את העמידה ב-SLA" if sla.difference > 0 else "לפגוע בעמידה ב-SLA"
        effects.append(f"{phrase} ב-{_format_points(sla.difference)} נקודות")
    if wait is not None and abs(wait.difference) >= 3:
        direction = "לקצר" if wait.difference < 0 else "להאריך"
        effects.append(f"{direction} את זמן ההמתנה ב-{abs(wait.difference):.0f} שניות")

    if not effects:
        return [
            Recommendation(
                id="no_material_effect",
                severity=Severity.INFO,
                title="השפעה זניחה",
                body=f"{subject} אינה משנה את מדדי השירות באופן מהותי בתצורה הנוכחית של המוקד.",
            )
        ]

    body = f"{subject} צפויה " + ", ".join(effects[:-1])
    body = f"{body} ו{effects[-1]}." if len(effects) > 1 else f"{subject} צפויה {effects[0]}."

    improving = calls.is_improvement or (sla is not None and sla.difference > 0)
    return [
        Recommendation(
            id="headline",
            severity=Severity.POSITIVE if improving else Severity.WARNING,
            title="השפעת התרחיש",
            body=body,
        )
    ]


def _capacity_warnings(
    indexed: dict[KpiId, SimulatedKpi],
    scenario_values: dict[str, float],
    baseline: BaselineMetrics,
) -> list[Recommendation]:
    out: list[Recommendation] = []

    if scenario_values.get(R.V_OVERLOADED, 0.0) >= 1.0:
        out.append(
            Recommendation(
                id="overloaded",
                severity=Severity.CRITICAL,
                title="הביקוש חורג מהקיבולת",
                body=(
                    "בתרחיש זה נפח הפניות בשעת השיא גדול מיכולת הטיפול של המצבת. "
                    "התור גדל ללא גבול וזמני ההמתנה שמוצגים הם רצפה בלבד. "
                    "יש להגדיל קיבולת כוח אדם, לקצר זמן טיפול או להסיט נפח נוסף לערוצים דיגיטליים."
                ),
            )
        )
        return out

    occupancy = indexed.get(KpiId.OCCUPANCY)
    if occupancy is not None:
        if occupancy.scenario >= OCCUPANCY_CEILING:
            out.append(
                Recommendation(
                    id="occupancy_high",
                    severity=Severity.WARNING,
                    title=f"תפוסת נציגים גבוהה — {occupancy.scenario * 100:.0f}%",
                    body=(
                        "תפוסה מעל 90% אינה ברת קיימא לאורך זמן: היא מתבטאת בשחיקה, בעלייה בתחלופה "
                        "ובירידה באיכות המענה שאינה נמדדת ב-SLA. שקול תוספת תקן לצד השינוי."
                    ),
                )
            )
        elif occupancy.scenario <= OCCUPANCY_FLOOR and occupancy.scenario > 0:
            out.append(
                Recommendation(
                    id="occupancy_low",
                    severity=Severity.INFO,
                    title=f"תפוסת נציגים נמוכה — {occupancy.scenario * 100:.0f}%",
                    body=(
                        "המצבת גדולה מהנדרש לנפח שבתרחיש. ניתן להסיט תקן למוקד אחר "
                        "או להרחיב את שעות הפעילות באותו כוח אדם."
                    ),
                )
            )

    return out


def _target_checks(
    indexed: dict[KpiId, SimulatedKpi],
    baseline: BaselineMetrics,
    levers: dict[LeverId, float],
) -> list[Recommendation]:
    out: list[Recommendation] = []

    abandonment = indexed.get(KpiId.ABANDONMENT_RATE)
    if abandonment is not None:
        target_display = levers.get(LeverId.ABANDONMENT_TARGET)
        target = (
            target_display / 100.0 if target_display is not None else baseline.abandonment_target
        )
        if abandonment.scenario > target:
            gap = (abandonment.scenario - target) * 100
            out.append(
                Recommendation(
                    id="abandonment_over_target",
                    severity=Severity.WARNING,
                    title="חריגה מיעד הנטישה",
                    body=(
                        f"שיעור הנטישה בתרחיש הוא {abandonment.scenario * 100:.1f}%, "
                        f"גבוה ב-{gap:.1f} נקודות מהיעד שהוגדר ({target * 100:.1f}%)."
                    ),
                )
            )
        elif abandonment.is_improvement:
            out.append(
                Recommendation(
                    id="abandonment_improved",
                    severity=Severity.POSITIVE,
                    title="עמידה ביעד הנטישה",
                    body=(
                        f"שיעור הנטישה יורד ל-{abandonment.scenario * 100:.1f}% ונמצא בתוך היעד. "
                        "כל אחוז נטישה שנחסך הוא פנייה שתחזור בהמשך היום."
                    ),
                )
            )

    return out


def _staffing_gap(
    indexed: dict[KpiId, SimulatedKpi],
    baseline: BaselineMetrics,
    levers: dict[LeverId, float],
) -> list[Recommendation]:
    required = indexed.get(KpiId.REQUIRED_AGENTS)
    if required is None:
        return []

    # Compare against the roster *in the scenario*, not today's. A user who
    # has just added fifteen agents must not be told they are six short —
    # that contradicts the other recommendations on the same screen and makes
    # the whole panel look unreliable.
    scheduled = levers.get(LeverId.WORKFORCE_CAPACITY, baseline.agents_scheduled)

    gap = required.scenario - scheduled
    if abs(gap) < 1:
        return []

    if gap > 0:
        return [
            Recommendation(
                id="staffing_shortfall",
                severity=Severity.WARNING,
                title=f"חסרים כ-{_format_number(gap)} נציגים בשעת השיא",
                body=(
                    f"כדי לעמוד ביעדי השירות בתרחיש זה נדרשת מצבת של {_format_number(required.scenario)} "
                    f"נציגים בשעת השיא, מול {_format_number(scheduled)} בתרחיש הנוכחי."
                ),
            )
        ]

    return [
        Recommendation(
            id="staffing_surplus",
            severity=Severity.POSITIVE,
            title=f"התפנו כ-{_format_number(abs(gap))} תקנים",
            body=(
                f"התרחיש מאפשר לעמוד ביעדים עם {_format_number(required.scenario)} נציגים בשעת השיא "
                f"במקום {_format_number(scheduled)} — פער שניתן להסיט למוקדים בעומס."
            ),
        )
    ]
