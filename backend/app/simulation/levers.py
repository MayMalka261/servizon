"""Registry of the operational levers.

Bounds, steps and Hebrew labels live here rather than in the UI, so a lever can
never be dragged somewhere the model cannot evaluate. `GET /api/levers` serves
this registry verbatim.

Values are expressed in *display* units — percentages as 0-100, durations in
seconds, headcount in agents. `to_model_units` converts to the fractions the
engine works in.
"""

from __future__ import annotations

from app.domain.enums import LeverId, SimulationTab
from app.domain.models import LeverDefinition

BOTH_TABS: tuple[SimulationTab, ...] = (
    SimulationTab.DIGITAL_CHANNELS,
    SimulationTab.PHONE_CENTER,
)
PHONE_ONLY: tuple[SimulationTab, ...] = (SimulationTab.PHONE_CENTER,)
DIGITAL_ONLY: tuple[SimulationTab, ...] = (SimulationTab.DIGITAL_CHANNELS,)

#: Belongs to no tab, so it never reaches the filter panel and is dropped from
#: any request that names it.
#:
#: The definition is kept rather than deleted because the engine still reads
#: these quantities — they simply hold their observed baseline value instead of
#: being steerable. Removing them outright would mean unpicking the rule graph
#: for controls that may well come back.
HIDDEN: tuple[SimulationTab, ...] = ()

GROUP_DIGITAL = "digital"
GROUP_AI = "ai"
GROUP_WORKFORCE = "workforce"
GROUP_QUALITY = "quality"
GROUP_TARGETS = "targets"

GROUP_LABELS: dict[str, str] = {
    GROUP_DIGITAL: "אימוץ דיגיטלי",
    GROUP_AI: "שימוש ב-AI",
    GROUP_WORKFORCE: "קיבולת כוח אדם",
    GROUP_QUALITY: "איכות השירות",
    GROUP_TARGETS: "יעדי שירות",
}

GROUP_ORDER: tuple[str, ...] = (
    GROUP_DIGITAL,
    GROUP_WORKFORCE,
    GROUP_AI,
    GROUP_QUALITY,
    GROUP_TARGETS,
)

#: Levers expressed as a percentage of contacts / quality, 0-100.
_PERCENT_LEVERS: frozenset[LeverId] = frozenset(
    {
        LeverId.DIGITAL_ADOPTION,
        LeverId.SELF_SERVICE_RATE,
        LeverId.AUTOMATION_LEVEL,
        LeverId.AGENT_AI,
        LeverId.CUSTOMER_AI,
        LeverId.KNOWLEDGE_BASE_QUALITY,
        LeverId.FIRST_CALL_RESOLUTION,
        LeverId.ABANDONMENT_TARGET,
    }
)

