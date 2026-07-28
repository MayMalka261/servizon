"""Repository interface for reading raw service data.

Implementations are read-only by design. Nothing in this application writes
back to the source system — simulations run on in-memory snapshots.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class ServiceDataRepository(ABC):
    """Reads the four canonical tables described in `schema.py`."""

    #: Short identifier surfaced on the health endpoint.
    name: str = "base"

    @abstractmethod
    def load_centers(self) -> pd.DataFrame:
        """Center dimension. One row per center."""

    @abstractmethod
    def load_interactions(self) -> pd.DataFrame:
        """Contact volume facts, per center / channel / time bucket."""

    @abstractmethod
    def load_staffing(self) -> pd.DataFrame:
        """Staffing facts, per center / time bucket."""

    @abstractmethod
    def load_channels(self) -> pd.DataFrame:
        """Channel configuration, per center / channel."""

    def health_check(self) -> bool:
        """Cheap reachability probe. Overridden where a connection exists."""
        return True
