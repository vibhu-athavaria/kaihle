"""Attempt service — manages the student assessment-taking lifecycle.


Handles:
- Getting/creating student attempts for Tier 1 (diagnostic) and Tier 2 assessments.
- Per-question response submission with deterministic MCQ scoring.
- Bulk answer submission with Celery task dispatch.
- Result retrieval with role-based access control.

Design notes:
- Questions returned to students always have correct_answer=None (stripped here).
- Scoring is deterministic string comparison — no LLM involved (CONSTITUTION §8).
- calculate_gap_states Celery task is fired after submit; we do NOT await it.
"""

import uuid
from datetime import UTC, datetime
from typing import Protocol, cast

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import (
    Assessment,
    AssessmentSelectedQuestion,
    AssessmentStatus,
    AttemptStatus,
    ScoredBy,
    StudentAttempt,
    StudentResponse,
)
from app.models.curriculum import QuestionBank
from app.models.school import ClassEnrollment
from app.models.user import UserRole
from app.schemas.attempts import AttemptResultResponse

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Protocols (avoid circular imports)
# ---------------------------------------------------------------------------


class _OnboardingServiceProtocol(Protocol):
    """Minimal interface expected from OnboardingService."""

    async def check_and_update_onboarding_complete(
        self,
        student_id: uuid.UUID,
        class_id: uuid.UUID,
    ) -> bool: ...


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class AttemptNotFoundError(Exception):
    """Raised when the expected StudentAttempt row does not exist."""


class AttemptAlreadyCompletedError(Exception):
    """Raised when a student tries to answer or submit a completed attempt."""


class QuestionNotInAssessmentError(Exception):
    """Raised when the given question_id is not in the attempt's assessment."""


class DuplicateResponseError(Exception):
    """Raised when a response for the same question already exists in the attempt."""


