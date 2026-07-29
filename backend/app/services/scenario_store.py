"""Persistence for saved scenarios.

A local SQLite file by default. Scenarios are the only thing this application
writes anywhere, and they are stored separately from the read data source so
that pointing the app at a production database never risks writing to it.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from app.domain.enums import LeverId, SimulationTab
from app.domain.models import Scenario, ScenarioCreate, ScenarioUpdate

#: Saved scenarios per center. Enough for the A/B/C comparison the tool offers,
#: with headroom, while keeping the picker usable.
MAX_SCENARIOS_PER_CENTER = 12


class Base(DeclarativeBase):
    pass


class ScenarioRow(Base):
    __tablename__ = "scenarios"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    center_id: Mapped[str] = mapped_column(String(40), index=True)
    name: Mapped[str] = mapped_column(String(80))
    tab: Mapped[str] = mapped_column(String(32))
    #: JSON rather than a child table: levers are read and written whole, never
    #: queried individually, so a join would buy nothing.
    levers_json: Mapped[str] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class ScenarioLimitError(RuntimeError):
    """Raised when a center already holds the maximum number of scenarios."""


class ScenarioStore:
    def __init__(self, database_url: str) -> None:
        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        self._engine = create_engine(database_url, future=True, connect_args=connect_args)
        Base.metadata.create_all(self._engine)
        self._session_factory = sessionmaker(bind=self._engine, expire_on_commit=False)

    # -- mapping ----------------------------------------------------------

    @staticmethod
    def _to_model(row: ScenarioRow) -> Scenario:
        raw: dict[str, float] = json.loads(row.levers_json)
        levers: dict[LeverId, float] = {}
        for key, value in raw.items():
            try:
                levers[LeverId(key)] = float(value)
            except ValueError:
                # A lever removed in a later version — drop it rather than
                # failing to load an otherwise valid saved scenario.
                continue
        return Scenario(
            id=row.id,
            center_id=row.center_id,
            name=row.name,
            tab=SimulationTab(row.tab),
            levers=levers,
            notes=row.notes,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    # -- queries ----------------------------------------------------------

    def list_for_center(self, center_id: str) -> tuple[Scenario, ...]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(ScenarioRow)
                .where(ScenarioRow.center_id == center_id)
                .order_by(ScenarioRow.created_at.asc())
            ).all()
            return tuple(self._to_model(row) for row in rows)

    def get(self, scenario_id: str) -> Scenario | None:
        with self._session_factory() as session:
            row = session.get(ScenarioRow, scenario_id)
            return self._to_model(row) if row else None

    def get_many(self, scenario_ids: list[str]) -> tuple[Scenario, ...]:
        if not scenario_ids:
            return ()
        with self._session_factory() as session:
            rows = session.scalars(
                select(ScenarioRow).where(ScenarioRow.id.in_(scenario_ids))
            ).all()
            found = {row.id: self._to_model(row) for row in rows}
        # Preserve the caller's ordering so comparison columns stay where the
        # user put them.
        return tuple(found[sid] for sid in scenario_ids if sid in found)

    # -- mutations --------------------------------------------------------

    def create(self, payload: ScenarioCreate) -> Scenario:
        with self._session_factory() as session:
            existing = session.scalars(
                select(ScenarioRow).where(ScenarioRow.center_id == payload.center_id)
            ).all()
            if len(existing) >= MAX_SCENARIOS_PER_CENTER:
                raise ScenarioLimitError(
                    f"הגעת למגבלה של {MAX_SCENARIOS_PER_CENTER} תרחישים שמורים למוקד זה"
                )

            now = datetime.now(UTC)
            row = ScenarioRow(
                id=f"scn_{uuid.uuid4().hex[:12]}",
                center_id=payload.center_id,
                name=payload.name.strip(),
                tab=payload.tab.value,
                levers_json=json.dumps(
                    {k.value: v for k, v in payload.levers.items()}, ensure_ascii=False
                ),
                notes=payload.notes,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            session.commit()
            return self._to_model(row)

    def update(self, scenario_id: str, payload: ScenarioUpdate) -> Scenario | None:
        with self._session_factory() as session:
            row = session.get(ScenarioRow, scenario_id)
            if row is None:
                return None
            if payload.name is not None:
                row.name = payload.name.strip()
            if payload.levers is not None:
                row.levers_json = json.dumps(
                    {k.value: v for k, v in payload.levers.items()}, ensure_ascii=False
                )
            if payload.notes is not None:
                row.notes = payload.notes
            row.updated_at = datetime.now(UTC)
            session.commit()
            return self._to_model(row)

    def delete(self, scenario_id: str) -> bool:
        with self._session_factory() as session:
            row = session.get(ScenarioRow, scenario_id)
            if row is None:
                return False
            session.delete(row)
            session.commit()
            return True
