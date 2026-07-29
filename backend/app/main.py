"""FastAPI application entry point.

In production this single process serves both the API and the built frontend,
so the closed-network install is one service on one port with no reverse proxy
to configure.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import centers, health, levers, scenarios, simulate
from app.config import get_settings
from app.core.logging import configure_logging
from app.repositories.factory import build_repository
from app.services.data_service import DataService
from app.services.scenario_store import ScenarioStore
from app.services.scheduler import RefreshScheduler
from app.services.snapshot_store import SnapshotStore
from app.simulation.engine import SimulationEngine

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_dir)

    engine = SimulationEngine(settings.coefficients_path)
    repository = build_repository(settings)
    store = SnapshotStore()
    data_service = DataService(repository, engine, store, settings)

    app.state.settings = settings
    app.state.engine = engine
    app.state.data_service = data_service
    app.state.scenario_store = ScenarioStore(settings.scenarios_database_url)

    if settings.refresh_on_startup:
        data_service.refresh()

    scheduler = RefreshScheduler(data_service, settings.refresh_minutes)
    scheduler.start()
    app.state.scheduler = scheduler

    log.info(
        "startup_complete",
        data_source=repository.name,
        centers=len(store.current().centers) if store.is_ready else 0,
    )

    try:
        yield
    finally:
        scheduler.shutdown()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Servizon — What If Simulation Engine",
        description=(
            "שכבת סימולציה מעל נתוני מוקדי השירות. "
            "כל הסימולציות רצות על עותק זמני בזיכרון; נתוני המקור אינם משתנים."
        ),
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )

    # Only relevant for the Vite dev server. In production the frontend is
    # served from this same origin.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(centers.router)
    app.include_router(levers.router)
    app.include_router(simulate.router)
    app.include_router(scenarios.router)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Last line of defence.

        Logs the detail locally and returns a generic Hebrew message — an
        internal stack trace should never reach the browser.
        """
        log.error("unhandled_exception", path=request.url.path, error=str(exc), exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={"detail": "אירעה שגיאה בעיבוד הבקשה. פנה למנהל המערכת."},
        )

    _mount_frontend(app, settings.static_dir)
    return app


def _mount_frontend(app: FastAPI, static_dir) -> None:  # type: ignore[no-untyped-def]
    """Serve the built SPA when it exists.

    Absent during backend development, which is why this is conditional rather
    than a hard requirement.
    """
    if not static_dir.exists():
        log.info("frontend_not_mounted", reason="build directory missing", path=str(static_dir))
        return

    assets = static_dir / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    index = static_dir / "index.html"

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str) -> FileResponse:
        """Client-side routing: any unmatched path returns the SPA shell.

        Registered after the API routers, so it only catches what they did not.
        """
        candidate = static_dir / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index)

    log.info("frontend_mounted", path=str(static_dir))


app = create_app()
