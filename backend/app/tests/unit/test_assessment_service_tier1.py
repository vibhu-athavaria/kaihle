"""Unit tests for AssessmentService.design_tier1_diagnostic.

Tests: class ownership check, existing DRAFT replacement, question sampling,
InsufficientQuestionsError, response shape.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.assessment import AssessmentStatus, AssessmentType
from app.schemas.assessments import DesignTier1DiagnosticRequest
from app.services.assessment_service import (
    AssessmentService,
    InsufficientQuestionsError,
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


@pytest.mark.asyncio
async def test_design_tier1_when_insufficient_questions_then_raises_insufficient_error() -> None:
    db = _make_db()
    school_id = uuid.uuid4()
    teacher_id = uuid.uuid4()
    fake_class = _make_class(school_id=school_id, teacher_id=teacher_id)

    # result1: class found
    result1 = MagicMock()
    result1.scalar_one_or_none.return_value = fake_class
    # result2: no existing diagnostic
    result2 = MagicMock()
    result2.scalar_one_or_none.return_value = None
    # result3: question rows — only 3 questions, but we need 20
    q1 = (uuid.uuid4(), uuid.uuid4(), 2.0)
    q2 = (uuid.uuid4(), uuid.uuid4(), 3.0)
    q3 = (uuid.uuid4(), uuid.uuid4(), 1.0)
    result3 = MagicMock()
    result3.all.return_value = [q1, q2, q3]
    db.execute = AsyncMock(side_effect=[result1, result2, result3])

    service = AssessmentService(db)
    body = DesignTier1DiagnosticRequest(topic_ids=[uuid.uuid4()], question_count=20)

    with pytest.raises(InsufficientQuestionsError) as exc_info:
        await service.design_tier1_diagnostic(
            class_id=fake_class.id,
            school_id=school_id,
            teacher_id=teacher_id,
            body=body,
        )
    assert exc_info.value.available == 3
    assert exc_info.value.requested == 20


@pytest.mark.asyncio
async def test_design_tier1_when_valid_then_creates_draft_assessment() -> None:
    db = _make_db()
    school_id = uuid.uuid4()
    teacher_id = uuid.uuid4()
    topic_id = uuid.uuid4()
    fake_class = _make_class(school_id=school_id, teacher_id=teacher_id)

    # result1: class found
    result1 = MagicMock()
    result1.scalar_one_or_none.return_value = fake_class
    # result2: no existing diagnostic
    result2 = MagicMock()
    result2.scalar_one_or_none.return_value = None
    # result3: 25 question rows
    question_rows = [(uuid.uuid4(), topic_id, float(i % 5 + 1)) for i in range(25)]
    result3 = MagicMock()
    result3.all.return_value = question_rows
    db.execute = AsyncMock(side_effect=[result1, result2, result3])

    service = AssessmentService(db)
    body = DesignTier1DiagnosticRequest(topic_ids=[topic_id], question_count=10)
    assessment = await service.design_tier1_diagnostic(
        class_id=fake_class.id,
        school_id=school_id,
        teacher_id=teacher_id,
        body=body,
    )

    assert assessment.status == AssessmentStatus.DRAFT
    assert assessment.assessment_type == AssessmentType.DIAGNOSTIC
    assert assessment.is_system_generated is False
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

    # result for the DELETE bridge rows execute
    delete_result = MagicMock()

    question_rows = [(uuid.uuid4(), topic_id, float(i % 5 + 1)) for i in range(25)]
    result3 = MagicMock()
    result3.all.return_value = question_rows

    db.execute = AsyncMock(side_effect=[result1, result2, delete_result, result3])

    service = AssessmentService(db)
    body = DesignTier1DiagnosticRequest(topic_ids=[topic_id], question_count=10)

    with patch(
        "app.services.assessment_service.delete",
        return_value=MagicMock(),
    ):
        assessment = await service.design_tier1_diagnostic(
            class_id=fake_class.id,
            school_id=school_id,
            teacher_id=teacher_id,
            body=body,
        )

    db.delete.assert_called_once_with(existing_assessment)
    assert assessment.is_system_generated is False
