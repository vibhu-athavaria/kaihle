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

from app.ai.similarity import normalise_text
from app.models.assessment import (
    Assessment,
    AssessmentStatus,
    AssessmentTopicConfig,
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
    LearningObjective,
    QuestionBank,
    Subject,
    Subtopic,
    SubtopicObjective,
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
    curriculum = Curriculum(
        id=uuid.uuid4(),
        name=f"Test Curriculum {uuid.uuid4().hex[:6]}",
        code=f"TC{uuid.uuid4().hex[:4]}",
        is_active=True,
    )
    db.add(curriculum)
    await db.flush()

    # grades.level is globally UNIQUE with CHECK (level BETWEEN 1 AND 13) — only 13
    # slots exist. This helper is called more than once per test, and drawing the level
    # at random made two calls collide with probability 1/13, so the suite failed on
    # roughly one CI seed in thirteen. Claim the lowest level not already taken instead:
    # deterministic, and correct however many chains a test builds.
    used_levels = set((await db.execute(select(Grade.level))).scalars().all())
    free_level = next((lvl for lvl in range(1, 14) if lvl not in used_levels), None)
    if free_level is None:
        raise RuntimeError("No free grade level: all 13 are taken. Split the test or reuse a chain.")

    grade = Grade(
        id=uuid.uuid4(),
        name=f"Grade {free_level}",
        level=free_level,
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
) -> Assessment:
    assessment = Assessment(
        id=uuid.uuid4(),
        school_id=school.id,
        class_id=class_.id,
        created_by=teacher.id,
        title="Test Assessment",
        assessment_type=AssessmentType.DIAGNOSTIC,
        status=AssessmentStatus.ACTIVE,
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
    async def test_gap_states_when_perfect_score_then_strong_band_reachable(
        self,
        db_session: AsyncSession,
        school: School,
    ) -> None:
        """10/10 on a first DIAGNOSTIC reaches Strong — Finding 1 regression test.

        Was test_gap_states_correct_after_submit_10_correct_of_10, asserting
        mastery == 0.7 exactly. That was the bug: the retired formula applied score * 0.7
        to every first diagnostic regardless of assessment content, and 0.7 is exactly the
        Strong-band boundary (> 0.7), so a PERFECT score could never reach it — every top
        performer showed as "Developing", forever.

        Under mastery_model.estimate with no mastery_priors row yet (falls back to the
        bootstrap default Beta(2,3)): posterior = (10+2)/(10+2+0+3) = 12/15 = 0.8,
        comfortably inside Strong. The exact value is asserted, not just the band, because
        an inequality alone would not catch a regression that landed at, say, 0.71.
        """
        curriculum, grade, subject, ct, subtopic = await _create_curriculum_chain(db_session, school)
        teacher = await _create_teacher(db_session, school)
        class_ = await _create_class(db_session, school, curriculum, grade, subject, teacher)

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

        assessment = await _create_assessment(db_session, school, class_, teacher)
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
        assert gap_state.mastery_score == pytest.approx(0.8, abs=1e-9)
        assert gap_state.mastery_score > 0.7  # Strong band — the ceiling that could never
        # be reached before is now reached exactly when the evidence supports it.
        assert gap_state.needs_review is False

    @pytest.mark.asyncio
    async def test_gap_states_when_partial_score_then_shrunk_toward_prior_not_raw(
        self,
        db_session: AsyncSession,
        school: School,
    ) -> None:
        """3/5 correct, first attempt: posterior sits between the prior mean and the raw
        score — shrinkage happening, not a flat multiplier and not the raw proportion.

        With no calibrated prior (bootstrap default Beta(2,3), mean 0.4): raw score is
        0.6; posterior = (3+2)/(5+2+3) = 5/10 = 0.5 — pulled toward 0.4, but not equal to
        either endpoint.
        """
        curriculum, grade, subject, ct, subtopic = await _create_curriculum_chain(db_session, school)
        teacher = await _create_teacher(db_session, school)
        class_ = await _create_class(db_session, school, curriculum, grade, subject, teacher)
        questions = [await _create_question(db_session, subtopic) for _ in range(5)]

        student = User(
            id=uuid.uuid4(),
            school_id=school.id,
            email=f"student-shrink-{uuid.uuid4().hex[:8]}@test.com",
            first_name="Student",
            last_name="Shrunk",
            role=UserRole.STUDENT,
            is_active=True,
        )
        db_session.add(student)
        await db_session.flush()

        assessment = await _create_assessment(db_session, school, class_, teacher)
        attempt = await _create_attempt(db_session, assessment, student)
        for i, q in enumerate(questions):
            await _create_response(db_session, attempt, q, is_correct=i < 3)

        service = GapService(db_session)
        await service.calculate_gap_states_for_attempt(attempt.id)

        gap_state = (
            await db_session.execute(
                select(GapState).where(
                    GapState.student_id == student.id,
                    GapState.subtopic_id == subtopic.id,
                )
            )
        ).scalar_one_or_none()
        assert gap_state is not None
        assert gap_state.mastery_score == pytest.approx(0.5, abs=1e-9)
        assert 0.4 < gap_state.mastery_score < 0.6  # shrunk toward the prior, not raw

    @pytest.mark.asyncio
    async def test_gap_states_when_confidence_written_then_matches_pure_estimator(
        self,
        db_session: AsyncSession,
        school: School,
    ) -> None:
        """gap_states.confidence matches what mastery_model.estimate computes directly for
        the same observations and prior — verifies the wiring, not the math (the math has
        its own pure test suite in test_mastery_model.py)."""
        from app.services.mastery_model import Observation, estimate

        curriculum, grade, subject, ct, subtopic = await _create_curriculum_chain(db_session, school)
        teacher = await _create_teacher(db_session, school)
        class_ = await _create_class(db_session, school, curriculum, grade, subject, teacher)
        questions = [await _create_question(db_session, subtopic) for _ in range(4)]

        student = User(
            id=uuid.uuid4(),
            school_id=school.id,
            email=f"student-conf-{uuid.uuid4().hex[:8]}@test.com",
            first_name="Student",
            last_name="Confidence",
            role=UserRole.STUDENT,
            is_active=True,
        )
        db_session.add(student)
        await db_session.flush()

        assessment = await _create_assessment(db_session, school, class_, teacher)
        attempt = await _create_attempt(db_session, assessment, student)
        for i, q in enumerate(questions):
            await _create_response(db_session, attempt, q, is_correct=i < 3)

        service = GapService(db_session)
        await service.calculate_gap_states_for_attempt(attempt.id)

        gap_state = (
            await db_session.execute(
                select(GapState).where(
                    GapState.student_id == student.id,
                    GapState.subtopic_id == subtopic.id,
                )
            )
        ).scalar_one_or_none()
        assert gap_state is not None

        expected = estimate(
            [Observation(correct=3, total=4, age_index=0)],
            prior_alpha=2.0,
            prior_beta=3.0,
            decay=0.7,
        )
        assert gap_state.confidence == pytest.approx(expected.confidence, abs=1e-6)
        assert gap_state.mastery_score == pytest.approx(expected.score, abs=1e-6)

    @pytest.mark.asyncio
    async def test_gap_states_when_repeat_attempt_then_recent_weighted_above_historical(
        self,
        db_session: AsyncSession,
        school: School,
    ) -> None:
        """A weak first attempt followed by a strong second attempt scores higher than
        equal weighting of the two would — recency decay favouring the recent evidence,
        exercised end to end: the first call's written correct_count/total_count is what
        the second call reads back as history.
        """
        curriculum, grade, subject, ct, subtopic = await _create_curriculum_chain(db_session, school)
        teacher = await _create_teacher(db_session, school)
        class_ = await _create_class(db_session, school, curriculum, grade, subject, teacher)

        student = User(
            id=uuid.uuid4(),
            school_id=school.id,
            email=f"student-recency-{uuid.uuid4().hex[:8]}@test.com",
            first_name="Student",
            last_name="Recency",
            role=UserRole.STUDENT,
            is_active=True,
        )
        db_session.add(student)
        await db_session.flush()

        service = GapService(db_session)

        # First attempt: 1/5 correct.
        first_questions = [await _create_question(db_session, subtopic) for _ in range(5)]
        first_assessment = await _create_assessment(db_session, school, class_, teacher)
        first_attempt = await _create_attempt(db_session, first_assessment, student)
        for i, q in enumerate(first_questions):
            await _create_response(db_session, first_attempt, q, is_correct=i == 0)
        await service.calculate_gap_states_for_attempt(first_attempt.id)

        # Second attempt: 5/5 correct — should pull the score up more than an
        # equally-weighted average of the two attempts would.
        second_questions = [await _create_question(db_session, subtopic) for _ in range(5)]
        second_assessment = await _create_assessment(db_session, school, class_, teacher)
        second_attempt = await _create_attempt(db_session, second_assessment, student)
        for q in second_questions:
            await _create_response(db_session, second_attempt, q, is_correct=True)
        await service.calculate_gap_states_for_attempt(second_attempt.id)

        gap_state = (
            await db_session.execute(
                select(GapState).where(
                    GapState.student_id == student.id,
                    GapState.subtopic_id == subtopic.id,
                )
            )
        ).scalar_one_or_none()
        assert gap_state is not None

        # decay=0.7: weighted_correct = 5*1 + 1*0.7 = 5.7, weighted_total = 5+3.5 = 8.5.
        # posterior = (5.7+2)/(8.5+5) = 7.7/13.5.
        assert gap_state.mastery_score == pytest.approx(7.7 / 13.5, abs=1e-6)

        # Equal weighting (decay=1) of the same two attempts would give (6+2)/(10+5) =
        # 8/15 — lower. Recency weighting must place the recent-favouring score above it.
        equal_weighted = 8.0 / 15.0
        assert gap_state.mastery_score > equal_weighted

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
        first_score = (
            await db_session.execute(
                select(GapState.mastery_score, GapState.confidence).where(
                    GapState.student_id == student.id,
                    GapState.subtopic_id == subtopic.id,
                    GapState.class_id == class_.id,
                )
            )
        ).one()

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

        # Idempotent in VALUE, not just in row count: the same attempt_id re-run must not
        # double-count the (unchanged) attempt as new evidence via ON CONFLICT DO NOTHING
        # on student_attempt_subtopic_scores — the second call's historical query must see
        # the same rows the first call did, not the first call's row plus a duplicate.
        assert gap_states[0].mastery_score == pytest.approx(first_score.mastery_score, abs=1e-9)
        assert gap_states[0].confidence == pytest.approx(first_score.confidence, abs=1e-9)

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

    @pytest.mark.asyncio
    async def test_gap_states_when_attempt_completed_then_total_correct_and_total_attempted_match_responses(
        self,
        db_session: AsyncSession,
        school: School,
    ) -> None:
        """3/5 correct on a first attempt: gap_states.total_correct/total_attempted must
        reflect the real counts, not the pre-fix hardcoded 0/0.
        """
        curriculum, grade, subject, ct, subtopic = await _create_curriculum_chain(db_session, school)
        teacher = await _create_teacher(db_session, school)
        class_ = await _create_class(db_session, school, curriculum, grade, subject, teacher)
        questions = [await _create_question(db_session, subtopic) for _ in range(5)]

        student = User(
            id=uuid.uuid4(),
            school_id=school.id,
            email=f"student-counts-{uuid.uuid4().hex[:8]}@test.com",
            first_name="Student",
            last_name="Counts",
            role=UserRole.STUDENT,
            is_active=True,
        )
        db_session.add(student)
        await db_session.flush()

        assessment = await _create_assessment(db_session, school, class_, teacher)
        attempt = await _create_attempt(db_session, assessment, student)
        for i, q in enumerate(questions):
            await _create_response(db_session, attempt, q, is_correct=i < 3)

        await GapService(db_session).calculate_gap_states_for_attempt(attempt.id)

        gap_state = (
            await db_session.execute(
                select(GapState).where(
                    GapState.student_id == student.id,
                    GapState.subtopic_id == subtopic.id,
                )
            )
        ).scalar_one_or_none()
        assert gap_state is not None
        assert gap_state.total_correct == 3
        assert gap_state.total_attempted == 5

    @pytest.mark.asyncio
    async def test_gap_states_when_repeat_attempt_then_total_correct_and_total_attempted_accumulate(
        self,
        db_session: AsyncSession,
        school: School,
    ) -> None:
        """total_correct/total_attempted sum across attempts, not just the latest one —
        the pre-fix bug always wrote 0 regardless of history, so a naive fix that only
        persisted the current attempt's counts (dropping history) would still be wrong.
        """
        curriculum, grade, subject, ct, subtopic = await _create_curriculum_chain(db_session, school)
        teacher = await _create_teacher(db_session, school)
        class_ = await _create_class(db_session, school, curriculum, grade, subject, teacher)

        student = User(
            id=uuid.uuid4(),
            school_id=school.id,
            email=f"student-accum-{uuid.uuid4().hex[:8]}@test.com",
            first_name="Student",
            last_name="Accumulate",
            role=UserRole.STUDENT,
            is_active=True,
        )
        db_session.add(student)
        await db_session.flush()

        service = GapService(db_session)

        # First attempt: 1/5 correct.
        first_questions = [await _create_question(db_session, subtopic) for _ in range(5)]
        first_assessment = await _create_assessment(db_session, school, class_, teacher)
        first_attempt = await _create_attempt(db_session, first_assessment, student)
        for i, q in enumerate(first_questions):
            await _create_response(db_session, first_attempt, q, is_correct=i == 0)
        await service.calculate_gap_states_for_attempt(first_attempt.id)

        # Second attempt: 4/4 correct.
        second_questions = [await _create_question(db_session, subtopic) for _ in range(4)]
        second_assessment = await _create_assessment(db_session, school, class_, teacher)
        second_attempt = await _create_attempt(db_session, second_assessment, student)
        for q in second_questions:
            await _create_response(db_session, second_attempt, q, is_correct=True)
        await service.calculate_gap_states_for_attempt(second_attempt.id)

        gap_state = (
            await db_session.execute(
                select(GapState).where(
                    GapState.student_id == student.id,
                    GapState.subtopic_id == subtopic.id,
                )
            )
        ).scalar_one_or_none()
        assert gap_state is not None
        assert gap_state.total_correct == 1 + 4
        assert gap_state.total_attempted == 5 + 4


@pytest.mark.asyncio
class TestGapStatesAfterCurriculumRemap:
    """Regression tests for the v2 curriculum remap.

    A remapped question has subtopic_id = NULL and is reachable only through its
    learning objective. Resolving attribution via question_bank.subtopic_id silently
    dropped every such response, so no mastery was ever recorded for a remapped
    scope — the diagnostic, which is the core product, went quietly dead.
    """

    async def test_gap_states_when_question_has_no_subtopic_id_then_attributed_via_objective(
        self,
        db_session: AsyncSession,
        school: School,
    ) -> None:
        curriculum, grade, subject, ct, subtopic = await _create_curriculum_chain(db_session, school)
        teacher = await _create_teacher(db_session, school)
        class_ = await _create_class(db_session, school, curriculum, grade, subject, teacher)

        objective = LearningObjective(
            id=uuid.uuid4(),
            canonical_code=f"LO-{uuid.uuid4().hex[:10]}",
            name="Remapped objective",
            learning_objective="Order negative integers on a number line.",
            normalised_objective=normalise_text("Order negative integers on a number line."),
            topic_id=ct.topic_id,
            grade_id=grade.id,
            is_active=True,
        )
        db_session.add(objective)
        await db_session.flush()
        db_session.add(SubtopicObjective(subtopic_id=subtopic.id, learning_objective_id=objective.id))
        await db_session.flush()

        # Exactly the post-wipe shape: no subtopic_id, bound only via the objective.
        question = QuestionBank(
            id=uuid.uuid4(),
            subtopic_id=None,
            learning_objective_id=objective.id,
            question_text="What is -3 + 5?",
            question_type="MCQ",
            options=[{"key": "A", "text": "2"}],
            correct_answer="A",
            canonical_form=f"q-{uuid.uuid4().hex[:8]}",
            problem_signature={},
            difficulty_level=2.0,
            source="bank",
            is_active=True,
        )
        db_session.add(question)
        await db_session.flush()

        student = User(
            id=uuid.uuid4(),
            school_id=school.id,
            email=f"student-remap-{uuid.uuid4().hex[:8]}@test.com",
            first_name="Student",
            last_name="Remap",
            role=UserRole.STUDENT,
            is_active=True,
        )
        db_session.add(student)
        await db_session.flush()

        assessment = await _create_assessment(db_session, school, class_, teacher)
        attempt = await _create_attempt(db_session, assessment, student)
        await _create_response(db_session, attempt, question, is_correct=True)

        result = await GapService(db_session).calculate_gap_states_for_attempt(attempt.id)

        assert result["subtopics_updated"] == 1
        gs = await db_session.execute(
            select(GapState).where(
                GapState.student_id == student.id,
                GapState.subtopic_id == subtopic.id,
                GapState.class_id == class_.id,
            )
        )
        assert gs.scalar_one_or_none() is not None

    async def test_gap_states_when_objective_placed_outside_class_scope_then_not_attributed(
        self,
        db_session: AsyncSession,
        school: School,
    ) -> None:
        """An objective can be taught in several placements. Attribution must stay
        inside the class's own curriculum/subject/grade, never leak across it."""
        curriculum, grade, subject, ct, subtopic = await _create_curriculum_chain(db_session, school)
        other_curriculum, other_grade, other_subject, other_ct, other_subtopic = await _create_curriculum_chain(
            db_session, school
        )
        teacher = await _create_teacher(db_session, school)
        class_ = await _create_class(db_session, school, curriculum, grade, subject, teacher)

        objective = LearningObjective(
            id=uuid.uuid4(),
            canonical_code=f"LO-{uuid.uuid4().hex[:10]}",
            name="Shared objective",
            learning_objective="Shared across two placements.",
            normalised_objective=normalise_text("Shared across two placements."),
            topic_id=other_ct.topic_id,
            grade_id=other_grade.id,
            is_active=True,
        )
        db_session.add(objective)
        await db_session.flush()
        # Placed ONLY outside the class's scope.
        db_session.add(SubtopicObjective(subtopic_id=other_subtopic.id, learning_objective_id=objective.id))
        await db_session.flush()

        question = QuestionBank(
            id=uuid.uuid4(),
            subtopic_id=None,
            learning_objective_id=objective.id,
            question_text="Out of scope?",
            question_type="MCQ",
            options=[{"key": "A", "text": "1"}],
            correct_answer="A",
            canonical_form=f"q-{uuid.uuid4().hex[:8]}",
            problem_signature={},
            difficulty_level=2.0,
            source="bank",
            is_active=True,
        )
        db_session.add(question)
        await db_session.flush()

        student = User(
            id=uuid.uuid4(),
            school_id=school.id,
            email=f"student-scope-{uuid.uuid4().hex[:8]}@test.com",
            first_name="Student",
            last_name="Scope",
            role=UserRole.STUDENT,
            is_active=True,
        )
        db_session.add(student)
        await db_session.flush()

        assessment = await _create_assessment(db_session, school, class_, teacher)
        attempt = await _create_attempt(db_session, assessment, student)
        await _create_response(db_session, attempt, question, is_correct=True)

        await GapService(db_session).calculate_gap_states_for_attempt(attempt.id)

        leaked = await db_session.execute(
            select(GapState).where(
                GapState.student_id == student.id,
                GapState.subtopic_id == other_subtopic.id,
            )
        )
        assert leaked.scalar_one_or_none() is None

    async def test_gap_states_when_legacy_question_still_has_subtopic_id_then_still_attributed(
        self,
        db_session: AsyncSession,
        school: School,
    ) -> None:
        """Untouched scopes keep a populated subtopic_id. The fallback must preserve
        them, or fixing the remapped scope would break every scope that was fine."""
        curriculum, grade, subject, ct, subtopic = await _create_curriculum_chain(db_session, school)
        teacher = await _create_teacher(db_session, school)
        class_ = await _create_class(db_session, school, curriculum, grade, subject, teacher)
        question = await _create_question(db_session, subtopic)

        student = User(
            id=uuid.uuid4(),
            school_id=school.id,
            email=f"student-legacy-{uuid.uuid4().hex[:8]}@test.com",
            first_name="Student",
            last_name="Legacy",
            role=UserRole.STUDENT,
            is_active=True,
        )
        db_session.add(student)
        await db_session.flush()

        assessment = await _create_assessment(db_session, school, class_, teacher)
        attempt = await _create_attempt(db_session, assessment, student)
        await _create_response(db_session, attempt, question, is_correct=True)

        result = await GapService(db_session).calculate_gap_states_for_attempt(attempt.id)

        assert result["subtopics_updated"] == 1


async def _add_topic_at_grade(
    db: AsyncSession,
    curriculum: Curriculum,
    subject: Subject,
    level: int,
    topic_name: str,
) -> tuple[Grade, CurriculumTopic, Subtopic]:
    """Create a Grade + CurriculumTopic + Subtopic within an existing curriculum/subject,
    at an explicit grade level. Distinct from _create_curriculum_chain, which always
    creates its own fresh curriculum AND subject — these tests need two topics that
    share the same curriculum (a real Tier 1 diagnostic's prior-grade topic lives in the
    same curriculum as the class's own grade), with independently controlled levels.
    """
    grade = Grade(id=uuid.uuid4(), name=f"Grade {level}", level=level, is_active=True)
    db.add(grade)
    await db.flush()

    topic = Topic(id=uuid.uuid4(), name=topic_name, is_active=True)
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
        name=f"{topic_name} Subtopic",
        learning_objective=f"Learn {topic_name}",
        is_active=True,
    )
    db.add(subtopic)
    await db.flush()

    return grade, ct, subtopic


async def _create_objective_question(
    db: AsyncSession,
    ct: CurriculumTopic,
    grade: Grade,
    subtopic: Subtopic,
) -> QuestionBank:
    """Create a question reachable ONLY via the learning-objective bridge (subtopic_id
    NULL), exactly like a post-remap question. _create_question sets subtopic_id
    directly, which resolves via the legacy fallback (Step 4b) — a path that has never
    been grade-scoped and so cannot exercise the scoped-join fix these tests target.
    """
    objective = LearningObjective(
        id=uuid.uuid4(),
        canonical_code=f"LO-{uuid.uuid4().hex[:10]}",
        name=f"Objective for {subtopic.name}",
        learning_objective=f"Learn {subtopic.name}",
        normalised_objective=normalise_text(f"Learn {subtopic.name}"),
        topic_id=ct.topic_id,
        grade_id=grade.id,
        is_active=True,
    )
    db.add(objective)
    await db.flush()
    db.add(SubtopicObjective(subtopic_id=subtopic.id, learning_objective_id=objective.id))
    await db.flush()

    question = QuestionBank(
        id=uuid.uuid4(),
        subtopic_id=None,
        learning_objective_id=objective.id,
        question_text=f"Question for {subtopic.name}",
        question_type="MCQ",
        options=[{"key": "A", "text": "Correct"}],
        correct_answer="A",
        canonical_form=f"q-{uuid.uuid4().hex[:8]}",
        problem_signature={},
        difficulty_level=2.0,
        source="bank",
        is_active=True,
    )
    db.add(question)
    await db.flush()
    return question


@pytest.mark.asyncio
class TestGapStatesPriorGradeAttribution:
    """Regression tests for Bug 2: a Tier 1 diagnostic may legitimately include topics
    from the class's own grade AND the previous grade (grade.level - 1) — a teacher
    chooses this explicitly via DesignTier1DiagnosticRequest.topic_ids, validated by
    AssessmentService._resolve_and_validate_topic_grades. Before this fix, attribution
    filtered strictly on CurriculumTopic.grade_id == klass.grade_id, silently dropping
    every response to a configured prior-grade (or cross-subject-fallback) topic.
    """

    async def test_gap_states_when_response_is_for_configured_prior_grade_topic_then_attributed(
        self,
        db_session: AsyncSession,
        school: School,
    ) -> None:
        curriculum = Curriculum(
            id=uuid.uuid4(),
            name=f"Test Curriculum {uuid.uuid4().hex[:6]}",
            code=f"TC{uuid.uuid4().hex[:4]}",
            is_active=True,
        )
        db_session.add(curriculum)
        await db_session.flush()

        subject = Subject(
            id=uuid.uuid4(),
            name=f"Mathematics {uuid.uuid4().hex[:4]}",
            code=f"MATH{uuid.uuid4().hex[:4]}",
            is_active=True,
        )
        db_session.add(subject)
        await db_session.flush()
        db_session.add(CurriculumSubject(curriculum_id=curriculum.id, subject_id=subject.id, is_core=True))
        await db_session.flush()

        class_grade, _class_ct, _class_subtopic = await _add_topic_at_grade(
            db_session, curriculum, subject, level=6, topic_name="Current Grade Algebra"
        )
        prior_grade, prior_ct, prior_subtopic = await _add_topic_at_grade(
            db_session, curriculum, subject, level=5, topic_name="Prior Grade Algebra"
        )

        teacher = await _create_teacher(db_session, school)
        class_ = await _create_class(db_session, school, curriculum, class_grade, subject, teacher)
        question = await _create_objective_question(db_session, prior_ct, prior_grade, prior_subtopic)

        student = User(
            id=uuid.uuid4(),
            school_id=school.id,
            email=f"student-priorgrade-{uuid.uuid4().hex[:8]}@test.com",
            first_name="Student",
            last_name="PriorGrade",
            role=UserRole.STUDENT,
            is_active=True,
        )
        db_session.add(student)
        await db_session.flush()

        assessment = await _create_assessment(db_session, school, class_, teacher)
        db_session.add(
            AssessmentTopicConfig(assessment_id=assessment.id, curriculum_topic_id=prior_ct.id, grade_id=prior_grade.id)
        )
        await db_session.flush()

        attempt = await _create_attempt(db_session, assessment, student)
        await _create_response(db_session, attempt, question, is_correct=True)

        result = await GapService(db_session).calculate_gap_states_for_attempt(attempt.id)

        assert result["subtopics_updated"] == 1
        gap_state = (
            await db_session.execute(
                select(GapState).where(
                    GapState.student_id == student.id,
                    GapState.subtopic_id == prior_subtopic.id,
                )
            )
        ).scalar_one_or_none()
        assert gap_state is not None

    async def test_gap_states_when_response_is_for_prior_grade_topic_with_no_assessment_topic_config_then_not_attributed(
        self,
        db_session: AsyncSession,
        school: School,
    ) -> None:
        """Same shape as the previous test, but with no AssessmentTopicConfig row — the
        fallback to curriculum/subject/grade scoping must still apply, so a prior-grade
        response is NOT attributed. Proves the fix only widens scope for assessments that
        actually configured it, rather than attributing every prior-grade topic always.
        """
        curriculum = Curriculum(
            id=uuid.uuid4(),
            name=f"Test Curriculum {uuid.uuid4().hex[:6]}",
            code=f"TC{uuid.uuid4().hex[:4]}",
            is_active=True,
        )
        db_session.add(curriculum)
        await db_session.flush()

        subject = Subject(
            id=uuid.uuid4(),
            name=f"Mathematics {uuid.uuid4().hex[:4]}",
            code=f"MATH{uuid.uuid4().hex[:4]}",
            is_active=True,
        )
        db_session.add(subject)
        await db_session.flush()
        db_session.add(CurriculumSubject(curriculum_id=curriculum.id, subject_id=subject.id, is_core=True))
        await db_session.flush()

        class_grade, _class_ct, _class_subtopic = await _add_topic_at_grade(
            db_session, curriculum, subject, level=8, topic_name="Current Grade Algebra"
        )
        prior_grade, prior_ct, prior_subtopic = await _add_topic_at_grade(
            db_session, curriculum, subject, level=7, topic_name="Prior Grade Algebra"
        )

        teacher = await _create_teacher(db_session, school)
        class_ = await _create_class(db_session, school, curriculum, class_grade, subject, teacher)
        question = await _create_objective_question(db_session, prior_ct, prior_grade, prior_subtopic)

        student = User(
            id=uuid.uuid4(),
            school_id=school.id,
            email=f"student-noconfig-{uuid.uuid4().hex[:8]}@test.com",
            first_name="Student",
            last_name="NoConfig",
            role=UserRole.STUDENT,
            is_active=True,
        )
        db_session.add(student)
        await db_session.flush()

        assessment = await _create_assessment(db_session, school, class_, teacher)
        # No AssessmentTopicConfig row — nothing configured for this assessment.
        attempt = await _create_attempt(db_session, assessment, student)
        await _create_response(db_session, attempt, question, is_correct=True)

        result = await GapService(db_session).calculate_gap_states_for_attempt(attempt.id)

        assert result["subtopics_updated"] == 0
        gap_state = (
            await db_session.execute(
                select(GapState).where(
                    GapState.student_id == student.id,
                    GapState.subtopic_id == prior_subtopic.id,
                )
            )
        ).scalar_one_or_none()
        assert gap_state is None

    async def test_gap_states_when_response_is_for_configured_cross_subject_fallback_topic_then_attributed(
        self,
        db_session: AsyncSession,
        school: School,
    ) -> None:
        """Mirrors the live future-school-bali case: an ENGL class's Tier 1 diagnostic
        configured a prior-grade topic under a DIFFERENT Subject row (a continuing "ENG"
        course). A fix that only widened the grade_id filter while still requiring
        CurriculumTopic.subject_id == klass.subject_id would still miss this — the fix
        must trust assessment_topic_config's configured topics regardless of subject.
        """
        curriculum = Curriculum(
            id=uuid.uuid4(),
            name=f"Test Curriculum {uuid.uuid4().hex[:6]}",
            code=f"TC{uuid.uuid4().hex[:4]}",
            is_active=True,
        )
        db_session.add(curriculum)
        await db_session.flush()

        class_subject = Subject(
            id=uuid.uuid4(),
            name=f"English Language {uuid.uuid4().hex[:4]}",
            code=f"ENGL{uuid.uuid4().hex[:4]}",
            is_active=True,
        )
        prior_subject = Subject(
            id=uuid.uuid4(),
            name=f"General English {uuid.uuid4().hex[:4]}",
            code=f"ENG{uuid.uuid4().hex[:4]}",
            is_active=True,
        )
        db_session.add(class_subject)
        db_session.add(prior_subject)
        await db_session.flush()
        db_session.add(CurriculumSubject(curriculum_id=curriculum.id, subject_id=class_subject.id, is_core=True))
        db_session.add(CurriculumSubject(curriculum_id=curriculum.id, subject_id=prior_subject.id, is_core=True))
        await db_session.flush()

        class_grade, _class_ct, _class_subtopic = await _add_topic_at_grade(
            db_session, curriculum, class_subject, level=10, topic_name="IGCSE English"
        )
        prior_grade, prior_ct, prior_subtopic = await _add_topic_at_grade(
            db_session, curriculum, prior_subject, level=8, topic_name="General English"
        )

        teacher = await _create_teacher(db_session, school)
        class_ = await _create_class(db_session, school, curriculum, class_grade, class_subject, teacher)
        question = await _create_objective_question(db_session, prior_ct, prior_grade, prior_subtopic)

        student = User(
            id=uuid.uuid4(),
            school_id=school.id,
            email=f"student-crosssubj-{uuid.uuid4().hex[:8]}@test.com",
            first_name="Student",
            last_name="CrossSubject",
            role=UserRole.STUDENT,
            is_active=True,
        )
        db_session.add(student)
        await db_session.flush()

        assessment = await _create_assessment(db_session, school, class_, teacher)
        db_session.add(
            AssessmentTopicConfig(assessment_id=assessment.id, curriculum_topic_id=prior_ct.id, grade_id=prior_grade.id)
        )
        await db_session.flush()

        attempt = await _create_attempt(db_session, assessment, student)
        await _create_response(db_session, attempt, question, is_correct=True)

        result = await GapService(db_session).calculate_gap_states_for_attempt(attempt.id)

        assert result["subtopics_updated"] == 1
        gap_state = (
            await db_session.execute(
                select(GapState).where(
                    GapState.student_id == student.id,
                    GapState.subtopic_id == prior_subtopic.id,
                )
            )
        ).scalar_one_or_none()
        assert gap_state is not None
