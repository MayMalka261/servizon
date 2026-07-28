"""Thread-safe in-memory store of the current snapshots.

The background refresh builds a complete new dataset off to the side and swaps
it in with a single assignment. Readers therefore always see one internally
consistent generation — never half of the old data and half of the new — and a
refresh that fails leaves the previous generation serving traffic untouched.

Nothing here writes to the source system. Snapshots are frozen models, so a
simulation physically cannot alter the data it ran against.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import UTC, datetime

from app.domain.models import ServiceCenter, Snapshot


@dataclass(frozen=True, slots=True)
class Generation:
    """One complete, self-consistent load of the data."""

    centers: dict[str, ServiceCenter]
    snapshots: dict[str, Snapshot]
    loaded_at: datetime
    #: Increments on every successful refresh.
    revision: int


class SnapshotStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._generation: Generation | None = None
        self._last_error: str | None = None
        self._last_attempt: datetime | None = None

    # -- writing ----------------------------------------------------------

    def publish(
        self,
        centers: dict[str, ServiceCenter],
        snapshots: dict[str, Snapshot],
    ) -> Generation:
        with self._lock:
            revision = (self._generation.revision + 1) if self._generation else 1
            generation = Generation(
                centers=centers,
                snapshots=snapshots,
                loaded_at=datetime.now(UTC),
                revision=revision,
            )
            self._generation = generation
            self._last_error = None
            self._last_attempt = generation.loaded_at
            return generation

    def record_failure(self, message: str) -> None:
        """Note a failed refresh without disturbing the served generation."""
        with self._lock:
            self._last_error = message
            self._last_attempt = datetime.now(UTC)

    # -- reading ----------------------------------------------------------

    @property
    def is_ready(self) -> bool:
        with self._lock:
            return self._generation is not None

    def current(self) -> Generation:
        with self._lock:
            if self._generation is None:
                raise RuntimeError("snapshot store is empty; the first refresh has not completed")
            return self._generation

    def list_centers(self) -> tuple[ServiceCenter, ...]:
        return tuple(self.current().centers.values())

    def get_center(self, center_id: str) -> ServiceCenter | None:
        return self.current().centers.get(center_id)

    def get_snapshot(self, center_id: str) -> Snapshot | None:
        return self.current().snapshots.get(center_id)

    @property
    def loaded_at(self) -> datetime | None:
        with self._lock:
            return self._generation.loaded_at if self._generation else None

    @property
    def last_error(self) -> str | None:
        with self._lock:
            return self._last_error

    @property
    def revision(self) -> int:
        with self._lock:
            return self._generation.revision if self._generation else 0
