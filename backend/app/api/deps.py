"""Dependency wiring.

Components are built once during the lifespan and stashed on `app.state`; these
functions hand them to route handlers. Keeping construction out of the routes
is what lets tests swap in a different repository with one line.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from app.domain.models import ServiceCenter, Snapshot
from app.services.data_service import DataService
from app.services.scenario_store import ScenarioStore
from app.services.scheduler import RefreshScheduler
from app.services.snapshot_store import SnapshotStore
from app.simulation.engine import SimulationEngine


def get_data_service(request: Request) -> DataService:
    return request.app.state.data_service  # type: ignore[no-any-return]


def get_store(request: Request) -> SnapshotStore:
    store: SnapshotStore = request.app.state.data_service.store
    if not store.is_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="הנתונים עדיין נטענים. נסה שוב בעוד רגע.",
        )
    return store


def get_engine(request: Request) -> SimulationEngine:
    return request.app.state.engine  # type: ignore[no-any-return]


def get_scenario_store(request: Request) -> ScenarioStore:
    return request.app.state.scenario_store  # type: ignore[no-any-return]


def get_scheduler(request: Request) -> RefreshScheduler | None:
    return getattr(request.app.state, "scheduler", None)


StoreDep = Annotated[SnapshotStore, Depends(get_store)]
EngineDep = Annotated[SimulationEngine, Depends(get_engine)]
DataServiceDep = Annotated[DataService, Depends(get_data_service)]
ScenarioStoreDep = Annotated[ScenarioStore, Depends(get_scenario_store)]


def require_center(store: StoreDep, center_id: str) -> ServiceCenter:
    center = store.get_center(center_id)
    if center is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"מוקד {center_id} לא נמצא",
        )
    return center


def require_snapshot(store: StoreDep, center_id: str) -> Snapshot:
    snapshot = store.get_snapshot(center_id)
    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"אין נתונים זמינים עבור מוקד {center_id}",
        )
    return snapshot
