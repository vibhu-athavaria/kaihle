"""Integration tests for Tier 1 diagnostic trigger (M0-6-T2).

Tests exercise the real DB through:
- AssessmentService.create_class_diagnostic() — assessment created at class creation
- AssessmentService.create_diagnostic_attempt() — student attempt at enrollment
"""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import (
    Assessment,
    AssessmentSelectedQuestion,
    AssessmentStatus,
    AssessmentType,
    AttemptStatus,
    StudentAttempt,
)
from app.models.curriculum import (
    Curriculum,
    CurriculumSubject,
    CurriculumTopic,
    Grade,
    QuestionBank,
    Subject,
    Subtopic,
    Topic,
)
from app.models.school import Class, School
from app.models.user import StudentProfile, User, UserRole
from app.services.assessment_service import MAX_DIAGNOSTIC_QUESTIONS_PER_ATTEMPT, AssessmentService

# ── Helpers ──────────────────────────────────────────────────────────────


async def _create_question(db: AsyncSession, subtopic_id: uuid.UUID) -> QuestionBank:
    """Helper to create a question in the bank."""
    q = QuestionBank(
        id=uuid.uuid4(),
        subtopic_id=subtopic_id,
        question_text="What is 2+2?",
        question_type="MCQ",
        options=[{"key": "A", "text": "4"}, {"key": "B", "text": "3"}],
        correct_answer="A",
        canonical_form="What is 2+2?",
        problem_signature={},
        is_active=True,
    )
    db.add(q)
    await db.flush()
    return q


async def _setup_full_class(
    db: AsyncSession,
    school: School,
    curriculum: Curriculum,
    grade: Grade,
    subject: Subject,
    teacher: User,
    num_topics: int = 3,
    questions_per_topic: int = 3,
) -> tuple[Class, list[CurriculumTopic], list[QuestionBank]]:
    """Set up a class with curriculum topics, subtopics, and questions."""
    cs = CurriculumSubject(
        curriculum_id=curriculum.id,
        subject_id=subject.id,
        is_core=True,
    )
    db.add(cs)

    class_ = Class(
        id=uuid.uuid4(),
        school_id=school.id,
        grade_id=grade.id,
        subject_id=subject.id,
        curriculum_id=curriculum.id,
        teacher_id=teacher.id,
        name="Test Integration Class",
        academic_year="2026",
        is_active=True,
    )
    db.add(class_)
    await db.flush()

    topics = []
    questions = []
    for i in range(num_topics):
        topic = Topic(id=uuid.uuid4(), name=f"Topic {i + 1}", is_active=True)
        db.add(topic)
        await db.flush()

        ct = CurriculumTopic(
            id=uuid.uuid4(),
            curriculum_id=curriculum.id,
            subject_id=subject.id,
            grade_id=grade.id,
            topic_id=topic.id,
            is_required=True,
            is_active=True,
        )
        db.add(ct)
        await db.flush()
        topics.append(ct)

        subtopic = Subtopic(
            id=uuid.uuid4(),
            curriculum_topic_id=ct.id,
            name=f"Subtopic {i + 1}",
            learning_objective="Learn something",
            is_active=True,
        )
        db.add(subtopic)
        await db.flush()

        for _ in range(questions_per_topic):
            q = await _create_question(db, subtopic.id)
            questions.append(q)

    await db.commit()
    return class_, topics, questions


async def _create_student_with_profile(db: AsyncSession, school: School) -> tuple[User, StudentProfile]:
    """Create a student user and student profile."""
    student = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"student-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Test",
        last_name="Student",
        role=UserRole.STUDENT,
    )
    db.add(student)
    await db.flush()

    profile = StudentProfile(
        id=uuid.uuid4(),
        user_id=student.id,
        # v2.1: onboarding_diagnostic_status moved to class_enrollments
    )
    db.add(profile)
    await db.commit()
    return student, profile


