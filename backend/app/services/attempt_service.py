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

import random as _random
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
    AssessmentType,
    AttemptStatus,
    ScoredBy,
    StudentAttempt,
    StudentResponse,
)
from app.models.curriculum import CurriculumTopic, QuestionBank, Subtopic, Topic
from app.models.school import ClassEnrollment
from app.models.user import UserRole
from app.schemas.attempts import (
    AttemptDetailResponse,
    AttemptResultResponse,
    AttemptReviewItem,
    AttemptReviewResponse,
    QuestionDetailItem,
)

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

    # ── diagnostic ─────────────────────────────────────────────

    async def get_class_diagnostic(
        self,
        class_id: uuid.UUID,
        student_id: uuid.UUID,
        school_id: uuid.UUID,
    ) -> tuple[StudentAttempt, Assessment, list[QuestionBank], list[StudentResponse]]:
        """Return the student's diagnostic attempt for a class.

        Args:
            class_id: The class UUID.
            student_id: The requesting student's user ID.
            school_id: The student's school (for multi-tenancy guard).

        Returns:
            (StudentAttempt, Assessment, questions_without_correct_answer, existing_responses)

        Raises:
            ValueError: If no ACTIVE DIAGNOSTIC assessment is found for the class.
            AttemptNotFoundError: If the student's attempt row does not yet exist.
        """
        # Step 1 — find the ACTIVE DIAGNOSTIC assessment for this class
        assessment_result = await self.db.execute(
            select(Assessment).where(
                Assessment.class_id == class_id,
                Assessment.school_id == school_id,
                Assessment.assessment_type == AssessmentType.DIAGNOSTIC,
                Assessment.status == AssessmentStatus.ACTIVE,
            )
        )
        assessment = assessment_result.scalar_one_or_none()
        if assessment is None:
            logger.warning(
                "no_active_diagnostic",
                class_id=str(class_id),
                school_id=str(school_id),
            )
            raise ValueError("No active diagnostic found for this class")

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

        # Apply per-student question limit from assessment.question_count.
        # The pool may have up to MAX_DIAGNOSTIC_POOL questions; each student
        # sees at most question_count. Sample is seeded by student_id
        # so the same student always sees the same subset on revisit.
        max_per_attempt = assessment.question_count
        if max_per_attempt and len(questions) > max_per_attempt:
            rng = _random.Random(str(student_id))
            questions = rng.sample(questions, max_per_attempt)

        # Load existing responses for resume
        responses_result = await self.db.execute(
            select(StudentResponse).where(StudentResponse.attempt_id == attempt.id)
        )
        responses = list(responses_result.scalars().all())

        return attempt, assessment, questions, responses

    # ── Tier 2: lazy attempt creation ───────────────────────────────────

    async def get_or_create_attempt(
        self,
        assessment_id: uuid.UUID,
        student_id: uuid.UUID,
        school_id: uuid.UUID,
    ) -> tuple[StudentAttempt, Assessment, list[QuestionBank], list[StudentResponse]]:
        """Return existing attempt or create one if the student is enrolled.

        Used for Tier 2 (teacher-created) assessments where the attempt is
        created lazily on first access rather than pre-created at enrollment.

        Args:
            assessment_id: The assessment UUID.
            student_id: The requesting student's user ID.
            school_id: The student's school (for multi-tenancy guard).

        Returns:
            (StudentAttempt, Assessment, questions_without_correct_answer, existing_responses)

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

            # Load existing responses for resume
            responses_result = await self.db.execute(
                select(StudentResponse).where(StudentResponse.attempt_id == existing_attempt.id)
            )
            responses = list(responses_result.scalars().all())

            return existing_attempt, assessment, questions, responses

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
        return attempt, assessment, questions, []

    # ── Attempt retrieval ─────────────────────────────────────────────────

    async def get_attempt(
        self,
        attempt_id: uuid.UUID,
        requesting_user_id: uuid.UUID,
        requesting_user_role: UserRole,
        school_id: uuid.UUID | None,
    ) -> tuple[StudentAttempt, Assessment, list[QuestionBank], list[StudentResponse]]:
        """Return an existing attempt with its questions.

        Access rules:
        - STUDENT: only their own attempt.
        - TEACHER / SCHOOL_ADMIN: attempt must belong to same school.
        - KAIHLE_ADMIN: unrestricted.

        Args:
            attempt_id: The StudentAttempt UUID.
            requesting_user_id: The requesting user's ID.
            requesting_user_role: The requesting user's role.
            school_id: The requesting user's school ID (None for KAIHLE_ADMIN).

        Returns:
            (StudentAttempt, Assessment, questions_without_correct_answer, existing_responses)

        Raises:
            AttemptNotFoundError: If attempt not found.
            AttemptAccessDeniedError: If access denied.
        """
        # Load attempt
        attempt_result = await self.db.execute(select(StudentAttempt).where(StudentAttempt.id == attempt_id))
        attempt = attempt_result.scalar_one_or_none()
        if attempt is None:
            raise AttemptNotFoundError(f"Attempt not found: {attempt_id}")

        # Authorization
        if requesting_user_role == UserRole.STUDENT:
            if attempt.student_id != requesting_user_id:
                raise AttemptAccessDeniedError("Access denied")
        elif requesting_user_role == UserRole.KAIHLE_ADMIN:
            pass  # KAIHLE_ADMIN bypasses school check
        else:
            # TEACHER / SCHOOL_ADMIN: verify attempt belongs to same school
            assessment_result = await self.db.execute(select(Assessment).where(Assessment.id == attempt.assessment_id))
            assessment = assessment_result.scalar_one_or_none()
            if assessment is None or (school_id is not None and assessment.school_id != school_id):
                raise AttemptAccessDeniedError("Access denied")

        # Load assessment and questions
        assessment_result = await self.db.execute(select(Assessment).where(Assessment.id == attempt.assessment_id))
        assessment = assessment_result.scalar_one_or_none()
        if assessment is None:
            raise AttemptNotFoundError(f"Assessment not found for attempt: {attempt_id}")

        questions = await self._load_questions(attempt.assessment_id, strip_answers=True)

        # Load existing responses for resume
        responses_result = await self.db.execute(
            select(StudentResponse).where(StudentResponse.attempt_id == attempt_id)
        )
        responses = list(responses_result.scalars().all())

        # Start the clock the moment the student opens the assessment.
        # This ensures the timer is accurate even if the student hasn't answered yet.
        if attempt.started_at is None and attempt.status != AttemptStatus.COMPLETED:
            attempt.started_at = datetime.now(UTC)
            await self.db.flush()

        return attempt, assessment, questions, responses

    # ── Per-question response ────────────────────────────────────────────

    async def submit_response(
        self,
        attempt_id: uuid.UUID,
        student_id: uuid.UUID,
        school_id: uuid.UUID,
        question_id: uuid.UUID,
        selected_key: str,
        time_taken_ms: int | None = None,
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
            time_taken_ms: Milliseconds the student spent on this question (optional).

        Raises:
            ValueError: If attempt not found or belongs to a different student/school.
            AttemptAlreadyCompletedError: If attempt.status == COMPLETED.
            QuestionNotInAssessmentError: If question_id not in assessment.
            Note: If a response for this question already exists, it is updated (upsert).
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

        # Load existing response for this (attempt, question) pair
        existing_result = await self.db.execute(
            select(StudentResponse).where(
                StudentResponse.attempt_id == attempt_id,
                StudentResponse.question_id == question_id,
            )
        )
        existing_response = existing_result.scalar_one_or_none()

        # Load question for scoring
        question_result = await self.db.execute(select(QuestionBank).where(QuestionBank.id == question_id))
        question = question_result.scalar_one_or_none()
        if question is None:
            raise QuestionNotInAssessmentError(f"Question {question_id} not found in question bank")

        is_correct = selected_key.strip().lower() == question.correct_answer.strip().lower()

        if existing_response is not None:
            # Upsert: update existing response so students can change answers mid-assessment
            existing_response.answer_given = selected_key
            existing_response.is_correct = is_correct
            existing_response.score = 1.0 if is_correct else 0.0
            existing_response.time_taken_ms = time_taken_ms
            logger.info(
                "response_updated",
                attempt_id=str(attempt_id),
                question_id=str(question_id),
                is_correct=is_correct,
            )
        else:
            response = StudentResponse(
                id=uuid.uuid4(),
                attempt_id=attempt_id,
                question_id=question_id,
                answer_given=selected_key,
                is_correct=is_correct,
                score=1.0 if is_correct else 0.0,
                scored_by=ScoredBy.RULE,
                time_taken_ms=time_taken_ms,
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
        timed_out: bool = False,
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

        # Load assessment to check type
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

        # When the client timer expired, mark unanswered questions as wrong —
        # but ONLY the questions that were actually shown to this student.
        # The pool in AssessmentSelectedQuestion may be larger than question_count;
        # marking the full pool would corrupt the score denominator and gap_states
        # with questions the student never saw.
        if timed_out:
            answered_result = await self.db.execute(
                select(StudentResponse.question_id).where(StudentResponse.attempt_id == attempt_id)
            )
            answered_ids: set[uuid.UUID] = {row[0] for row in answered_result.all()}

            # Reconstruct this student's assigned question subset using the same
            # seeded RNG as get_class_diagnostic — same seed → same subset.
            all_question_ids_result = await self.db.execute(
                select(AssessmentSelectedQuestion.question_id)
                .where(AssessmentSelectedQuestion.assessment_id == attempt.assessment_id)
                .order_by(AssessmentSelectedQuestion.order_index)
            )
            all_pool_ids: list[uuid.UUID] = [q_id for (q_id,) in all_question_ids_result.all()]

            max_per_attempt = assessment.question_count
            if max_per_attempt and len(all_pool_ids) > max_per_attempt:
                rng = _random.Random(str(student_id))
                assigned_ids: list[uuid.UUID] = rng.sample(all_pool_ids, max_per_attempt)
            else:
                assigned_ids = all_pool_ids

            unanswered_rows = [q_id for q_id in assigned_ids if q_id not in answered_ids]
            for q_id in unanswered_rows:
                self.db.add(
                    StudentResponse(
                        id=uuid.uuid4(),
                        attempt_id=attempt_id,
                        question_id=q_id,
                        answer_given="",
                        is_correct=False,
                        score=0.0,
                        scored_by=ScoredBy.RULE,
                        time_taken_ms=None,
                    )
                )

            await self.db.flush()
            logger.info(
                "timed_out_unanswered_marked_wrong",
                attempt_id=str(attempt_id),
                assigned_count=len(assigned_ids),
                unanswered_count=len(unanswered_rows),
            )

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

        # Fire Celery task — non-blocking.
        # Skip if the student submitted with zero real answers (e.g. blank timed-out
        # submit). The gap service filters empty-string responses but firing the task
        # for a fully blank attempt just wastes a worker and logs a misleading skip.
        real_answer_count = sum(1 for r in all_responses if r.answer_given and r.answer_given.strip())
        if real_answer_count == 0:
            logger.warning(
                "attempt_submitted_all_blank_gap_calculation_skipped",
                attempt_id=str(attempt_id),
                student_id=str(student_id),
            )
        else:
            from app.tasks.gap_tasks import calculate_gap_states  # noqa: PLC0415

            calculate_gap_states.delay(str(attempt_id))

        logger.info(
            "attempt_submitted",
            attempt_id=str(attempt_id),
            student_id=str(student_id),
            score=score_pct,
            total=total,
            correct=correct,
            is_diagnostic=assessment.assessment_type == AssessmentType.DIAGNOSTIC,
        )

        # Tier 1 diagnostic: update enrollment onboarding status
        if assessment.assessment_type == AssessmentType.DIAGNOSTIC:
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

    async def get_attempt_detail(
        self,
        attempt_id: uuid.UUID,
        requesting_user_id: uuid.UUID,
        requesting_user_role: str,
        school_id: uuid.UUID,
    ) -> AttemptDetailResponse:
        """Return per-question breakdown for teacher review of a completed attempt.

        Includes subtopic name, topic name, difficulty level, the key selected by
        the student, the correct key, and whether it was correct.

        Access rules — same as get_attempt_results:
        - STUDENT: only their own attempt.
        - TEACHER / SCHOOL_ADMIN: attempt must belong to their school.
        - KAIHLE_ADMIN: unrestricted (CONSTITUTION Rule 12).

        Args:
            attempt_id: The StudentAttempt UUID.
            requesting_user_id: ID of the requesting user.
            requesting_user_role: Role string.
            school_id: Multi-tenancy guard (ignored for KAIHLE_ADMIN).

        Returns:
            AttemptDetailResponse with per-question breakdown.

        Raises:
            ValueError: Attempt not found or not yet completed.
            AttemptAccessDeniedError: Cross-school or student own-attempt violation.
        """
        attempt = await self.db.get(StudentAttempt, attempt_id)
        if attempt is None:
            raise ValueError(f"Attempt not found: {attempt_id}")
        if attempt.status != AttemptStatus.COMPLETED:
            raise ValueError("Attempt not yet completed")

        assessment = await self.db.get(Assessment, attempt.assessment_id)

        # Authorization
        if requesting_user_role == UserRole.STUDENT:
            if attempt.student_id != requesting_user_id:
                raise AttemptAccessDeniedError("Access denied")
        elif requesting_user_role != UserRole.KAIHLE_ADMIN:
            if assessment is None or assessment.school_id != school_id:
                raise AttemptAccessDeniedError("Access denied")

        # Load responses
        responses_result = await self.db.execute(
            select(StudentResponse).where(StudentResponse.attempt_id == attempt_id)
        )
        responses = responses_result.scalars().all()
        response_map = {r.question_id: r for r in responses}
        question_ids = list(response_map.keys())

        # Load questions with subtopic and topic names via single JOIN query
        rows = (
            await self.db.execute(
                select(
                    QuestionBank.id.label("id"),
                    QuestionBank.question_text.label("question_text"),
                    QuestionBank.correct_answer.label("correct_answer"),
                    QuestionBank.difficulty_level.label("difficulty_level"),
                    Subtopic.name.label("subtopic_name"),
                    Topic.name.label("topic_name"),
                )
                .join(Subtopic, Subtopic.id == QuestionBank.subtopic_id)
                .join(CurriculumTopic, CurriculumTopic.id == Subtopic.curriculum_topic_id)
                .join(Topic, Topic.id == CurriculumTopic.topic_id)
                .where(QuestionBank.id.in_(question_ids))
            )
        ).all()

        question_detail_map = {row.id: row for row in rows}

        questions: list[QuestionDetailItem] = []
        for position, (q_id, resp) in enumerate(response_map.items(), start=1):
            row = question_detail_map.get(q_id)
            if row is None:
                continue
            questions.append(
                QuestionDetailItem(
                    question_id=q_id,
                    question_text=row.question_text,
                    subtopic_name=row.subtopic_name,
                    topic_name=row.topic_name,
                    difficulty_level=row.difficulty_level or 0,
                    selected_key=resp.answer_given,
                    correct_answer=row.correct_answer,
                    is_correct=bool(resp.is_correct),
                    position=resp.position if hasattr(resp, "position") else position,
                )
            )

        # Sort by position for consistent ordering
        questions.sort(key=lambda q: q.position)

        from app.models.user import User

        user_result = await self.db.execute(
            select(User.first_name, User.last_name).where(User.id == attempt.student_id)
        )
        user_row = user_result.one_or_none()
        student_name = f"{user_row.first_name or ''} {user_row.last_name or ''}".strip() if user_row else "Unknown"

        logger.info(
            "attempt_detail_fetched",
            attempt_id=str(attempt_id),
            question_count=len(questions),
            requesting_role=requesting_user_role,
        )

        return AttemptDetailResponse(
            attempt_id=attempt_id,
            assessment_id=attempt.assessment_id,
            assessment_title=assessment.title if assessment else "",
            assessment_type=assessment.assessment_type if assessment else "",
            student_id=attempt.student_id,
            student_name=student_name,
            score=attempt.overall_score,
            submitted_at=attempt.completed_at,
            status=attempt.status.value if hasattr(attempt.status, "value") else str(attempt.status),
            questions=questions,
        )

    async def get_attempt_review(
        self,
        attempt_id: uuid.UUID,
        student_id: uuid.UUID,
        school_id: uuid.UUID,
    ) -> AttemptReviewResponse:
        """Return the per-question review for a student after they complete an attempt.

        Only the owning student may call this. Only available once the attempt is COMPLETED.

        Args:
            attempt_id: The StudentAttempt UUID.
            student_id: The requesting student (ownership check).
            school_id: The student's school (multi-tenancy guard).

        Returns:
            AttemptReviewResponse with every question, the student's selection, and correct answer.

        Raises:
            AttemptNotFoundError: Attempt not found or doesn't belong to this student/school.
            AttemptAccessDeniedError: Ownership mismatch.
            ValueError: Attempt not yet completed.
        """
        attempt = await self.db.get(StudentAttempt, attempt_id)
        if attempt is None or attempt.student_id != student_id:
            raise AttemptAccessDeniedError("Access denied")

        if attempt.status != AttemptStatus.COMPLETED:
            raise ValueError("Attempt not yet completed")

        assessment = await self.db.get(Assessment, attempt.assessment_id)
        if assessment is None or assessment.school_id != school_id:
            raise AttemptAccessDeniedError("Access denied")

        # Load all responses for this attempt
        responses_result = await self.db.execute(
            select(StudentResponse).where(StudentResponse.attempt_id == attempt_id)
        )
        responses = responses_result.scalars().all()
        response_map = {r.question_id: r for r in responses}
        question_ids = list(response_map.keys())

        # Load question details with subtopic and topic names
        rows = (
            await self.db.execute(
                select(
                    QuestionBank.id.label("id"),
                    QuestionBank.question_text.label("question_text"),
                    QuestionBank.correct_answer.label("correct_answer"),
                    QuestionBank.difficulty_level.label("difficulty_level"),
                    QuestionBank.options.label("options"),
                    Subtopic.name.label("subtopic_name"),
                    Topic.name.label("topic_name"),
                )
                .join(Subtopic, Subtopic.id == QuestionBank.subtopic_id)
                .join(CurriculumTopic, CurriculumTopic.id == Subtopic.curriculum_topic_id)
                .join(Topic, Topic.id == CurriculumTopic.topic_id)
                .where(QuestionBank.id.in_(question_ids))
            )
        ).all()

        question_map = {row.id: row for row in rows}

        review_items: list[AttemptReviewItem] = []
        for position, (q_id, resp) in enumerate(response_map.items(), start=1):
            row = question_map.get(q_id)
            if row is None:
                continue

            raw_options: list[dict[str, str]] = row.options or []
            options_list = sorted(raw_options, key=lambda o: o.get("key", ""))

            selected = resp.answer_given if resp.answer_given else None

            review_items.append(
                AttemptReviewItem(
                    position=position,
                    question_id=q_id,
                    question_text=row.question_text,
                    subtopic_name=row.subtopic_name,
                    topic_name=row.topic_name,
                    difficulty_level=row.difficulty_level or 0,
                    options=options_list,
                    selected_key=selected,
                    correct_answer=row.correct_answer,
                    is_correct=bool(resp.is_correct),
                )
            )

        review_items.sort(key=lambda item: item.position)

        total = len(review_items)
        correct = sum(1 for item in review_items if item.is_correct)

        logger.info(
            "attempt_review_fetched",
            attempt_id=str(attempt_id),
            student_id=str(student_id),
            question_count=total,
        )

        return AttemptReviewResponse(
            attempt_id=attempt_id,
            assessment_id=attempt.assessment_id,
            title=assessment.title,
            score=attempt.overall_score if attempt.overall_score is not None else 0.0,
            correct_count=correct,
            total_questions=total,
            time_limit_minutes=assessment.time_limit_minutes,
            timed_out=assessment.time_limit_minutes > 0
            and attempt.completed_at is not None
            and attempt.started_at is not None
            and (attempt.completed_at - attempt.started_at).total_seconds() > assessment.time_limit_minutes * 60,
            questions=review_items,
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
