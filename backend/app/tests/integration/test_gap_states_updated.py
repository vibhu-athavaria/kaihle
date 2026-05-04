"""Integration tests for gap state calculation (M1-4-T3).

Tests exercise the full stack via GapService.calculate_gap_states_for_attempt(),
which contains the same logic as the Celery task but is callable from async context.
Real DB: creates attempt, responses, and verifies gap_states row.

Run with:
    pytest backend/app/tests/integration/test_gap_states_updated.py -v
"""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import (
    Assessment,
    AssessmentStatus,
    AssessmentType,
    AttemptStatus,
    StudentAttempt,
    StudentAttemptSubtopicScore,
    StudentResponse,
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
from app.models.gap import GapState
from app.models.school import Class, School
from app.models.user import User, UserRole
from app.services.gap_service import GapService

# ── Helpers ──────────────────────────────────────────────────────────────────


async def _create_curriculum_chain(
    db: AsyncSession,
    school: School,
) -> tuple[Curriculum, Grade, Subject, CurriculumTopic, Subtopic]:
    """Create a minimal curriculum chain. Flushes after each model for FK constraints."""
    import random

    curriculum = Curriculum(
        id=uuid.uuid4(),
        name=f"Test Curriculum {uuid.uuid4().hex[:6]}",
        code=f"TC{uuid.uuid4().hex[:4]}",
        is_active=True,
    )
    db.add(curriculum)
    await db.flush()

    grade = Grade(
        id=uuid.uuid4(),
        name=f"Grade {random.randint(1, 13)}",
        level=random.randint(1, 13),
        is_active=True,
    )
    db.add(grade)
    await db.flush()

    subject = Subject(
        id=uuid.uuid4(),
        name=f"Mathematics {uuid.uuid4().hex[:4]}",
        code=f"MATH{uuid.uuid4().hex[:4]}",
        is_active=True,
    )
    db.add(subject)
    await db.flush()

    cs = CurriculumSubject(
        curriculum_id=curriculum.id,
        subject_id=subject.id,
        is_core=True,
    )
    db.add(cs)
    await db.flush()

    topic = Topic(
        id=uuid.uuid4(),
        name="Algebra",
        is_active=True,
    )
    db.add(topic)
    await db.flush()

    ct = CurriculumTopic(
        id=uuid.uuid4(),
        curriculum_id=curriculum.id,
        subject_id=subject.id,
        grade_id=grade.id,
        topic_id=topic.id,
        is_active=True,
        is_required=True,
    )
    db.add(ct)
    await db.flush()

    subtopic = Subtopic(
        id=uuid.uuid4(),
        curriculum_topic_id=ct.id,
        name="Linear Equations",
        learning_objective="Solve linear equations",
        is_active=True,
    )
    db.add(subtopic)
    await db.flush()

    return curriculum, grade, subject, ct, subtopic


async def _create_teacher(db: AsyncSession, school: School) -> User:
    teacher = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"teacher-gap-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Test",
        last_name="Teacher",
        role=UserRole.TEACHER,
        is_active=True,
    )
    db.add(teacher)
    await db.flush()
    return teacher


async def _create_class(
    db: AsyncSession,
    school: School,
    curriculum: Curriculum,
    grade: Grade,
    subject: Subject,
    teacher: User,
) -> Class:
    class_ = Class(
        id=uuid.uuid4(),
        school_id=school.id,
        grade_id=grade.id,
        subject_id=subject.id,
        curriculum_id=curriculum.id,
        teacher_id=teacher.id,
        name="Gap Test Class",
        academic_year="2025-2026",
        is_active=True,
    )
    db.add(class_)
    await db.flush()
    return class_


async def _create_question(db: AsyncSession, subtopic: Subtopic) -> QuestionBank:
    q = QuestionBank(
        id=uuid.uuid4(),
        subtopic_id=subtopic.id,
        question_text="Solve for x: 2x = 8",
        question_type="MCQ",
        options=[{"key": "A", "text": "4"}, {"key": "B", "text": "3"}],
        correct_answer="A",
        canonical_form="Solve for x: 2x = 8",
        problem_signature={},
        is_active=True,
    )
    db.add(q)
    await db.flush()
    return q


async def _create_assessment(
    db: AsyncSession,
    school: School,
    class_: Class,
    teacher: User,
    is_system_generated: bool = False,
) -> Assessment:
    assessment = Assessment(
        id=uuid.uuid4(),
        school_id=school.id,
        class_id=class_.id,
        created_by=None if is_system_generated else teacher.id,
        title="Test Assessment",
        assessment_type=AssessmentType.DIAGNOSTIC,
        status=AssessmentStatus.ACTIVE,
        is_system_generated=is_system_generated,
        config={"num_questions": 10},
    )
    db.add(assessment)
    await db.flush()
    return assessment


async def _create_attempt(
    db: AsyncSession,
    assessment: Assessment,
    student: User,
    status: str = AttemptStatus.COMPLETED,
) -> StudentAttempt:
    attempt = StudentAttempt(
        id=uuid.uuid4(),
        assessment_id=assessment.id,
        student_id=student.id,
        status=status,
        completed_at=datetime.now(UTC) if status == AttemptStatus.COMPLETED else None,
    )
    db.add(attempt)
    await db.flush()
    return attempt


async def _create_response(
    db: AsyncSession,
    attempt: StudentAttempt,
    question: QuestionBank,
    is_correct: bool,
) -> StudentResponse:
    response = StudentResponse(
        id=uuid.uuid4(),
        attempt_id=attempt.id,
        question_id=question.id,
        answer_given="A" if is_correct else "B",
        is_correct=is_correct,
        score=1.0 if is_correct else 0.0,
        scored_by="RULE",
    )
    db.add(response)
    await db.flush()
    return response


