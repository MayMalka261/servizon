from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.config import get_settings
from app.domain.enums import KpiId, LeverId, SimulationTab
from app.domain.models import BaselineMetrics, LeverBounds, Snapshot
from app.simulation.coefficients import Coefficients, load_coefficients
from app.simulation.engine import SimulationEngine
from app.simulation.kpis import KPI_DEFINITIONS


@pytest.fixture(scope="session")
def settings():
    return get_settings()


@pytest.fixture(scope="session")
def engine(settings) -> SimulationEngine:
    return SimulationEngine(settings.coefficients_path)


@pytest.fixture(scope="session")
def coefficients(settings) -> Coefficients:
    return load_coefficients(settings.coefficients_path, "technical_support")


@pytest.fixture
def baseline() -> BaselineMetrics:
    """A moderately strained center: enough headroom to move in either direction."""
    return BaselineMetrics(
        daily_contacts=4000.0,
        peak_hour_contacts=400.0,
        aht_sec=300.0,
        agents_scheduled=55.0,
        shrinkage=0.28,
        working_hours_per_day=12.0,
        digital_adoption=0.45,
        self_service_rate=0.30,
        automation_level=0.25,
        agent_ai_usage=0.30,
        customer_ai_usage=0.30,
        knowledge_base_quality=0.60,
        fcr=0.70,
        sla_target_sec=60.0,
        abandonment_target=0.05,
        queue_size=20.0,
        patience_sec=200.0,
    )


@pytest.fixture
def snapshot(baseline: BaselineMetrics) -> Snapshot:
    return Snapshot(
        id="snap_test_0001",
        center_id="SC-TEST",
        captured_at=datetime.now(UTC),
        baseline=baseline,
        kpis=(),
        trend={tab: () for tab in SimulationTab},
        lever_defaults={
            LeverId.DIGITAL_ADOPTION: 45.0,
            LeverId.SELF_SERVICE_RATE: 30.0,
            LeverId.AUTOMATION_LEVEL: 25.0,
            LeverId.AGENT_AI: 30.0,
            LeverId.CUSTOMER_AI: 30.0,
            LeverId.KNOWLEDGE_BASE_QUALITY: 60.0,
            LeverId.FIRST_CALL_RESOLUTION: 70.0,
            LeverId.ABANDONMENT_TARGET: 5.0,
            LeverId.WORKFORCE_CAPACITY: 55.0,
            LeverId.WORKING_HOURS: 12.0,
            LeverId.AVERAGE_HANDLE_TIME: 300.0,
            LeverId.SLA_TARGET: 60.0,
            LeverId.QUEUE_SIZE: 20.0,
        },
        lever_bounds={
            LeverId.WORKFORCE_CAPACITY: LeverBounds(min=22.0, max=138.0, step=1.0),
            LeverId.QUEUE_SIZE: LeverBounds(min=5.0, max=60.0, step=1.0),
        },
    )


@pytest.fixture(scope="session")
def all_kpi_ids() -> tuple[KpiId, ...]:
    return tuple(k.id for k in KPI_DEFINITIONS)
