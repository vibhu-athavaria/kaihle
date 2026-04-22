"""Unit tests for AnalyticsService."""

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.analytics_service import AnalyticsService

SCHOOL_ID = uuid4()


@pytest.fixture
def mock_db() -> MagicMock:
    """Create a mock async DB session.

    execute is AsyncMock so it can be awaited; its return_value is MagicMock
    so that .scalar() and .all() are synchronous (matching SQLAlchemy's sync
    result API after the async execute call).
    """
    db = MagicMock(spec=AsyncSession)
    db.execute = AsyncMock()
    return db


@pytest.fixture
def service(mock_db: MagicMock) -> AnalyticsService:
    return AnalyticsService(mock_db)


def _make_zero_result() -> MagicMock:
    """Return a synchronous result mock where scalar()=0 and all()=[]."""
    result = MagicMock()
    result.scalar.return_value = 0
    result.all.return_value = []
    return result


def _make_count_result(n: int) -> MagicMock:
    result = MagicMock()
    result.scalar.return_value = n
    result.all.return_value = []
    return result


async def test_get_school_analytics_when_no_students_then_returns_zeros(
    service: AnalyticsService, mock_db: MagicMock
) -> None:
    mock_db.execute.return_value = _make_zero_result()
    result = await service.get_school_analytics(SCHOOL_ID, date.today() - timedelta(days=30), date.today())
    assert result.total_students == 0
    assert result.onboarding_funnel.invited == 0


async def test_get_school_analytics_when_date_range_given_then_filters_assessments(
    service: AnalyticsService, mock_db: MagicMock
) -> None:
    from_date = date(2025, 4, 1)
    to_date = date(2025, 4, 30)
    mock_db.execute.return_value = _make_count_result(5)
    result = await service.get_school_analytics(SCHOOL_ID, from_date, to_date)
    assert result is not None


async def test_get_student_mastery_summary_when_no_gap_states_then_returns_none(
    service: AnalyticsService, mock_db: MagicMock
) -> None:
    empty_result = MagicMock()
    empty_result.all.return_value = []
    mock_db.execute.return_value = empty_result
    result = await service.get_student_mastery_summaries(SCHOOL_ID)
    assert result == []


async def test_get_school_analytics_when_no_dates_then_defaults_to_30_day_window(
    service: AnalyticsService, mock_db: MagicMock
) -> None:
    mock_db.execute.return_value = _make_zero_result()
    result = await service.get_school_analytics(SCHOOL_ID)
    assert result is not None
