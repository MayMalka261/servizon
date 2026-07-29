"""Selects the repository implementation from configuration.

This is the only place in the application that knows more than one data source
exists. Everything else depends on `ServiceDataRepository`.
"""

from __future__ import annotations

from app.config import Settings
from app.repositories.base import ServiceDataRepository
from app.repositories.csv_repo import CsvRepository
from app.repositories.sql_repo import SqlRepository


def build_repository(settings: Settings) -> ServiceDataRepository:
    source = settings.data_source.strip().lower()
    if source == "csv":
        return CsvRepository(settings.seed_dir)
    if source == "sql":
        return SqlRepository(settings.database_url)
    raise ValueError(
        f"Unknown SERVIZON_DATA_SOURCE={settings.data_source!r}; expected 'csv' or 'sql'"
    )
