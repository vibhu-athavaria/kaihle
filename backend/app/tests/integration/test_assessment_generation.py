"""Integration tests for AssessmentService Tier 2 (teacher-created assessments).

Uses a real test database session — no mocking of persistence layer.

Naming convention: test_<what>_when_<condition>_then_<expected>
"""

import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import (
    Assessment,
    AssessmentSelectedQuestion,
    AssessmentStatus,
    AssessmentType,
)
from app.models.curriculum import (
    Curriculum,
    CurriculumTopic,
    Grade,
    QuestionBank,
    Subject,
    Subtopic,
    Topic,
)
from app.models.school import Class, School
from app.models.user import User, UserRole
from app.schemas.assessments import AssessmentCreateRequest
from app.services.assessment_service import (
    AssessmentService,
    InsufficientQuestionsError,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_curriculum_setup(
    db: AsyncSession,
    school: School,
) -> tuple[Subject, Grade, Curriculum, list[CurriculumTopic], list[Subtopic], User, Class]:
    """Create a minimal curriculum setup and a class for tests."""
    subject = Subject(
        id=uuid.uuid4(), name=f"Maths-{uuid.uuid4().hex[:4]}", code=f"M{uuid.uuid4().hex[:3]}", is_active=True
    )
    grade = Grade(id=uuid.uuid4(), name="Grade 9", level=9, is_active=True)
    curriculum = Curriculum(
        id=uuid.uuid4(), name=f"Curr-{uuid.uuid4().hex[:4]}", code=f"C{uuid.uuid4().hex[:4]}", is_active=True
    )
    topic1 = Topic(id=uuid.uuid4(), name="Algebra", is_active=True)
    topic2 = Topic(id=uuid.uuid4(), name="Geometry", is_active=True)
    db.add_all([subject, grade, curriculum, topic1, topic2])
    await db.flush()

    ct1 = CurriculumTopic(
        id=uuid.uuid4(),
        curriculum_id=curriculum.id,
        subject_id=subject.id,
        grade_id=grade.id,
        topic_id=topic1.id,
        is_active=True,
    )
    ct2 = CurriculumTopic(
        id=uuid.uuid4(),
        curriculum_id=curriculum.id,
        subject_id=subject.id,
        grade_id=grade.id,
        topic_id=topic2.id,
        is_active=True,
    )
    db.add_all([ct1, ct2])
    await db.flush()

    st1 = Subtopic(
        id=uuid.uuid4(),
        curriculum_topic_id=ct1.id,
        name="Linear Equations",
        learning_objective="Solve linear equations",
        is_active=True,
    )
    st2 = Subtopic(
        id=uuid.uuid4(),
        curriculum_topic_id=ct2.id,
        name="Triangles",
        learning_objective="Properties of triangles",
        is_active=True,
    )
    db.add_all([st1, st2])
    await db.flush()

    teacher = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"t-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Test",
        last_name="Teacher",
        role=UserRole.TEACHER,
        is_active=True,
    )
    db.add(teacher)
    await db.flush()

    class_ = Class(
        id=uuid.uuid4(),
        school_id=school.id,
        grade_id=grade.id,
        subject_id=subject.id,
        curriculum_id=curriculum.id,
        teacher_id=teacher.id,
        name="Maths 9A",
        academic_year="2025-2026",
        is_active=True,
    )
    db.add(class_)
    await db.flush()

    return subject, grade, curriculum, [ct1, ct2], [st1, st2], teacher, class_


async def _add_questions(
    db: AsyncSession,
    subtopic: Subtopic,
    count: int,
    difficulty: float = 2.0,
) -> list[QuestionBank]:
    questions = []
    for i in range(count):
        q = QuestionBank(
            id=uuid.uuid4(),
            subtopic_id=subtopic.id,
            question_text=f"Question {i + 1}",
            question_type="MCQ",
            options=[
                {"key": "A", "text": "Option A"},
                {"key": "B", "text": "Option B"},
                {"key": "C", "text": "Option C"},
                {"key": "D", "text": "Option D"},
            ],
            correct_answer="A",
            difficulty_level=difficulty,
            canonical_form=f"q-{uuid.uuid4().hex}",
            problem_signature={},
            is_active=True,
        )
        questions.append(q)
    db.add_all(questions)
    await db.flush()
    return questions


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_creation_flow_when_valid_then_assessment_and_bridge_rows_in_db(
    db_session: AsyncSession, test_school: School
) -> None:
    """Create an assessment end-to-end and verify DB state."""
    _, _, _, curriculum_topics, subtopics, teacher, class_ = await _create_curriculum_setup(db_session, test_school)

    # Add 10 questions across 2 subtopics
    await _add_questions(db_session, subtopics[0], 5)
    await _add_questions(db_session, subtopics[1], 5)

    service = AssessmentService(db_session)
    body = AssessmentCreateRequest(
        title="Test Progress Check",
        topic_ids=[],
        questions_per_topic=3,
        assessment_type=AssessmentType.PROGRESS_CHECK,
        difficulty_min=1.0,
        difficulty_max=5.0,
    )

    assessment = await service.create_assessment(test_school.id, teacher.id, class_.id, body)
    await db_session.commit()

    # Verify Assessment row in DB
    stored = await db_session.get(Assessment, assessment.id)
    assert stored is not None
    assert stored.status == AssessmentStatus.DRAFT
    assert stored.school_id == test_school.id
    assert stored.question_count == 3
    assert stored.created_by == teacher.id

    # Verify bridge rows
    bridge_count = (
        await db_session.execute(
            select(func.count(AssessmentSelectedQuestion.question_id)).where(
                AssessmentSelectedQuestion.assessment_id == assessment.id
            )
        )
    ).scalar()
    assert bridge_count == 3


