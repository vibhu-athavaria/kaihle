"""Assessment service for creating and managing assessments.

Handles system-generated (Tier 1) and teacher-created (Tier 2) assessments.
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
from app.models.user import User

logger = structlog.get_logger()

MAX_DIAGNOSTIC_QUESTIONS = 20


class AssessmentService:
    """Service for assessment-related operations."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_system_diagnostic(
        self,
        student_id: uuid.UUID,
        class_id: uuid.UUID,
    ) -> list[Assessment]:
        """Create one Tier 1 DIAGNOSTIC assessment per subject for the student's class.

        This is idempotent — safe to call multiple times. Already-existing system-generated
        assessments for this class+student are skipped, not duplicated.

        Args:
            student_id: The student user ID.
            class_id: The class UUID the student is enrolled in.

        Returns:
            List of newly created Assessment rows (empty if all already existed).

        Raises:
            ValueError: If the class or student record is not found.
        """
        # 1. Load class — get school_id, curriculum_id, grade_id, subject_id
        result = await self.db.execute(select(Class).where(Class.id == class_id))
        class_ = result.scalar_one_or_none()
        if class_ is None:
            raise ValueError(f"Class not found: class_id={class_id}")

        # 2. Verify student belongs to this school
        result = await self.db.execute(select(User).where(User.id == student_id))
        student = result.scalar_one_or_none()
        if student is None:
            raise ValueError(f"Student not found: student_id={student_id}")
        if student.school_id != class_.school_id:
            raise ValueError(f"Student school_id {student.school_id} does not match class school_id {class_.school_id}")

        # 3. Each class is for one subject. Build the list of (subject_id,) to process.
        #    A class has exactly one subject, but check idempotency per-class.
        subjects_to_process = [(class_.subject_id,)]

        created: list[Assessment] = []
        for (subject_id,) in subjects_to_process:
            assessment = await self._create_subject_diagnostic_if_not_exists(
                class_=class_,
                subject_id=subject_id,
                student_id=student_id,
            )
            if assessment is not None:
                created.append(assessment)

        logger.info(
            "system_diagnostics_created",
            student_id=str(student_id),
            class_id=str(class_id),
            new_assessments=len(created),
        )
        return created

    async def _create_subject_diagnostic_if_not_exists(
        self,
        class_: Class,
        subject_id: uuid.UUID,
        student_id: uuid.UUID,
    ) -> Assessment | None:
        """Create a single system diagnostic for a subject if one doesn't already exist.

        Idempotency check: if an is_system_generated=TRUE assessment already exists
        for this class_id, skip and return None.

        Args:
            class_: The Class ORM object.
            subject_id: Subject for which to create the diagnostic.
            student_id: The student this diagnostic is for.

        Returns:
            The created Assessment, or None if already existed.
        """
        # Idempotency: check if system-generated assessment already exists for this class
        existing = await self.db.execute(
            select(Assessment).where(
                Assessment.class_id == class_.id,
                Assessment.is_system_generated.is_(True),
            )
        )
        if existing.scalar_one_or_none() is not None:
            logger.debug(
                "system_diagnostic_already_exists",
                class_id=str(class_.id),
                subject_id=str(subject_id),
            )
            return None

        # Load subject name for assessment title
        subject_result = await self.db.execute(select(Subject).where(Subject.id == subject_id))
        subject = subject_result.scalar_one_or_none()
        subject_name = subject.name if subject else "Unknown Subject"

        # Build assessment title using class name for grade context
        title = f"Onboarding Diagnostic — {subject_name} ({class_.name})"

        # Create assessment row (created_by=NULL for system-generated)
        assessment = Assessment(
            id=uuid.uuid4(),
            class_id=class_.id,
            created_by=None,  # NULL = system-created, no teacher owner
            title=title,
            assessment_type=AssessmentType.DIAGNOSTIC,
            status=AssessmentStatus.ACTIVE,  # immediately active
            is_system_generated=True,
            curriculum_topic_id=None,  # broad sweep, not topic-specific
            config={},
        )
        self.db.add(assessment)
        await self.db.flush()  # get assessment.id before inserting questions

        # Select questions spanning all curriculum_topics
        question_ids = await self._select_questions_for_diagnostic(
            curriculum_id=class_.curriculum_id,
            subject_id=subject_id,
            grade_id=class_.grade_id,
        )

        # Insert assessment_selected_questions bridge rows
        for order_index, question_id in enumerate(question_ids):
            bridge = AssessmentSelectedQuestion(
                assessment_id=assessment.id,
                question_id=question_id,
                order_index=order_index,
            )
            self.db.add(bridge)

        # Create student_attempt row
        attempt = StudentAttempt(
            id=uuid.uuid4(),
            assessment_id=assessment.id,
            student_id=student_id,
            status=AttemptStatus.NOT_STARTED,
            total_questions=len(question_ids),
        )
        self.db.add(attempt)

        logger.info(
            "system_diagnostic_created",
            class_id=str(class_.id),
            subject_id=str(subject_id),
            assessment_id=str(assessment.id),
            question_count=len(question_ids),
        )
        return assessment

    async def _select_questions_for_diagnostic(
        self,
        curriculum_id: uuid.UUID,
        subject_id: uuid.UUID,
        grade_id: uuid.UUID,
    ) -> list[uuid.UUID]:
        """Select up to MAX_DIAGNOSTIC_QUESTIONS questions spread across curriculum topics.

        Strategy: distribute questions evenly across all active curriculum topics
        for the curriculum+subject+grade combination. If total available < 20, use all.

        Args:
            curriculum_id: The curriculum UUID.
            subject_id: The subject UUID.
            grade_id: The grade UUID.

        Returns:
            Ordered list of question UUIDs to include in the assessment.
        """
        # Load all active curriculum topics for this curriculum+subject+grade
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

        # Distribute question budget evenly across topics
        per_topic = max(1, MAX_DIAGNOSTIC_QUESTIONS // len(topics))
        remainder = MAX_DIAGNOSTIC_QUESTIONS - (per_topic * len(topics))

        selected: list[uuid.UUID] = []

        for topic in topics:
            n = per_topic + (1 if remainder > 0 else 0)
            if remainder > 0:
                remainder -= 1

            topic_questions = await self._sample_questions_for_topic(topic.id, n)
            selected.extend(topic_questions)

            if len(selected) >= MAX_DIAGNOSTIC_QUESTIONS:
                break

        return selected[:MAX_DIAGNOSTIC_QUESTIONS]

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
        # QuestionBank links to Subtopic which links to CurriculumTopic
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

        # Random sample, capped at n
        sample_size = min(n, len(question_ids))
        return random.sample(question_ids, sample_size)
