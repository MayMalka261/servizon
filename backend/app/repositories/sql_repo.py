"""SQL-backed repository.

Written against SQLAlchemy Core with plain SELECTs, so the same code runs on
SQL Server, PostgreSQL, Oracle and SQLite. Only the connection URL changes.

`scripts/load_sql.py` materialises the seed CSVs into SQLite, which lets the
SQL path be exercised in tests today rather than on the day of the migration.
"""

from __future__ import annotations

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.repositories.base import ServiceDataRepository
from app.repositories.schema import (
    CENTERS_COLUMNS,
    CHANNELS_COLUMNS,
    INTERACTIONS_COLUMNS,
    STAFFING_COLUMNS,
    TABLE_CENTERS,
    TABLE_CHANNELS,
    TABLE_INTERACTIONS,
    TABLE_STAFFING,
)
from app.repositories.csv_repo import _coerce


class SqlRepository(ServiceDataRepository):
    name = "sql"

    def __init__(self, database_url: str, schema: str | None = None) -> None:
        self._engine: Engine = create_engine(database_url, pool_pre_ping=True, future=True)
        self._schema = schema

    def _qualified(self, table: str) -> str:
        return f"{self._schema}.{table}" if self._schema else table

    def _read(self, table: str, columns: dict[str, str]) -> pd.DataFrame:
        column_list = ", ".join(columns)
        query = f"SELECT {column_list} FROM {self._qualified(table)}"  # noqa: S608
        # Table and column names come from `schema.py` constants, never user
        # input, so there is no injection surface here.
        with self._engine.connect() as connection:
            frame = pd.read_sql(text(query), connection)
        return _coerce(frame, columns, table)

    def load_centers(self) -> pd.DataFrame:
        return self._read(TABLE_CENTERS, CENTERS_COLUMNS)

    def load_interactions(self) -> pd.DataFrame:
        return self._read(TABLE_INTERACTIONS, INTERACTIONS_COLUMNS)

    def load_staffing(self) -> pd.DataFrame:
        return self._read(TABLE_STAFFING, STAFFING_COLUMNS)

    def load_channels(self) -> pd.DataFrame:
        return self._read(TABLE_CHANNELS, CHANNELS_COLUMNS)

    def health_check(self) -> bool:
        try:
            with self._engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except Exception:  # noqa: BLE001 - health probe must never raise
            return False
        return True
