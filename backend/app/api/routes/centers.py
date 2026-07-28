"""Service center directory."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import StoreDep, require_center, require_snapshot
from app.domain.enums import (
    CENTER_TYPE_LABELS,
    DISTRICT_LABELS,
    SIZE_LABELS,
    STATUS_LABELS,
    CenterSize,
    CenterStatus,
    CenterType,
    District,
)
from app.domain.models import ServiceCenter, Snapshot

router = APIRouter(prefix="/api/centers", tags=["centers"])


@router.get("", response_model=list[ServiceCenter], summary="List service centers")
def list_centers(
    store: StoreDep,
    search: str | None = Query(default=None, max_length=80),
    center_type: CenterType | None = None,
    district: District | None = None,
    status: CenterStatus | None = None,
    size: CenterSize | None = None,
) -> list[ServiceCenter]:
    """Filtered directory.

    Filtering happens server-side so the client never has to hold the full set
    in memory, which matters once the deployment covers every center in the
    organisation rather than the twenty in the seed data.
    """
    centers = store.list_centers()

    if search:
        needle = search.strip().casefold()
        centers = tuple(
            c for c in centers if needle in c.name.casefold() or needle in c.id.casefold()
        )
    if center_type is not None:
        centers = tuple(c for c in centers if c.center_type is center_type)
    if district is not None:
        centers = tuple(c for c in centers if c.district is district)
    if status is not None:
        centers = tuple(c for c in centers if c.status is status)
    if size is not None:
        centers = tuple(c for c in centers if c.size is size)

    return sorted(centers, key=lambda c: (-c.daily_contacts, c.name))


@router.get("/filters", summary="Available filter options")
def filter_options() -> dict[str, list[dict[str, str]]]:
    """Filter values with their Hebrew labels, so the UI holds no translations."""
    return {
        "center_type": [{"value": k.value, "label": v} for k, v in CENTER_TYPE_LABELS.items()],
        "district": [{"value": k.value, "label": v} for k, v in DISTRICT_LABELS.items()],
        "status": [{"value": k.value, "label": v} for k, v in STATUS_LABELS.items()],
        "size": [{"value": k.value, "label": v} for k, v in SIZE_LABELS.items()],
    }


@router.get("/{center_id}", response_model=ServiceCenter, summary="Get one center")
def get_center(store: StoreDep, center_id: str) -> ServiceCenter:
    return require_center(store, center_id)


@router.get(
    "/{center_id}/snapshot",
    response_model=Snapshot,
    summary="Current baseline for a center",
)
def get_snapshot(store: StoreDep, center_id: str) -> Snapshot:
    """The live baseline a scenario is simulated against.

    Polled in the background by the client. The `id` is content-derived, so an
    unchanged refresh returns the same one and open scenarios are left alone.
    """
    return require_snapshot(store, center_id)
