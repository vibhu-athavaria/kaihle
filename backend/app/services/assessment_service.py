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
from typing import cast

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
from app.models.user import User

logger = structlog.get_logger()

# Total questions selected into assessment_selected_questions at class creation.
# This is the pool from which adaptive question selection draws at attempt time.
MAX_DIAGNOSTIC_POOL = 60

# Maximum questions a student actually answers in one diagnostic attempt.
# Stored in assessment config; enforced by the student-facing API.
MAX_DIAGNOSTIC_QUESTIONS_PER_ATTEMPT = 20


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

        # Load subject name for assessment title
        subject_result = await self.db.execute(select(Subject).where(Subject.id == class_.subject_id))
        subject = subject_result.scalar_one_or_none()
        subject_name = subject.name if subject else "Unknown Subject"

        title = f"Onboarding Diagnostic — {subject_name} ({class_.name})"

        assessment = Assessment(
            id=uuid.uuid4(),
            class_id=class_.id,
            created_by=None,  # NULL = system-created, no teacher owner
            title=title,
            assessment_type=AssessmentType.DIAGNOSTIC,
            status=AssessmentStatus.ACTIVE,  # immediately active for students
            is_system_generated=True,
            curriculum_topic_id=None,  # broad sweep, not topic-specific
            config={"max_questions_per_attempt": MAX_DIAGNOSTIC_QUESTIONS_PER_ATTEMPT},
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
        result = await self.db.execute(select(Class).where(Class.id == class_id))
        class_ = result.scalar_one_or_none()
        if class_ is None:
            raise ValueError(f"Class not found: class_id={class_id}")

        # Verify student exists and belongs to the same school
        result = await self.db.execute(select(User).where(User.id == student_id))
        student = result.scalar_one_or_none()
        if student is None:
            raise ValueError(f"Student not found: student_id={student_id}")
        if student.school_id != class_.school_id:
            raise ValueError(f"Student school_id {student.school_id} does not match class school_id {class_.school_id}")

        # Find the system-generated diagnostic for this class
        result = await self.db.execute(
            select(Assessment).where(
                Assessment.class_id == class_.id,
                Assessment.is_system_generated.is_(True),
            )
        )
        assessment = result.scalar_one_or_none()
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
        existing_attempt = cast(StudentAttempt | None, result.scalar_one_or_none())
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

        Strategy: distribute questions evenly across all active curriculum topics
        for the curriculum+subject+grade combination. If total available < pool size,
        use all available.

        Args:
            curriculum_id: The curriculum UUID.
            subject_id: The subject UUID.
            grade_id: The grade UUID.

        Returns:
            Ordered list of question UUIDs to include in the assessment pool.
        """
        topics_result = await self.db.execute(
            select(CurriculumTopic).where(
                CurriculumTopic.curriculum_id == curriculum_id,
                CurriculumTopic.subject_id == subject_id,
                CurriculumTopic.grade_id == grade_id,
                CurriculumTopic.is_active.is_(True),
            )
        )
        topics = list(topics_result.scalars().all())

        if not topics:
            logger.warning(
                "no_curriculum_topics_found",
                curriculum_id=str(curriculum_id),
                subject_id=str(subject_id),
                grade_id=str(grade_id),
            )
            return []

        # Distribute pool budget evenly across topics
        per_topic = max(1, MAX_DIAGNOSTIC_POOL // len(topics))
        remainder = MAX_DIAGNOSTIC_POOL - (per_topic * len(topics))

        selected: list[uuid.UUID] = []

        for topic in topics:
            n = per_topic + (1 if remainder > 0 else 0)
            if remainder > 0:
                remainder -= 1

            topic_questions = await self._sample_questions_for_topic(topic.id, n)
            selected.extend(topic_questions)

            if len(selected) >= MAX_DIAGNOSTIC_POOL:
                break

        return selected[:MAX_DIAGNOSTIC_POOL]

    async def _sample_questions_for_topic(
        self,
        curriculum_topic_id: uuid.UUID,
        n: int,
    ) -> list[uuid.UUID]:
        """Sample up to n active questions from subtopics under a curriculum topic.

        Args:
            curriculum_topic_id: The curriculum topic UUID.
            n: Maximum number of questions to sample.

        Returns:
            List of sampled question UUIDs.
        """
        result = await self.db.execute(
            select(QuestionBank.id)
            .join(Subtopic, QuestionBank.subtopic_id == Subtopic.id)
            .where(
                Subtopic.curriculum_topic_id == curriculum_topic_id,
                QuestionBank.is_active.is_(True),
                Subtopic.is_active.is_(True),
            )
        )
        question_ids = [row[0] for row in result.all()]

        if not question_ids:
            return []

        sample_size = min(n, len(question_ids))
        return random.sample(question_ids, sample_size)
