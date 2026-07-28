"""Structured logging to stdout and a rotating local file.

Local files only — nothing is shipped off the machine, which is a hard
requirement on a closed network.
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

import structlog


def configure_logging(level: str, log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)

    numeric_level = getattr(logging, level.upper(), logging.INFO)

    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / "servizon.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    stream_handler = logging.StreamHandler()

    logging.basicConfig(
        level=numeric_level,
        format="%(message)s",
        handlers=[stream_handler, file_handler],
        force=True,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
