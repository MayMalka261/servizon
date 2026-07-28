"""Background refresh.

Runs the ETL on a fixed interval in a worker thread so requests are never
blocked by a reload. `max_instances=1` with `coalesce=True` means a slow
refresh cannot stack up behind itself on a loaded database.
"""

from __future__ import annotations

from datetime import datetime

import structlog
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.services.data_service import DataService

log = structlog.get_logger(__name__)

JOB_ID = "servizon_refresh"


class RefreshScheduler:
    def __init__(self, data_service: DataService, interval_minutes: int) -> None:
        self._data_service = data_service
        self._interval_minutes = interval_minutes
        self._scheduler = BackgroundScheduler(timezone="UTC")

    def start(self) -> None:
        self._scheduler.add_job(
            self._data_service.refresh,
            trigger=IntervalTrigger(minutes=self._interval_minutes),
            id=JOB_ID,
            name="Reload service center data",
            max_instances=1,
            coalesce=True,
            replace_existing=True,
        )
        self._scheduler.start()
        log.info("scheduler_started", interval_minutes=self._interval_minutes)

    def shutdown(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            log.info("scheduler_stopped")

    @property
    def next_run(self) -> datetime | None:
        job = self._scheduler.get_job(JOB_ID) if self._scheduler.running else None
        return job.next_run_time if job else None
