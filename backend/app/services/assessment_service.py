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
from typing import Any, TypedDict, cast

import structlog
from sqlalchemy import Integer, and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import (
    Assessment,
    AssessmentSelectedQuestion,
    AssessmentStatus,
    AssessmentTopicConfig,
    AssessmentType,
    AttemptStatus,
    StudentAttempt,
    StudentResponse,
)
from app.models.curriculum import CurriculumTopic, Grade, QuestionBank, Subject, Subtopic, Topic
from app.models.school import Class, ClassEnrollment
from app.models.user import User, UserRole
from app.schemas.assessments import (
    AssessmentCreateRequest,
    AssessmentResultsSummary,
    DesignTier1DiagnosticRequest,
    StudentAttemptSummary,
    TopicAvailability,
    TopicBreakdownItem,
)

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
    """Generate a human-readable title for a assessment."""
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
    """Construct a system-generated Assessment (legacy — no longer used).

    Kept for reference only; system-generated diagnostics are no longer created.
    All assessments are now teacher-created via design_tier1_diagnostic.
    """
    return Assessment(
        id=uuid.uuid4(),
        school_id=school_id,
        class_id=class_id,
        created_by=None,
        title=title,
        assessment_type=AssessmentType.DIAGNOSTIC,
        status=AssessmentStatus.ACTIVE,
    )


