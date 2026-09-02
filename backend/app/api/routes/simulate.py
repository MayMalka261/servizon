"""The simulation endpoint."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.api.deps import EngineDep, StoreDep, require_center, require_snapshot
from app.domain.models import SimulationRequest, SimulationResult
from app.services.etl import build_baseline_for_range

router = APIRouter(prefix="/api", tags=["simulation"])


@router.post("/simulate", response_model=SimulationResult, summary="Run a what-if scenario")
def simulate(
    payload: SimulationRequest,
    store: StoreDep,
    engine: EngineDep,
) -> SimulationResult:
    """Evaluate a scenario against the center's current snapshot.

    Read-only. The snapshot is a frozen model and the engine never writes to
    it, so no amount of simulation can disturb the live data.

    If the background refresh has moved the baseline since the client last
    loaded it, the scenario is still evaluated — against the *new* baseline —
    and `snapshot_changed` is set so the UI can say so without discarding the
    user's work.

    A `date_from`/`date_to` pair narrows "current" to that slice of history —
    the same rows the trend chart draws from — so picking "last week" moves
    both the chart and the KPI cards together.
    """
    center = require_center(store, payload.center_id)
    snapshot = require_snapshot(store, payload.center_id)

    snapshot_changed = payload.snapshot_id is not None and payload.snapshot_id != snapshot.id

    baseline_override = None
    if payload.date_from or payload.date_to:
        history = store.get_history(payload.center_id)
        if history is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"אין נתוני היסטוריה עבור מוקד {payload.center_id}",
            )
        baseline_override = build_baseline_for_range(
            history,
            engine.coefficients_for(center.center_type.value),
            payload.date_from,
            payload.date_to,
        )
        if baseline_override is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="אין נתונים בטווח התאריכים שנבחר",
            )

    return engine.run(
        snapshot=snapshot,
        center_type=center.center_type.value,
        tab=payload.tab,
        requested_levers=payload.levers,
        snapshot_changed=snapshot_changed,
        baseline_override=baseline_override,
    )
