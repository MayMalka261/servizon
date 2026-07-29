"""Package everything needed to install Servizon on a network with no internet.

Run on a connected machine. Produces `offline-bundle/`, which can be copied to
the target as a single directory and installed with no package downloads.

    python scripts/build_offline_bundle.py

What it collects:
  * every Python wheel, for the target platform
  * the whole npm dependency tree, or the built frontend if you prefer to
    build here and ship only static files
  * seed data, coefficients, scripts and documentation
  * an INSTALL file with the exact commands to run on the far side

The frontend is built here by default. Building on the target would require the
npm toolchain there, and shipping a `dist/` of static files is both smaller and
one less thing to go wrong during the transfer.
"""

from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BUNDLE = PROJECT_ROOT / "offline-bundle"


def run(command: list[str], cwd: Path | None = None) -> None:
    printable = " ".join(command)
    print(f"  $ {printable}")
    result = subprocess.run(command, cwd=cwd, shell=False)
    if result.returncode != 0:
        raise SystemExit(f"failed: {printable}")


def copy(source: Path, destination: Path, *, ignore: tuple[str, ...] = ()) -> None:
    if source.is_dir():
        shutil.copytree(
            source,
            destination,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(*ignore) if ignore else None,
        )
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the offline transfer bundle")
    parser.add_argument(
        "--skip-frontend-build",
        action="store_true",
        help="ship node_modules sources instead of a built dist/",
    )
    parser.add_argument(
        "--python-version",
        default=f"{sys.version_info.major}.{sys.version_info.minor}",
        help="target Python version for wheel resolution",
    )
    args = parser.parse_args()

    if BUNDLE.exists():
        shutil.rmtree(BUNDLE)
    BUNDLE.mkdir(parents=True)

    print("\n[1/5] downloading Python wheels")
    wheels = BUNDLE / "wheels"
    wheels.mkdir()
    # No --platform/--only-binary: some dependencies are source-only, and a
    # partial wheel set fails on the far side where there is no fallback.
    run(
        [
            sys.executable,
            "-m",
            "pip",
            "download",
            "-r",
            str(PROJECT_ROOT / "backend" / "requirements.txt"),
            "-d",
            str(wheels),
        ]
    )

    print("\n[2/5] building the frontend")
    frontend = PROJECT_ROOT / "frontend"
    if args.skip_frontend_build:
        print("  skipped; copying sources")
        copy(frontend, BUNDLE / "frontend", ignore=("node_modules", "dist", ".vite"))
    else:
        run(["npm", "run", "build"], cwd=frontend)
        copy(frontend / "dist", BUNDLE / "frontend" / "dist")
        print("  built dist/ copied")

    print("\n[3/5] copying the backend")
    copy(
        PROJECT_ROOT / "backend",
        BUNDLE / "backend",
        ignore=(
            ".venv",
            "__pycache__",
            "*.pyc",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
            "logs",
            "*.db",
        ),
    )

    print("\n[4/5] copying scripts and documentation")
    copy(PROJECT_ROOT / "scripts", BUNDLE / "scripts", ignore=("__pycache__",))
    copy(PROJECT_ROOT / "docs", BUNDLE / "docs")
    for name in ("README.md", ".gitignore"):
        source = PROJECT_ROOT / name
        if source.exists():
            copy(source, BUNDLE / name)

    print("\n[5/5] writing install instructions")
    (BUNDLE / "INSTALL-OFFLINE.txt").write_text(
        _instructions(args.python_version, args.skip_frontend_build),
        encoding="utf-8",
    )

    total = sum(f.stat().st_size for f in BUNDLE.rglob("*") if f.is_file())
    print(f"\nbundle ready: {BUNDLE}")
    print(f"size: {total / 1024 / 1024:.1f} MB")
    print("copy the whole directory to the target and follow INSTALL-OFFLINE.txt")


def _instructions(python_version: str, sources_only: bool) -> str:
    frontend_step = (
        "3. Frontend (sources shipped — needs npm on the target):\n"
        "     cd frontend\n"
        "     npm ci --offline\n"
        "     npm run build\n"
        if sources_only
        else "3. Frontend: already built. frontend/dist is served by the backend.\n"
    )

    return f"""Servizon — offline installation
================================================================

Built on {platform.platform()} for Python {python_version}.
Nothing here reaches the internet. No package is downloaded during install.


1. Python environment
     cd backend
     python -m venv .venv
     .venv\\Scripts\\activate           (Windows)
     source .venv/bin/activate         (Linux)

2. Dependencies, from the bundled wheels only
     pip install --no-index --find-links ../wheels -r requirements.txt

{frontend_step}
4. Seed data
     Included under backend/data/seed. To regenerate:
       python ../scripts/generate_seed.py --days 28

5. Run
     cd backend
     .venv\\Scripts\\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

     Open http://<host>:8000 — the API and the interface are one service.

6. Verify
     .venv\\Scripts\\python -m pytest -q
     curl http://localhost:8000/api/health


Pointing at the real database
----------------------------------------------------------------
Set in backend/.env:

     SERVIZON_DATA_SOURCE=sql
     SERVIZON_DATABASE_URL=mssql+pyodbc://user:pw@host/db?driver=ODBC+Driver+18+for+SQL+Server

The application only ever reads from this source. Saved scenarios go to a
separate local SQLite file, so pointing at production cannot write to it.

Confirm the swap with:
     .venv\\Scripts\\python -m pytest tests/test_repositories.py -q


Checks worth making after the transfer
----------------------------------------------------------------
* Hebrew renders with the correct typography, not a fallback serif.
  If it does not, frontend/public/fonts/ is missing. The fonts are bundled
  deliberately — there is no route to fonts.googleapis.com from here.
* The browser console shows no request to any external host.
* /api/health reports status "ok" and a recent last_refresh.
"""


if __name__ == "__main__":
    main()
