"""Integration tests for Tier 1 diagnostic trigger (M0-6-T2).

Tests exercise the real DB through AssessmentService.create_system_diagnostic().
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
from app.models.user import OnboardingStatus, StudentProfile, User, UserRole
from app.services.assessment_service import AssessmentService


async def _create_question(
    db: AsyncSession,
    subtopic_id: uuid.UUID,
) -> QuestionBank:
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


async def _create_curriculum_topic(
    db: AsyncSession,
    curriculum_id: uuid.UUID,
    subject_id: uuid.UUID,
    grade_id: uuid.UUID,
    topic_id: uuid.UUID,
) -> CurriculumTopic:
    """Helper to create a curriculum topic binding."""
    ct = CurriculumTopic(
        id=uuid.uuid4(),
        curriculum_id=curriculum_id,
        subject_id=subject_id,
        grade_id=grade_id,
        topic_id=topic_id,
        is_required=True,
        is_active=True,
    )
    db.add(ct)
    await db.flush()
    return ct


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
    """Set up a class with curriculum topics and questions."""
    # Link subject to curriculum
    cs = CurriculumSubject(
        curriculum_id=curriculum.id,
        subject_id=subject.id,
        is_core=True,
    )
    db.add(cs)

    # Create class
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

    # Create topics, curriculum_topics, subtopics and questions
    topics = []
    questions = []
    for i in range(num_topics):
        topic = Topic(
            id=uuid.uuid4(),
            name=f"Topic {i + 1}",
            is_active=True,
        )
        db.add(topic)
        await db.flush()

        ct = await _create_curriculum_topic(db, curriculum.id, subject.id, grade.id, topic.id)
        topics.append(ct)

        # Create subtopic
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
        onboarding_diagnostic_status=OnboardingStatus.PENDING,
    )
    db.add(profile)
    await db.commit()
    return student, profile


@pytest.mark.asyncio
async def test_trigger_when_class_has_subject_then_assessment_created(
    db_session: AsyncSession,
    test_school: School,
    test_curriculum: Curriculum,
    test_grade: Grade,
    test_subject: Subject,
    test_teacher: User,
) -> None:
    """Creates an ACTIVE is_system_generated assessment for the class subject."""
    class_, topics, questions = await _setup_full_class(
        db_session, test_school, test_curriculum, test_grade, test_subject, test_teacher
    )
    student, profile = await _create_student_with_profile(db_session, test_school)

    service = AssessmentService(db_session)
    created = await service.create_system_diagnostic(student.id, class_.id)
    await db_session.commit()

    assert len(created) == 1
    assessment = created[0]
    assert assessment.is_system_generated is True
    assert assessment.status == AssessmentStatus.ACTIVE
    assert assessment.assessment_type == AssessmentType.DIAGNOSTIC
    assert assessment.created_by is None
    assert assessment.curriculum_topic_id is None
    assert assessment.class_id == class_.id


@pytest.mark.asyncio
async def test_trigger_when_already_triggered_then_returns_existing_no_duplicates(
    db_session: AsyncSession,
    test_school: School,
    test_curriculum: Curriculum,
    test_grade: Grade,
    test_subject: Subject,
    test_teacher: User,
) -> None:
    """Re-triggering for same student+class returns existing assessment without duplicating."""
    class_, topics, questions = await _setup_full_class(
        db_session, test_school, test_curriculum, test_grade, test_subject, test_teacher
    )
    student, profile = await _create_student_with_profile(db_session, test_school)

    service = AssessmentService(db_session)

    # First call — creates new
    result_first = await service.create_system_diagnostic(student.id, class_.id)
    await db_session.commit()

    # Second call — returns existing
    result_second = await service.create_system_diagnostic(student.id, class_.id)
    await db_session.commit()

    assert len(result_first) == 1
    assert len(result_second) == 1
    assert result_first[0].id == result_second[0].id

    # Verify only 1 assessment in DB for this class
    result = await db_session.execute(
        select(Assessment).where(
            Assessment.class_id == class_.id,
            Assessment.is_system_generated.is_(True),
        )
    )
    assessments = result.scalars().all()
    assert len(assessments) == 1


@pytest.mark.asyncio
async def test_trigger_when_created_then_student_attempt_exists(
    db_session: AsyncSession,
    test_school: School,
    test_curriculum: Curriculum,
    test_grade: Grade,
    test_subject: Subject,
    test_teacher: User,
) -> None:
    """Each assessment has a matching student_attempts row with status NOT_STARTED."""
    class_, topics, questions = await _setup_full_class(
        db_session, test_school, test_curriculum, test_grade, test_subject, test_teacher
    )
    student, profile = await _create_student_with_profile(db_session, test_school)

    service = AssessmentService(db_session)
    created = await service.create_system_diagnostic(student.id, class_.id)
    await db_session.commit()

    assert len(created) == 1
    assessment = created[0]

    result = await db_session.execute(
        select(StudentAttempt).where(
            StudentAttempt.assessment_id == assessment.id,
            StudentAttempt.student_id == student.id,
        )
    )
    attempt = result.scalar_one_or_none()
    assert attempt is not None
    assert attempt.status == AttemptStatus.NOT_STARTED


@pytest.mark.asyncio
async def test_trigger_when_class_has_subject_then_questions_span_all_topics(
    db_session: AsyncSession,
    test_school: School,
    test_curriculum: Curriculum,
    test_grade: Grade,
    test_subject: Subject,
    test_teacher: User,
) -> None:
    """Questions span all curriculum_topics for the subject+grade."""
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
    student, profile = await _create_student_with_profile(db_session, test_school)

    service = AssessmentService(db_session)
    created = await service.create_system_diagnostic(student.id, class_.id)
    await db_session.commit()

    assessment = created[0]

    # Get selected questions
    result = await db_session.execute(
        select(AssessmentSelectedQuestion).where(AssessmentSelectedQuestion.assessment_id == assessment.id)
    )
    selected = result.scalars().all()

    # 3 topics × 2 questions each = 6 total (all used since < 20)
    assert len(selected) == 6


@pytest.mark.asyncio
async def test_trigger_when_question_bank_has_5_questions_then_uses_all_5(
    db_session: AsyncSession,
    test_school: School,
    test_curriculum: Curriculum,
    test_grade: Grade,
    test_subject: Subject,
    test_teacher: User,
) -> None:
    """Uses all available questions when bank has fewer than MAX_DIAGNOSTIC_QUESTIONS."""
    class_, topics, questions = await _setup_full_class(
        db_session,
        test_school,
        test_curriculum,
        test_grade,
        test_subject,
        test_teacher,
        num_topics=1,
        questions_per_topic=5,
    )
    student, profile = await _create_student_with_profile(db_session, test_school)

    service = AssessmentService(db_session)
    created = await service.create_system_diagnostic(student.id, class_.id)
    await db_session.commit()

    assessment = created[0]

    result = await db_session.execute(
        select(AssessmentSelectedQuestion).where(AssessmentSelectedQuestion.assessment_id == assessment.id)
    )
    selected = result.scalars().all()
    assert len(selected) == 5


@pytest.mark.asyncio
async def test_trigger_when_assessment_created_then_is_system_generated_true(
    db_session: AsyncSession,
    test_school: School,
    test_curriculum: Curriculum,
    test_grade: Grade,
    test_subject: Subject,
    test_teacher: User,
) -> None:
    """Assessment is created with is_system_generated=TRUE."""
    class_, _, _ = await _setup_full_class(
        db_session, test_school, test_curriculum, test_grade, test_subject, test_teacher
    )
    student, profile = await _create_student_with_profile(db_session, test_school)

    service = AssessmentService(db_session)
    created = await service.create_system_diagnostic(student.id, class_.id)
    await db_session.commit()

    assert created[0].is_system_generated is True


@pytest.mark.asyncio
async def test_trigger_when_assessment_created_then_created_by_is_null(
    db_session: AsyncSession,
    test_school: School,
    test_curriculum: Curriculum,
    test_grade: Grade,
    test_subject: Subject,
    test_teacher: User,
) -> None:
    """Assessment is created with created_by=NULL (system-created, no teacher owner)."""
    class_, _, _ = await _setup_full_class(
        db_session, test_school, test_curriculum, test_grade, test_subject, test_teacher
    )
    student, profile = await _create_student_with_profile(db_session, test_school)

    service = AssessmentService(db_session)
    created = await service.create_system_diagnostic(student.id, class_.id)
    await db_session.commit()

    assert created[0].created_by is None