# ── Integration tests ────────────────────────────────────────────────────────


class TestGapStatesUpdated:
    """Integration tests for gap state calculation.

    Calls GapService.calculate_gap_states_for_attempt() directly (no Celery broker needed).
    The Celery task is a thin wrapper around this service method.
    """

    @pytest.mark.asyncio
    async def test_gap_states_updated_within_reasonable_time_after_submit(
        self,
        db_session: AsyncSession,
        school: School,
    ) -> None:
        """Call service method directly, verify gap_states row exists after."""
        curriculum, grade, subject, ct, subtopic = await _create_curriculum_chain(db_session, school)
        teacher = await _create_teacher(db_session, school)
        class_ = await _create_class(db_session, school, curriculum, grade, subject, teacher)
        question = await _create_question(db_session, subtopic)

        student = User(
            id=uuid.uuid4(),
            school_id=school.id,
            email=f"student-gap-{uuid.uuid4().hex[:8]}@test.com",
            first_name="Student",
            last_name="Gap",
            role=UserRole.STUDENT,
            is_active=True,
        )
        db_session.add(student)
        await db_session.flush()

        assessment = await _create_assessment(db_session, school, class_, teacher)
        attempt = await _create_attempt(db_session, assessment, student)
        await _create_response(db_session, attempt, question, is_correct=True)

        # Run gap calculation using the service (same logic as Celery task)
        service = GapService(db_session)
        result = await service.calculate_gap_states_for_attempt(attempt.id)

        assert result["subtopics_updated"] == 1

        # Verify gap_state row was created
        gs_result = await db_session.execute(
            select(GapState).where(
                GapState.student_id == student.id,
                GapState.subtopic_id == subtopic.id,
                GapState.class_id == class_.id,
            )
        )
        gap_state = gs_result.scalar_one_or_none()
        assert gap_state is not None

    @pytest.mark.asyncio
    async def test_gap_states_correct_after_submit_10_correct_of_10(
        self,
        db_session: AsyncSession,
        school: School,
    ) -> None:
        """10 correct responses → mastery=1.0 (first attempt, not system-generated)."""
        curriculum, grade, subject, ct, subtopic = await _create_curriculum_chain(db_session, school)
        teacher = await _create_teacher(db_session, school)
        class_ = await _create_class(db_session, school, curriculum, grade, subject, teacher)

        # Create 10 questions in the same subtopic
        questions = [await _create_question(db_session, subtopic) for _ in range(10)]

        student = User(
            id=uuid.uuid4(),
            school_id=school.id,
            email=f"student-10c-{uuid.uuid4().hex[:8]}@test.com",
            first_name="Student",
            last_name="Perfect",
            role=UserRole.STUDENT,
            is_active=True,
        )
        db_session.add(student)
        await db_session.flush()

        assessment = await _create_assessment(db_session, school, class_, teacher, is_system_generated=False)
        attempt = await _create_attempt(db_session, assessment, student)

        for q in questions:
            await _create_response(db_session, attempt, q, is_correct=True)

        service = GapService(db_session)
        await service.calculate_gap_states_for_attempt(attempt.id)

        gs_result = await db_session.execute(
            select(GapState).where(
                GapState.student_id == student.id,
                GapState.subtopic_id == subtopic.id,
            )
        )
        gap_state = gs_result.scalar_one_or_none()
        assert gap_state is not None
        assert gap_state.mastery_score == pytest.approx(1.0, abs=1e-9)
        assert gap_state.needs_review is False

    @pytest.mark.asyncio
    async def test_celery_task_idempotent_when_called_twice(
        self,
        db_session: AsyncSession,
        school: School,
    ) -> None:
        """Calling calculate_gap_states twice with same attempt_id → single gap_states row."""
        curriculum, grade, subject, ct, subtopic = await _create_curriculum_chain(db_session, school)
        teacher = await _create_teacher(db_session, school)
        class_ = await _create_class(db_session, school, curriculum, grade, subject, teacher)
        question = await _create_question(db_session, subtopic)

        student = User(
            id=uuid.uuid4(),
            school_id=school.id,
            email=f"student-idempotent-{uuid.uuid4().hex[:8]}@test.com",
            first_name="Student",
            last_name="Idempotent",
            role=UserRole.STUDENT,
            is_active=True,
        )
        db_session.add(student)
        await db_session.flush()

        assessment = await _create_assessment(db_session, school, class_, teacher)
        attempt = await _create_attempt(db_session, assessment, student)
        await _create_response(db_session, attempt, question, is_correct=True)

        service = GapService(db_session)

        # Call twice — both calls use ON CONFLICT DO UPDATE / DO NOTHING
        await service.calculate_gap_states_for_attempt(attempt.id)
        await service.calculate_gap_states_for_attempt(attempt.id)

        # Should be exactly one gap_states row for this student/subtopic/class
        gs_result = await db_session.execute(
            select(GapState).where(
                GapState.student_id == student.id,
                GapState.subtopic_id == subtopic.id,
                GapState.class_id == class_.id,
            )
        )
        gap_states = gs_result.scalars().all()
        assert len(gap_states) == 1

        # Should be exactly one subtopic score row
        score_result = await db_session.execute(
            select(StudentAttemptSubtopicScore).where(
                StudentAttemptSubtopicScore.student_id == student.id,
                StudentAttemptSubtopicScore.subtopic_id == subtopic.id,
                StudentAttemptSubtopicScore.attempt_id == attempt.id,
            )
        )
        scores = score_result.scalars().all()
        assert len(scores) == 1