# ── create_class_diagnostic tests ────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_class_diagnostic_when_new_class_then_assessment_created(
    db_session: AsyncSession,
    test_school: School,
    test_curriculum: Curriculum,
    test_grade: Grade,
    test_subject: Subject,
    test_teacher: User,
) -> None:
    """Creates an ACTIVE is_system_generated assessment with question pool."""
    class_, topics, questions = await _setup_full_class(
        db_session, test_school, test_curriculum, test_grade, test_subject, test_teacher
    )

    service = AssessmentService(db_session)
    assessment = await service.create_class_diagnostic(class_.id)
    await db_session.commit()

    assert assessment.is_system_generated is True
    assert assessment.status == AssessmentStatus.ACTIVE
    assert assessment.assessment_type == AssessmentType.DIAGNOSTIC
    assert assessment.created_by is None
    assert assessment.curriculum_topic_id is None
    assert assessment.class_id == class_.id
    assert assessment.config["max_questions_per_attempt"] == MAX_DIAGNOSTIC_QUESTIONS_PER_ATTEMPT


@pytest.mark.asyncio
async def test_create_class_diagnostic_when_called_twice_then_no_duplicate(
    db_session: AsyncSession,
    test_school: School,
    test_curriculum: Curriculum,
    test_grade: Grade,
    test_subject: Subject,
    test_teacher: User,
) -> None:
    """Re-calling for same class returns existing assessment, no duplicate."""
    class_, _, _ = await _setup_full_class(
        db_session, test_school, test_curriculum, test_grade, test_subject, test_teacher
    )

    service = AssessmentService(db_session)
    first = await service.create_class_diagnostic(class_.id)
    await db_session.commit()
    second = await service.create_class_diagnostic(class_.id)

    assert first.id == second.id

    result = await db_session.execute(
        select(Assessment).where(
            Assessment.class_id == class_.id,
            Assessment.is_system_generated.is_(True),
        )
    )
    assert len(result.scalars().all()) == 1


@pytest.mark.asyncio
async def test_create_class_diagnostic_when_3_topics_then_questions_span_all(
    db_session: AsyncSession,
    test_school: School,
    test_curriculum: Curriculum,
    test_grade: Grade,
    test_subject: Subject,
    test_teacher: User,
) -> None:
    """Question pool spans all curriculum_topics for the subject+grade."""
    class_, topics, questions = await _setup_full_class(
        db_session,
        test_school,
        test_curriculum,
        test_grade,
        test_subject,
        test_teacher,
        num_topics=3,
        questions_per_topic=2,
    )

    service = AssessmentService(db_session)
    assessment = await service.create_class_diagnostic(class_.id)
    await db_session.commit()

    result = await db_session.execute(
        select(AssessmentSelectedQuestion).where(AssessmentSelectedQuestion.assessment_id == assessment.id)
    )
    selected = result.scalars().all()
    # 3 topics × 2 questions = 6 (all used since < pool size)
    assert len(selected) == 6


@pytest.mark.asyncio
async def test_create_class_diagnostic_when_few_questions_then_uses_all(
    db_session: AsyncSession,
    test_school: School,
    test_curriculum: Curriculum,
    test_grade: Grade,
    test_subject: Subject,
    test_teacher: User,
) -> None:
    """Uses all available questions when bank has fewer than pool size."""
    class_, _, _ = await _setup_full_class(
        db_session,
        test_school,
        test_curriculum,
        test_grade,
        test_subject,
        test_teacher,
        num_topics=1,
        questions_per_topic=5,
    )

    service = AssessmentService(db_session)
    assessment = await service.create_class_diagnostic(class_.id)
    await db_session.commit()

    result = await db_session.execute(
        select(AssessmentSelectedQuestion).where(AssessmentSelectedQuestion.assessment_id == assessment.id)
    )
    assert len(result.scalars().all()) == 5


# ── create_diagnostic_attempt tests ──────────────────────────────────────


