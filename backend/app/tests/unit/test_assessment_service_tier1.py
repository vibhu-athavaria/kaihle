"""Unit tests for AssessmentService.design_tier1_diagnostic and check_topic_availability.

Tests: class ownership check, existing DRAFT replacement, question sampling,
InsufficientQuestionsError, grade validation, per-topic-per-difficulty sampling,
topic availability check, response shape.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.assessment import AssessmentStatus, AssessmentType
from app.schemas.assessments import DesignTier1DiagnosticRequest
from app.services.assessment_service import (
    AssessmentService,
    TeacherNotClassOwnerError,
)


def _make_db() -> AsyncMock:
    db = AsyncMock()
    db.flush = AsyncMock()
    db.delete = AsyncMock()
    db.add = MagicMock()
    db.execute = AsyncMock()
    return db


def _make_class(school_id: uuid.UUID, teacher_id: uuid.UUID) -> MagicMock:
    cls = MagicMock()
    cls.id = uuid.uuid4()
    cls.school_id = school_id
    cls.teacher_id = teacher_id
    cls.name = "Math 7A"
    return cls


@pytest.mark.asyncio
async def test_design_tier1_when_class_not_found_then_raises_value_error() -> None:
    db = _make_db()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result)

    service = AssessmentService(db)
    body = DesignTier1DiagnosticRequest(topic_ids=[uuid.uuid4()])

    with pytest.raises(ValueError, match="Class not found"):
        await service.design_tier1_diagnostic(
            class_id=uuid.uuid4(),
            school_id=uuid.uuid4(),
            teacher_id=uuid.uuid4(),
            body=body,
        )


@pytest.mark.asyncio
async def test_design_tier1_when_teacher_not_owner_then_raises_teacher_not_class_owner_error() -> None:
    db = _make_db()
    school_id = uuid.uuid4()
    real_teacher_id = uuid.uuid4()
    other_teacher_id = uuid.uuid4()

    fake_class = _make_class(school_id=school_id, teacher_id=real_teacher_id)

    result = MagicMock()
    result.scalar_one_or_none.return_value = fake_class
    db.execute = AsyncMock(return_value=result)

    service = AssessmentService(db)
    body = DesignTier1DiagnosticRequest(topic_ids=[uuid.uuid4()])

    with pytest.raises(TeacherNotClassOwnerError):
        await service.design_tier1_diagnostic(
            class_id=fake_class.id,
            school_id=school_id,
            teacher_id=other_teacher_id,
            body=body,
        )


@pytest.mark.asyncio
async def test_design_tier1_when_existing_active_diagnostic_then_raises_value_error() -> None:
    db = _make_db()
    school_id = uuid.uuid4()
    teacher_id = uuid.uuid4()
    fake_class = _make_class(school_id=school_id, teacher_id=teacher_id)

    existing_assessment = MagicMock()
    existing_assessment.status = AssessmentStatus.ACTIVE

    result1 = MagicMock()
    result1.scalar_one_or_none.return_value = fake_class
    result2 = MagicMock()
    result2.scalar_one_or_none.return_value = existing_assessment
    db.execute = AsyncMock(side_effect=[result1, result2])

    service = AssessmentService(db)
    body = DesignTier1DiagnosticRequest(topic_ids=[uuid.uuid4()])

    with pytest.raises(ValueError, match="ACTIVE"):
        await service.design_tier1_diagnostic(
            class_id=fake_class.id,
            school_id=school_id,
            teacher_id=teacher_id,
            body=body,
        )


def _make_grade_and_topic_mocks(topic_id: uuid.UUID, grade_level: int = 8) -> tuple[MagicMock, MagicMock]:
    """Return (result_class_grade, result_topic_grades) mocks for the two new queries."""
    result_class_grade = MagicMock()
    result_class_grade.scalar_one_or_none.return_value = grade_level
    topic_rows = [SimpleNamespace(curriculum_topic_id=topic_id, grade_level=grade_level, grade_id=uuid.uuid4())]
    result_topic_grades = MagicMock()
    result_topic_grades.all.return_value = topic_rows
    return result_class_grade, result_topic_grades


@pytest.mark.asyncio
async def test_design_tier1_when_thin_pool_then_creates_assessment_with_student_facing_count() -> None:
    # Pool has only 1 question per difficulty (5 total across levels 1–5).
    # student_facing_count = questions_per_topic × topics = 2 × 1 = 2.
    # question_count stores the student-facing number, not the pool size.
    db = _make_db()
    school_id = uuid.uuid4()
    teacher_id = uuid.uuid4()
    topic_id = uuid.uuid4()
    fake_class = _make_class(school_id=school_id, teacher_id=teacher_id)

    result1 = MagicMock()
    result1.scalar_one_or_none.return_value = fake_class
    result2 = MagicMock()
    result2.scalar_one_or_none.return_value = None
    result_grade, result_topic_grades = _make_grade_and_topic_mocks(topic_id)
    result_questions = MagicMock()
    result_questions.all.return_value = [(uuid.uuid4(), topic_id, float(d)) for d in range(1, 6)]
    db.execute = AsyncMock(side_effect=[result1, result2, result_grade, result_topic_grades, result_questions])

    service = AssessmentService(db)
    body = DesignTier1DiagnosticRequest(topic_ids=[topic_id], questions_per_topic=2)
    assessment = await service.design_tier1_diagnostic(
        class_id=fake_class.id,
        school_id=school_id,
        teacher_id=teacher_id,
        body=body,
    )
    # student_facing_count = 2 (questions_per_topic) × 1 (topic) = 2
    assert assessment.question_count == 2


@pytest.mark.asyncio
async def test_design_tier1_when_valid_then_creates_draft_assessment() -> None:
    db = _make_db()
    school_id = uuid.uuid4()
    teacher_id = uuid.uuid4()
    topic_id = uuid.uuid4()
    fake_class = _make_class(school_id=school_id, teacher_id=teacher_id)

    result1 = MagicMock()
    result1.scalar_one_or_none.return_value = fake_class
    result2 = MagicMock()
    result2.scalar_one_or_none.return_value = None
    result_grade, result_topic_grades = _make_grade_and_topic_mocks(topic_id)
    question_rows = [(uuid.uuid4(), topic_id, float(i % 5 + 1)) for i in range(25)]
    result_questions = MagicMock()
    result_questions.all.return_value = question_rows
    db.execute = AsyncMock(side_effect=[result1, result2, result_grade, result_topic_grades, result_questions])

    service = AssessmentService(db)
    body = DesignTier1DiagnosticRequest(topic_ids=[topic_id], questions_per_topic=2)
    assessment = await service.design_tier1_diagnostic(
        class_id=fake_class.id,
        school_id=school_id,
        teacher_id=teacher_id,
        body=body,
    )

    assert assessment.status == AssessmentStatus.DRAFT
    assert assessment.assessment_type == AssessmentType.DIAGNOSTIC
    assert assessment.created_by == teacher_id
    db.add.assert_called()
    db.flush.assert_called()


@pytest.mark.asyncio
async def test_design_tier1_when_existing_draft_then_replaces_it() -> None:
    db = _make_db()
    school_id = uuid.uuid4()
    teacher_id = uuid.uuid4()
    topic_id = uuid.uuid4()
    fake_class = _make_class(school_id=school_id, teacher_id=teacher_id)

    existing_assessment = MagicMock()
    existing_assessment.id = uuid.uuid4()
    existing_assessment.status = AssessmentStatus.DRAFT

    result1 = MagicMock()
    result1.scalar_one_or_none.return_value = fake_class
    result2 = MagicMock()
    result2.scalar_one_or_none.return_value = existing_assessment
    delete_result = MagicMock()
    result_grade, result_topic_grades = _make_grade_and_topic_mocks(topic_id)
    question_rows = [(uuid.uuid4(), topic_id, float(i % 5 + 1)) for i in range(25)]
    result_questions = MagicMock()
    result_questions.all.return_value = question_rows

    db.execute = AsyncMock(
        side_effect=[result1, result2, delete_result, result_grade, result_topic_grades, result_questions]
    )

    service = AssessmentService(db)
    body = DesignTier1DiagnosticRequest(topic_ids=[topic_id], questions_per_topic=2)

    with patch(
        "app.services.assessment_service.delete",
        return_value=MagicMock(),
    ):
        await service.design_tier1_diagnostic(
            class_id=fake_class.id,
            school_id=school_id,
            teacher_id=teacher_id,
            body=body,
        )

    db.delete.assert_called_once_with(existing_assessment)


# ── Grade validation tests ────────────────────────────────────────────────────


def _make_class_with_grade(
    school_id: uuid.UUID,
    teacher_id: uuid.UUID,
    grade_level: int = 8,
) -> MagicMock:
    cls = MagicMock()
    cls.id = uuid.uuid4()
    cls.school_id = school_id
    cls.teacher_id = teacher_id
    cls.name = f"Math Grade {grade_level}"
    cls.grade_id = uuid.uuid4()
    return cls


def _make_topic_row(topic_id: uuid.UUID, grade_level: int) -> SimpleNamespace:
    """Simulate a (CurriculumTopic.id, Grade.level, CurriculumTopic.grade_id) row."""
    return SimpleNamespace(
        curriculum_topic_id=topic_id,
        grade_level=grade_level,
        grade_id=uuid.uuid4(),
    )


@pytest.mark.asyncio
async def test_design_tier1_when_previous_grade_topic_included_then_accepted() -> None:
    """Topics from class.grade.level - 1 must be accepted without error."""
    db = _make_db()
    school_id = uuid.uuid4()
    teacher_id = uuid.uuid4()
    fake_class = _make_class_with_grade(school_id=school_id, teacher_id=teacher_id, grade_level=8)

    current_topic_id = uuid.uuid4()
    previous_topic_id = uuid.uuid4()

    result_class = MagicMock()
    result_class.scalar_one_or_none.return_value = fake_class
    result_existing = MagicMock()
    result_existing.scalar_one_or_none.return_value = None
    # Grade validation query: returns rows for current + previous grade topics
    result_class_grade = MagicMock()
    result_class_grade.scalar_one_or_none.return_value = 8
    topic_rows = [
        SimpleNamespace(curriculum_topic_id=current_topic_id, grade_level=8, grade_id=uuid.uuid4()),
        SimpleNamespace(curriculum_topic_id=previous_topic_id, grade_level=7, grade_id=uuid.uuid4()),
    ]
    result_topics = MagicMock()
    result_topics.all.return_value = topic_rows
    # Question sampling query
    question_rows = [(uuid.uuid4(), current_topic_id, float(i % 5 + 1)) for i in range(10)]
    question_rows += [(uuid.uuid4(), previous_topic_id, float(i % 5 + 1)) for i in range(10)]
    result_questions = MagicMock()
    result_questions.all.return_value = question_rows

    db.execute = AsyncMock(
        side_effect=[result_class, result_existing, result_class_grade, result_topics, result_questions]
    )

    service = AssessmentService(db)
    body = DesignTier1DiagnosticRequest(topic_ids=[current_topic_id, previous_topic_id])

    # Should not raise
    assessment = await service.design_tier1_diagnostic(
        class_id=fake_class.id,
        school_id=school_id,
        teacher_id=teacher_id,
        body=body,
    )
    assert assessment.assessment_type == AssessmentType.DIAGNOSTIC


@pytest.mark.asyncio
async def test_design_tier1_when_topic_from_wrong_grade_then_raises_value_error() -> None:
    """Topics from grades other than current or current-1 must raise ValueError."""
    db = _make_db()
    school_id = uuid.uuid4()
    teacher_id = uuid.uuid4()
    fake_class = _make_class_with_grade(school_id=school_id, teacher_id=teacher_id, grade_level=8)
    wrong_grade_topic_id = uuid.uuid4()

    result_class = MagicMock()
    result_class.scalar_one_or_none.return_value = fake_class
    result_existing = MagicMock()
    result_existing.scalar_one_or_none.return_value = None
    result_class_grade = MagicMock()
    result_class_grade.scalar_one_or_none.return_value = 8
    topic_rows = [
        SimpleNamespace(curriculum_topic_id=wrong_grade_topic_id, grade_level=6, grade_id=uuid.uuid4()),
    ]
    result_topics = MagicMock()
    result_topics.all.return_value = topic_rows

    db.execute = AsyncMock(side_effect=[result_class, result_existing, result_class_grade, result_topics])

    service = AssessmentService(db)
    body = DesignTier1DiagnosticRequest(topic_ids=[wrong_grade_topic_id])

    with pytest.raises(ValueError, match=str(wrong_grade_topic_id)):
        await service.design_tier1_diagnostic(
            class_id=fake_class.id,
            school_id=school_id,
            teacher_id=teacher_id,
            body=body,
        )


@pytest.mark.asyncio
async def test_design_tier1_when_bank_has_2_per_difficulty_then_selects_2_per_difficulty_per_topic() -> None:
    """With 3 topics, 5 difficulty levels, 2 questions each: expect 3×5×2 = 30 bridge rows."""
    db = _make_db()
    school_id = uuid.uuid4()
    teacher_id = uuid.uuid4()
    fake_class = _make_class_with_grade(school_id=school_id, teacher_id=teacher_id, grade_level=8)

    topic_ids = [uuid.uuid4() for _ in range(3)]

    result_class = MagicMock()
    result_class.scalar_one_or_none.return_value = fake_class
    result_existing = MagicMock()
    result_existing.scalar_one_or_none.return_value = None
    result_class_grade = MagicMock()
    result_class_grade.scalar_one_or_none.return_value = 8
    topic_grade_rows = [
        SimpleNamespace(curriculum_topic_id=tid, grade_level=8, grade_id=uuid.uuid4()) for tid in topic_ids
    ]
    result_topics = MagicMock()
    result_topics.all.return_value = topic_grade_rows

    # 3 topics × 5 difficulties × 4 questions each = 60 questions in bank
    question_rows = []
    for tid in topic_ids:
        for diff in range(1, 6):
            for _ in range(4):
                question_rows.append((uuid.uuid4(), tid, float(diff)))
    result_questions = MagicMock()
    result_questions.all.return_value = question_rows

    db.execute = AsyncMock(
        side_effect=[result_class, result_existing, result_class_grade, result_topics, result_questions]
    )

    service = AssessmentService(db)
    body = DesignTier1DiagnosticRequest(
        topic_ids=topic_ids,
        questions_per_topic=2,
        minimum_difficulty=1,
        maximum_difficulty=5,
    )
    await service.design_tier1_diagnostic(
        class_id=fake_class.id,
        school_id=school_id,
        teacher_id=teacher_id,
        body=body,
    )

    # Bridge rows = all db.add calls after the first (assessment itself)
    add_calls = db.add.call_args_list
    bridge_calls = [c for c in add_calls if hasattr(c[0][0], "question_id")]
    # 3 topics × 5 levels × 2 per level = 30
    assert len(bridge_calls) == 30


@pytest.mark.asyncio
async def test_design_tier1_when_bank_short_on_difficulty_then_uses_available() -> None:
    """When a difficulty level has only 1 question, use 1 (no error)."""
    db = _make_db()
    school_id = uuid.uuid4()
    teacher_id = uuid.uuid4()
    fake_class = _make_class_with_grade(school_id=school_id, teacher_id=teacher_id, grade_level=8)
    topic_id = uuid.uuid4()

    result_class = MagicMock()
    result_class.scalar_one_or_none.return_value = fake_class
    result_existing = MagicMock()
    result_existing.scalar_one_or_none.return_value = None
    result_class_grade = MagicMock()
    result_class_grade.scalar_one_or_none.return_value = 8
    result_topics = MagicMock()
    result_topics.all.return_value = [
        SimpleNamespace(curriculum_topic_id=topic_id, grade_level=8, grade_id=uuid.uuid4())
    ]
    # Difficulty 3 has only 1 question; all others have 2
    question_rows = []
    for diff in range(1, 6):
        count = 1 if diff == 3 else 2
        for _ in range(count):
            question_rows.append((uuid.uuid4(), topic_id, float(diff)))
    result_questions = MagicMock()
    result_questions.all.return_value = question_rows

    db.execute = AsyncMock(
        side_effect=[result_class, result_existing, result_class_grade, result_topics, result_questions]
    )

    service = AssessmentService(db)
    body = DesignTier1DiagnosticRequest(topic_ids=[topic_id], questions_per_topic=2)

    # Should not raise InsufficientQuestionsError — uses what's available
    assessment = await service.design_tier1_diagnostic(
        class_id=fake_class.id,
        school_id=school_id,
        teacher_id=teacher_id,
        body=body,
    )
    assert assessment is not None


# ── check_topic_availability tests ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_check_topic_availability_when_topic_has_enough_then_fulfillable_true() -> None:
    """Topic with 10 questions at each difficulty → fulfillable when questions_per_topic=2."""
    db = _make_db()
    topic_id = uuid.uuid4()
    grade_id = uuid.uuid4()

    # Row: (curriculum_topic_id, topic_name, grade_level, grade_id, difficulty, count)
    rows = [
        SimpleNamespace(
            curriculum_topic_id=topic_id, topic_name="Algebra", grade_level=8, grade_id=grade_id, difficulty=d, count=10
        )
        for d in range(1, 6)
    ]
    result = MagicMock()
    result.all.return_value = rows
    db.execute = AsyncMock(return_value=result)

    service = AssessmentService(db)
    availability = await service.check_topic_availability(
        class_id=uuid.uuid4(),
        school_id=uuid.uuid4(),
        topic_ids=[topic_id],
        questions_per_topic=2,
        minimum_difficulty=1,
        maximum_difficulty=5,
        question_types=["MCQ", "TRUE_FALSE"],
    )

    assert len(availability) == 1
    assert availability[0].curriculum_topic_id == topic_id
    assert availability[0].fulfillable is True
    assert availability[0].available_questions >= 2


@pytest.mark.asyncio
async def test_check_topic_availability_when_topic_short_then_fulfillable_false() -> None:
    """Topic with only 1 question total → not fulfillable when questions_per_topic=5."""
    db = _make_db()
    topic_id = uuid.uuid4()
    grade_id = uuid.uuid4()

    rows = [
        SimpleNamespace(
            curriculum_topic_id=topic_id, topic_name="Geometry", grade_level=8, grade_id=grade_id, difficulty=1, count=1
        )
    ]
    result = MagicMock()
    result.all.return_value = rows
    db.execute = AsyncMock(return_value=result)

    service = AssessmentService(db)
    availability = await service.check_topic_availability(
        class_id=uuid.uuid4(),
        school_id=uuid.uuid4(),
        topic_ids=[topic_id],
        questions_per_topic=5,
        minimum_difficulty=1,
        maximum_difficulty=5,
        question_types=["MCQ", "TRUE_FALSE"],
    )

    assert availability[0].fulfillable is False
    assert availability[0].available_questions == 1


@pytest.mark.asyncio
async def test_create_assessment_when_called_then_no_config_attribute_exists() -> None:
    """create_assessment must use typed columns — Assessment must not have a config attr."""
    from app.models.assessment import Assessment

    assert not hasattr(Assessment, "config"), "Assessment.config should not exist after T1 migration"
