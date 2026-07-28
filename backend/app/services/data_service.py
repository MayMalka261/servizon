"""Orchestrates repository -> ETL -> snapshot store.

The single seam between "where the data comes from" and "what the application
does with it".
"""

from __future__ import annotations

import structlog

from app.config import Settings
from app.repositories.base import ServiceDataRepository
from app.services.etl import build_dataset
from app.services.snapshot_store import Generation, SnapshotStore
from app.simulation.engine import SimulationEngine

log = structlog.get_logger(__name__)


class DataService:
    def __init__(
        self,
        repository: ServiceDataRepository,
        engine: SimulationEngine,
        store: SnapshotStore,
        settings: Settings,
    ) -> None:
        self._repository = repository
        self._engine = engine
        self._store = store
        self._settings = settings

    @property
    def store(self) -> SnapshotStore:
        return self._store

    @property
    def repository(self) -> ServiceDataRepository:
        return self._repository

    def refresh(self) -> Generation | None:
        """Rebuild every snapshot from source.

        Failures are logged and swallowed: the scheduler must not die because
        the database blinked, and the previously loaded generation keeps
        serving. The error surfaces on `/api/health`.
        """
        try:
            centers = self._repository.load_centers()
            interactions = self._repository.load_interactions()
            staffing = self._repository.load_staffing()
            channels = self._repository.load_channels()

            directory, snapshots = build_dataset(
                centers=centers,
                interactions=interactions,
                staffing=staffing,
                channels=channels,
                coefficients_for=self._engine.coefficients_for,
            )
        except Exception as exc:  # noqa: BLE001 - refresh must never crash the app
            log.error("refresh_failed", error=str(exc), source=self._repository.name)
            self._store.record_failure(str(exc))
            return None

        generation = self._store.publish(directory, snapshots)
        log.info(
            "refresh_complete",
            source=self._repository.name,
            centers=len(directory),
            revision=generation.revision,
        )
        return generation
