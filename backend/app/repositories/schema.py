"""The canonical data contract.

Both repository implementations produce frames matching these schemas, so the
ETL and the simulation engine never learn where the data came from. Swapping
CSV for SQL Server is a repository change and nothing else.

Note on table count: the spec describes three *fact* tables — interactions,
staffing and channels. `centers` is a small dimension table carrying names and
classifications. If the production system embeds those attributes inside one of
the three facts, map them here during ETL; nothing downstream changes.
"""

from __future__ import annotations

from typing import Final

TABLE_CENTERS: Final = "centers"
TABLE_INTERACTIONS: Final = "interactions"
TABLE_STAFFING: Final = "staffing"
TABLE_CHANNELS: Final = "channels"

#: Dimension: one row per service center.
CENTERS_COLUMNS: Final[dict[str, str]] = {
    "center_id": "string",
    "center_name": "string",
    "center_type": "string",
    "district": "string",
    "status": "string",
    "headcount": "int64",
    "working_hours_per_day": "float64",
}

#: Fact: contact volume aggregated per center / channel / half-hour bucket.
INTERACTIONS_COLUMNS: Final[dict[str, str]] = {
    "center_id": "string",
    "ts_bucket": "datetime64[ns]",
    "channel": "string",
    "offered": "float64",
    "handled": "float64",
    "abandoned": "float64",
    "aht_sec": "float64",
    "wait_sec": "float64",
    "resolved_first_contact": "float64",
}

#: Fact: staffing per center / half-hour bucket.
STAFFING_COLUMNS: Final[dict[str, str]] = {
    "center_id": "string",
    "ts_bucket": "datetime64[ns]",
    "agents_scheduled": "float64",
    "agents_logged_in": "float64",
    "shrinkage_pct": "float64",
    "sla_target_sec": "float64",
}

#: Fact: per-channel configuration, one row per center / channel.
CHANNELS_COLUMNS: Final[dict[str, str]] = {
    "center_id": "string",
    "channel": "string",
    "enabled": "bool",
    "self_service_rate": "float64",
    "automation_level": "float64",
    "agent_ai_usage": "float64",
    "customer_ai_usage": "float64",
    "knowledge_base_quality": "float64",
}

TABLE_SCHEMAS: Final[dict[str, dict[str, str]]] = {
    TABLE_CENTERS: CENTERS_COLUMNS,
    TABLE_INTERACTIONS: INTERACTIONS_COLUMNS,
    TABLE_STAFFING: STAFFING_COLUMNS,
    TABLE_CHANNELS: CHANNELS_COLUMNS,
}
