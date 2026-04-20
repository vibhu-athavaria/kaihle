"""Assessment service for creating and managing assessments.

Handles system-generated (Tier 1) and teacher-created (Tier 2) assessments.

Design:
- Assessment = "what is being tested" (questions, config, type) — created once per class.
- StudentAttempt = "who is taking it" — created per student enrollment.
- Tier 1 diagnostics use a question pool of MAX_DIAGNOSTIC_POOL (60) questions,
  but each student answers at most MAX_DIAGNOSTIC_QUESTIONS_PER_ATTEMPT (20)
  via adaptive selection at the attempt/UI layer.
"""

import hashlib
import random
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import and_, delete, func, select
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
from app.models.school import Class, ClassEnrollment
from app.models.user import User, UserRole
from app.schemas.assessments import AssessmentCreateRequest, AssessmentResultsSummary, StudentAttemptSummary

logger = structlog.get_logger()


class QuestionBankEmptyError(Exception):
    """Raised when the question bank has no questions for the given subject/grade.

    This is an expected condition during development before import_questions.py
    has been run. The Celery task handles this by logging a warning and exiting
    cleanly without creating an empty assessment.
    """


class InsufficientQuestionsError(Exception):
    """Raised when the question bank has fewer questions than requested.

    Args:
        requested: Number of questions requested.
        available: Number of questions found matching the criteria.
        criteria: Dict describing the filter applied (subject, grade, topic, difficulty).
    """

    def __init__(self, requested: int, available: int, criteria: dict[str, object]) -> None:
        self.requested = requested
        self.available = available
        self.criteria = criteria
        super().__init__(
            f"Requested {requested} questions but only {available} available matching criteria: {criteria}"
        )


class AssessmentAccessDeniedError(Exception):
    """Raised when a user tries to access an assessment that belongs to a different school.

    This produces a 403 Forbidden rather than 404 Not Found so that cross-school
    access is distinguishable from a missing resource (CONSTITUTION Rule 7).
    """


class TeacherNotClassOwnerError(Exception):
    """Raised when a teacher tries to create an assessment for a class they do not teach."""


# Total questions selected into assessment_selected_questions at class creation.
# This is the pool from which adaptive question selection draws at attempt time.
MAX_DIAGNOSTIC_POOL = 60

# Maximum questions a student actually answers in one diagnostic attempt.
# Stored in assessment config; enforced by the student-facing API.
MAX_DIAGNOSTIC_QUESTIONS_PER_ATTEMPT = 20


def _sample_by_topic(
    rows: list[tuple[uuid.UUID, uuid.UUID]],
    n: int,
    rng: random.Random,
) -> list[uuid.UUID]:
    """Sample up to n question IDs with balanced topic distribution.

    Groups by curriculum_topic_id, shuffles within each group using rng,
    then round-robins across groups until n questions are collected.

    Args:
        rows: List of (question_id, curriculum_topic_id) tuples.
        n: Number of questions to select.
        rng: Seeded Random instance for deterministic selection.

    Returns:
        List of selected question UUIDs (len <= n).
    """
    if not rows:
        return []

    by_topic: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
    for qid, tid in rows:
        by_topic[tid].append(qid)

    for topic_questions in by_topic.values():
        rng.shuffle(topic_questions)  # noqa: S311 — not cryptographic

    topic_lists = list(by_topic.values())
    selected: list[uuid.UUID] = []
    idx = 0
    while len(selected) < n:
        made_progress = False
        for tlist in topic_lists:
            if idx < len(tlist) and len(selected) < n:
                selected.append(tlist[idx])
                made_progress = True
        if not made_progress:
            break
        idx += 1

    return selected[:n]


