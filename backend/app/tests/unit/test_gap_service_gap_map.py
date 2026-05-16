"""Unit tests for GapService gap map aggregation methods."""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.services.gap_service import GapService


def _make_db() -> MagicMock:
    db = MagicMock()
    db.scalar = AsyncMock()
    db.execute = AsyncMock()
    return db


def _make_class(class_id: uuid.UUID, school_id: uuid.UUID, grade_id: uuid.UUID) -> SimpleNamespace:
    return SimpleNamespace(
        id=class_id,
        school_id=school_id,
        grade_id=grade_id,
        subject_id=uuid.uuid4(),
        is_active=True,
    )


def _make_family_execute_result(subject_id: uuid.UUID) -> MagicMock:
    """Return a mock execute result yielding one subject id row (for family lookup)."""
    result = MagicMock()
    result.all.return_value = [(subject_id,)]
    return result


class TestGetClassGapMap:
    @pytest.mark.asyncio
    async def test_get_class_gap_map_when_wrong_school_id_then_raises_404(self) -> None:
        db = _make_db()
        db.scalar.return_value = None  # Class not found for wrong school
        service = GapService(db)

        with pytest.raises(HTTPException) as exc_info:
            await service.get_class_gap_map(uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_class_gap_map_when_no_subtopics_then_returns_empty_nodes(self) -> None:
        db = _make_db()
        class_id, school_id = uuid.uuid4(), uuid.uuid4()
        subject_id = uuid.uuid4()
        # scalar calls: class lookup, then subject_family_code
        db.scalar.side_effect = [_make_class(class_id, school_id, uuid.uuid4()), "SCI"]
        empty_result = MagicMock()
        empty_result.all.return_value = []
        # execute calls: family subject ids, subtopics, gap_rows
        db.execute.side_effect = [
            _make_family_execute_result(subject_id),
            empty_result,
            empty_result,
        ]
        service = GapService(db)

        result = await service.get_class_gap_map(class_id, school_id, subject_id)

        assert result.nodes == []
        assert result.class_id == class_id

    @pytest.mark.asyncio
    async def test_get_class_gap_map_when_students_have_gap_states_then_class_average_correct(self) -> None:
        db = _make_db()
        class_id, school_id, grade_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        subtopic_id, topic_id, subject_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        student_id_1, student_id_2 = uuid.uuid4(), uuid.uuid4()
        # scalar calls: class lookup, subject_family_code
        db.scalar.side_effect = [_make_class(class_id, school_id, grade_id), "SCI"]

        subtopic_row = SimpleNamespace(
            subtopic_id=subtopic_id,
            subtopic_name="Algebra",
            topic_id=topic_id,
            topic_name="Maths",
            grade_id=grade_id,
            grade_name="Grade 7",
            grade_level=7,
        )
        subtopics_result = MagicMock()
        subtopics_result.all.return_value = [subtopic_row]

        gap_row_1 = SimpleNamespace(
            subtopic_id=subtopic_id,
            student_id=student_id_1,
            mastery_score=0.6,
            last_assessed_at=datetime(2026, 4, 1, tzinfo=UTC),
            first_name="Alice",
            last_name="Smith",
        )
        gap_row_2 = SimpleNamespace(
            subtopic_id=subtopic_id,
            student_id=student_id_2,
            mastery_score=0.8,
            last_assessed_at=datetime(2026, 4, 1, tzinfo=UTC),
            first_name="Bob",
            last_name="Jones",
        )
        gap_result = MagicMock()
        gap_result.all.return_value = [gap_row_1, gap_row_2]
        # execute calls: family subject ids, subtopics, gap_rows
        db.execute.side_effect = [_make_family_execute_result(subject_id), subtopics_result, gap_result]
        service = GapService(db)

        result = await service.get_class_gap_map(class_id, school_id, subject_id)

        assert len(result.nodes) == 1
        assert result.nodes[0].class_average is not None
        assert abs(result.nodes[0].class_average - 0.7) < 0.001
        assert len(result.nodes[0].student_scores) == 2

    @pytest.mark.asyncio
    async def test_get_class_gap_map_when_subtopic_has_no_gap_states_then_class_average_none(self) -> None:
        db = _make_db()
        class_id, school_id, grade_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        subtopic_id, topic_id, subject_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        # scalar calls: class lookup, subject_family_code
        db.scalar.side_effect = [_make_class(class_id, school_id, grade_id), "SCI"]

        subtopic_row = SimpleNamespace(
            subtopic_id=subtopic_id,
            subtopic_name="Algebra",
            topic_id=topic_id,
            topic_name="Maths",
            grade_id=grade_id,
            grade_name="Grade 7",
            grade_level=7,
        )
        subtopics_result = MagicMock()
        subtopics_result.all.return_value = [subtopic_row]
        gap_result = MagicMock()
        gap_result.all.return_value = []
        # execute calls: family subject ids, subtopics, gap_rows
        db.execute.side_effect = [_make_family_execute_result(subject_id), subtopics_result, gap_result]
        service = GapService(db)

        result = await service.get_class_gap_map(class_id, school_id, subject_id)

        assert len(result.nodes) == 1
        assert result.nodes[0].class_average is None
        assert result.nodes[0].student_scores == []

    @pytest.mark.asyncio
    async def test_get_class_gap_map_when_subject_has_no_family_then_falls_back_to_exact_subject(self) -> None:
        """Subjects with no subject_family_code (e.g. Geography) fall back to exact subject filter."""
        db = _make_db()
        class_id, school_id, grade_id, subject_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        # scalar calls: class lookup, subject_family_code returns None
        db.scalar.side_effect = [_make_class(class_id, school_id, grade_id), None]
        empty_result = MagicMock()
        empty_result.all.return_value = []
        # execute calls: NO family lookup (skipped), subtopics, gap_rows
        db.execute.side_effect = [empty_result, empty_result]
        service = GapService(db)

        result = await service.get_class_gap_map(class_id, school_id, subject_id)

        assert result.nodes == []


class TestGetStudentGapMap:
    @pytest.mark.asyncio
    async def test_get_student_gap_map_when_student_not_enrolled_then_raises_404(self) -> None:
        db = _make_db()
        db.scalar.return_value = None  # no enrolled class
        service = GapService(db)

        with pytest.raises(HTTPException) as exc_info:
            await service.get_student_gap_map(uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_student_gap_map_when_student_has_gap_state_then_score_returned(self) -> None:
        db = _make_db()
        student_id, subject_id = uuid.uuid4(), uuid.uuid4()
        subtopic_id, topic_id = uuid.uuid4(), uuid.uuid4()
        # scalar calls: enrolled class, subject_family_code
        db.scalar.side_effect = [SimpleNamespace(grade_id=uuid.uuid4(), id=uuid.uuid4()), "SCI"]

        subtopic_row = SimpleNamespace(
            subtopic_id=subtopic_id, subtopic_name="Equations", topic_id=topic_id, topic_name="Algebra"
        )
        subtopics_result = MagicMock()
        subtopics_result.all.return_value = [subtopic_row]

        gap_row = SimpleNamespace(
            subtopic_id=subtopic_id, mastery_score=0.75, last_assessed_at=datetime(2026, 4, 1, tzinfo=UTC)
        )
        gap_result = MagicMock()
        gap_result.all.return_value = [gap_row]
        # execute calls: family subject ids, subtopics, gap_rows
        db.execute.side_effect = [_make_family_execute_result(subject_id), subtopics_result, gap_result]
        service = GapService(db)

        result = await service.get_student_gap_map(student_id, uuid.uuid4(), subject_id)

        assert len(result.scores) == 1
        assert result.scores[0].mastery_score == 0.75

    @pytest.mark.asyncio
    async def test_get_student_gap_map_when_no_assessed_subtopics_then_returns_empty_scores(self) -> None:
        """API only returns assessed subtopics — unassessed subtopics are excluded at the query level."""
        db = _make_db()
        subject_id = uuid.uuid4()
        # scalar calls: enrolled class, subject_family_code
        db.scalar.side_effect = [SimpleNamespace(grade_id=uuid.uuid4(), id=uuid.uuid4()), "MATH"]

        empty_result = MagicMock()
        empty_result.all.return_value = []
        # execute calls: family subject ids, subtopics (empty — subquery excludes unassessed), gap_rows
        db.execute.side_effect = [_make_family_execute_result(subject_id), empty_result, empty_result]
        service = GapService(db)

        result = await service.get_student_gap_map(uuid.uuid4(), uuid.uuid4(), subject_id)

        assert result.scores == []


class TestGetClassSummary:
    @pytest.mark.asyncio
    async def test_get_class_summary_when_wrong_school_id_then_raises_404(self) -> None:
        db = _make_db()
        db.scalar.return_value = None
        service = GapService(db)

        with pytest.raises(HTTPException) as exc_info:
            await service.get_class_summary(uuid.uuid4(), uuid.uuid4())
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_class_summary_when_no_assessments_then_avg_mastery_none(self) -> None:
        db = _make_db()
        class_id, school_id = uuid.uuid4(), uuid.uuid4()
        # scalar calls in order: class lookup, below_threshold count, total enrollment count
        db.scalar.side_effect = [_make_class(class_id, school_id, uuid.uuid4()), 0, 5]
        agg_row = SimpleNamespace(avg_mastery=None, assessed_students=0, last_updated=None)
        agg_result = MagicMock()
        agg_result.one.return_value = agg_row
        db.execute.return_value = agg_result
        service = GapService(db)

        result = await service.get_class_summary(class_id, school_id)

        assert result.avg_mastery is None
        assert result.student_count == 5
        assert result.assessed_student_count == 0
        assert result.students_below_threshold == 0

    @pytest.mark.asyncio
    async def test_get_class_summary_when_2_of_5_assessed_then_counts_correct(self) -> None:
        db = _make_db()
        class_id, school_id = uuid.uuid4(), uuid.uuid4()
        # scalar calls in order: class lookup, below_threshold count (1 student below 0.4), total enrollment count
        db.scalar.side_effect = [_make_class(class_id, school_id, uuid.uuid4()), 1, 5]
        agg_row = SimpleNamespace(avg_mastery=0.6, assessed_students=2, last_updated=datetime(2026, 4, 1, tzinfo=UTC))
        agg_result = MagicMock()
        agg_result.one.return_value = agg_row
        db.execute.return_value = agg_result
        service = GapService(db)

        result = await service.get_class_summary(class_id, school_id)

        assert result.student_count == 5
        assert result.assessed_student_count == 2
        assert result.avg_mastery is not None
        assert abs(result.avg_mastery - 0.6) < 0.001
        assert result.students_below_threshold == 1


class TestVerifyTeacherHasStudentAccess:
    @pytest.mark.asyncio
    async def test_verify_teacher_has_student_access_when_correct_school_then_returns_true(self) -> None:
        db = _make_db()
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = uuid.uuid4()  # found a class_id
        db.execute.return_value = execute_result
        service = GapService(db)

        result = await service._verify_teacher_has_student_access(uuid.uuid4(), uuid.uuid4(), uuid.uuid4())

        assert result is True

    @pytest.mark.asyncio
    async def test_verify_teacher_has_student_access_when_wrong_school_then_returns_false(self) -> None:
        db = _make_db()
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = None  # no matching class in this school
        db.execute.return_value = execute_result
        service = GapService(db)

        result = await service._verify_teacher_has_student_access(uuid.uuid4(), uuid.uuid4(), uuid.uuid4())

        assert result is False

    @pytest.mark.asyncio
    async def test_verify_teacher_has_student_access_when_inactive_enrollment_then_returns_false(self) -> None:
        db = _make_db()
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = None  # inactive enrollment filtered out
        db.execute.return_value = execute_result
        service = GapService(db)

        result = await service._verify_teacher_has_student_access(uuid.uuid4(), uuid.uuid4(), uuid.uuid4())

        assert result is False
