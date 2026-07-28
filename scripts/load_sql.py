"""Load the seed CSVs into a SQL database.

Exists so the SQL code path is exercised now rather than discovered to be
broken on migration day. Points at local SQLite by default; pass any
SQLAlchemy URL to target SQL Server, PostgreSQL or Oracle.

    python scripts/load_sql.py
    python scripts/load_sql.py --url "mssql+pyodbc://user:pw@host/db?driver=ODBC+Driver+18+for+SQL+Server"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.repositories.schema import (  # noqa: E402
    TABLE_CENTERS,
    TABLE_CHANNELS,
    TABLE_INTERACTIONS,
    TABLE_STAFFING,
)

DEFAULT_SEED = PROJECT_ROOT / "backend" / "data" / "seed"
DEFAULT_URL = f"sqlite:///{PROJECT_ROOT / 'backend' / 'data' / 'servizon.db'}"

FILES = {
    TABLE_CENTERS: "centers.csv",
    TABLE_CHANNELS: "channels.csv",
    TABLE_INTERACTIONS: "interactions.csv",
    TABLE_STAFFING: "staffing.csv",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Load Servizon seed CSVs into SQL")
    parser.add_argument("--url", default=DEFAULT_URL, help="SQLAlchemy database URL")
    parser.add_argument("--seed-dir", type=Path, default=DEFAULT_SEED)
    args = parser.parse_args()

    engine = create_engine(args.url, future=True)

    for table, filename in FILES.items():
        path = args.seed_dir / filename
        if not path.exists():
            raise SystemExit(f"missing {path}; run scripts/generate_seed.py first")

        frame = pd.read_csv(path, encoding="utf-8")
        if "ts_bucket" in frame.columns:
            frame["ts_bucket"] = pd.to_datetime(frame["ts_bucket"])

        frame.to_sql(table, engine, if_exists="replace", index=False, chunksize=5000)
        print(f"{table:<14} {len(frame):>8,} rows")

    print(f"\nloaded into {args.url}")
    print("run with:  SERVIZON_DATA_SOURCE=sql uvicorn app.main:app")


if __name__ == "__main__":
    main()
