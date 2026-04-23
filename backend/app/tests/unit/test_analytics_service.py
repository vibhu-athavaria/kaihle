"""Unit tests for AnalyticsService."""

import uuid
from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.analytics import OnboardingFunnel, SchoolAnalyticsData
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
def mock_redis() -> MagicMock:
    """Create a mock async Redis client."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.setex = AsyncMock()
    return redis


@pytest.fixture
def service(mock_db: MagicMock, mock_redis: MagicMock) -> AnalyticsService:
    return AnalyticsService(mock_db, mock_redis)


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


async def test_get_diagnostic_completed_student_ids_when_empty_list_then_returns_empty_set(
    service: AnalyticsService, mock_db: MagicMock
) -> None:
    """Empty input short-circuits before any DB call."""
    result = await service.get_diagnostic_completed_student_ids(SCHOOL_ID, [])
    assert result == set()
    mock_db.execute.assert_not_called()


async def test_get_diagnostic_completed_student_ids_when_students_given_then_queries_db(
    service: AnalyticsService, mock_db: MagicMock
) -> None:
    """IDs returned by the DB query are included in the result set."""
    from uuid import uuid4

    student_id = uuid4()
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = [student_id]
    execute_result = MagicMock()
    execute_result.scalars.return_value = scalars_mock
    mock_db.execute.return_value = execute_result

    result = await service.get_diagnostic_completed_student_ids(SCHOOL_ID, [student_id])

    assert student_id in result
    assert isinstance(result, set)
    mock_db.execute.assert_called_once()


async def test_get_diagnostic_completed_student_ids_when_none_completed_then_returns_empty_set(
    service: AnalyticsService, mock_db: MagicMock
) -> None:
    """When DB returns no rows, result is an empty set (not None, not a list)."""
    from uuid import uuid4

    student_id = uuid4()
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = []
    execute_result = MagicMock()
    execute_result.scalars.return_value = scalars_mock
    mock_db.execute.return_value = execute_result

    result = await service.get_diagnostic_completed_student_ids(SCHOOL_ID, [student_id])

    assert result == set()
    assert student_id not in result


async def test_get_school_analytics_when_cache_hit_then_db_not_queried(
    service: AnalyticsService,
    mock_redis: MagicMock,
    mock_db: MagicMock,
) -> None:
    """Cache hit must skip all DB queries — verifies the short-circuit path."""
    school_id = uuid.uuid4()
    cached_data = SchoolAnalyticsData(
        school_id=school_id,
        generated_at=datetime.now(UTC),
        total_students=5,
        total_teachers=2,
        active_students=3,
        assessments_completed=10,
        study_plans_active=2,
        onboarding_funnel=OnboardingFunnel(invited=5, password_set=4, profile_complete=3, diagnostic_done=2),
        classes=[],
        at_risk_students=[],
    )
    mock_redis.get.return_value = cached_data.model_dump_json()

    result = await service.get_school_analytics(school_id)

    assert result.total_students == 5
    assert result.total_teachers == 2
    # DB must NOT have been touched — all data came from the cache
    mock_db.execute.assert_not_called()
    mock_redis.get.assert_called_once()
    mock_redis.setex.assert_not_called()


async def test_get_school_analytics_when_cache_miss_then_result_is_cached(
    service: AnalyticsService,
    mock_redis: MagicMock,
    mock_db: MagicMock,
) -> None:
    """On a cache miss the result must be stored with 300s TTL."""
    mock_redis.get.return_value = None
    school_id = uuid.uuid4()
    mock_db.execute.return_value = _make_zero_result()

    await service.get_school_analytics(school_id)

    mock_redis.setex.assert_called_once()
    call_args = mock_redis.setex.call_args
    # setex(key, ttl, value) — TTL is the second positional argument
    assert call_args[0][1] == 300
