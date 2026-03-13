"""Assessment service for creating and managing assessments.

Handles system-generated (Tier 1) and teacher-created (Tier 2) assessments.

Design:
- Assessment = "what is being tested" (questions, config, type) — created once per class.
- StudentAttempt = "who is taking it" — created per student enrollment.
- Tier 1 diagnostics use a question pool of MAX_DIAGNOSTIC_POOL (60) questions,
  but each student answers at most MAX_DIAGNOSTIC_QUESTIONS_PER_ATTEMPT (20)
  via adaptive selection at the attempt/UI layer.
"""

import random
import uuid

import structlog
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
from app.models.curriculum import CurriculumTopic, QuestionBank, Subject, Subtopic
from app.models.school import Class
from app.models.user import User, UserRole

logger = structlog.get_logger()

# Total questions selected into assessment_selected_questions at class creation.
# This is the pool from which adaptive question selection draws at attempt time.
MAX_DIAGNOSTIC_POOL = 60

# Maximum questions a student actually answers in one diagnostic attempt.
# Stored in assessment config; enforced by the student-facing API.
MAX_DIAGNOSTIC_QUESTIONS_PER_ATTEMPT = 20

# System user ID used for system-generated assessments.
# This is a placeholder - in production, this would be a real system user.
SYSTEM_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")


def _make_system_assessment(class_id: uuid.UUID, title: str) -> Assessment:
    """Construct a system-generated Assessment.

    System-generated assessments use a fixed system user ID to satisfy the
    NOT NULL constraint on created_by. The is_system_generated flag
    distinguishes system-created from teacher-created assessments.

    Args:
        class_id: The class this assessment belongs to.
        title: Human-readable title.

    Returns:
        An unsaved Assessment instance with is_system_generated=True.
    """
    return Assessment(
        id=uuid.uuid4(),
        class_id=class_id,
        created_by=SYSTEM_USER_ID,
        title=title,
        assessment_type=AssessmentType.DIAGNOSTIC,
        status=AssessmentStatus.ACTIVE,  # immediately active for students
        is_system_generated=True,
        curriculum_topic_id=None,  # broad sweep, not topic-specific
        config={"max_questions_per_attempt": MAX_DIAGNOSTIC_QUESTIONS_PER_ATTEMPT},
    )