LEVER_DEFINITIONS: tuple[LeverDefinition, ...] = (
    LeverDefinition(
        id=LeverId.DIGITAL_ADOPTION,
        label="אחוז פניות דיגיטליות",
        tooltip="שיעור הפניות שמתחילות בערוץ דיגיטלי במקום בטלפון. העלאה מסיטה נפח מהמוקד הטלפוני.",
        unit="%",
        min=0,
        max=100,
        step=1,
        tabs=BOTH_TABS,
        group=GROUP_DIGITAL,
        group_label=GROUP_LABELS[GROUP_DIGITAL],
    ),
    LeverDefinition(
        id=LeverId.SELF_SERVICE_RATE,
        label="שירות עצמי",
        tooltip="שיעור הפניות שנסגרות ללא מגע נציג. משפיע ישירות על נפח השיחות הנכנסות.",
        unit="%",
        min=0,
        max=100,
        step=1,
        tabs=HIDDEN,
        group=GROUP_DIGITAL,
        group_label=GROUP_LABELS[GROUP_DIGITAL],
    ),
    LeverDefinition(
        id=LeverId.AUTOMATION_LEVEL,
        label="רמת אוטומציה",
        tooltip="שיעור התהליכים המטופלים אוטומטית מקצה לקצה, ללא התערבות נציג.",
        unit="%",
        min=0,
        max=100,
        step=1,
        tabs=HIDDEN,
        group=GROUP_DIGITAL,
        group_label=GROUP_LABELS[GROUP_DIGITAL],
    ),
    LeverDefinition(
        id=LeverId.WORKFORCE_CAPACITY,
        label="כמות נציגים",
        tooltip="מספר הנציגים המתוקננים במשמרת השיא. הטווח נגזר מהמצבת הנוכחית של המוקד.",
        unit="נציגים",
        min=1,
        max=500,
        step=1,
        tabs=BOTH_TABS,
        group=GROUP_WORKFORCE,
        group_label=GROUP_LABELS[GROUP_WORKFORCE],
        dynamic_bounds=True,
    ),
    LeverDefinition(
        id=LeverId.WORKING_HOURS,
        label="שעות פעילות",
        tooltip="שעות פעילות המוקד ביממה. הרחבה פורסת את אותו נפח על חלון רחב יותר ומורידה את השיא.",
        unit="שעות",
        min=4,
        max=24,
        step=1,
        tabs=HIDDEN,
        group=GROUP_WORKFORCE,
        group_label=GROUP_LABELS[GROUP_WORKFORCE],
    ),
    LeverDefinition(
        id=LeverId.AVERAGE_HANDLE_TIME,
        label="זמן טיפול בפנייה",
        tooltip="משך טיפול ממוצע בפנייה, בשניות. קיצור משחרר קיבולת בלי להוסיף תקן.",
        unit="שנ'",
        min=30,
        max=900,
        step=5,
        tabs=BOTH_TABS,
        group=GROUP_WORKFORCE,
        group_label=GROUP_LABELS[GROUP_WORKFORCE],
    ),
    LeverDefinition(
        id=LeverId.FIRST_CALL_RESOLUTION,
        label="פתרון בפנייה ראשונה",
        tooltip="שיעור הפניות שנסגרות במגע הראשון. כל פנייה שלא נסגרה חוזרת ומגדילה את הנפח.",
        unit="%",
        min=30,
        max=99,
        step=1,
        tabs=HIDDEN,
        group=GROUP_QUALITY,
        group_label=GROUP_LABELS[GROUP_QUALITY],
    ),
    LeverDefinition(
        id=LeverId.AGENT_AI,
        label="שימוש נציג ב-AI",
        tooltip="שיעור הנציגים הנעזרים ב-AI תוך כדי שיחה. מקצר טיפול ומשפר פתרון בפנייה ראשונה.",
        unit="%",
        min=0,
        max=100,
        step=1,
        tabs=HIDDEN,
        group=GROUP_AI,
        group_label=GROUP_LABELS[GROUP_AI],
    ),
    LeverDefinition(
        id=LeverId.CUSTOMER_AI,
        label="שימוש לקוח ב-AI",
        tooltip="שיעור הפונים שמקבלים מענה מ-AI לפני הגעה לנציג. מסיט נפח מהתור.",
        unit="%",
        min=0,
        max=100,
        step=1,
        tabs=HIDDEN,
        group=GROUP_AI,
        group_label=GROUP_LABELS[GROUP_AI],
    ),
    LeverDefinition(
        id=LeverId.KNOWLEDGE_BASE_QUALITY,
        label="איכות מאגר הידע",
        tooltip="שלמות ועדכניות מאגר הידע. מאגר טוב מקצר טיפול ומעלה פתרון בפנייה ראשונה.",
        unit="%",
        min=0,
        max=100,
        step=1,
        tabs=HIDDEN,
        group=GROUP_QUALITY,
        group_label=GROUP_LABELS[GROUP_QUALITY],
    ),
    LeverDefinition(
        id=LeverId.SLA_TARGET,
        label="SLA טלפוני",
        tooltip="הזמן שבתוכו יש לענות לפנייה. זהו יעד מדידה — הקשחתו מורידה את אחוז העמידה מבלי לשנות את זמן ההמתנה בפועל.",
        unit="שנ'",
        min=10,
        max=300,
        step=5,
        tabs=BOTH_TABS,
        group=GROUP_TARGETS,
        group_label=GROUP_LABELS[GROUP_TARGETS],
    ),
    LeverDefinition(
        id=LeverId.ABANDONMENT_TARGET,
        label="יעד נטישה",
        tooltip="שיעור הנטישה המרבי המותר. משמש להשוואה מול התוצאה המחושבת ולהפקת התרעות.",
        unit="%",
        min=0,
        max=25,
        step=0.5,
        tabs=HIDDEN,
        group=GROUP_TARGETS,
        group_label=GROUP_LABELS[GROUP_TARGETS],
    ),
    LeverDefinition(
        id=LeverId.QUEUE_SIZE,
        label="גודל תור מרבי",
        tooltip="מספר הממתינים המרבי בתור. תור מוצהר וקצר מקטין נטישה מוקדמת, אך תור ארוך מדי שוחק סבלנות.",
        unit="ממתינים",
        min=1,
        max=400,
        step=1,
        tabs=HIDDEN,
        group=GROUP_TARGETS,
        group_label=GROUP_LABELS[GROUP_TARGETS],
        dynamic_bounds=True,
    ),
)

LEVERS_BY_ID: dict[LeverId, LeverDefinition] = {lever.id: lever for lever in LEVER_DEFINITIONS}


def levers_for_tab(tab: SimulationTab) -> tuple[LeverDefinition, ...]:
    return tuple(lever for lever in LEVER_DEFINITIONS if tab in lever.tabs)


def is_percent_lever(lever_id: LeverId) -> bool:
    return lever_id in _PERCENT_LEVERS


def to_model_units(lever_id: LeverId, display_value: float) -> float:
    """Convert a display value to the unit the engine expects.

    Percent levers become fractions; everything else passes through.
    """
    if is_percent_lever(lever_id):
        return display_value / 100.0
    return display_value


def to_display_units(lever_id: LeverId, model_value: float) -> float:
    if is_percent_lever(lever_id):
        return model_value * 100.0
    return model_value
