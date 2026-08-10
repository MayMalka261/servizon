"""Vercel serverless entrypoint.

Vercel discovers a Python function from the module-level `app` object in this
file. It exists only so the demo has a public URL — the same FastAPI
application is served, unchanged, so what visitors exercise is the real
simulation engine and not a reimplementation of it.

Three things differ from a normal deployment, all forced by the platform:

* No background scheduler. A serverless instance is frozen between requests,
  so a timer started at import would never fire. Data is loaded once per cold
  start, which for read-only demo data is equivalent.
* Scenarios are written under /tmp, the only writable path. They therefore
  live as long as the instance does, which is not long.
* Static files are served by Vercel's CDN, not by FastAPI, so the SPA mount
  inside the application never engages.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# The backend is a sibling of this directory, not an installed package.
BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

# Defaults are set before the app is imported, because configuration is read
# at import time. Anything already present in the environment wins, so these
# can still be overridden from the Vercel dashboard.
os.environ.setdefault("SERVIZON_SERVERLESS", "true")
os.environ.setdefault("SERVIZON_DATA_SOURCE", "csv")
os.environ.setdefault("SERVIZON_SCENARIOS_DATABASE_URL", "sqlite:////tmp/scenarios.db")
os.environ.setdefault("SERVIZON_LOG_DIR", "/tmp/logs")

from app.main import app  # noqa: E402  (import must follow the env defaults)

__all__ = ["app"]
