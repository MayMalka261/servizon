"""Canonical enumerations shared across the whole backend.

Hebrew display labels live here so the API is the single source of truth for
terminology. The frontend renders whatever the server sends and never keeps a
parallel translation table that can drift.
"""

from __future__ import annotations

from enum import StrEnum


class CenterType(StrEnum):
    """Functional classification of a service center."""

    TECHNICAL_SUPPORT = "technical_support"
    PERSONNEL = "personnel"
    LOGISTICS = "logistics"
    MEDICAL = "medical"
    GENERAL_INQUIRIES = "general_inquiries"


class District(StrEnum):
    """Geographic command / district the center belongs to."""

    NORTH = "north"
    CENTER = "center"
    SOUTH = "south"
    JERUSALEM = "jerusalem"
    HQ = "hq"


class CenterStatus(StrEnum):
    """Operational health of the center right now."""

    ACTIVE = "active"
    STRAINED = "strained"
    CRITICAL = "critical"
    OFFLINE = "offline"


class CenterSize(StrEnum):
    """Size bucket, derived from headcount during ETL."""

    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class ChannelKind(StrEnum):
    """Contact channels. PHONE is the only non-digital channel."""

    PHONE = "phone"
    WEB = "web"
    WHATSAPP = "whatsapp"
    EMAIL = "email"
    FORMS = "forms"
    CHAT = "chat"


DIGITAL_CHANNELS: frozenset[ChannelKind] = frozenset(
    {
        ChannelKind.WEB,
        ChannelKind.WHATSAPP,
        ChannelKind.EMAIL,
        ChannelKind.FORMS,
        ChannelKind.CHAT,
    }
)


class SimulationTab(StrEnum):
    """The two tabs of the Simulation Center."""

    DIGITAL_CHANNELS = "digital_channels"
    PHONE_CENTER = "phone_center"


class LeverId(StrEnum):
    """Operational levers the user can move."""

    DIGITAL_ADOPTION = "digital_adoption"
    # AI is steered through the two specific levers below rather than one
    # blended control — they act at different points in the journey.
    AGENT_AI = "agent_ai"
    CUSTOMER_AI = "customer_ai"
    WORKFORCE_CAPACITY = "workforce_capacity"
    WORKING_HOURS = "working_hours"
    SLA_TARGET = "sla_target"
    ABANDONMENT_TARGET = "abandonment_target"
    AVERAGE_HANDLE_TIME = "average_handle_time"
    FIRST_CALL_RESOLUTION = "first_call_resolution"
    QUEUE_SIZE = "queue_size"
    SELF_SERVICE_RATE = "self_service_rate"
    AUTOMATION_LEVEL = "automation_level"
    KNOWLEDGE_BASE_QUALITY = "knowledge_base_quality"


class KpiId(StrEnum):
    """Service metrics produced by the simulation engine.

    Split by the question each one answers. The phone metrics describe a queue:
    how long people wait and whether there are enough agents. The digital
    metrics describe deflection: how much never needs an agent at all. Showing
    a manager "incoming calls" while they are analysing the web channel is a
    category error, which is why the two groups stay separate.
    """

    # -- phone center: the queue ---------------------------------------
    INCOMING_CALLS = "incoming_calls"
    AVERAGE_WAITING_TIME = "average_waiting_time"
    ABANDONMENT_RATE = "abandonment_rate"
    SLA = "sla"
    OCCUPANCY = "occupancy"
    UTILIZATION = "utilization"
    QUEUE_LENGTH = "queue_length"
    REQUIRED_AGENTS = "required_agents"
    AHT = "aht"

    # -- digital channels: deflection ----------------------------------
    DIGITAL_CONTACTS = "digital_contacts"
    CONTAINMENT_RATE = "containment_rate"
    ESCALATED_CONTACTS = "escalated_contacts"
    DIGITAL_ADOPTION = "digital_adoption"
    SELF_SERVICE_RATE = "self_service_rate"
    AUTOMATION_LEVEL = "automation_level"
    # Agent-side and customer-side AI are reported separately rather than as a
    # blended figure: they are different programmes with different owners, and
    # an average of the two is a number nobody can act on.
    CUSTOMER_AI_USAGE = "customer_ai_usage"
    AGENT_AI_USAGE = "agent_ai_usage"

    # -- cross-channel outcomes ----------------------------------------
    CUSTOMER_SATISFACTION = "customer_satisfaction"
    FCR = "fcr"


class KpiFormat(StrEnum):
    """How the frontend should render a KPI value."""

    NUMBER = "number"
    PERCENT = "percent"
    DURATION = "duration"  # seconds -> mm:ss


class Direction(StrEnum):
    """Whether a rising value is good or bad for this KPI.

    Drives the colour of the delta badge: a falling abandonment rate is green,
    a falling SLA is red.

    NEUTRAL exists for metrics with a healthy *band* rather than a direction.
    Occupancy is the case in point — 96% means agents are burning out and 45%
    means the roster is oversized, so neither arrow deserves a colour. Forcing
    those into "higher is better" paints a genuine fix red.
    """

    HIGHER_IS_BETTER = "higher_is_better"
    LOWER_IS_BETTER = "lower_is_better"
    NEUTRAL = "neutral"


class Severity(StrEnum):
    """Recommendation weight."""

    POSITIVE = "positive"
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


# --------------------------------------------------------------------------
# Hebrew display labels
# --------------------------------------------------------------------------

CENTER_TYPE_LABELS: dict[CenterType, str] = {
    CenterType.TECHNICAL_SUPPORT: "תמיכה טכנית",
    CenterType.PERSONNEL: "כוח אדם",
    CenterType.LOGISTICS: "לוגיסטיקה",
    CenterType.MEDICAL: "רפואה",
    CenterType.GENERAL_INQUIRIES: "פניות כלליות",
}

DISTRICT_LABELS: dict[District, str] = {
    District.NORTH: "פיקוד צפון",
    District.CENTER: "פיקוד מרכז",
    District.SOUTH: "פיקוד דרום",
    District.JERUSALEM: "ירושלים",
    District.HQ: "מטה כללי",
}

STATUS_LABELS: dict[CenterStatus, str] = {
    CenterStatus.ACTIVE: "תקין",
    CenterStatus.STRAINED: "בעומס",
    CenterStatus.CRITICAL: "קריטי",
    CenterStatus.OFFLINE: "לא פעיל",
}

SIZE_LABELS: dict[CenterSize, str] = {
    CenterSize.SMALL: "קטן",
    CenterSize.MEDIUM: "בינוני",
    CenterSize.LARGE: "גדול",
}

CHANNEL_LABELS: dict[ChannelKind, str] = {
    ChannelKind.PHONE: "טלפון",
    ChannelKind.WEB: "אתר",
    ChannelKind.WHATSAPP: "וואטסאפ",
    ChannelKind.EMAIL: "אימייל",
    ChannelKind.FORMS: "טפסים",
    ChannelKind.CHAT: "צ'אט",
}

TAB_LABELS: dict[SimulationTab, str] = {
    SimulationTab.DIGITAL_CHANNELS: "ערוצים דיגיטליים",
    SimulationTab.PHONE_CENTER: "מוקד טלפוני",
}
