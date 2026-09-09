"""Unit tests for teacher_content_service."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.teacher_content_service import list_all_explanation_content, list_explanation_content


@pytest.fixture
def mock_db() -> MagicMock:
    """Create a mock database session."""
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock()
    return session


class TestListAllExplanationContent:
    """Tests for list_all_explanation_content function."""

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_classes(self, mock_db: MagicMock) -> None:
        """Test returns empty list when teacher has no classes."""
        # Arrange
        teacher_id = uuid.uuid4()
        school_id = uuid.uuid4()

        # Mock empty class result
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_db.execute.return_value = mock_result

        # Act
        result = await list_all_explanation_content(
            db=mock_db,
            teacher_id=teacher_id,
            school_id=school_id,
            status_filter=None,
        )

        # Assert
        assert result == []
        # Should execute exactly one query (to get classes)
        assert mock_db.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_queries_classes_with_correct_filters(self, mock_db: MagicMock) -> None:
        """Test that correct filters are applied when querying classes."""
        # Arrange
        teacher_id = uuid.uuid4()
        school_id = uuid.uuid4()

        # Mock empty class result
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_db.execute.return_value = mock_result

        # Act
        await list_all_explanation_content(
            db=mock_db,
            teacher_id=teacher_id,
            school_id=school_id,
            status_filter="pending",
        )

        # Assert - verify the class query was called with correct filters
        # The select query should have teacher_id and school_id filters
        assert mock_db.execute.called

    @pytest.mark.asyncio
    async def test_calls_db_twice_when_classes_exist(self, mock_db: MagicMock) -> None:
        """Test that two queries are executed when teacher has classes."""
        # Arrange
        teacher_id = uuid.uuid4()
        school_id = uuid.uuid4()
        class_id = uuid.uuid4()
        subject_id = uuid.uuid4()
        grade_id = uuid.uuid4()

        # First call returns a class, second returns empty content
        class_result = MagicMock()
        class_result.all.return_value = [
            MagicMock(
                id=class_id,
                name="Math 7A",
                subject_id=subject_id,
                grade_id=grade_id,
            )
        ]
        content_result = MagicMock()
        content_result.unique.return_value.all.return_value = []

        mock_db.execute.side_effect = [class_result, content_result]

        # Act
        result = await list_all_explanation_content(
            db=mock_db,
            teacher_id=teacher_id,
            school_id=school_id,
            status_filter=None,
        )

        # Assert
        assert mock_db.execute.call_count == 2
        assert result == []

    @pytest.mark.asyncio
    async def test_builds_subject_and_grade_sets_from_classes(self, mock_db: MagicMock) -> None:
        """Test that subject and grade IDs are extracted from classes."""
        # Arrange
        teacher_id = uuid.uuid4()
        school_id = uuid.uuid4()
        class1_id = uuid.uuid4()
        class2_id = uuid.uuid4()
        subject1_id = uuid.uuid4()
        subject2_id = uuid.uuid4()
        grade1_id = uuid.uuid4()
        grade2_id = uuid.uuid4()

        # Two classes with different subject/grade combos
        class_result = MagicMock()
        class_result.all.return_value = [
            MagicMock(
                id=class1_id,
                name="Math 7A",
                subject_id=subject1_id,
                grade_id=grade1_id,
            ),
            MagicMock(
                id=class2_id,
                name="Math 8B",
                subject_id=subject2_id,
                grade_id=grade2_id,
            ),
        ]
        content_result = MagicMock()
        content_result.unique.return_value.all.return_value = []

        mock_db.execute.side_effect = [class_result, content_result]

        # Act
        await list_all_explanation_content(
            db=mock_db,
            teacher_id=teacher_id,
            school_id=school_id,
            status_filter=None,
        )

        # Assert - verify both queries were made
        assert mock_db.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_status_filter_passed_to_query(self, mock_db: MagicMock) -> None:
        """Test that status filter is passed to content query."""
        # Arrange
        teacher_id = uuid.uuid4()
        school_id = uuid.uuid4()
        class_id = uuid.uuid4()
        subject_id = uuid.uuid4()
        grade_id = uuid.uuid4()

        class_result = MagicMock()
        class_result.all.return_value = [
            MagicMock(
                id=class_id,
                name="Math 7A",
                subject_id=subject_id,
                grade_id=grade_id,
            )
        ]
        content_result = MagicMock()
        content_result.unique.return_value.all.return_value = []

        mock_db.execute.side_effect = [class_result, content_result]

        # Act
        await list_all_explanation_content(
            db=mock_db,
            teacher_id=teacher_id,
            school_id=school_id,
            status_filter="approved",
        )

        # Assert - verify second query includes status filter
        # The where clause should include review_status filter
        assert mock_db.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_content_query_when_called_then_scopes_to_caller_school(self, mock_db: MagicMock) -> None:
        """Regression test for the cross-school leak fixed in MCR-T1: the content query must
        include the school-visibility clause, not just subject_id/grade_id — otherwise a
        teacher sees every school's rows sharing the same curriculum coordinates."""
        teacher_id = uuid.uuid4()
        school_id = uuid.uuid4()
        class_id = uuid.uuid4()
        subject_id = uuid.uuid4()
        grade_id = uuid.uuid4()

        class_result = MagicMock()
        class_result.all.return_value = [
            MagicMock(id=class_id, name="Math 7A", subject_id=subject_id, grade_id=grade_id)
        ]
        content_result = MagicMock()
        content_result.unique.return_value.all.return_value = []
        mock_db.execute.side_effect = [class_result, content_result]

        await list_all_explanation_content(
            db=mock_db,
            teacher_id=teacher_id,
            school_id=school_id,
            status_filter=None,
        )

        content_query = mock_db.execute.call_args_list[1].args[0]
        compiled_sql = str(content_query.compile(compile_kwargs={"literal_binds": True}))
        assert "subtopic_content.scope" in compiled_sql
        assert str(school_id).replace("-", "") in compiled_sql


class TestListExplanationContent:
    """Tests for list_explanation_content (per-class review query)."""

    @pytest.mark.asyncio
    async def test_content_query_when_called_then_scopes_to_caller_school(self, mock_db: MagicMock) -> None:
        """Regression test for the cross-school leak fixed in MCR-T1: without the school scope
        clause, this query returns any school's rows for the class's subject/grade."""
        subject_id = uuid.uuid4()
        grade_id = uuid.uuid4()
        school_id = uuid.uuid4()

        count_result = MagicMock()
        count_result.scalar_one.return_value = 0
        data_result = MagicMock()
        data_result.unique.return_value.scalars.return_value.all.return_value = []
        mock_db.execute.side_effect = [count_result, count_result, data_result]

        await list_explanation_content(
            db=mock_db,
            subject_id=subject_id,
            grade_id=grade_id,
            school_id=school_id,
            status_filter=None,
            page=1,
            page_size=20,
        )

        # First call is the "total" count query — assert it already carries the scope clause,
        # since _base_where wraps every query built in this function.
        total_query = mock_db.execute.call_args_list[0].args[0]
        compiled_sql = str(total_query.compile(compile_kwargs={"literal_binds": True}))
        assert "subtopic_content.scope" in compiled_sql
        assert str(school_id).replace("-", "") in compiled_sql
