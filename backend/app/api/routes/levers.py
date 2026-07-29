"""Lever and KPI metadata.

Served from the registry so bounds, labels and tooltips exist in exactly one
place. The UI renders whatever arrives here.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.domain.enums import TAB_LABELS, SimulationTab
from app.domain.models import LeverDefinition
from app.simulation.kpis import KPI_DEFINITIONS
from app.simulation.levers import GROUP_LABELS, GROUP_ORDER, LEVER_DEFINITIONS

router = APIRouter(prefix="/api", tags=["metadata"])


@router.get("/levers", response_model=list[LeverDefinition], summary="Lever registry")
def list_levers(tab: SimulationTab | None = None) -> list[LeverDefinition]:
    if tab is None:
        return list(LEVER_DEFINITIONS)
    return [lever for lever in LEVER_DEFINITIONS if tab in lever.tabs]


@router.get("/metadata", summary="Tabs, lever groups and KPI definitions")
def metadata() -> dict[str, object]:
    return {
        "tabs": [{"value": tab.value, "label": label} for tab, label in TAB_LABELS.items()],
        "lever_groups": [{"value": group, "label": GROUP_LABELS[group]} for group in GROUP_ORDER],
        "kpis": [
            {
                "id": kpi.id.value,
                "label": kpi.label,
                "format": kpi.format.value,
                "direction": kpi.direction.value,
                "tabs": [tab.value for tab in kpi.tabs],
                "order": kpi.order,
            }
            for kpi in KPI_DEFINITIONS
        ],
    }