def _sample_pool_with_difficulty_distribution(
    rows: list[tuple[uuid.UUID, uuid.UUID, float | None]],
    pool_size: int,
    rng: random.Random,
) -> list[uuid.UUID]:
    """Sample up to pool_size question IDs distributed evenly across difficulty levels.

    Groups rows by difficulty integer, allocates pool_size // num_levels slots per
    level (remainder distributed to lower levels), then within each level samples
    with topic balance via _sample_by_topic. The final pool is shuffled so questions
    are not ordered by difficulty — the adaptive engine handles ordering at attempt time.

    Args:
        rows: List of (question_id, curriculum_topic_id, difficulty_level) tuples.
        pool_size: Target pool size (e.g. MAX_DIAGNOSTIC_POOL).
        rng: Seeded Random instance for deterministic selection.

    Returns:
        Shuffled list of selected question UUIDs (len <= pool_size).
    """
    if not rows:
        return []

    by_difficulty: dict[int, list[tuple[uuid.UUID, uuid.UUID]]] = defaultdict(list)
    for qid, tid, diff in rows:
        level = int(diff) if diff is not None else 3
        by_difficulty[level].append((qid, tid))

    levels = sorted(by_difficulty.keys())
    num_levels = len(levels)
    per_level = pool_size // num_levels
    remainder = pool_size % num_levels

    selected: list[uuid.UUID] = []
    for i, level in enumerate(levels):
        target = per_level + (1 if i < remainder else 0)
        level_selected = _sample_by_topic(by_difficulty[level], target, rng)
        selected.extend(level_selected)

    rng.shuffle(selected)  # noqa: S311 — not cryptographic
    return selected[:pool_size]


def _generate_title(body: AssessmentCreateRequest, class_name: str, subject_name: str) -> str:
    """Generate a human-readable title for a Tier 2 assessment."""
    if body.title:
        return body.title
    prefix = {
        AssessmentType.DIAGNOSTIC: "Diagnostic",
        AssessmentType.TOPIC_SPECIFIC: "Topic Assessment",
        AssessmentType.PROGRESS_CHECK: "Progress Check",
        AssessmentType.FINAL: "Final Assessment",
    }.get(body.assessment_type, "Assessment")
    return f"{prefix} — {subject_name} ({class_name})"


