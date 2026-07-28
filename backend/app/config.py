"""Application settings.

Everything is environment-overridable so the same build can be promoted from a
developer laptop to the closed network without a code change.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_ROOT.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SERVIZON_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Servizon"
    debug: bool = False

    # -- Data access -------------------------------------------------------
    #: "csv" or "sql". Selects the repository implementation at startup.
    data_source: str = "csv"
    seed_dir: Path = BACKEND_ROOT / "data" / "seed"
    #: Any SQLAlchemy URL — SQLite, SQL Server, PostgreSQL or Oracle.
    database_url: str = f"sqlite:///{BACKEND_ROOT / 'data' / 'servizon.db'}"
    #: Scenarios always persist locally, independent of the read data source.
    scenarios_database_url: str = f"sqlite:///{BACKEND_ROOT / 'data' / 'scenarios.db'}"

    # -- Refresh -----------------------------------------------------------
    refresh_minutes: int = Field(default=3, ge=1, le=120)
    refresh_on_startup: bool = True

    # -- Simulation --------------------------------------------------------
    coefficients_path: Path = BACKEND_ROOT / "config" / "coefficients.yaml"

    # -- HTTP --------------------------------------------------------------
    host: str = "127.0.0.1"
    port: int = 8000
    #: Vite dev server. In production the frontend is served from this same
    #: process, so CORS is irrelevant there.
    cors_origins: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173")
    #: Built frontend. When present it is mounted at "/".
    static_dir: Path = PROJECT_ROOT / "frontend" / "dist"

    # -- Logging -----------------------------------------------------------
    log_level: str = "INFO"
    log_dir: Path = BACKEND_ROOT / "logs"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