class AttemptAccessDeniedError(Exception):
    """Raised when a user attempts to access an attempt they are not authorised to view."""


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class AttemptService:
    """Service for attempt-lifecycle operations."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Tier 1 (diagnostic) ─────────────────────────────────────────────

    async def get_class_diagnostic(
        self,
        class_id: uuid.UUID,
        student_id: uuid.UUID,
        school_id: uuid.UUID,
    ) -> tuple[StudentAttempt, list[QuestionBank]]:
        """Return the student's Tier 1 diagnostic attempt for a class.

        The attempt is pre-created by the Celery onboarding task at enrollment.
        This endpoint only reads — it never creates.

        Args:
            class_id: The class UUID.
            student_id: The requesting student's user ID.
            school_id: The student's school (for multi-tenancy guard).

        Returns:
            (StudentAttempt, questions_without_correct_answer)

        Raises:
            ValueError: If no ACTIVE system-generated assessment is found for the class.
            AttemptNotFoundError: If the student's attempt row does not yet exist.
        """
        # Step 1 — find the Tier 1 ACTIVE assessment for this class
        assessment_result = await self.db.execute(
            select(Assessment).where(
                Assessment.class_id == class_id,
                Assessment.school_id == school_id,
                Assessment.is_system_generated.is_(True),
                Assessment.status == AssessmentStatus.ACTIVE,
            )
        )
        assessment = assessment_result.scalar_one_or_none()
        if assessment is None:
            logger.warning(
                "no_active_tier1_diagnostic",
                class_id=str(class_id),
                school_id=str(school_id),
            )
            raise ValueError("No active Tier 1 diagnostic found for this class")

        # Step 2 — find the student's pre-created attempt
        attempt_result = await self.db.execute(
            select(StudentAttempt).where(
                StudentAttempt.assessment_id == assessment.id,
                StudentAttempt.student_id == student_id,
            )
        )
        attempt = attempt_result.scalar_one_or_none()
        if attempt is None:
            logger.warning(
                "diagnostic_attempt_missing",
                student_id=str(student_id),
                class_id=str(class_id),
                assessment_id=str(assessment.id),
            )
            raise AttemptNotFoundError("Diagnostic attempt not yet created for this student")

        # Step 3 — load questions in order, stripped of correct answers
        questions = await self._load_questions(assessment.id, strip_answers=True)

        return attempt, questions

    # ── Tier 2: lazy attempt creation ───────────────────────────────────

    async def get_or_create_attempt(
        self,
        assessment_id: uuid.UUID,
        student_id: uuid.UUID,
        school_id: uuid.UUID,
    ) -> tuple[StudentAttempt, list[QuestionBank]]:
        """Return existing attempt or create one if the student is enrolled.

        Used for Tier 2 (teacher-created) assessments where the attempt is
        created lazily on first access rather than pre-created at enrollment.

        Args:
            assessment_id: The assessment UUID.
            student_id: The requesting student's user ID.
            school_id: The student's school (for multi-tenancy guard).

        Returns:
            (StudentAttempt, questions_without_correct_answer)

        Raises:
            ValueError: If assessment not found, not ACTIVE, or student not enrolled.
        """
        # Load and validate assessment
        assessment_result = await self.db.execute(
            select(Assessment).where(
                Assessment.id == assessment_id,
                Assessment.school_id == school_id,
            )
        )
        assessment = assessment_result.scalar_one_or_none()
        if assessment is None:
            raise ValueError(f"Assessment not found: {assessment_id}")
        if assessment.status != AssessmentStatus.ACTIVE:
            raise ValueError("Assessment is not active")

        # Return existing attempt if present
        existing_result = await self.db.execute(
            select(StudentAttempt).where(
                StudentAttempt.assessment_id == assessment_id,
                StudentAttempt.student_id == student_id,
            )
        )
        existing_attempt = existing_result.scalar_one_or_none()
        if existing_attempt is not None:
            questions = await self._load_questions(assessment_id, strip_answers=True)
            return existing_attempt, questions

        # Verify enrollment before creating
        enrollment_result = await self.db.execute(
            select(ClassEnrollment).where(
                ClassEnrollment.class_id == assessment.class_id,
                ClassEnrollment.student_id == student_id,
            )
        )
        if enrollment_result.scalar_one_or_none() is None:
            raise ValueError("Student not enrolled in class")

        # Create new attempt
        attempt = StudentAttempt(
            id=uuid.uuid4(),
            assessment_id=assessment_id,
            student_id=student_id,
            status=AttemptStatus.NOT_STARTED,
        )
        self.db.add(attempt)
        await self.db.flush()

        logger.info(
            "tier2_attempt_created",
            attempt_id=str(attempt.id),
            assessment_id=str(assessment_id),
            student_id=str(student_id),
        )

        questions = await self._load_questions(assessment_id, strip_answers=True)
        return attempt, questions

    # ── Per-question response ────────────────────────────────────────────

    async def submit_response(
        self,
        attempt_id: uuid.UUID,
        student_id: uuid.UUID,
        school_id: uuid.UUID,
        question_id: uuid.UUID,
        selected_key: str,
    ) -> None:
        """Record a single answer for an in-progress attempt.

        Scoring is deterministic: case-insensitive string comparison of the
        selected key against the stored correct_answer.

        Args:
            attempt_id: The StudentAttempt UUID.
            student_id: The requesting student (ownership check).
            school_id: The student's school (multi-tenancy guard).
            question_id: The question being answered.
            selected_key: The option key the student chose (e.g. "A").

        Raises:
            ValueError: If attempt not found or belongs to a different student/school.
            AttemptAlreadyCompletedError: If attempt.status == COMPLETED.
            QuestionNotInAssessmentError: If question_id not in assessment.
            DuplicateResponseError: If a response for this question already exists.
        """
        attempt = await self._load_and_verify_attempt(attempt_id, student_id, school_id)

        if attempt.status == AttemptStatus.COMPLETED:
            raise AttemptAlreadyCompletedError(f"Attempt {attempt_id} is already completed")

        # Verify question belongs to this assessment
        bridge_result = await self.db.execute(
            select(AssessmentSelectedQuestion).where(
                AssessmentSelectedQuestion.assessment_id == attempt.assessment_id,
                AssessmentSelectedQuestion.question_id == question_id,
            )
        )
        if bridge_result.scalar_one_or_none() is None:
            raise QuestionNotInAssessmentError(f"Question {question_id} is not in assessment {attempt.assessment_id}")

        # Duplicate guard
        dup_result = await self.db.execute(
            select(StudentResponse).where(
                StudentResponse.attempt_id == attempt_id,
                StudentResponse.question_id == question_id,
            )
        )
        if dup_result.scalar_one_or_none() is not None:
            raise DuplicateResponseError(f"Response for question {question_id} already exists in attempt {attempt_id}")

        # Load question for scoring
        question_result = await self.db.execute(select(QuestionBank).where(QuestionBank.id == question_id))
        question = question_result.scalar_one_or_none()
        if question is None:
            raise QuestionNotInAssessmentError(f"Question {question_id} not found in question bank")

        is_correct = selected_key.strip().lower() == question.correct_answer.strip().lower()

        response = StudentResponse(
            id=uuid.uuid4(),
            attempt_id=attempt_id,
            question_id=question_id,
            answer_given=selected_key,
            is_correct=is_correct,
            score=1.0 if is_correct else 0.0,
            scored_by=ScoredBy.RULE,
            time_taken_ms=None,
        )
        self.db.add(response)

        # Transition attempt from NOT_STARTED → IN_PROGRESS on first answer
        if attempt.status == AttemptStatus.NOT_STARTED:
            attempt.status = AttemptStatus.IN_PROGRESS
            attempt.started_at = datetime.now(UTC)

        logger.info(
            "response_submitted",
            attempt_id=str(attempt_id),
            question_id=str(question_id),
            is_correct=is_correct,
        )

    # ── Bulk submit ──────────────────────────────────────────────────────

    async def submit_attempt(
        self,
        attempt_id: uuid.UUID,
        student_id: uuid.UUID,
        school_id: uuid.UUID,
        answers: list[dict[str, object]],
        onboarding_service: _OnboardingServiceProtocol,
    ) -> AttemptResultResponse:
        """Submit all answers and finalise the attempt.

        Idempotent for each answer: skips questions already responded to.
        Fires the calculate_gap_states Celery task after scoring.
        For Tier 1 diagnostics, also calls check_and_update_onboarding_complete.

        Args:
            attempt_id: The StudentAttempt UUID.
            student_id: The requesting student (ownership check).
            school_id: The student's school (multi-tenancy guard).
            answers: List of dicts with keys ``question_id`` (UUID) and
                     ``selected_key`` (str).
            onboarding_service: An OnboardingService instance; injected to avoid
                                circular imports at module level.

        Returns:
            AttemptResultResponse with final score details.

        Raises:
            AttemptAlreadyCompletedError: If attempt is already COMPLETED.
            ValueError: If attempt not found or ownership mismatch.
        """
        attempt = await self._load_and_verify_attempt(attempt_id, student_id, school_id)

        if attempt.status == AttemptStatus.COMPLETED:
            raise AttemptAlreadyCompletedError(f"Attempt {attempt_id} is already completed")

        # Load assessment for is_system_generated flag
        assessment_result = await self.db.execute(select(Assessment).where(Assessment.id == attempt.assessment_id))
        assessment = assessment_result.scalar_one()

        # Process each answer — idempotent: skip already-saved responses
        existing_responses_result = await self.db.execute(
            select(StudentResponse.question_id).where(StudentResponse.attempt_id == attempt_id)
        )
        already_answered: set[uuid.UUID] = {row[0] for row in existing_responses_result.all()}

        for answer in answers:
            raw_q_id = answer["question_id"]
            if isinstance(raw_q_id, uuid.UUID):
                q_id = raw_q_id
            else:
                try:
                    q_id = uuid.UUID(str(raw_q_id))
                except (ValueError, AttributeError):
                    logger.warning("submit_attempt_invalid_question_id", raw_q_id=str(raw_q_id))
                    continue
            selected_key = str(answer["selected_key"])

            if q_id in already_answered:
                continue

            # Verify question in assessment
            bridge_result = await self.db.execute(
                select(AssessmentSelectedQuestion).where(
                    AssessmentSelectedQuestion.assessment_id == attempt.assessment_id,
                    AssessmentSelectedQuestion.question_id == q_id,
                )
            )
            if bridge_result.scalar_one_or_none() is None:
                logger.warning(
                    "submit_attempt_skipping_invalid_question",
                    question_id=str(q_id),
                    assessment_id=str(attempt.assessment_id),
                )
                continue

            question_result = await self.db.execute(select(QuestionBank).where(QuestionBank.id == q_id))
            question = question_result.scalar_one_or_none()
            if question is None:
                logger.warning(
                    "submit_attempt_question_not_in_bank",
                    question_id=str(q_id),
                    assessment_id=str(attempt.assessment_id),
                )
                continue

            is_correct = selected_key.strip().lower() == question.correct_answer.strip().lower()

            response = StudentResponse(
                id=uuid.uuid4(),
                attempt_id=attempt_id,
                question_id=q_id,
                answer_given=selected_key,
                is_correct=is_correct,
                score=1.0 if is_correct else 0.0,
                scored_by=ScoredBy.RULE,
                time_taken_ms=None,
            )
            self.db.add(response)

        await self.db.flush()

        # Compute score from all stored responses
        all_responses_result = await self.db.execute(
            select(StudentResponse).where(StudentResponse.attempt_id == attempt_id)
        )
        all_responses = all_responses_result.scalars().all()
        total = len(all_responses)
        correct = sum(1 for r in all_responses if r.is_correct)
        score_pct = correct / total if total > 0 else 0.0

        # Mark attempt COMPLETED
        attempt.status = AttemptStatus.COMPLETED
        attempt.completed_at = datetime.now(UTC)
        attempt.overall_score = score_pct
        if attempt.started_at is None:
            attempt.started_at = attempt.completed_at

        await self.db.flush()

        # Fire Celery task — non-blocking
        from app.tasks.gap_tasks import calculate_gap_states  # noqa: PLC0415

        calculate_gap_states.delay(str(attempt_id))

        logger.info(
            "attempt_submitted",
            attempt_id=str(attempt_id),
            student_id=str(student_id),
            score=score_pct,
            total=total,
            correct=correct,
            is_system_generated=assessment.is_system_generated,
        )

        # Tier 1 diagnostic: update enrollment onboarding status
        if assessment.is_system_generated:
            await onboarding_service.check_and_update_onboarding_complete(
                student_id=student_id,
                class_id=assessment.class_id,
            )

        return AttemptResultResponse(
            attempt_id=attempt_id,
            score=score_pct,
            total_questions=total,
            correct_count=correct,
            time_taken_seconds=None,
            submitted_at=attempt.completed_at,
        )

    # ── Results retrieval ────────────────────────────────────────────────

    async def get_attempt_results(
        self,
        attempt_id: uuid.UUID,
        requesting_user_id: uuid.UUID,
        requesting_user_role: str,
        school_id: uuid.UUID,
    ) -> AttemptResultResponse:
        """Return scored results for a completed attempt.

        Access rules:
        - STUDENT: only their own attempt.
        - TEACHER / SCHOOL_ADMIN / KAIHLE_ADMIN: any attempt in their school
          (KAIHLE_ADMIN has no school restriction).

        Args:
            attempt_id: The StudentAttempt UUID.
            requesting_user_id: The requesting user's ID.
            requesting_user_role: The requesting user's role string.
            school_id: The requesting user's school ID (multi-tenancy guard).

        Returns:
            AttemptResultResponse with score details.

        Raises:
            ValueError: If attempt not found, not yet completed, or access denied.
        """
        attempt_result = await self.db.execute(select(StudentAttempt).where(StudentAttempt.id == attempt_id))
        attempt = attempt_result.scalar_one_or_none()
        if attempt is None:
            raise ValueError(f"Attempt not found: {attempt_id}")

        if attempt.status != AttemptStatus.COMPLETED:
            raise ValueError("Attempt not yet completed")

        # Authorization
        if requesting_user_role == UserRole.STUDENT:
            if attempt.student_id != requesting_user_id:
                raise AttemptAccessDeniedError("Access denied")
        elif requesting_user_role == UserRole.KAIHLE_ADMIN:
            pass  # KaihleAdmin can access any attempt — explicit bypass per Rule 12
        else:
            # Teachers / SchoolAdmins: verify attempt belongs to same school
            assessment_result = await self.db.execute(select(Assessment).where(Assessment.id == attempt.assessment_id))
            assessment = assessment_result.scalar_one_or_none()
            if assessment is None or assessment.school_id != school_id:
                raise AttemptAccessDeniedError("Access denied")

        # Compute score from stored responses
        all_responses_result = await self.db.execute(
            select(StudentResponse).where(StudentResponse.attempt_id == attempt_id)
        )
        all_responses = all_responses_result.scalars().all()
        total = len(all_responses)
        correct = sum(1 for r in all_responses if r.is_correct)

        return AttemptResultResponse(
            attempt_id=attempt_id,
            score=attempt.overall_score if attempt.overall_score is not None else 0.0,
            total_questions=total,
            correct_count=correct,
            time_taken_seconds=attempt.time_taken_seconds,
            submitted_at=cast(datetime, attempt.completed_at),
        )

    # ── Internal helpers ─────────────────────────────────────────────────

    async def _load_and_verify_attempt(
        self,
        attempt_id: uuid.UUID,
        student_id: uuid.UUID,
        school_id: uuid.UUID,
    ) -> StudentAttempt:
        """Load a StudentAttempt and verify ownership.

        Args:
            attempt_id: The attempt UUID.
            student_id: Must match attempt.student_id.
            school_id: The student's school (used to verify via assessment.school_id).

        Returns:
            The verified StudentAttempt.

        Raises:
            ValueError: If not found or ownership mismatch.
        """
        attempt_result = await self.db.execute(select(StudentAttempt).where(StudentAttempt.id == attempt_id))
        attempt = attempt_result.scalar_one_or_none()
        if attempt is None:
            raise ValueError(f"Attempt not found: {attempt_id}")
        if attempt.student_id != student_id:
            raise ValueError("Access denied: attempt belongs to a different student")

        # Verify school via assessment
        assessment_result = await self.db.execute(select(Assessment).where(Assessment.id == attempt.assessment_id))
        assessment = assessment_result.scalar_one_or_none()
        if assessment is None or assessment.school_id != school_id:
            raise ValueError("Access denied: school mismatch")

        return attempt

    async def _load_questions(
        self,
        assessment_id: uuid.UUID,
        strip_answers: bool = True,
    ) -> list[QuestionBank]:
        """Load questions for an assessment in order_index order.

        Args:
            assessment_id: The assessment UUID.
            strip_answers: When True, sets correct_answer=None on each row.

        Returns:
            Ordered list of QuestionBank rows.
        """
        rows = (
            await self.db.execute(
                select(QuestionBank)
                .join(
                    AssessmentSelectedQuestion,
                    AssessmentSelectedQuestion.question_id == QuestionBank.id,
                )
                .where(AssessmentSelectedQuestion.assessment_id == assessment_id)
                .order_by(AssessmentSelectedQuestion.order_index)
            )
        ).all()
        questions = [row[0] for row in rows]
        if strip_answers:
            for q in questions:
                # Expunge before mutating so SQLAlchemy does not track the change
                # and cannot accidentally flush NULL back to the DB.
                self.db.expunge(q)
                q.correct_answer = None
        return questions
