"""Unit tests for MiniCourseService.get_student_course_progress.

Tests verify that the teacher-facing progress endpoint:
- Returns ordered progress rows when the student has data.
- Returns an empty list when the student has no progress.
- Raises HTTP 403 when the student belongs to a different school.

Run with: pytest app/tests/unit/test_student_course_progress_service.py -v
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.services.mini_course_service import MiniCourseService


def _make_db_row(
    subtopic_id: object,
    subtopic_name: str,
    topic_name: str,
    last_visited_at: datetime,
    explanation_accessed: bool = False,
    video_accessed: bool = False,
    check_questions_score: float | None = None,
) -> MagicMock:
    """Helper: build a mock SQLAlchemy result row."""
    row = MagicMock()
    row.subtopic_id = subtopic_id
    row.subtopic_name = subtopic_name
    row.topic_name = topic_name
    row.last_visited_at = last_visited_at
    row.explanation_accessed = explanation_accessed
    row.video_accessed = video_accessed
    row.check_questions_score = check_questions_score
    return row


class TestGetStudentCourseProgress:
    """Unit tests for MiniCourseService.get_student_course_progress."""

    @pytest.mark.asyncio
    async def test_get_student_course_progress_when_student_has_progress_then_returns_ordered_list(
        self,
    ) -> None:
        """Service returns SubtopicProgressItems ordered by last_visited_at DESC when rows exist."""
        student_id = uuid4()
        school_id = uuid4()
        subtopic_id_a = uuid4()
        subtopic_id_b = uuid4()

        now = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)
        earlier = datetime(2026, 5, 14, 8, 0, 0, tzinfo=UTC)

        rows = [
            _make_db_row(subtopic_id_a, "Fractions", "Number", now, explanation_accessed=True),
            _make_db_row(
                subtopic_id_b, "Algebra Basics", "Algebra", earlier, video_accessed=True, check_questions_score=0.8
            ),
        ]

        mock_student = MagicMock()

        db = AsyncMock()

        # First execute call: student membership check → returns a student
        student_result = MagicMock()
        student_result.scalar_one_or_none.return_value = mock_student

        # Second execute call: progress rows query → returns rows
        progress_result = MagicMock()
        progress_result.all.return_value = rows

        db.execute = AsyncMock(side_effect=[student_result, progress_result])

        service = MiniCourseService(db)
        response = await service.get_student_course_progress(
            student_id=student_id,
            school_id=school_id,
            teacher_id=uuid4(),
        )

        assert response.student_id == student_id
        assert len(response.progress) == 2

        first = response.progress[0]
        assert first.subtopic_id == subtopic_id_a
        assert first.subtopic_name == "Fractions"
        assert first.topic_name == "Number"
        assert first.explanation_accessed is True
        assert first.video_accessed is False
        assert first.check_questions_score is None
        assert first.last_visited_at == now

        second = response.progress[1]
        assert second.subtopic_id == subtopic_id_b
        assert second.check_questions_score == 0.8

    @pytest.mark.asyncio
    async def test_get_student_course_progress_when_student_has_no_progress_then_returns_empty_list(
        self,
    ) -> None:
        """Service returns an empty progress list when no rows exist for the student."""
        student_id = uuid4()
        school_id = uuid4()

        mock_student = MagicMock()

        db = AsyncMock()

        student_result = MagicMock()
        student_result.scalar_one_or_none.return_value = mock_student

        progress_result = MagicMock()
        progress_result.all.return_value = []

        db.execute = AsyncMock(side_effect=[student_result, progress_result])

        service = MiniCourseService(db)
        response = await service.get_student_course_progress(
            student_id=student_id,
            school_id=school_id,
            teacher_id=uuid4(),
        )

        assert response.student_id == student_id
        assert response.progress == []

    @pytest.mark.asyncio
    async def test_get_student_course_progress_when_school_id_mismatch_then_raises_403(
        self,
    ) -> None:
        """Service raises HTTP 403 when student is not found in the given school."""
        student_id = uuid4()
        school_id = uuid4()  # Teacher's school — does not match student's school

        db = AsyncMock()

        student_result = MagicMock()
        student_result.scalar_one_or_none.return_value = None  # student not in this school

        db.execute = AsyncMock(return_value=student_result)

        service = MiniCourseService(db)

        with pytest.raises(HTTPException) as exc_info:
            await service.get_student_course_progress(
                student_id=student_id,
                school_id=school_id,
                teacher_id=uuid4(),
            )

        assert exc_info.value.status_code == 403