def _make_system_assessment(class_id: uuid.UUID, school_id: uuid.UUID, title: str) -> Assessment:
    """Construct a system-generated Assessment.

    System-generated assessments have created_by=NULL, distinguished by
    the is_system_generated=True flag.

    Args:
        class_id: The class this assessment belongs to.
        school_id: The school this assessment belongs to (required by Rule 2).
        title: Human-readable title.

    Returns:
        An unsaved Assessment instance with is_system_generated=True.
    """
    return Assessment(
        id=uuid.uuid4(),
        school_id=school_id,
        class_id=class_id,
        created_by=None,
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
            QuestionBankEmptyError: If no questions exist for this subject/grade.
            ValueError: If the class is not found.
        """
        # Load class
        result = await self.db.execute(select(Class).where(Class.id == class_id))
        class_ = result.scalar_one_or_none()
        if class_ is None:
            raise ValueError(f"Class not found: class_id={class_id}")

        # Count available questions before doing anything else
        question_count_result = await self.db.execute(
            select(func.count(QuestionBank.id))
            .join(Subtopic, Subtopic.id == QuestionBank.subtopic_id)
            .join(CurriculumTopic, CurriculumTopic.id == Subtopic.curriculum_topic_id)
            .where(
                CurriculumTopic.subject_id == class_.subject_id,
                CurriculumTopic.grade_id == class_.grade_id,
            )
        )
        question_count = question_count_result.scalar() or 0

        if not question_count:
            raise QuestionBankEmptyError(
                f"No questions in question_bank for subject={class_.subject_id} "
                f"grade={class_.grade_id}. Run import_questions.py first."
            )

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
            school_id=class_.school_id,
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
        # Single query: fetch all active questions with their topic and difficulty,
        # for this curriculum+subject+grade combination.
        rows = await self.db.execute(
            select(QuestionBank.id, Subtopic.curriculum_topic_id, QuestionBank.difficulty_level)
            .select_from(CurriculumTopic)
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

        all_rows: list[tuple[uuid.UUID, uuid.UUID, float | None]] = [tuple(row) for row in rows.all()]

        if not all_rows:
            logger.warning(
                "no_questions_found_for_diagnostic",
                curriculum_id=str(curriculum_id),
                subject_id=str(subject_id),
                grade_id=str(grade_id),
            )
            return []

        # Deterministic seed derived from curriculum+subject+grade so the same
        # class always produces the same question pool.
        seed = int(curriculum_id) ^ int(subject_id) ^ int(grade_id)
        rng = random.Random(seed)  # noqa: S311 — not used for cryptography

        return _sample_pool_with_difficulty_distribution(all_rows, MAX_DIAGNOSTIC_POOL, rng)

    # ── Tier 2: teacher-created assessments ─────────────────────────────────

    async def create_assessment(
        self,
        school_id: uuid.UUID | None,
        teacher_id: uuid.UUID,
        class_id: uuid.UUID,
        body: AssessmentCreateRequest,
    ) -> Assessment:
        """Create a Tier 2 (teacher-created) assessment with question sampling.

        Validates teacher ownership, samples questions with topic distribution,
        and persists the assessment + bridge rows atomically.

        Args:
            school_id: The school ID from the authenticated teacher's JWT.
            teacher_id: The teacher user ID.
            class_id: The class this assessment is for (from URL path).
            body: Assessment configuration (title, topics, count, difficulty).

        Returns:
            Unsaved (flushed) Assessment in DRAFT status.

        Raises:
            ValueError: If class not found in this school.
            TeacherNotClassOwnerError: If teacher does not own the class.
            InsufficientQuestionsError: If question bank has fewer than requested.
        """
        # Step 1 — Verify teacher owns the class
        class_ = (
            await self.db.execute(
                select(Class).where(
                    Class.id == class_id,
                    Class.school_id == school_id,
                    Class.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
        if class_ is None:
            raise ValueError(f"Class not found: class_id={class_id}")
        if class_.teacher_id != teacher_id:
            raise TeacherNotClassOwnerError(f"Teacher {teacher_id} does not own class {class_id}")

        # Step 2 — Build question filter via Subtopic join (QuestionBank has no direct topic FK)
        q = (
            select(QuestionBank.id, Subtopic.curriculum_topic_id, QuestionBank.difficulty_level)
            .join(Subtopic, Subtopic.id == QuestionBank.subtopic_id)
            .join(CurriculumTopic, CurriculumTopic.id == Subtopic.curriculum_topic_id)
            .where(
                CurriculumTopic.subject_id == class_.subject_id,
                CurriculumTopic.grade_id == class_.grade_id,
                QuestionBank.is_active.is_(True),
                QuestionBank.difficulty_level.between(body.difficulty_min, body.difficulty_max),
            )
        )
        if body.topic_ids:
            q = q.where(CurriculumTopic.id.in_(body.topic_ids))

        # Step 3 — Sample a pool of body.question_count questions distributed across
        # difficulty levels. Error only when the bank has fewer than question_count.
        rows = (await self.db.execute(q)).all()
        if len(rows) < body.question_count:
            raise InsufficientQuestionsError(
                requested=body.question_count,
                available=len(rows),
                criteria={
                    "subject_id": str(class_.subject_id),
                    "grade_id": str(class_.grade_id),
                    "topic_ids": [str(t) for t in body.topic_ids],
                    "difficulty_min": body.difficulty_min,
                    "difficulty_max": body.difficulty_max,
                },
            )

        # Deterministic seed: same class + same config always yields the same pool.
        topic_ids_key = ",".join(sorted(str(t) for t in body.topic_ids))
        config_hash = int(
            hashlib.sha256(
                f"{body.assessment_type}:{body.difficulty_min}:{body.difficulty_max}:{topic_ids_key}".encode()
            ).hexdigest(),
            16,
        )
        seed = int(class_id) ^ config_hash
        rng = random.Random(seed)  # noqa: S311 — not used for cryptography

        selected_ids = _sample_pool_with_difficulty_distribution(
            [(row[0], row[1], row[2]) for row in rows],
            body.question_count,
            rng,
        )

        # Step 4 — Resolve title (auto-generate when not provided)
        if body.title:
            title = body.title
        else:
            subject_result = await self.db.execute(select(Subject.name).where(Subject.id == class_.subject_id))
            subject_name = subject_result.scalar_one_or_none() or "Unknown Subject"
            title = _generate_title(body, class_.name, subject_name)

        # Step 5 — Create Assessment in DRAFT status
        assessment = Assessment(
            id=uuid.uuid4(),
            school_id=school_id,
            class_id=class_id,
            created_by=teacher_id,
            assessment_type=body.assessment_type,
            is_system_generated=False,
            status=AssessmentStatus.DRAFT,
            title=title,
            question_count=body.question_count,
            deadline=body.deadline,
            config={},
        )
        self.db.add(assessment)
        await self.db.flush()  # get assessment.id without committing

        # Step 6 — Create bridge rows
        bridge_rows = [
            AssessmentSelectedQuestion(
                assessment_id=assessment.id,
                question_id=qid,
                order_index=idx,
            )
            for idx, qid in enumerate(selected_ids)
        ]
        self.db.add_all(bridge_rows)

        logger.info(
            "tier2_assessment_created",
            assessment_id=str(assessment.id),
            class_id=str(class_id),
            teacher_id=str(teacher_id),
            question_count=body.question_count,
            assessment_type=body.assessment_type,
        )
        return assessment

    async def get_assessment(
        self,
        assessment_id: uuid.UUID,
        school_id: uuid.UUID | None,
        requesting_user_id: uuid.UUID,
        requesting_user_role: str,
    ) -> tuple[Assessment, list[QuestionBank]]:
        """Load an assessment with its questions in order.

        Args:
            assessment_id: The assessment UUID.
            school_id: The requesting user's school (for multi-tenancy check).
            requesting_user_id: The requesting user's ID.
            requesting_user_role: Role string (TEACHER, STUDENT, SCHOOL_ADMIN, KAIHLE_ADMIN).

        Returns:
            Tuple of (Assessment, list[QuestionBank]) where questions are in order_index order.
            For STUDENT role, correct_answer is set to None on each question.

        Raises:
            ValueError: If assessment not found or school_id mismatch.
        """
        # KaihleAdmin can access any assessment; all others are scoped to their school.
        # For non-KaihleAdmin: first check existence, then school membership, so we
        # can return 403 for cross-school access instead of 404 (CONSTITUTION Rule 7).
        if requesting_user_role == UserRole.KAIHLE_ADMIN:
            assessment = (
                await self.db.execute(select(Assessment).where(Assessment.id == assessment_id))
            ).scalar_one_or_none()
            if assessment is None:
                raise ValueError(f"Assessment not found: {assessment_id}")
        else:
            assessment = (
                await self.db.execute(select(Assessment).where(Assessment.id == assessment_id))
            ).scalar_one_or_none()
            if assessment is None:
                raise ValueError(f"Assessment not found: {assessment_id}")
            if assessment.school_id != school_id:
                raise AssessmentAccessDeniedError(f"Assessment {assessment_id} belongs to a different school.")

        # Load questions in order_index order
        question_rows = (
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
        questions = [row[0] for row in question_rows]

        # Strip correct answers for students — never expose to student-facing API
        if requesting_user_role == UserRole.STUDENT:
            for q in questions:
                q.correct_answer = None

        return assessment, questions

    async def publish_assessment(
        self,
        assessment_id: uuid.UUID,
        school_id: uuid.UUID | None,
        teacher_id: uuid.UUID,
        deadline: datetime | None,
    ) -> Assessment:
        """Transition a DRAFT assessment to ACTIVE status.

        Args:
            assessment_id: The assessment UUID.
            school_id: For multi-tenancy guard.
            teacher_id: Must match assessment.created_by.
            deadline: Optional due date; can be None.

        Returns:
            The updated Assessment with status=ACTIVE.

        Raises:
            ValueError: If not found, wrong school, wrong teacher, wrong status,
                        or no questions in the assessment.
        """
        assessment = (
            await self.db.execute(
                select(Assessment).where(
                    Assessment.id == assessment_id,
                    Assessment.school_id == school_id,
                )
            )
        ).scalar_one_or_none()
        if assessment is None:
            raise ValueError(f"Assessment not found: {assessment_id}")
        if assessment.created_by != teacher_id:
            raise TeacherNotClassOwnerError(f"Only the creating teacher can publish assessment {assessment_id}")
        if assessment.status != AssessmentStatus.DRAFT:
            raise ValueError(f"Cannot publish: status is {assessment.status}. Must be DRAFT.")

        # Guard: cannot publish empty assessment
        q_count = (
            await self.db.execute(
                select(func.count(AssessmentSelectedQuestion.question_id)).where(
                    AssessmentSelectedQuestion.assessment_id == assessment_id
                )
            )
        ).scalar()
        if not q_count:
            raise ValueError("Cannot publish assessment with no questions")

        assessment.status = AssessmentStatus.ACTIVE
        assessment.published_at = datetime.now(UTC)
        assessment.deadline = deadline

        logger.info(
            "assessment_published",
            assessment_id=str(assessment_id),
            teacher_id=str(teacher_id),
            deadline=deadline.isoformat() if deadline else None,
        )
        return assessment

    async def list_class_assessments(
        self,
        class_id: uuid.UUID,
        school_id: uuid.UUID | None,
        requesting_user_id: uuid.UUID,
        requesting_user_role: str,
        status_filter: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[Assessment], int]:
        """List assessments for a class with role-based visibility rules.

        Role-based visibility:
        - TEACHER: must own the class; sees all statuses.
        - STUDENT: sees only ACTIVE and CLOSED (plus system-generated regardless of status).
        - SCHOOL_ADMIN: sees all assessments within school_id scope.
        - KAIHLE_ADMIN: sees all (no school_id filter).

        Args:
            class_id: The class to list assessments for.
            school_id: Requesting user's school_id (for multi-tenancy guard).
            requesting_user_id: The requesting user's ID.
            requesting_user_role: Role string.
            status_filter: Optional status to filter by (DRAFT, ACTIVE, CLOSED).
            page: 1-based page number.
            page_size: Items per page.

        Returns:
            Tuple of (items, total) where items is the paginated slice.

        Raises:
            TeacherNotClassOwnerError: If teacher does not own the class.
            ValueError: If class not found (for teacher/student).
        """
        # Build base query
        if requesting_user_role == UserRole.KAIHLE_ADMIN:
            base_q = select(Assessment).where(Assessment.class_id == class_id)
        else:
            base_q = select(Assessment).where(
                Assessment.class_id == class_id,
                Assessment.school_id == school_id,
            )

        # Role-based ownership/visibility rules
        if requesting_user_role == UserRole.TEACHER:
            # Verify teacher owns this class
            class_result = await self.db.execute(
                select(Class).where(
                    Class.id == class_id,
                    Class.school_id == school_id,
                    Class.is_active.is_(True),
                )
            )
            class_ = class_result.scalar_one_or_none()
            if class_ is None:
                raise ValueError(f"Class not found: class_id={class_id}")
            if class_.teacher_id != requesting_user_id:
                raise TeacherNotClassOwnerError(f"Teacher {requesting_user_id} does not own class {class_id}")
            # Teachers see all statuses — no additional filter

        elif requesting_user_role == UserRole.STUDENT:
            # Students see only ACTIVE and CLOSED assessments,
            # EXCEPT system-generated assessments which are always visible
            base_q = base_q.where(
                (Assessment.status.in_([AssessmentStatus.ACTIVE, AssessmentStatus.CLOSED]))
                | (Assessment.is_system_generated.is_(True))
            )

        # Apply optional status filter (for TEACHER, SCHOOL_ADMIN, KAIHLE_ADMIN)
        if status_filter and requesting_user_role != UserRole.STUDENT:
            base_q = base_q.where(Assessment.status == status_filter)

        # Count total
        count_q = select(func.count()).select_from(base_q.subquery())
        total = (await self.db.execute(count_q)).scalar() or 0

        # Paginate
        offset = (page - 1) * page_size
        items_q = base_q.order_by(Assessment.created_at.desc()).offset(offset).limit(page_size)
        items = list((await self.db.execute(items_q)).scalars().all())

        return items, total

    async def list_teacher_assessments(
        self,
        teacher_id: uuid.UUID,
        school_id: uuid.UUID,
        status_filter: str | None,
    ) -> list[dict[str, Any]]:
        """List all assessments across all classes owned by a teacher.

        More efficient than calling list_class_assessments for each class - uses a single
        query with JOIN to filter by teacher's classes.

        Args:
            teacher_id: The teacher's ID.
            school_id: The school to scope to.
            status_filter: Optional status filter.

        Returns:
            List of dicts with assessment and class_name.
        """
        base_q = (
            select(Assessment, Class.name.label("class_name"))
            .join(Class, Class.id == Assessment.class_id)
            .where(
                Class.teacher_id == teacher_id,
                Class.school_id == school_id,
                Class.is_active.is_(True),
                Assessment.school_id == school_id,
            )
        )

        if status_filter:
            base_q = base_q.where(Assessment.status == status_filter)

        results = await self.db.execute(base_q.order_by(Assessment.created_at.desc()))
        rows = results.all()

        return [
            {
                "id": row[0].id,
                "class_id": row[0].class_id,
                "class_name": row[1],
                "title": row[0].title,
                "assessment_type": row[0].assessment_type,
                "is_system_generated": row[0].is_system_generated,
                "status": row[0].status,
                "question_count": row[0].question_count,
                "created_at": row[0].created_at,
                "published_at": row[0].published_at,
                "deadline": row[0].deadline,
            }
            for row in rows
        ]

    async def close_assessment(
        self,
        assessment_id: uuid.UUID,
        school_id: uuid.UUID | None,
        teacher_id: uuid.UUID,
    ) -> Assessment:
        """Transition an ACTIVE assessment to CLOSED status.

        No new attempts are accepted after closing — enforced in the attempt service.

        Args:
            assessment_id: The assessment UUID.
            school_id: For multi-tenancy guard.
            teacher_id: Must match assessment.created_by.

        Returns:
            The updated Assessment with status=CLOSED.

        Raises:
            ValueError: If not found, wrong school, wrong teacher, or status is not ACTIVE.
        """
        assessment = (
            await self.db.execute(
                select(Assessment).where(
                    Assessment.id == assessment_id,
                    Assessment.school_id == school_id,
                )
            )
        ).scalar_one_or_none()
        if assessment is None:
            raise ValueError(f"Assessment not found: {assessment_id}")
        if assessment.created_by != teacher_id:
            raise TeacherNotClassOwnerError(f"Only the creating teacher can close assessment {assessment_id}")
        if assessment.status != AssessmentStatus.ACTIVE:
            raise ValueError(f"Cannot close: status is {assessment.status}. Must be ACTIVE.")

        assessment.status = AssessmentStatus.CLOSED

        logger.info(
            "assessment_closed",
            assessment_id=str(assessment_id),
            teacher_id=str(teacher_id),
        )
        return assessment

    async def delete_assessment(
        self,
        assessment_id: uuid.UUID,
        school_id: uuid.UUID | None,
        teacher_id: uuid.UUID,
    ) -> None:
        """Permanently delete a DRAFT assessment and its selected-question bridge rows.

        Only DRAFT assessments can be deleted — ACTIVE or CLOSED assessments have
        student attempt records and must not be removed.

        Args:
            assessment_id: The assessment UUID.
            school_id: For multi-tenancy guard.
            teacher_id: Must match assessment.created_by.

        Raises:
            ValueError: If not found, wrong school, or status is not DRAFT.
            TeacherNotClassOwnerError: If teacher does not own the assessment.
        """
        assessment = (
            await self.db.execute(
                select(Assessment).where(
                    Assessment.id == assessment_id,
                    Assessment.school_id == school_id,
                )
            )
        ).scalar_one_or_none()
        if assessment is None:
            raise ValueError(f"Assessment not found: {assessment_id}")
        if assessment.created_by != teacher_id:
            raise TeacherNotClassOwnerError(f"Only the creating teacher can delete assessment {assessment_id}")
        if assessment.status != AssessmentStatus.DRAFT:
            raise ValueError(f"Cannot delete: status is {assessment.status}. Only DRAFT assessments can be deleted.")

        # Delete bridge rows first — no ORM cascade defined on Assessment.
        await self.db.execute(
            delete(AssessmentSelectedQuestion.__table__).where(  # type: ignore
                AssessmentSelectedQuestion.assessment_id == assessment_id
            )
        )
        await self.db.delete(assessment)

        logger.info(
            "assessment_deleted",
            assessment_id=str(assessment_id),
            teacher_id=str(teacher_id),
        )

    async def get_assessment_results(
        self,
        assessment_id: uuid.UUID,
        school_id: uuid.UUID | None,
        requesting_user_id: uuid.UUID,
        requesting_user_role: str,
    ) -> AssessmentResultsSummary:
        """Return all student attempt summaries for an assessment (class overview).

        Distinct from get_attempt_results (per-student question breakdown). This
        returns one row per enrolled student, including NOT_STARTED students with
        null attempt_id and score.

        Multi-tenancy: KAIHLE_ADMIN bypasses school check; all others verified.
        TEACHER must own the class.

        Args:
            assessment_id: The assessment to fetch results for.
            school_id: Requesting user's school_id (None for KAIHLE_ADMIN).
            requesting_user_id: The requesting user's ID (for teacher ownership check).
            requesting_user_role: Role string.

        Returns:
            AssessmentResultsSummary with one StudentAttemptSummary per enrolled student.

        Raises:
            ValueError: If assessment or class not found.
            AssessmentAccessDeniedError: If cross-school access or teacher doesn't own class.
        """
        # Step 1 — Load assessment
        assessment = await self.db.get(Assessment, assessment_id)
        if assessment is None:
            raise ValueError(f"Assessment {assessment_id} not found")

        # Step 2 — School access guard (CONSTITUTION Rule 3)
        if requesting_user_role != UserRole.KAIHLE_ADMIN:
            if assessment.school_id != school_id:
                raise AssessmentAccessDeniedError()

        # Step 3 — Always fetch class
        class_ = await self.db.get(Class, assessment.class_id)
        if class_ is None:
            raise ValueError(f"Class not found for assessment {assessment_id}")

        # Step 4 — TEACHER must own the class
        if requesting_user_role == UserRole.TEACHER:
            if class_.teacher_id != requesting_user_id:
                raise AssessmentAccessDeniedError()

        # Step 5 — One query: all enrolled students left-joined to their attempt
        rows = (
            await self.db.execute(
                select(
                    ClassEnrollment.student_id,
                    User.first_name,
                    User.last_name,
                    StudentAttempt.id.label("attempt_id"),
                    StudentAttempt.overall_score,
                    StudentAttempt.status,
                    StudentAttempt.completed_at,
                )
                .join(User, User.id == ClassEnrollment.student_id)
                .outerjoin(
                    StudentAttempt,
                    and_(
                        StudentAttempt.student_id == ClassEnrollment.student_id,
                        StudentAttempt.assessment_id == assessment_id,
                    ),
                )
                .where(
                    ClassEnrollment.class_id == assessment.class_id,
                    ClassEnrollment.is_active.is_(True),
                )
                .order_by(StudentAttempt.overall_score.asc().nullsfirst())
            )
        ).all()

        attempts = [
            StudentAttemptSummary(
                attempt_id=row.attempt_id,
                student_id=row.student_id,
                student_name=f"{row.first_name or ''} {row.last_name or ''}".strip() or "Unknown",
                score=float(row.overall_score) if row.overall_score is not None else None,
                submitted_at=row.completed_at,
                status=row.status or "NOT_STARTED",
            )
            for row in rows
        ]

        logger.info(
            "assessment_results_fetched",
            assessment_id=str(assessment_id),
            total_students=len(attempts),
            submitted_count=sum(1 for a in attempts if a.status == "SUBMITTED"),
        )

        return AssessmentResultsSummary(
            assessment_id=assessment.id,
            assessment_title=assessment.title,
            assessment_type=assessment.assessment_type,
            class_id=assessment.class_id,
            class_name=class_.name,
            total_students=len(attempts),
            submitted_count=sum(1 for a in attempts if a.status == "SUBMITTED"),
            attempts=attempts,
        )


def _sample_with_topic_distribution(rows: list[tuple[uuid.UUID, str]], n: int) -> list[uuid.UUID]:
    """Sample up to n question IDs distributed evenly across topics.

    Groups rows by topic, allocates n // num_topics slots per topic
    (remainder distributed to earlier topics), then samples within each topic.
    Shuffles the final selection.

    Args:
        rows: List of (question_id, topic) tuples.
        n: Target sample size.

    Returns:
        List of selected question UUIDs (len <= n).
    """
    if not rows:
        return []

    from collections import defaultdict

    by_topic: dict[str, list[uuid.UUID]] = defaultdict(list)
    for qid, topic in rows:
        by_topic[topic].append(qid)

    topics = list(by_topic.keys())
    num_topics = len(topics)
    per_topic = n // num_topics
    remainder = n % num_topics

    selected: list[uuid.UUID] = []
    for i, topic in enumerate(topics):
        target = per_topic + (1 if i < remainder else 0)
        topic_qids = by_topic[topic]
        if len(topic_qids) <= target:
            selected.extend(topic_qids)
        else:
            selected.extend(random.sample(topic_qids, target))

    random.shuffle(selected)
    return selected[:n]
