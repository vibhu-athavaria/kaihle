"""Unit tests for AnalyticsService."""

import uuid
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.analytics_service import AnalyticsService


@pytest.fixture
def mock_db() -> Generator[MagicMock, None, None]:
    """Create a mock database session."""
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock()
    return session


@pytest.fixture
def analytics_service(mock_db: MagicMock) -> AnalyticsService:
    """Create an AnalyticsService with a mock database."""
    return AnalyticsService(mock_db)


@pytest.fixture
def school_id() -> uuid.UUID:
    return uuid.uuid4()


class TestGetStudentMasterySummaries:
    """Tests for AnalyticsService.get_student_mastery_summaries."""

    @pytest.mark.asyncio
    async def test_get_student_mastery_summaries_when_students_exist_then_returns_summaries(
        self,
        analytics_service: AnalyticsService,
        mock_db: MagicMock,
        school_id: uuid.UUID,
    ) -> None:
        """When students with gap_states exist, returns correct mastery aggregates."""
        # Arrange
        student_id = uuid.uuid4()
        mock_row = MagicMock()
        mock_row.student_id = student_id
        mock_row.worst_mastery = 0.35
        mock_row.class_count = 2
        mock_row.needs_work_class_count = 1

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_db.execute = AsyncMock(return_value=mock_result)

        # Act
        summaries = await analytics_service.get_student_mastery_summaries(school_id)

        # Assert
        assert len(summaries) == 1
        assert summaries[0].student_id == student_id
        assert summaries[0].worst_mastery == 0.35
        assert summaries[0].class_count == 2
        assert summaries[0].needs_work_class_count == 1

    @pytest.mark.asyncio
    async def test_get_student_mastery_summaries_when_no_gap_states_then_worst_mastery_is_none(
        self,
        analytics_service: AnalyticsService,
        mock_db: MagicMock,
        school_id: uuid.UUID,
    ) -> None:
        """When a student is enrolled but has no gap_states, worst_mastery is None."""
        # Arrange
        student_id = uuid.uuid4()
        mock_row = MagicMock()
        mock_row.student_id = student_id
        mock_row.worst_mastery = None  # no assessments yet
        mock_row.class_count = 1
        mock_row.needs_work_class_count = 0

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_db.execute = AsyncMock(return_value=mock_result)

        # Act
        summaries = await analytics_service.get_student_mastery_summaries(school_id)

        # Assert
        assert summaries[0].worst_mastery is None
        assert summaries[0].class_count == 1

    @pytest.mark.asyncio
    async def test_get_student_mastery_summaries_when_no_students_then_returns_empty_list(
        self,
        analytics_service: AnalyticsService,
        mock_db: MagicMock,
        school_id: uuid.UUID,
    ) -> None:
        """When there are no enrolled students, returns an empty list."""
        # Arrange
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        # Act
        summaries = await analytics_service.get_student_mastery_summaries(school_id)

        # Assert
        assert summaries == []

    @pytest.mark.asyncio
    async def test_get_student_mastery_summaries_when_multiple_students_then_returns_all(
        self,
        analytics_service: AnalyticsService,
        mock_db: MagicMock,
        school_id: uuid.UUID,
    ) -> None:
        """Returns one summary per student when multiple students exist."""
        # Arrange
        ids = [uuid.uuid4() for _ in range(3)]
        rows = []
        for i, sid in enumerate(ids):
            row = MagicMock()
            row.student_id = sid
            row.worst_mastery = 0.2 + i * 0.2
            row.class_count = i + 1
            row.needs_work_class_count = 0
            rows.append(row)

        mock_result = MagicMock()
        mock_result.fetchall.return_value = rows
        mock_db.execute = AsyncMock(return_value=mock_result)

        # Act
        summaries = await analytics_service.get_student_mastery_summaries(school_id)

        # Assert
        assert len(summaries) == 3
        summary_map = {s.student_id: s for s in summaries}
        for i, sid in enumerate(ids):
            assert sid in summary_map
            assert summary_map[sid].class_count == i + 1


class TestGetDiagnosticCompletedStudentIds:
    """Tests for AnalyticsService.get_diagnostic_completed_student_ids."""

    @pytest.mark.asyncio
    async def test_get_diagnostic_completed_student_ids_when_some_completed_then_returns_subset(
        self,
        analytics_service: AnalyticsService,
        mock_db: MagicMock,
        school_id: uuid.UUID,
    ) -> None:
        """Returns only student_ids with at least one COMPLETED diagnostic enrollment."""
        # Arrange
        completed_id = uuid.uuid4()
        pending_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [(completed_id,)]
        mock_db.execute = AsyncMock(return_value=mock_result)

        # Act
        result = await analytics_service.get_diagnostic_completed_student_ids(school_id, [completed_id, pending_id])

        # Assert
        assert completed_id in result
        assert pending_id not in result

    @pytest.mark.asyncio
    async def test_get_diagnostic_completed_student_ids_when_empty_input_then_returns_empty_set(
        self,
        analytics_service: AnalyticsService,
        mock_db: MagicMock,
        school_id: uuid.UUID,
    ) -> None:
        """When no student_ids provided, returns empty set without hitting DB."""
        # Act
        result = await analytics_service.get_diagnostic_completed_student_ids(school_id, [])

        # Assert — DB must NOT be called (short-circuit)
        assert result == set()
        mock_db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_diagnostic_completed_student_ids_when_none_completed_then_returns_empty_set(
        self,
        analytics_service: AnalyticsService,
        mock_db: MagicMock,
        school_id: uuid.UUID,
    ) -> None:
        """When no students have completed diagnostics, returns empty set."""
        # Arrange
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        student_ids = [uuid.uuid4(), uuid.uuid4()]

        # Act
        result = await analytics_service.get_diagnostic_completed_student_ids(school_id, student_ids)

        # Assert
        assert result == set()
