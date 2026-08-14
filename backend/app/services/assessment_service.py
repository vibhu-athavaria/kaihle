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
    QuestionReviewItem,
    StudentAttempt,
    StudentResponse,
)
from app.models.curriculum import CurriculumTopic, Grade, QuestionBank, Subject, Subtopic, Topic
from app.models.school import Class, ClassEnrollment
from app.models.user import User, UserRole
from app.schemas.assessments import (
    AddQuestionRequest,
    AddQuestionResponse,
    AssessmentCreateRequest,
    AssessmentPreviewQuestion,
    AssessmentPreviewResponse,
    AssessmentResultsSummary,
    AssessmentUpdateRequest,
    AssessmentUpdateResponse,
    DesignTier1DiagnosticRequest,
    QuestionOption,
    RemoveQuestionResponse,
    ReplacementCandidate,
    ReplaceQuestionResponse,
    StudentAttemptSummary,
    SuggestEditRequest,
    SuggestEditResponse,
    TopicAvailability,
    TopicBreakdownItem,
)
from app.services.question_selection import (
    StudentTier,
    active_scope_filters,
    join_questions_via_objectives,
    tier_filter,
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


class TopicGradeOutOfRangeError(Exception):
    """Raised when a selected topic sits outside the class's current-or-previous grade.

    Distinct from a missing topic: the topic exists, it is just not permissible for
    this class. Routes map it to 422 rather than 404, because the resource was found
    and the request was invalid.

    Args:
        topic_id: The offending curriculum_topic.
        topic_grade_level: The grade level that topic belongs to.
        class_grade_level: The class's own grade level; the allowed window is
            {class_grade_level, class_grade_level - 1}.
    """

    def __init__(self, topic_id: uuid.UUID, topic_grade_level: int, class_grade_level: int) -> None:
        self.topic_id = topic_id
        self.topic_grade_level = topic_grade_level
        self.class_grade_level = class_grade_level
        super().__init__(
            f"Topic {topic_id} belongs to grade level {topic_grade_level}, which is not the "
            f"current grade ({class_grade_level}) or previous grade ({class_grade_level - 1})"
        )


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

    async def _resolve_and_validate_topic_grades(
        self,
        class_id: uuid.UUID,
        class_grade_id: uuid.UUID,
        class_subject_id: uuid.UUID,
        topic_ids: list[uuid.UUID],
    ) -> dict[uuid.UUID, tuple[int, uuid.UUID]]:
        """Resolve each topic's grade and reject any outside the class's grade or subject.

        Topics may come from the class's current grade or the previous grade (level - 1).
        Probing the prior grade is how a diagnostic finds gaps that predate the current
        year, so it is deliberate rather than a tolerance.

        Subject is checked here rather than left to the question query. A foreign-subject
        topic otherwise slips through: create_assessment's query filters on subject so it
        contributes no questions, but Step 8 still writes it an assessment_topic_config
        row, and attempt attribution trusts that table. design_tier1_diagnostic's query
        does not filter subject at all, so it would sample the foreign subject's questions
        outright.

        This is the ONLY grade constraint applied once topic_ids are supplied. Callers
        must not additionally filter their question query on the class's grade: a
        curriculum_topic already pins exactly one grade, so combining the two predicates
        yields an empty set for every prior-grade topic.

        Args:
            class_id: The class, used only for error messages.
            class_grade_id: The class's grade, whose level defines the window.
            class_subject_id: The class's subject; topics from any other are rejected.
            topic_ids: curriculum_topics.id values to validate. Empty is allowed and
                returns an empty map without querying.

        Returns:
            Map of curriculum_topic_id -> (grade_level, grade_id).

        Raises:
            ValueError: If the class grade is missing, a topic does not exist, or a topic
                belongs to a different subject.
            TopicGradeOutOfRangeError: If a topic exists but sits outside the window.
        """
        if not topic_ids:
            return {}

        class_grade_level: int | None = (
            await self.db.execute(select(Grade.level).where(Grade.id == class_grade_id))
        ).scalar_one_or_none()
        if class_grade_level is None:
            raise ValueError(f"Grade not found for class_id={class_id}")
        allowed_levels = {class_grade_level, class_grade_level - 1}

        # Bulk query to avoid N+1
        topic_grade_rows = (
            await self.db.execute(
                select(
                    CurriculumTopic.id.label("curriculum_topic_id"),
                    Grade.level.label("grade_level"),
                    Grade.id.label("grade_id"),
                    CurriculumTopic.subject_id.label("subject_id"),
                )
                .join(Grade, Grade.id == CurriculumTopic.grade_id)
                .where(CurriculumTopic.id.in_(topic_ids))
            )
        ).all()

        topic_grade_map: dict[uuid.UUID, tuple[int, uuid.UUID]] = {}
        topic_subject: dict[uuid.UUID, uuid.UUID] = {}
        for row in topic_grade_rows:
            topic_grade_map[row.curriculum_topic_id] = (row.grade_level, row.grade_id)
            topic_subject[row.curriculum_topic_id] = row.subject_id

        for topic_id in topic_ids:
            if topic_id not in topic_grade_map:
                raise ValueError(f"Topic {topic_id} not found")
            if topic_subject[topic_id] != class_subject_id:
                raise ValueError(f"Topic {topic_id} belongs to a different subject than this class")
            grade_level, _ = topic_grade_map[topic_id]
            if grade_level not in allowed_levels:
                raise TopicGradeOutOfRangeError(
                    topic_id=topic_id,
                    topic_grade_level=grade_level,
                    class_grade_level=class_grade_level,
                )

        return topic_grade_map

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
            if existing.status not in (AssessmentStatus.DRAFT, AssessmentStatus.CLOSED):
                raise ValueError(
                    f"Cannot replace diagnostic: existing assessment is {existing.status}. "
                    "Only DRAFT or CLOSED diagnostics can be replaced."
                )
            await self.db.execute(
                delete(AssessmentSelectedQuestion.__table__).where(  # type: ignore
                    AssessmentSelectedQuestion.assessment_id == existing.id
                )
            )
            await self.db.delete(existing)
            await self.db.flush()

        topic_grade_map = await self._resolve_and_validate_topic_grades(
            class_id=class_id,
            class_grade_id=class_.grade_id,
            class_subject_id=class_.subject_id,
            topic_ids=body.topic_ids,
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
        tier: StudentTier | None = None,
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
            tier: IGCSE Core/Extended tier. None (the default) applies no tier
                restriction, which is correct below IGCSE where tiering does not exist.

        Returns:
            Ordered list of question UUIDs to include in the assessment pool.
        """
        # Single query: fetch all active questions with their topic and difficulty,
        # for this curriculum+subject+grade combination. Resolution goes through
        # learning objectives, never question_bank.subtopic_id — see
        # app/services/question_selection.py for why.
        # DISTINCT because a question reachable via two subtopics of the same topic
        # would otherwise be counted twice and skew the difficulty distribution.
        rows = await self.db.execute(
            join_questions_via_objectives(
                select(
                    QuestionBank.id,
                    Subtopic.curriculum_topic_id,
                    QuestionBank.difficulty_level,
                ).select_from(CurriculumTopic)
            )
            .where(
                *active_scope_filters(curriculum_id, subject_id, grade_id),
                tier_filter(tier),
            )
            .distinct()
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

        # Step 2 — Validate the selected topics sit in the class's grade window.
        # topic_ids is guaranteed non-empty by the schema (min_length=1).
        topic_grade_map = await self._resolve_and_validate_topic_grades(
            class_id=class_id,
            class_grade_id=class_.grade_id,
            class_subject_id=class_.subject_id,
            topic_ids=body.topic_ids,
        )

        # Step 3 — Build question filter via Subtopic join (QuestionBank has no direct topic FK).
        # Grade is constrained by the selected topics alone: each curriculum_topic pins
        # exactly one grade and Step 2 has already checked it is in range. Adding
        # CurriculumTopic.grade_id == class_.grade_id here would contradict every
        # prior-grade topic and return zero rows.
        total_questions = body.questions_per_topic * len(body.topic_ids)
        q = (
            select(QuestionBank.id, Subtopic.curriculum_topic_id, QuestionBank.difficulty_level)
            .join(Subtopic, Subtopic.id == QuestionBank.subtopic_id)
            .join(CurriculumTopic, CurriculumTopic.id == Subtopic.curriculum_topic_id)
            .where(
                CurriculumTopic.id.in_(body.topic_ids),
                CurriculumTopic.subject_id == class_.subject_id,
                QuestionBank.is_active.is_(True),
                QuestionBank.difficulty_level.between(body.minimum_difficulty, body.maximum_difficulty),
                QuestionBank.question_type.in_(body.question_types),
            )
        )

        # Step 4 — Sample a pool distributed across difficulty levels.
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

        # Step 5 — Resolve title (auto-generate when not provided)
        if body.title:
            title = body.title
        else:
            subject_result = await self.db.execute(select(Subject.name).where(Subject.id == class_.subject_id))
            subject_name = subject_result.scalar_one_or_none() or "Unknown Subject"
            title = _generate_title(body, class_.name, subject_name)

        # Step 6 — Create Assessment in DRAFT status
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

        # Step 7 — Create bridge rows
        bridge_rows = [
            AssessmentSelectedQuestion(
                assessment_id=assessment.id,
                question_id=qid,
                order_index=idx,
            )
            for idx, qid in enumerate(selected_ids)
        ]
        self.db.add_all(bridge_rows)

        # Step 8 — Create assessment_topic_config rows.
        # Grade comes from the topic itself, not the class: a prior-grade topic must be
        # recorded at its own grade or the config misreports what the assessment covers.
        for topic_id in body.topic_ids:
            _, topic_grade_id = topic_grade_map[topic_id]
            self.db.add(
                AssessmentTopicConfig(
                    assessment_id=assessment.id,
                    curriculum_topic_id=topic_id,
                    grade_id=topic_grade_id,
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

    # ── Preview (teacher-facing with correct answers) ────────────────────────

    async def get_assessment_preview(
        self,
        assessment_id: uuid.UUID,
        school_id: uuid.UUID | None,
        teacher_id: uuid.UUID,
    ) -> AssessmentPreviewResponse:
        """Return full assessment details with all pool questions including correct answers.

        Only the creating teacher may preview their own assessment. Available for
        all statuses (DRAFT, ACTIVE, CLOSED) so teachers can review closed assessments.

        Args:
            assessment_id: The assessment UUID.
            school_id: Teacher's school (multi-tenancy guard).
            teacher_id: Must match assessment.created_by.

        Returns:
            AssessmentPreviewResponse with questions including correct_answer_key.

        Raises:
            ValueError: If assessment not found or school mismatch.
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
            raise TeacherNotClassOwnerError(f"Teacher {teacher_id} does not own assessment {assessment_id}")

        # Load all pool questions with full curriculum context (single JOIN query)
        rows = (
            await self.db.execute(
                select(
                    Subtopic.id.label("subtopic_id"),
                    QuestionBank.id.label("question_id"),
                    QuestionBank.question_text,
                    QuestionBank.question_type,
                    QuestionBank.options,
                    QuestionBank.correct_answer,
                    QuestionBank.explanation,
                    QuestionBank.difficulty_level,
                    QuestionBank.source,
                    Subtopic.name.label("subtopic_name"),
                    Topic.name.label("topic_name"),
                    AssessmentSelectedQuestion.order_index,
                )
                .join(
                    AssessmentSelectedQuestion,
                    AssessmentSelectedQuestion.question_id == QuestionBank.id,
                )
                .join(Subtopic, Subtopic.id == QuestionBank.subtopic_id)
                .join(CurriculumTopic, CurriculumTopic.id == Subtopic.curriculum_topic_id)
                .join(Topic, Topic.id == CurriculumTopic.topic_id)
                .where(AssessmentSelectedQuestion.assessment_id == assessment_id)
                .order_by(AssessmentSelectedQuestion.order_index)
            )
        ).all()

        # Count attempts for the warning flag
        attempt_count = (
            await self.db.execute(
                select(func.count(StudentAttempt.id)).where(StudentAttempt.assessment_id == assessment_id)
            )
        ).scalar() or 0

        questions = [
            AssessmentPreviewQuestion(
                question_id=row.question_id,
                question_text=row.question_text,
                question_type=row.question_type,
                options=[QuestionOption(key=o["key"], text=o["text"]) for o in (row.options or [])],
                correct_answer_key=row.correct_answer,
                explanation=row.explanation,
                difficulty_level=int(row.difficulty_level) if row.difficulty_level is not None else 0,
                subtopic_id=row.subtopic_id,
                subtopic_name=row.subtopic_name,
                topic_name=row.topic_name,
                order_index=row.order_index,
                is_teacher_submitted=row.source == "teacher",
            )
            for row in rows
        ]

        return AssessmentPreviewResponse(
            id=assessment.id,
            class_id=assessment.class_id,
            title=assessment.title,
            assessment_type=assessment.assessment_type,
            status=assessment.status,
            question_count=assessment.question_count,
            questions_per_topic=assessment.questions_per_topic,
            minimum_difficulty=assessment.minimum_difficulty,
            maximum_difficulty=assessment.maximum_difficulty,
            time_limit_minutes=assessment.time_limit_minutes,
            deadline=assessment.deadline,
            instructions=assessment.instructions,
            questions=questions,
            attempt_count=int(attempt_count),
        )

    # ── Edit assessment details ──────────────────────────────────────────────

    async def update_assessment(
        self,
        assessment_id: uuid.UUID,
        school_id: uuid.UUID | None,
        teacher_id: uuid.UUID,
        body: AssessmentUpdateRequest,
    ) -> AssessmentUpdateResponse:
        """Partial update for assessment details.

        Safe fields (always): title, instructions, deadline.
        Risky fields (allowed but flagged when attempts exist): question_count,
            time_limit_minutes, questions_per_topic, minimum_difficulty, maximum_difficulty.
        CLOSED assessments: only title and instructions editable.

        Args:
            assessment_id: The assessment UUID.
            school_id: Teacher's school (multi-tenancy guard).
            teacher_id: Must match assessment.created_by.
            body: Partial update body (omitted fields unchanged).

        Returns:
            AssessmentUpdateResponse with has_attempts=True if any attempt exists.

        Raises:
            ValueError: If assessment not found, school mismatch, or risky field
                        sent for a CLOSED assessment.
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
            raise TeacherNotClassOwnerError(f"Teacher {teacher_id} does not own assessment {assessment_id}")

        updates = body.model_dump(exclude_unset=True)

        # CLOSED assessments: block risky fields
        risky_fields = {
            "question_count",
            "time_limit_minutes",
            "questions_per_topic",
            "minimum_difficulty",
            "maximum_difficulty",
        }
        if assessment.status == AssessmentStatus.CLOSED:
            blocked = risky_fields & updates.keys()
            if blocked:
                raise ValueError(
                    f"Cannot update {blocked} on a CLOSED assessment. "
                    "Only title and instructions are editable after closing."
                )

        for field, value in updates.items():
            setattr(assessment, field, value)

        # Check if any attempt exists (for has_attempts warning flag)
        attempt_count = (
            await self.db.execute(
                select(func.count(StudentAttempt.id)).where(StudentAttempt.assessment_id == assessment_id)
            )
        ).scalar() or 0

        logger.info(
            "assessment_updated",
            assessment_id=str(assessment_id),
            teacher_id=str(teacher_id),
            updated_fields=list(updates.keys()),
            has_attempts=attempt_count > 0,
        )

        return AssessmentUpdateResponse(
            id=assessment.id,
            class_id=assessment.class_id,
            title=assessment.title,
            assessment_type=assessment.assessment_type,
            status=assessment.status,
            question_count=assessment.question_count,
            questions_per_topic=assessment.questions_per_topic,
            minimum_difficulty=assessment.minimum_difficulty,
            maximum_difficulty=assessment.maximum_difficulty,
            question_types=assessment.question_types,
            time_limit_minutes=assessment.time_limit_minutes,
            instructions=assessment.instructions,
            deadline=assessment.deadline,
            published_at=assessment.published_at,
            created_at=assessment.created_at,
            has_attempts=attempt_count > 0,
        )

    # ── Question pool management ─────────────────────────────────────────────

    async def _verify_teacher_owns_assessment(
        self,
        assessment_id: uuid.UUID,
        school_id: uuid.UUID | None,
        teacher_id: uuid.UUID,
    ) -> Assessment:
        """Load assessment and verify the teacher owns it. Raises on failure."""
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
            raise TeacherNotClassOwnerError(f"Teacher {teacher_id} does not own assessment {assessment_id}")
        return assessment

    async def add_question_to_assessment(
        self,
        assessment_id: uuid.UUID,
        school_id: uuid.UUID | None,
        teacher_id: uuid.UUID,
        body: AddQuestionRequest,
    ) -> AddQuestionResponse:
        """Add a teacher-created question directly to the assessment pool.

        The question is inserted into question_bank immediately (source='teacher',
        school_id set, review_status='PENDING_REVIEW') so it is live for students.
        A QuestionReviewItem (type=TEACHER_QUESTION) is created for KaihleAdmin review.
        On approve: school_id cleared → globally available.
        On reject: is_active set FALSE.

        Args:
            assessment_id: The assessment UUID.
            school_id: Teacher's school_id (multi-tenancy).
            teacher_id: Must own the assessment's class.
            body: New question details.

        Returns:
            AddQuestionResponse with question_id and review_item_id.

        Raises:
            ValueError: Assessment not found, school mismatch, or subtopic not in class scope.
            TeacherNotClassOwnerError: Teacher does not own the assessment.
        """
        assessment = await self._verify_teacher_owns_assessment(assessment_id, school_id, teacher_id)

        # Verify subtopic belongs to the class's subject + grade
        class_ = await self.db.get(Class, assessment.class_id)
        if class_ is None:
            raise ValueError(f"Class not found for assessment {assessment_id}")

        subtopic_row = (
            await self.db.execute(
                select(Subtopic.id)
                .join(CurriculumTopic, CurriculumTopic.id == Subtopic.curriculum_topic_id)
                .where(
                    Subtopic.id == body.subtopic_id,
                    CurriculumTopic.subject_id == class_.subject_id,
                    CurriculumTopic.grade_id == class_.grade_id,
                )
            )
        ).scalar_one_or_none()
        if subtopic_row is None:
            raise ValueError(
                f"Subtopic {body.subtopic_id} does not belong to subject {class_.subject_id} / grade {class_.grade_id}"
            )

        # Insert question_bank row
        canonical_form = hashlib.sha256(body.question_text.strip().lower().encode()).hexdigest()
        question = QuestionBank(
            id=uuid.uuid4(),
            subtopic_id=body.subtopic_id,
            question_text=body.question_text,
            question_type=body.question_type,
            options=body.options,
            correct_answer=body.correct_answer,
            difficulty_level=body.difficulty_level,
            explanation=body.explanation,
            canonical_form=canonical_form,
            problem_signature={},
            source="teacher",
            school_id=school_id,
            submitted_by=teacher_id,
            review_status="PENDING_REVIEW",
            is_active=True,
        )
        self.db.add(question)
        await self.db.flush()

        # Link to assessment pool at end of current order
        max_order_result = await self.db.execute(
            select(func.max(AssessmentSelectedQuestion.order_index)).where(
                AssessmentSelectedQuestion.assessment_id == assessment_id
            )
        )
        max_order = max_order_result.scalar() or -1
        self.db.add(
            AssessmentSelectedQuestion(
                assessment_id=assessment_id,
                question_id=question.id,
                order_index=max_order + 1,
            )
        )

        # Increment question_count
        if assessment.question_count is not None:
            assessment.question_count = assessment.question_count + 1

        # Create review item for KaihleAdmin
        review_item = QuestionReviewItem(
            id=uuid.uuid4(),
            item_type="TEACHER_QUESTION",
            question_id=question.id,
            submitted_by=teacher_id,
            school_id=school_id,  # type: ignore[arg-type]
            assessment_id=assessment_id,
            status="PENDING",
        )
        self.db.add(review_item)

        logger.info(
            "teacher_question_added_to_assessment",
            assessment_id=str(assessment_id),
            question_id=str(question.id),
            review_item_id=str(review_item.id),
            teacher_id=str(teacher_id),
        )

        return AddQuestionResponse(
            question_id=question.id,
            review_item_id=review_item.id,
        )

    async def remove_question_from_pool(
        self,
        assessment_id: uuid.UUID,
        question_id: uuid.UUID,
        school_id: uuid.UUID | None,
        teacher_id: uuid.UUID,
    ) -> RemoveQuestionResponse:
        """Remove a question from the assessment pool.

        Blocks if removal would bring question_count below 1.
        Returns has_responses=True if any student has already answered this question
        (frontend should warn before proceeding).

        Args:
            assessment_id: The assessment UUID.
            question_id: The question to remove.
            school_id: Teacher's school (multi-tenancy).
            teacher_id: Must own the assessment.

        Returns:
            RemoveQuestionResponse with has_responses flag.

        Raises:
            ValueError: Assessment/question not found, or removal would empty the pool.
            TeacherNotClassOwnerError: Teacher does not own the assessment.
        """
        assessment = await self._verify_teacher_owns_assessment(assessment_id, school_id, teacher_id)

        # Verify question is in the pool
        bridge = (
            await self.db.execute(
                select(AssessmentSelectedQuestion).where(
                    AssessmentSelectedQuestion.assessment_id == assessment_id,
                    AssessmentSelectedQuestion.question_id == question_id,
                )
            )
        ).scalar_one_or_none()
        if bridge is None:
            raise ValueError(f"Question {question_id} is not in assessment pool {assessment_id}")

        # Guard: pool must retain at least 1 question
        pool_size = (
            await self.db.execute(
                select(func.count(AssessmentSelectedQuestion.question_id)).where(
                    AssessmentSelectedQuestion.assessment_id == assessment_id
                )
            )
        ).scalar() or 0
        if pool_size <= 1:
            raise ValueError("Cannot remove: assessment must have at least 1 question in the pool.")

        # Check if any student has a response for this question
        response_exists = (
            await self.db.execute(
                select(StudentResponse.id)
                .join(StudentAttempt, StudentAttempt.id == StudentResponse.attempt_id)
                .where(
                    StudentAttempt.assessment_id == assessment_id,
                    StudentResponse.question_id == question_id,
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        has_responses = response_exists is not None

        # Remove bridge row
        await self.db.execute(
            delete(AssessmentSelectedQuestion.__table__).where(  # type: ignore
                AssessmentSelectedQuestion.assessment_id == assessment_id,
                AssessmentSelectedQuestion.question_id == question_id,
            )
        )

        # Decrement question_count
        if assessment.question_count is not None and assessment.question_count > 1:
            assessment.question_count = assessment.question_count - 1

        logger.info(
            "question_removed_from_pool",
            assessment_id=str(assessment_id),
            question_id=str(question_id),
            has_responses=has_responses,
            teacher_id=str(teacher_id),
        )

        return RemoveQuestionResponse(has_responses=has_responses)

    async def get_replacement_candidates(
        self,
        assessment_id: uuid.UUID,
        question_id: uuid.UUID,
        school_id: uuid.UUID | None,
        teacher_id: uuid.UUID,
        difficulty_level: int | None = None,
        question_type: str | None = None,
    ) -> list[ReplacementCandidate]:
        """Return question_bank candidates to replace a question in the pool.

        Candidates must:
        - Belong to the same curriculum_topic as the question being replaced.
        - Be active (is_active=True).
        - Not already be in the assessment pool.
        - Optionally match difficulty_level and/or question_type filters.

        Args:
            assessment_id: The assessment UUID.
            question_id: The question being replaced.
            school_id: Teacher's school (multi-tenancy).
            teacher_id: Must own the assessment.
            difficulty_level: Optional filter.
            question_type: Optional filter.

        Returns:
            List of ReplacementCandidate ordered by difficulty_level.
        """
        await self._verify_teacher_owns_assessment(assessment_id, school_id, teacher_id)

        # Get the curriculum_topic_id of the question being replaced
        topic_row = (
            await self.db.execute(
                select(Subtopic.curriculum_topic_id)
                .join(QuestionBank, QuestionBank.subtopic_id == Subtopic.id)
                .where(QuestionBank.id == question_id)
            )
        ).scalar_one_or_none()
        if topic_row is None:
            raise ValueError(f"Question {question_id} not found in question bank")
        curriculum_topic_id: uuid.UUID = topic_row

        # IDs already in the pool (to exclude)
        existing_ids_result = await self.db.execute(
            select(AssessmentSelectedQuestion.question_id).where(
                AssessmentSelectedQuestion.assessment_id == assessment_id
            )
        )
        existing_ids = {row[0] for row in existing_ids_result.all()}

        # Query candidates
        q = (
            select(
                QuestionBank.id.label("question_id"),
                QuestionBank.question_text,
                QuestionBank.question_type,
                QuestionBank.options,
                QuestionBank.correct_answer,
                QuestionBank.difficulty_level,
                Subtopic.name.label("subtopic_name"),
                Topic.name.label("topic_name"),
            )
            .join(Subtopic, Subtopic.id == QuestionBank.subtopic_id)
            .join(CurriculumTopic, CurriculumTopic.id == Subtopic.curriculum_topic_id)
            .join(Topic, Topic.id == CurriculumTopic.topic_id)
            .where(
                Subtopic.curriculum_topic_id == curriculum_topic_id,
                QuestionBank.is_active.is_(True),
                QuestionBank.id.notin_(existing_ids),
            )
            .order_by(QuestionBank.difficulty_level)
            .limit(50)
        )
        if difficulty_level is not None:
            q = q.where(QuestionBank.difficulty_level == difficulty_level)
        if question_type is not None:
            q = q.where(QuestionBank.question_type == question_type)

        rows = (await self.db.execute(q)).all()

        return [
            ReplacementCandidate(
                question_id=row.question_id,
                question_text=row.question_text,
                question_type=row.question_type,
                options=[QuestionOption(key=o["key"], text=o["text"]) for o in (row.options or [])],
                correct_answer_key=row.correct_answer,
                difficulty_level=int(row.difficulty_level) if row.difficulty_level is not None else 0,
                subtopic_name=row.subtopic_name,
                topic_name=row.topic_name,
            )
            for row in rows
        ]

    async def replace_question(
        self,
        assessment_id: uuid.UUID,
        old_question_id: uuid.UUID,
        replacement_id: uuid.UUID,
        school_id: uuid.UUID | None,
        teacher_id: uuid.UUID,
    ) -> ReplaceQuestionResponse:
        """Swap one question in the pool for another.

        Preserves the order_index of the replaced question.
        Returns has_responses_for_old=True if students have answered the old question
        (frontend warns but does NOT block).

        Raises:
            ValueError: old question not in pool, replacement not found or already in pool.
            TeacherNotClassOwnerError: Teacher does not own the assessment.
        """
        await self._verify_teacher_owns_assessment(assessment_id, school_id, teacher_id)

        # Load the old bridge row (need its order_index)
        old_bridge = (
            await self.db.execute(
                select(AssessmentSelectedQuestion).where(
                    AssessmentSelectedQuestion.assessment_id == assessment_id,
                    AssessmentSelectedQuestion.question_id == old_question_id,
                )
            )
        ).scalar_one_or_none()
        if old_bridge is None:
            raise ValueError(f"Question {old_question_id} is not in assessment pool {assessment_id}")

        # Verify replacement is not already in pool
        existing_replacement = (
            await self.db.execute(
                select(AssessmentSelectedQuestion).where(
                    AssessmentSelectedQuestion.assessment_id == assessment_id,
                    AssessmentSelectedQuestion.question_id == replacement_id,
                )
            )
        ).scalar_one_or_none()
        if existing_replacement is not None:
            raise ValueError(f"Question {replacement_id} is already in the assessment pool.")

        # Verify replacement exists in question_bank
        replacement_exists = (
            await self.db.execute(
                select(QuestionBank.id).where(
                    QuestionBank.id == replacement_id,
                    QuestionBank.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
        if replacement_exists is None:
            raise ValueError(f"Replacement question {replacement_id} not found or not active.")

        # Check if any student responded to the old question
        response_exists = (
            await self.db.execute(
                select(StudentResponse.id)
                .join(StudentAttempt, StudentAttempt.id == StudentResponse.attempt_id)
                .where(
                    StudentAttempt.assessment_id == assessment_id,
                    StudentResponse.question_id == old_question_id,
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        has_responses_for_old = response_exists is not None

        # Swap: delete old bridge, insert new at same order_index
        preserved_order = old_bridge.order_index
        await self.db.execute(
            delete(AssessmentSelectedQuestion.__table__).where(  # type: ignore
                AssessmentSelectedQuestion.assessment_id == assessment_id,
                AssessmentSelectedQuestion.question_id == old_question_id,
            )
        )
        self.db.add(
            AssessmentSelectedQuestion(
                assessment_id=assessment_id,
                question_id=replacement_id,
                order_index=preserved_order,
            )
        )

        logger.info(
            "question_replaced_in_pool",
            assessment_id=str(assessment_id),
            old_question_id=str(old_question_id),
            new_question_id=str(replacement_id),
            has_responses_for_old=has_responses_for_old,
            teacher_id=str(teacher_id),
        )

        return ReplaceQuestionResponse(has_responses_for_old=has_responses_for_old)

    async def suggest_question_edit(
        self,
        assessment_id: uuid.UUID,
        question_id: uuid.UUID,
        school_id: uuid.UUID | None,
        teacher_id: uuid.UUID,
        body: SuggestEditRequest,
    ) -> SuggestEditResponse:
        """Submit an edit suggestion for a question in the assessment pool.

        Creates a QuestionReviewItem (type=EDIT_SUGGESTION) for KaihleAdmin review.
        Does NOT modify the question_bank directly.
        Fires an async email notification to all KaihleAdmin users.

        Args:
            assessment_id: The assessment UUID.
            question_id: The question to suggest an edit for.
            school_id: Teacher's school (multi-tenancy).
            teacher_id: Must own the assessment.
            body: Proposed changes + required reason.

        Returns:
            SuggestEditResponse with review_item_id.

        Raises:
            ValueError: Assessment not found, question not in pool.
            TeacherNotClassOwnerError: Teacher does not own the assessment.
        """
        await self._verify_teacher_owns_assessment(assessment_id, school_id, teacher_id)

        # Verify question is in this assessment's pool
        in_pool = (
            await self.db.execute(
                select(AssessmentSelectedQuestion.question_id).where(
                    AssessmentSelectedQuestion.assessment_id == assessment_id,
                    AssessmentSelectedQuestion.question_id == question_id,
                )
            )
        ).scalar_one_or_none()
        if in_pool is None:
            raise ValueError(f"Question {question_id} is not in assessment pool {assessment_id}")

        review_item = QuestionReviewItem(
            id=uuid.uuid4(),
            item_type="EDIT_SUGGESTION",
            question_id=question_id,
            submitted_by=teacher_id,
            school_id=school_id,  # type: ignore[arg-type]
            assessment_id=assessment_id,
            suggested_question_text=body.suggested_question_text,
            suggested_options=body.suggested_options,  # type: ignore[arg-type]
            suggested_correct_answer=body.suggested_correct_answer,
            suggested_explanation=body.suggested_explanation,
            suggested_difficulty_level=body.suggested_difficulty_level,
            reason=body.reason,
            status="PENDING",
        )
        self.db.add(review_item)
        await self.db.flush()

        # Fire email notification to KaihleAdmin (non-blocking, deferred import to avoid cycle)
        try:
            from app.tasks.question_review_tasks import notify_kaihle_admins_of_review_item  # noqa: PLC0415

            notify_kaihle_admins_of_review_item.delay(str(review_item.id), "EDIT_SUGGESTION", str(teacher_id))
        except Exception:  # noqa: BLE001
            logger.warning(
                "edit_suggestion_email_task_failed",
                review_item_id=str(review_item.id),
            )

        logger.info(
            "edit_suggestion_submitted",
            assessment_id=str(assessment_id),
            question_id=str(question_id),
            review_item_id=str(review_item.id),
            teacher_id=str(teacher_id),
        )

        return SuggestEditResponse(review_item_id=review_item.id)


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