@pytest.mark.asyncio
async def test_create_and_publish_flow_then_status_transitions_correctly(
    db_session: AsyncSession, test_school: School
) -> None:
    """Create then publish an assessment — verify status transitions in DB."""
    _, _, _, _, subtopics, teacher, class_ = await _create_curriculum_setup(db_session, test_school)
    await _add_questions(db_session, subtopics[0], 5)

    service = AssessmentService(db_session)
    body = AssessmentCreateRequest(
        title="Quiz 1",
        topic_ids=[],
        questions_per_topic=3,
        assessment_type=AssessmentType.PROGRESS_CHECK,
    )

    assessment = await service.create_assessment(test_school.id, teacher.id, class_.id, body)
    await db_session.flush()

    await service.publish_assessment(assessment.id, test_school.id, teacher.id, deadline=None)
    await db_session.commit()

    stored = await db_session.get(Assessment, assessment.id)
    assert stored is not None
    assert stored.status == AssessmentStatus.ACTIVE
    assert stored.published_at is not None


@pytest.mark.asyncio
async def test_create_when_topic_filter_then_only_matching_topics_sampled(
    db_session: AsyncSession, test_school: School
) -> None:
    """When topic_ids filter is specified, only questions from those topics are sampled."""
    _, _, _, curriculum_topics, subtopics, teacher, class_ = await _create_curriculum_setup(db_session, test_school)

    # 5 questions for topic1, 5 questions for topic2
    await _add_questions(db_session, subtopics[0], 5)
    await _add_questions(db_session, subtopics[1], 5)

    service = AssessmentService(db_session)
    # Filter to only curriculum_topic[0]
    body = AssessmentCreateRequest(
        title="Algebra Only",
        topic_ids=[curriculum_topics[0].id],
        questions_per_topic=3,
        assessment_type=AssessmentType.TOPIC_SPECIFIC,
    )

    assessment = await service.create_assessment(test_school.id, teacher.id, class_.id, body)
    await db_session.flush()

    # Load bridge rows → check all questions come from subtopic[0] (algebra)
    subtopic0_ids = (
        (await db_session.execute(select(QuestionBank.id).where(QuestionBank.subtopic_id == subtopics[0].id)))
        .scalars()
        .all()
    )

    bridge_q_ids = (
        (
            await db_session.execute(
                select(AssessmentSelectedQuestion.question_id).where(
                    AssessmentSelectedQuestion.assessment_id == assessment.id
                )
            )
        )
        .scalars()
        .all()
    )

    assert all(qid in subtopic0_ids for qid in bridge_q_ids)


@pytest.mark.asyncio
async def test_create_when_insufficient_questions_then_raises_and_no_row_in_db(
    db_session: AsyncSession, test_school: School
) -> None:
    """InsufficientQuestionsError leaves no Assessment row in DB."""
    _, _, _, _, subtopics, teacher, class_ = await _create_curriculum_setup(db_session, test_school)
    await _add_questions(db_session, subtopics[0], 2)  # only 2 questions

    service = AssessmentService(db_session)
    body = AssessmentCreateRequest(
        title="Too Many",
        topic_ids=[],
        questions_per_topic=10,  # request 10, only 2 available
        assessment_type=AssessmentType.PROGRESS_CHECK,
    )

    with pytest.raises(InsufficientQuestionsError) as exc_info:
        await service.create_assessment(test_school.id, teacher.id, class_.id, body)

    assert exc_info.value.available == 2
    assert exc_info.value.requested == 10

    # No Assessment row should be in DB
    count = (
        await db_session.execute(select(func.count(Assessment.id)).where(Assessment.class_id == class_.id))
    ).scalar()
    assert count == 0


@pytest.mark.asyncio
async def test_publish_and_close_full_lifecycle_in_db(db_session: AsyncSession, test_school: School) -> None:
    """Full lifecycle: DRAFT → ACTIVE → CLOSED."""
    _, _, _, _, subtopics, teacher, class_ = await _create_curriculum_setup(db_session, test_school)
    await _add_questions(db_session, subtopics[0], 5)

    service = AssessmentService(db_session)
    body = AssessmentCreateRequest(
        title="Lifecycle Test",
        topic_ids=[],
        questions_per_topic=3,
        assessment_type=AssessmentType.PROGRESS_CHECK,
    )

    assessment = await service.create_assessment(test_school.id, teacher.id, class_.id, body)
    await db_session.flush()

    await service.publish_assessment(assessment.id, test_school.id, teacher.id, deadline=None)
    assert assessment.status == AssessmentStatus.ACTIVE

    await service.close_assessment(assessment.id, test_school.id, teacher.id)
    assert assessment.status == AssessmentStatus.CLOSED

    await db_session.commit()
    stored = await db_session.get(Assessment, assessment.id)
    assert stored is not None
    assert stored.status == AssessmentStatus.CLOSED