class AssessmentService:
    """Service for assessment-related operations."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Class-level: create diagnostic assessment ────────────────────────

    async def create_class_diagnostic(self, class_id: uuid.UUID) -> Assessment:
        """Create or retrieve a Tier 1 DIAGNOSTIC assessment for a class.

        Called when a class is created. Selects a pool of up to MAX_DIAGNOSTIC_POOL
        questions spanning all curriculum topics for the class's subject+grade.
        Idempotent — returns existing assessment if one already exists.

        Args:
            class_id: The class UUID.

        Returns:
            The existing or newly created Assessment.

        Raises:
            ValueError: If the class is not found.
        """
        # Load class
        result = await self.db.execute(select(Class).where(Class.id == class_id))
        class_ = result.scalar_one_or_none()
        if class_ is None:
            raise ValueError(f"Class not found: class_id={class_id}")

        # Idempotency: check if system-generated assessment already exists
        existing = await self.db.execute(
            select(Assessment).where(
                Assessment.class_id == class_.id,
                Assessment.is_system_generated.is_(True),
            )
        )
        existing_assessment = existing.scalar_one_or_none()
        if existing_assessment is not None:
            logger.debug(
                "class_diagnostic_already_exists",
                class_id=str(class_.id),
                assessment_id=str(existing_assessment.id),
            )
            return existing_assessment

        # Load subject name for assessment title (single query, not N+1)
        subject_result = await self.db.execute(select(Subject.name).where(Subject.id == class_.subject_id))
        subject_name = subject_result.scalar_one_or_none() or "Unknown Subject"

        title = f"Onboarding Diagnostic — {subject_name} ({class_.name})"

        assessment = _make_system_assessment(
            class_id=class_.id,
            title=title,
        )
        self.db.add(assessment)
        await self.db.flush()

        # Select question pool spanning all curriculum_topics
        question_ids = await self._select_questions_for_diagnostic(
            curriculum_id=class_.curriculum_id,
            subject_id=class_.subject_id,
            grade_id=class_.grade_id,
        )

        for order_index, question_id in enumerate(question_ids):
            bridge = AssessmentSelectedQuestion(
                assessment_id=assessment.id,
                question_id=question_id,
                order_index=order_index,
            )
            self.db.add(bridge)

        logger.info(
            "class_diagnostic_created",
            class_id=str(class_.id),
            assessment_id=str(assessment.id),
            pool_size=len(question_ids),
            max_per_attempt=MAX_DIAGNOSTIC_QUESTIONS_PER_ATTEMPT,
        )
        return assessment

    # ── Student-level: create attempt on enrollment ──────────────────────

    async def create_diagnostic_attempt(
        self,
        student_id: uuid.UUID,
        class_id: uuid.UUID,
    ) -> StudentAttempt:
        """Create a student attempt for the class's Tier 1 diagnostic assessment.

        Called when a student is enrolled in a class. The diagnostic assessment
        must already exist for the class (created at class creation time).
        Idempotent — returns existing attempt if one already exists for this
        student+assessment combination.

        Args:
            student_id: The student user ID.
            class_id: The class UUID.

        Returns:
            The existing or newly created StudentAttempt.

        Raises:
            ValueError: If class, student, or diagnostic assessment is not found,
                        or if student does not belong to the class's school.
        """
        # Load class
        class_result = await self.db.execute(select(Class).where(Class.id == class_id))
        class_ = class_result.scalar_one_or_none()
        if class_ is None:
            raise ValueError(f"Class not found: class_id={class_id}")

        # Verify student exists, has STUDENT role, and belongs to the same school
        user_result = await self.db.execute(select(User).where(User.id == student_id))
        student: User | None = user_result.scalar_one_or_none()
        if student is None:
            raise ValueError(f"Student not found: student_id={student_id}")
        if student.role != UserRole.STUDENT:
            raise ValueError(f"User student_id={student_id} has role '{student.role}', expected STUDENT")
        if student.school_id != class_.school_id:
            raise ValueError(f"Student school_id {student.school_id} does not match class school_id {class_.school_id}")

        # Find the system-generated diagnostic for this class
        assessment_result = await self.db.execute(
            select(Assessment).where(
                Assessment.class_id == class_.id,
                Assessment.is_system_generated.is_(True),
            )
        )
        assessment = assessment_result.scalar_one_or_none()
        if assessment is None:
            raise ValueError(
                f"No system-generated diagnostic found for class_id={class_id}. "
                f"Ensure create_class_diagnostic() was called first."
            )

        # Idempotency: check if attempt already exists for this student+assessment
        result = await self.db.execute(
            select(StudentAttempt).where(
                StudentAttempt.assessment_id == assessment.id,
                StudentAttempt.student_id == student_id,
            )
        )
        existing_attempt = result.scalar_one_or_none()
        if existing_attempt is not None:
            logger.debug(
                "diagnostic_attempt_already_exists",
                student_id=str(student_id),
                assessment_id=str(assessment.id),
                attempt_id=str(existing_attempt.id),
            )
            return existing_attempt

        # Count questions in the pool for total_questions
        q_count_result = await self.db.execute(
            select(AssessmentSelectedQuestion.question_id).where(
                AssessmentSelectedQuestion.assessment_id == assessment.id
            )
        )
        pool_size = len(q_count_result.all())

        attempt = StudentAttempt(
            id=uuid.uuid4(),
            assessment_id=assessment.id,
            student_id=student_id,
            status=AttemptStatus.NOT_STARTED,
            total_questions=pool_size,
        )
        self.db.add(attempt)

        logger.info(
            "diagnostic_attempt_created",
            student_id=str(student_id),
            assessment_id=str(assessment.id),
            attempt_id=str(attempt.id),
            pool_size=pool_size,
        )
        return attempt

    # ── Question selection ───────────────────────────────────────────────

    async def _select_questions_for_diagnostic(
        self,
        curriculum_id: uuid.UUID,
        subject_id: uuid.UUID,
        grade_id: uuid.UUID,
    ) -> list[uuid.UUID]:
        """Select up to MAX_DIAGNOSTIC_POOL questions spread across curriculum topics.

        Strategy: fetch all questions for the curriculum+subject+grade in a single
        query grouped by curriculum_topic_id, then distribute evenly in Python.
        Uses a deterministic seed derived from curriculum+subject+grade so the same
        class always produces the same question pool.

        Args:
            curriculum_id: The curriculum UUID.
            subject_id: The subject UUID.
            grade_id: The grade UUID.

        Returns:
            Ordered list of question UUIDs to include in the assessment pool.
        """
        # Single query: fetch all active questions with their topic, for this
        # curriculum+subject+grade combination. Eliminates N+1 per topic.
        rows = await self.db.execute(
            select(CurriculumTopic.id, QuestionBank.id)
            .join(Subtopic, Subtopic.curriculum_topic_id == CurriculumTopic.id)
            .join(QuestionBank, QuestionBank.subtopic_id == Subtopic.id)
            .where(
                CurriculumTopic.curriculum_id == curriculum_id,
                CurriculumTopic.subject_id == subject_id,
                CurriculumTopic.grade_id == grade_id,
                CurriculumTopic.is_active.is_(True),
                Subtopic.is_active.is_(True),
                QuestionBank.is_active.is_(True),
            )
        )

        # Group question IDs by topic ID
        questions_by_topic: dict[uuid.UUID, list[uuid.UUID]] = {}
        for topic_id, question_id in rows.all():
            questions_by_topic.setdefault(topic_id, []).append(question_id)

        if not questions_by_topic:
            logger.warning(
                "no_questions_found_for_diagnostic",
                curriculum_id=str(curriculum_id),
                subject_id=str(subject_id),
                grade_id=str(grade_id),
            )
            return []

        # Deterministic seed derived from curriculum+subject+grade so the same
        # class always produces the same question pool order.
        seed = int(curriculum_id) ^ int(subject_id) ^ int(grade_id)
        rng = random.Random(seed)  # noqa: S311 — not used for cryptography

        # Distribute pool budget evenly across topics
        topics = list(questions_by_topic.keys())
        per_topic = max(1, MAX_DIAGNOSTIC_POOL // len(topics))
        remainder = MAX_DIAGNOSTIC_POOL - (per_topic * len(topics))

        selected: list[uuid.UUID] = []
        for topic_id in topics:
            n = per_topic + (1 if remainder > 0 else 0)
            if remainder > 0:
                remainder -= 1

            pool = questions_by_topic[topic_id]
            sample_size = min(n, len(pool))
            selected.extend(rng.sample(pool, sample_size))

            if len(selected) >= MAX_DIAGNOSTIC_POOL:
                break

        return selected[:MAX_DIAGNOSTIC_POOL]
