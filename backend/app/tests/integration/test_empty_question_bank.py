"""Integration tests for empty question bank skip behavior (M0-9-T6 Fix 4).

Tests verify that when question_bank is empty:
- create_class_diagnostic raises QuestionBankEmptyError
- No Assessment row is created
- The service correctly detects empty question bank

Run with: pytest backend/app/tests/integration/test_empty_question_bank.py -v
"""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import Assessment
from app.models.curriculum import (
    Curriculum,
    CurriculumSubject,
    CurriculumTopic,
    Grade,
    Subject,
    Subtopic,
    Topic,
)
from app.models.school import Class, School
from app.models.user import User
from app.services.assessment_service import AssessmentService, QuestionBankEmptyError


@pytest.fixture
async def empty_class(
    db_session: AsyncSession,
    test_school: School,
    test_curriculum: Curriculum,
    test_grade: Grade,
    test_subject: Subject,
    test_teacher: User,
) -> Class:
    """Create a class with curriculum setup but NO questions in question_bank.

    This simulates the state before import_questions.py has been run.
    """
    # Set up curriculum structure but no questions
    cs = CurriculumSubject(
        curriculum_id=test_curriculum.id,
        subject_id=test_subject.id,
        is_core=True,
    )
    db_session.add(cs)

    topic = Topic(id=uuid.uuid4(), name="Test Topic", is_active=True)
    db_session.add(topic)
    await db_session.flush()

    ct = CurriculumTopic(
        id=uuid.uuid4(),
        curriculum_id=test_curriculum.id,
        subject_id=test_subject.id,
        grade_id=test_grade.id,
        topic_id=topic.id,
        is_required=True,
        is_active=True,
    )
    db_session.add(ct)
    await db_session.flush()

    subtopic = Subtopic(
        id=uuid.uuid4(),
        curriculum_topic_id=ct.id,
        name="Test Subtopic",
        learning_objective="Test objective",
        is_active=True,
    )
    db_session.add(subtopic)
    await db_session.flush()

    # Create class - NO questions added to question_bank
    class_ = Class(
        id=uuid.uuid4(),
        school_id=test_school.id,
        grade_id=test_grade.id,
        subject_id=test_subject.id,
        curriculum_id=test_curriculum.id,
        teacher_id=test_teacher.id,
        name="Empty Question Bank Class",
        academic_year="2025-2026",
        is_active=True,
    )
    db_session.add(class_)
    await db_session.commit()
    return class_


@pytest.mark.asyncio
async def test_create_class_diagnostic_when_question_bank_empty_then_raises_error(
    db_session: AsyncSession,
    empty_class: Class,
) -> None:
    """Test that create_class_diagnostic raises QuestionBankEmptyError when no questions exist."""
    service = AssessmentService(db_session)

    with pytest.raises(QuestionBankEmptyError) as exc_info:
        await service.create_class_diagnostic(empty_class.id)

    assert "No questions in question_bank" in str(exc_info.value)
    assert "Run import_questions.py first" in str(exc_info.value)


@pytest.mark.asyncio
async def test_create_class_diagnostic_when_question_bank_empty_then_no_assessment_created(
    db_session: AsyncSession,
    empty_class: Class,
) -> None:
    """Test that no Assessment row is created when question bank is empty."""
    service = AssessmentService(db_session)

    # Verify no assessment exists initially
    result = await db_session.execute(select(Assessment).where(Assessment.class_id == empty_class.id))
    initial_assessments = result.scalars().all()
    assert len(initial_assessments) == 0

    # Try to create diagnostic - should fail
    try:
        await service.create_class_diagnostic(empty_class.id)
    except QuestionBankEmptyError:
        pass  # Expected

    # Verify no assessment was created
    result = await db_session.execute(select(Assessment).where(Assessment.class_id == empty_class.id))
    final_assessments = result.scalars().all()
    assert len(final_assessments) == 0
