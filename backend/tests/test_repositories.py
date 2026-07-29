"""Repository parity.

The whole point of the repository abstraction is that swapping the data source
changes nothing downstream. These tests prove that on a real second
implementation rather than asserting it in a comment: the CSV and SQL
repositories are loaded, and the identical ETL and engine are run against both.
"""

from __future__ import annotations

import pandas as pd
import pytest
from sqlalchemy import create_engine

from app.config import get_settings
from app.domain.enums import LeverId, SimulationTab
from app.repositories.csv_repo import CsvRepository
from app.repositories.schema import (
    TABLE_CENTERS,
    TABLE_CHANNELS,
    TABLE_INTERACTIONS,
    TABLE_SCHEMAS,
    TABLE_STAFFING,
)
from app.repositories.sql_repo import SqlRepository
from app.services.etl import build_dataset
from app.simulation.engine import SimulationEngine

_FILES = {
    TABLE_CENTERS: "centers.csv",
    TABLE_CHANNELS: "channels.csv",
    TABLE_INTERACTIONS: "interactions.csv",
    TABLE_STAFFING: "staffing.csv",
}


@pytest.fixture(scope="module")
def csv_repo() -> CsvRepository:
    return CsvRepository(get_settings().seed_dir)


@pytest.fixture(scope="module")
def sql_repo(tmp_path_factory) -> SqlRepository:
    """Materialise the seed into a throwaway SQLite file."""
    settings = get_settings()
    db_path = tmp_path_factory.mktemp("sql") / "parity.db"
    url = f"sqlite:///{db_path}"
    engine = create_engine(url, future=True)

    for table, filename in _FILES.items():
        frame = pd.read_csv(settings.seed_dir / filename, encoding="utf-8")
        if "ts_bucket" in frame.columns:
            frame["ts_bucket"] = pd.to_datetime(frame["ts_bucket"])
        frame.to_sql(table, engine, if_exists="replace", index=False, chunksize=5000)

    engine.dispose()
    return SqlRepository(url)


class TestContract:
    @pytest.mark.parametrize("table", sorted(TABLE_SCHEMAS))
    def test_csv_satisfies_the_declared_schema(self, csv_repo: CsvRepository, table: str) -> None:
        loader = {
            TABLE_CENTERS: csv_repo.load_centers,
            TABLE_INTERACTIONS: csv_repo.load_interactions,
            TABLE_STAFFING: csv_repo.load_staffing,
            TABLE_CHANNELS: csv_repo.load_channels,
        }[table]
        frame = loader()
        assert list(frame.columns) == list(TABLE_SCHEMAS[table])
        assert not frame.empty

    def test_missing_column_fails_loudly(self, tmp_path) -> None:
        """A silent NaN column would surface much later as a nonsense KPI."""
        (tmp_path / "centers.csv").write_text("center_id,center_name\nSC-1,x\n", encoding="utf-8")
        for name in ("interactions.csv", "staffing.csv", "channels.csv"):
            (tmp_path / name).write_text("center_id\nSC-1\n", encoding="utf-8")

        with pytest.raises(ValueError, match="missing required columns"):
            CsvRepository(tmp_path).load_centers()

    def test_absent_seed_names_the_fix(self, tmp_path) -> None:
        with pytest.raises(FileNotFoundError, match="generate_seed"):
            CsvRepository(tmp_path / "nothing").load_centers()

    def test_health_checks(self, csv_repo: CsvRepository, sql_repo: SqlRepository) -> None:
        assert csv_repo.health_check()
        assert sql_repo.health_check()


class TestParity:
    def test_frames_match(self, csv_repo: CsvRepository, sql_repo: SqlRepository) -> None:
        for name in ("load_centers", "load_channels", "load_staffing", "load_interactions"):
            from_csv = getattr(csv_repo, name)()
            from_sql = getattr(sql_repo, name)()
            assert list(from_csv.columns) == list(from_sql.columns), name
            assert len(from_csv) == len(from_sql), name

    def test_identical_snapshots(self, csv_repo: CsvRepository, sql_repo: SqlRepository) -> None:
        """The ETL cannot tell the two sources apart."""
        engine = SimulationEngine(get_settings().coefficients_path)

        def load(repo):
            return build_dataset(
                centers=repo.load_centers(),
                interactions=repo.load_interactions(),
                staffing=repo.load_staffing(),
                channels=repo.load_channels(),
                coefficients_for=engine.coefficients_for,
            )

        csv_centers, csv_snapshots = load(csv_repo)
        sql_centers, sql_snapshots = load(sql_repo)

        assert csv_centers.keys() == sql_centers.keys()
        for center_id, center in csv_centers.items():
            assert center == sql_centers[center_id]

        for center_id, snapshot in csv_snapshots.items():
            other = sql_snapshots[center_id]
            # `captured_at` is wall-clock and differs by construction; the
            # content hash inside the id is what has to match.
            assert snapshot.id == other.id, center_id
            assert snapshot.baseline == other.baseline, center_id
            assert snapshot.kpis == other.kpis, center_id
            assert snapshot.lever_defaults == other.lever_defaults, center_id

    def test_identical_simulation_results(
        self, csv_repo: CsvRepository, sql_repo: SqlRepository
    ) -> None:
        engine = SimulationEngine(get_settings().coefficients_path)

        def simulate(repo):
            centers, snapshots = build_dataset(
                centers=repo.load_centers(),
                interactions=repo.load_interactions(),
                staffing=repo.load_staffing(),
                channels=repo.load_channels(),
                coefficients_for=engine.coefficients_for,
            )
            center_id = sorted(centers)[0]
            return engine.run(
                snapshots[center_id],
                centers[center_id].center_type.value,
                SimulationTab.PHONE_CENTER,
                {LeverId.DIGITAL_ADOPTION: 68.0, LeverId.AGENT_AI: 55.0},
            )

        assert simulate(csv_repo).kpis == simulate(sql_repo).kpis
