"""Saved scenarios and comparison."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response, status

from app.api.deps import (
    EngineDep,
    ScenarioStoreDep,
    StoreDep,
    require_center,
    require_snapshot,
)
from app.domain.enums import Direction, KpiId
from app.domain.models import (
    CompareColumn,
    CompareRequest,
    CompareResult,
    Scenario,
    ScenarioCreate,
    ScenarioUpdate,
    SimulatedKpi,
)
from app.services.scenario_store import ScenarioLimitError

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])


@router.get("", response_model=list[Scenario], summary="Scenarios saved for a center")
def list_scenarios(scenarios: ScenarioStoreDep, center_id: str) -> list[Scenario]:
    return list(scenarios.list_for_center(center_id))


@router.post(
    "",
    response_model=Scenario,
    status_code=status.HTTP_201_CREATED,
    summary="Save a scenario",
)
def create_scenario(
    payload: ScenarioCreate,
    scenarios: ScenarioStoreDep,
    store: StoreDep,
) -> Scenario:
    require_center(store, payload.center_id)
    try:
        return scenarios.create(payload)
    except ScenarioLimitError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.patch("/{scenario_id}", response_model=Scenario, summary="Update a scenario")
def update_scenario(
    scenario_id: str,
    payload: ScenarioUpdate,
    scenarios: ScenarioStoreDep,
) -> Scenario:
    updated = scenarios.update(scenario_id, payload)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="התרחיש לא נמצא")
    return updated


@router.delete(
    "/{scenario_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    # `from __future__ import annotations` turns the `-> Response` hint into a
    # string that FastAPI resolves to a truthy class, which it then treats as a
    # response model and rejects for 204. Stating it explicitly avoids that.
    response_model=None,
    summary="Delete a scenario",
)
def delete_scenario(scenario_id: str, scenarios: ScenarioStoreDep) -> Response:
    if not scenarios.delete(scenario_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="התרחיש לא נמצא")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/compare", response_model=CompareResult, summary="Compare saved scenarios")
def compare_scenarios(
    payload: CompareRequest,
    scenarios: ScenarioStoreDep,
    store: StoreDep,
    engine: EngineDep,
) -> CompareResult:
    """Evaluate several scenarios against one snapshot.

    Running them all against the same baseline in a single request is what
    makes the comparison meaningful — evaluating each one separately could
    straddle a background refresh and quietly compare different worlds.
    """
    center = require_center(store, payload.center_id)
    snapshot = require_snapshot(store, payload.center_id)

    saved = scenarios.get_many(payload.scenario_ids)
    if not saved:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="לא נמצאו תרחישים להשוואה",
        )

    columns: list[CompareColumn] = []
    for scenario in saved:
        if scenario.center_id != payload.center_id:
            continue
        result = engine.run(
            snapshot=snapshot,
            center_type=center.center_type.value,
            tab=scenario.tab,
            requested_levers=scenario.levers,
        )
        columns.append(
            CompareColumn(scenario_id=scenario.id, name=scenario.name, kpis=result.kpis)
        )

    if not columns:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="התרחישים שנבחרו אינם שייכים למוקד זה",
        )

    return CompareResult(
        center_id=payload.center_id,
        snapshot_id=snapshot.id,
        columns=tuple(columns),
        winners=_winners(columns),
    )


def _winners(columns: list[CompareColumn]) -> dict[KpiId, str]:
    """Best scenario per KPI, respecting each metric's desirable direction."""
    best: dict[KpiId, tuple[str, float]] = {}
    for column in columns:
        for kpi in column.kpis:
            current = best.get(kpi.id)
            if current is None or _beats(kpi, current[1]):
                best[kpi.id] = (column.scenario_id, kpi.scenario)
    return {kpi_id: scenario_id for kpi_id, (scenario_id, _) in best.items()}


def _beats(candidate: SimulatedKpi, incumbent: float) -> bool:
    if candidate.direction is Direction.HIGHER_IS_BETTER:
        return candidate.scenario > incumbent
    return candidate.scenario < incumbent
