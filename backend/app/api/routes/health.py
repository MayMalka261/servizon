"""Health and data freshness."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.deps import DataServiceDep, get_scheduler
from app.config import get_settings
from app.domain.models import HealthStatus
from app.services.scheduler import RefreshScheduler

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=HealthStatus, summary="Service health")
def health(
    request: Request,
    data_service: DataServiceDep,
    scheduler: RefreshScheduler | None = Depends(get_scheduler),
) -> HealthStatus:
    settings = get_settings()
    store = data_service.store

    if store.last_error is not None:
        state = "degraded"
    elif store.is_ready:
        state = "ok"
    else:
        state = "starting"

    return HealthStatus(
        status=state,
        data_source=data_service.repository.name,
        centers_loaded=len(store.current().centers) if store.is_ready else 0,
        last_refresh=store.loaded_at,
        next_refresh=scheduler.next_run if scheduler else None,
        refresh_minutes=settings.refresh_minutes,
    )


@router.post("/refresh", summary="Force an immediate data reload")
def force_refresh(data_service: DataServiceDep) -> dict[str, object]:
    """Manual reload, for demonstrations and for verifying the closed-network install.

    Deliberately does not clear anything on the client: an open scenario keeps
    its lever positions and is simply recomputed against the new baseline.
    """
    generation = data_service.refresh()
    if generation is None:
        return {"ok": False, "error": data_service.store.last_error}
    return {
        "ok": True,
        "revision": generation.revision,
        "centers": len(generation.centers),
        "loaded_at": generation.loaded_at,
    }