@pytest.mark.asyncio
async def test_create_attempt_when_enrolled_then_attempt_created(
    db_session: AsyncSession,
    test_school: School,
    test_curriculum: Curriculum,
    test_grade: Grade,
    test_subject: Subject,
    test_teacher: User,
) -> None:
    """Creates a NOT_STARTED attempt linked to the class diagnostic."""
    class_, _, _ = await _setup_full_class(
        db_session, test_school, test_curriculum, test_grade, test_subject, test_teacher
    )
    student, profile = await _create_student_with_profile(db_session, test_school)

    service = AssessmentService(db_session)
    assessment = await service.create_class_diagnostic(class_.id)
    await db_session.commit()

    attempt = await service.create_diagnostic_attempt(student.id, class_.id)
    await db_session.commit()

    assert attempt.status == AttemptStatus.NOT_STARTED
    assert attempt.assessment_id == assessment.id
    assert attempt.student_id == student.id


@pytest.mark.asyncio
async def test_create_attempt_when_called_twice_then_returns_existing(
    db_session: AsyncSession,
    test_school: School,
    test_curriculum: Curriculum,
    test_grade: Grade,
    test_subject: Subject,
    test_teacher: User,
) -> None:
    """Re-enrolling same student returns existing attempt, no duplicate."""
    class_, _, _ = await _setup_full_class(
        db_session, test_school, test_curriculum, test_grade, test_subject, test_teacher
    )
    student, _ = await _create_student_with_profile(db_session, test_school)

    service = AssessmentService(db_session)
    await service.create_class_diagnostic(class_.id)
    await db_session.commit()

    first = await service.create_diagnostic_attempt(student.id, class_.id)
    await db_session.commit()
    second = await service.create_diagnostic_attempt(student.id, class_.id)

    assert first.id == second.id

    result = await db_session.execute(
        select(StudentAttempt).where(
            StudentAttempt.student_id == student.id,
        )
    )
    assert len(result.scalars().all()) == 1


@pytest.mark.asyncio
async def test_create_attempt_when_multiple_students_then_separate_attempts(
    db_session: AsyncSession,
    test_school: School,
    test_curriculum: Curriculum,
    test_grade: Grade,
    test_subject: Subject,
    test_teacher: User,
) -> None:
    """Multiple students get separate attempts for the same class diagnostic."""
    class_, _, _ = await _setup_full_class(
        db_session, test_school, test_curriculum, test_grade, test_subject, test_teacher
    )
    student_a, _ = await _create_student_with_profile(db_session, test_school)
    student_b, _ = await _create_student_with_profile(db_session, test_school)

    service = AssessmentService(db_session)
    assessment = await service.create_class_diagnostic(class_.id)
    await db_session.commit()

    attempt_a = await service.create_diagnostic_attempt(student_a.id, class_.id)
    attempt_b = await service.create_diagnostic_attempt(student_b.id, class_.id)
    await db_session.commit()

    assert attempt_a.id != attempt_b.id
    assert attempt_a.assessment_id == assessment.id
    assert attempt_b.assessment_id == assessment.id


@pytest.mark.asyncio
async def test_create_attempt_when_no_diagnostic_exists_then_raises(
    db_session: AsyncSession,
    test_school: School,
    test_curriculum: Curriculum,
    test_grade: Grade,
    test_subject: Subject,
    test_teacher: User,
) -> None:
    """Raises ValueError if diagnostic assessment was not created for the class."""
    class_, _, _ = await _setup_full_class(
        db_session, test_school, test_curriculum, test_grade, test_subject, test_teacher
    )
    student, _ = await _create_student_with_profile(db_session, test_school)

    service = AssessmentService(db_session)
    # Deliberately skip create_class_diagnostic

    with pytest.raises(ValueError, match="No system-generated diagnostic found"):
        await service.create_diagnostic_attempt(student.id, class_.id)
