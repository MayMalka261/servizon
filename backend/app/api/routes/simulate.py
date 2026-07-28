"""The simulation endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import EngineDep, StoreDep, require_center, require_snapshot
from app.domain.models import SimulationRequest, SimulationResult

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
    """
    center = require_center(store, payload.center_id)
    snapshot = require_snapshot(store, payload.center_id)

    snapshot_changed = payload.snapshot_id is not None and payload.snapshot_id != snapshot.id

    return engine.run(
        snapshot=snapshot,
        center_type=center.center_type.value,
        tab=payload.tab,
        requested_levers=payload.levers,
        snapshot_changed=snapshot_changed,
    )