class AssessmentService:
    """Service for assessment-related operations."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Class-level: create diagnostic assessment ────────────────────────

    async def create_class_diagnostic(self, class_id: uuid.UUID) -> Assessment:
        """[DEPRECATED] Create or retrieve a system-generated Tier 1 DIAGNOSTIC assessment.

        Superseded by design_tier1_diagnostic() — teachers now design diagnostics
        explicitly via the wizard UI. This method remains only to support existing
        integration tests and legacy Celery tasks. Do not call from new code.

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

        # Idempotency: check if diagnostic assessment already exists
        existing = await self.db.execute(
            select(Assessment).where(
                Assessment.class_id == class_.id,
                Assessment.assessment_type == AssessmentType.DIAGNOSTIC,
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

        assessment.question_count = len(question_ids)

        logger.info(
            "class_diagnostic_created",
            class_id=str(class_.id),
            assessment_id=str(assessment.id),
            pool_size=len(question_ids),
            max_per_attempt=MAX_DIAGNOSTIC_QUESTIONS_PER_ATTEMPT,
        )
        return assessment

    async def design_tier1_diagnostic(
        self,
        class_id: uuid.UUID,
        school_id: uuid.UUID,
        teacher_id: uuid.UUID,
        body: DesignTier1DiagnosticRequest,
    ) -> Assessment:
        """Create a teacher-designed Tier 1 diagnostic for a class.

        Topics may come from the class's current grade or the previous grade (level - 1).
        Questions are sampled DIAGNOSTIC_QUESTIONS_PER_DIFFICULTY per difficulty level per topic.

        Replaces any previously created teacher-designed diagnostic for this class
        (idempotent replace — deletes DRAFT predecessor). ACTIVE/CLOSED ones cannot be replaced.

        Raises:
            TeacherNotClassOwnerError: If teacher does not own the class.
            ValueError: If class not found, topic grade invalid, or existing diagnostic is not DRAFT.
        """
        class_ = (
            await self.db.execute(select(Class).where(Class.id == class_id, Class.school_id == school_id))
        ).scalar_one_or_none()
        if class_ is None:
            raise ValueError(f"Class not found: class_id={class_id}")
        if class_.teacher_id != teacher_id:
            raise TeacherNotClassOwnerError(f"Teacher {teacher_id} does not own class {class_id}")

        # Remove any existing DRAFT teacher-designed diagnostic for this class
        existing = (
            await self.db.execute(
                select(Assessment).where(
                    Assessment.class_id == class_id,
                    Assessment.assessment_type == AssessmentType.DIAGNOSTIC,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            if existing.status != AssessmentStatus.DRAFT:
                raise ValueError(
                    f"Cannot replace diagnostic: existing assessment is {existing.status}. "
                    "Only DRAFT diagnostics can be replaced."
                )
            await self.db.execute(
                delete(AssessmentSelectedQuestion.__table__).where(  # type: ignore
                    AssessmentSelectedQuestion.assessment_id == existing.id
                )
            )
            await self.db.delete(existing)
            await self.db.flush()

        # Resolve the class grade level (single query)
        class_grade_level: int | None = (
            await self.db.execute(select(Grade.level).where(Grade.id == class_.grade_id))
        ).scalar_one_or_none()
        if class_grade_level is None:
            raise ValueError(f"Grade not found for class_id={class_id}")
        allowed_levels = {class_grade_level, class_grade_level - 1}

        # Validate topic grades — bulk query to avoid N+1
        topic_grade_rows = (
            await self.db.execute(
                select(
                    CurriculumTopic.id.label("curriculum_topic_id"),
                    Grade.level.label("grade_level"),
                    Grade.id.label("grade_id"),
                )
                .join(Grade, Grade.id == CurriculumTopic.grade_id)
                .where(CurriculumTopic.id.in_(body.topic_ids))
            )
        ).all()

        topic_grade_map: dict[uuid.UUID, tuple[int, uuid.UUID]] = {}
        for row in topic_grade_rows:
            topic_grade_map[row.curriculum_topic_id] = (row.grade_level, row.grade_id)

        for topic_id in body.topic_ids:
            if topic_id not in topic_grade_map:
                raise ValueError(f"Topic {topic_id} not found")
            grade_level, _ = topic_grade_map[topic_id]
            if grade_level not in allowed_levels:
                raise ValueError(
                    f"Topic {topic_id} belongs to grade level {grade_level}, "
                    f"which is not the current grade ({class_grade_level}) or previous grade ({class_grade_level - 1})"
                )

        # Sample questions: body.questions_per_topic per difficulty level per topic
        q = (
            select(QuestionBank.id, Subtopic.curriculum_topic_id, QuestionBank.difficulty_level)
            .join(Subtopic, Subtopic.id == QuestionBank.subtopic_id)
            .where(
                Subtopic.curriculum_topic_id.in_(body.topic_ids),
                QuestionBank.is_active.is_(True),
                QuestionBank.question_type.in_(body.question_types),
                QuestionBank.difficulty_level.between(body.minimum_difficulty, body.maximum_difficulty),
            )
        )
        rows = (await self.db.execute(q)).all()

        # Group questions by (topic_id, difficulty)
        by_topic_diff: dict[tuple[uuid.UUID, int], list[uuid.UUID]] = {}
        for qid, tid, diff in rows:
            level = int(diff) if diff is not None else 3
            key = (tid, level)
            by_topic_diff.setdefault(key, []).append(qid)

        rng = random.Random(str(class_id) + str(sorted(str(t) for t in body.topic_ids)))  # noqa: S311
        selected_ids: list[uuid.UUID] = []
        # Pool is intentionally large: sample questions_per_topic per difficulty
        # level per topic so different students receive different subsets.
        pool_per_diff = body.questions_per_topic
        topics_with_questions: set[uuid.UUID] = set()
        for topic_id in body.topic_ids:
            for diff in range(body.minimum_difficulty, body.maximum_difficulty + 1):
                candidates = by_topic_diff.get((topic_id, diff), [])
                if not candidates:
                    continue
                take = min(pool_per_diff, len(candidates))
                selected_ids.extend(rng.sample(candidates, take))
                topics_with_questions.add(topic_id)

        # student_facing_count is capped to topics that actually have questions
        # so the attempt service doesn't over-cap the student's question view.
        student_facing_count = body.questions_per_topic * len(topics_with_questions)

        assessment = Assessment(
            school_id=school_id,
            class_id=class_id,
            created_by=teacher_id,
            title=f"Tier 1 Diagnostic — {class_.name}",
            assessment_type=AssessmentType.DIAGNOSTIC,
            status=AssessmentStatus.DRAFT,
            question_count=student_facing_count,
            questions_per_topic=body.questions_per_topic,
            time_limit_minutes=body.time_limit_minutes if body.time_limit_minutes is not None else 0,
            question_types=body.question_types,
            minimum_difficulty=body.minimum_difficulty,
            maximum_difficulty=body.maximum_difficulty,
            deadline=body.deadline,
            created_at=datetime.now(UTC),
            instructions=None,
        )
        self.db.add(assessment)
        await self.db.flush()

        for order_index, question_id in enumerate(selected_ids):
            self.db.add(
                AssessmentSelectedQuestion(
                    assessment_id=assessment.id,
                    question_id=question_id,
                    order_index=order_index,
                )
            )

        for topic_id in body.topic_ids:
            _, grade_id = topic_grade_map[topic_id]
            self.db.add(
                AssessmentTopicConfig(
                    assessment_id=assessment.id,
                    curriculum_topic_id=topic_id,
                    grade_id=grade_id,
                )
            )

        logger.info(
            "tier1_diagnostic_designed",
            class_id=str(class_id),
            assessment_id=str(assessment.id),
            topic_count=len(body.topic_ids),
            question_count=len(selected_ids),
        )
        return assessment

    async def check_topic_availability(
        self,
        class_id: uuid.UUID,
        school_id: uuid.UUID,
        topic_ids: list[uuid.UUID],
        questions_per_topic: int,
        minimum_difficulty: int,
        maximum_difficulty: int,
        question_types: list[str],
    ) -> list[TopicAvailability]:
        """Return per-topic question availability for a diagnostic configuration.

        For each topic_id, counts available questions by difficulty level within
        the given difficulty range and question types. Returns TopicAvailability
        with fulfillable=True when available_questions >= questions_per_topic.
        """
        # Single query: LEFT JOIN from CurriculumTopic outward so topics with zero
        # questions are still returned (difficulty=NULL, count=0 for those rows).
        rows = (
            await self.db.execute(
                select(
                    CurriculumTopic.id.label("curriculum_topic_id"),
                    Topic.name.label("topic_name"),
                    Grade.level.label("grade_level"),
                    QuestionBank.difficulty_level.label("difficulty"),
                    func.count(QuestionBank.id).label("count"),
                )
                .join(Topic, Topic.id == CurriculumTopic.topic_id)
                .join(Grade, Grade.id == CurriculumTopic.grade_id)
                .outerjoin(Subtopic, Subtopic.curriculum_topic_id == CurriculumTopic.id)
                .outerjoin(
                    QuestionBank,
                    and_(
                        QuestionBank.subtopic_id == Subtopic.id,
                        QuestionBank.is_active.is_(True),
                        QuestionBank.question_type.in_(question_types),
                        QuestionBank.difficulty_level.between(minimum_difficulty, maximum_difficulty),
                    ),
                )
                .where(CurriculumTopic.id.in_(topic_ids))
                .group_by(
                    CurriculumTopic.id,
                    Topic.name,
                    Grade.level,
                    QuestionBank.difficulty_level,
                )
            )
        ).all()

        class _TopicAgg(TypedDict):
            topic_name: str
            grade_level: int
            per_difficulty: dict[int, int]
            total: int

        # Aggregate by topic — LEFT JOIN rows with difficulty=NULL are zero-question topics.
        topic_data: dict[uuid.UUID, _TopicAgg] = {}
        for row in rows:
            tid: uuid.UUID = row.curriculum_topic_id
            if tid not in topic_data:
                topic_data[tid] = {
                    "topic_name": str(row.topic_name),
                    "grade_level": int(row.grade_level),  # type: ignore[arg-type]
                    "per_difficulty": {},
                    "total": 0,
                }
            if row.difficulty is not None:
                diff = int(row.difficulty)  # type: ignore[arg-type]
                count = int(cast(Any, row.count))
                topic_data[tid]["per_difficulty"][diff] = count
                topic_data[tid]["total"] += count

        # Build result preserving the requested topic_ids order.
        result = []
        for tid in topic_ids:
            data = topic_data.get(tid, _TopicAgg(topic_name=str(tid), grade_level=0, per_difficulty={}, total=0))
            result.append(
                TopicAvailability(
                    curriculum_topic_id=tid,
                    topic_name=data["topic_name"],
                    grade_level=data["grade_level"],
                    available_questions=data["total"],
                    per_difficulty_available=data["per_difficulty"],
                    fulfillable=data["total"] >= questions_per_topic,
                )
            )
        return result

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

        # Find the active diagnostic for this class
        assessment_result = await self.db.execute(
            select(Assessment).where(
                Assessment.class_id == class_.id,
                Assessment.assessment_type == AssessmentType.DIAGNOSTIC,
                Assessment.status == AssessmentStatus.ACTIVE,
            )
        )
        assessment = assessment_result.scalar_one_or_none()
        if assessment is None:
            raise ValueError(
                f"No active diagnostic found for class_id={class_id}. "
                f"Ensure the teacher has published a diagnostic first."
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

    # ── teacher-created assessments ─────────────────────────────────

    async def create_assessment(
        self,
        school_id: uuid.UUID | None,
        teacher_id: uuid.UUID,
        class_id: uuid.UUID,
        body: AssessmentCreateRequest,
    ) -> Assessment:
        """Create a (teacher-created) assessment with question sampling.

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
        total_questions = body.questions_per_topic * max(len(body.topic_ids), 1)
        q = (
            select(QuestionBank.id, Subtopic.curriculum_topic_id, QuestionBank.difficulty_level)
            .join(Subtopic, Subtopic.id == QuestionBank.subtopic_id)
            .join(CurriculumTopic, CurriculumTopic.id == Subtopic.curriculum_topic_id)
            .where(
                CurriculumTopic.subject_id == class_.subject_id,
                CurriculumTopic.grade_id == class_.grade_id,
                QuestionBank.is_active.is_(True),
                QuestionBank.difficulty_level.between(body.minimum_difficulty, body.maximum_difficulty),
                QuestionBank.question_type.in_(body.question_types),
            )
        )
        if body.topic_ids:
            q = q.where(CurriculumTopic.id.in_(body.topic_ids))

        # Step 3 — Sample a pool distributed across difficulty levels.
        rows = (await self.db.execute(q)).all()
        if len(rows) < total_questions:
            raise InsufficientQuestionsError(
                requested=total_questions,
                available=len(rows),
                criteria={
                    "subject_id": str(class_.subject_id),
                    "grade_id": str(class_.grade_id),
                    "topic_ids": [str(t) for t in body.topic_ids],
                    "minimum_difficulty": body.minimum_difficulty,
                    "maximum_difficulty": body.maximum_difficulty,
                },
            )

        # Deterministic seed: same class + same config always yields the same pool.
        topic_ids_key = ",".join(sorted(str(t) for t in body.topic_ids))
        config_hash = int(
            hashlib.sha256(
                f"{body.assessment_type}:{body.minimum_difficulty}:{body.maximum_difficulty}:{topic_ids_key}".encode()
            ).hexdigest(),
            16,
        )
        seed = int(class_id) ^ config_hash
        rng = random.Random(seed)  # noqa: S311 — not used for cryptography

        selected_ids = _sample_pool_with_difficulty_distribution(
            [(row[0], row[1], row[2]) for row in rows],
            total_questions,
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
            status=AssessmentStatus.DRAFT,
            title=title,
            question_count=len(selected_ids),
            questions_per_topic=body.questions_per_topic,
            minimum_difficulty=body.minimum_difficulty,
            maximum_difficulty=body.maximum_difficulty,
            question_types=body.question_types,
            time_limit_minutes=body.time_limit_minutes if body.time_limit_minutes is not None else 0,
            deadline=body.deadline,
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

        # Step 7 — Create assessment_topic_config rows (grade = class grade)
        for topic_id in body.topic_ids:
            self.db.add(
                AssessmentTopicConfig(
                    assessment_id=assessment.id,
                    curriculum_topic_id=topic_id,
                    grade_id=class_.grade_id,
                )
            )

        logger.info(
            "assessment_created",
            assessment_id=str(assessment.id),
            class_id=str(class_id),
            teacher_id=str(teacher_id),
            question_count=len(selected_ids),
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
    ) -> tuple[list[Assessment], int, dict[uuid.UUID, int]]:
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
            # Students see only ACTIVE and CLOSED assessments
            base_q = base_q.where(Assessment.status.in_([AssessmentStatus.ACTIVE, AssessmentStatus.CLOSED]))

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

        # Fetch attempt counts for all assessments in one query to avoid N+1
        assessment_ids = [a.id for a in items]
        attempt_count_map: dict[uuid.UUID, int] = {}
        if assessment_ids:
            attempt_count_rows = (
                await self.db.execute(
                    select(StudentAttempt.assessment_id, func.count(StudentAttempt.id).label("cnt"))
                    .where(StudentAttempt.assessment_id.in_(assessment_ids))
                    .group_by(StudentAttempt.assessment_id)
                )
            ).all()
            for row in attempt_count_rows:
                attempt_count_map[row.assessment_id] = int(row.cnt)

        return items, total, attempt_count_map

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
            select(Assessment, Class.name.label("class_name"), Grade.name.label("grade_name"))
            .join(Class, Class.id == Assessment.class_id)
            .join(Grade, Grade.id == Class.grade_id)
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
                "grade_name": row[2],
                "title": row[0].title,
                "assessment_type": row[0].assessment_type,
                "status": row[0].status,
                "question_count": row[0].question_count,
                "questions_per_topic": row[0].questions_per_topic,
                "minimum_difficulty": row[0].minimum_difficulty,
                "maximum_difficulty": row[0].maximum_difficulty,
                "question_types": row[0].question_types,
                "time_limit_minutes": row[0].time_limit_minutes,
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
        """Permanently delete a DRAFT or attempt-free ACTIVE assessment.

        DRAFT assessments can always be deleted.
        ACTIVE assessments can be deleted only if no student has attempted them yet.
        CLOSED assessments cannot be deleted.

        Args:
            assessment_id: The assessment UUID.
            school_id: For multi-tenancy guard.
            teacher_id: Must match assessment.created_by.

        Raises:
            ValueError: If not found, wrong school, status is CLOSED, or attempts exist.
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

        if assessment.status == AssessmentStatus.ACTIVE:
            # Allow deletion only when no student attempts exist
            attempt_count_result = await self.db.execute(
                select(func.count(StudentAttempt.id)).where(StudentAttempt.assessment_id == assessment_id)
            )
            attempt_count = attempt_count_result.scalar() or 0
            if attempt_count > 0:
                raise ValueError(
                    f"Cannot delete: assessment has {attempt_count} student attempt(s). "
                    "Archive it instead by using the close endpoint."
                )
        elif assessment.status != AssessmentStatus.DRAFT:
            raise ValueError(
                f"Cannot delete: status is {assessment.status}. "
                "Only DRAFT or zero-attempt ACTIVE assessments can be deleted."
            )

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

        # Step 6 — Topic-level performance aggregation across all completed attempts.
        # Joins StudentResponse → QuestionBank → Subtopic → CurriculumTopic → Topic,
        # filtered to responses for this assessment's attempt IDs only.
        attempt_ids = [a.attempt_id for a in attempts if a.attempt_id is not None]
        topic_breakdown: list[TopicBreakdownItem] = []
        if attempt_ids:
            topic_rows = (
                await self.db.execute(
                    select(
                        Topic.name.label("topic_name"),
                        Subtopic.name.label("subtopic_name"),
                        func.sum(func.cast(StudentResponse.is_correct, Integer)).label("correct_count"),
                        func.count(StudentResponse.id).label("total_count"),
                    )
                    .join(QuestionBank, QuestionBank.id == StudentResponse.question_id)
                    .join(Subtopic, Subtopic.id == QuestionBank.subtopic_id)
                    .join(CurriculumTopic, CurriculumTopic.id == Subtopic.curriculum_topic_id)
                    .join(Topic, Topic.id == CurriculumTopic.topic_id)
                    .where(StudentResponse.attempt_id.in_(attempt_ids))
                    .group_by(Topic.name, Subtopic.name)
                )
            ).all()

            # Aggregate rows by topic (multiple subtopics may share the same topic)
            from collections import defaultdict

            topic_totals: dict[str, tuple[int, int]] = defaultdict(lambda: (0, 0))
            for row in topic_rows:
                prev_correct, prev_total = topic_totals[row.topic_name]
                topic_totals[row.topic_name] = (
                    prev_correct + (row.correct_count or 0),
                    prev_total + (row.total_count or 0),
                )

            topic_breakdown = sorted(
                [
                    TopicBreakdownItem(
                        topic_name=name,
                        correct_count=correct,
                        total_count=total,
                        avg_score=correct / total if total > 0 else 0.0,
                    )
                    for name, (correct, total) in topic_totals.items()
                    if total > 0
                ],
                key=lambda t: t.avg_score,  # weakest first
            )

        submitted_count = sum(1 for a in attempts if a.status == "COMPLETED")
        logger.info(
            "assessment_results_fetched",
            assessment_id=str(assessment_id),
            total_students=len(attempts),
            submitted_count=submitted_count,
        )

        return AssessmentResultsSummary(
            assessment_id=assessment.id,
            assessment_title=assessment.title,
            assessment_type=assessment.assessment_type,
            class_id=assessment.class_id,
            class_name=class_.name,
            total_students=len(attempts),
            submitted_count=submitted_count,
            attempts=attempts,
            topic_breakdown=topic_breakdown,
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
