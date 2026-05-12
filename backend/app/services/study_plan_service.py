"""Study Plan Service — M3-2-T1.

Orchestrates creation of personalised study plans:
- create_bulk_study_plans: creates multiple plans (one per student)
- get_study_plan: fetches a plan with ownership check
- list_student_plans: paginated list with school isolation via Class join
- submit_quiz: scores quiz, updates plan status, triggers gap recalculation
- mark_resource_watched: marks a resource as watched

The async content generation (curation + quiz generation) is handled by
the Celery task generate_bulk_study_plan_content.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    Class,
    ClassEnrollment,
    CurriculumTopic,
    StudyPlan,
    StudyPlanQuiz,
    StudyPlanResource,
    Subtopic,
)
from app.models.study_plan import StudyPlanStatus
from app.models.user import OnboardingStatus
from app.schemas.common import Page
from app.schemas.study_plans import (
    QuizSubmitRequest,
    QuizSubmitResponse,
    StudyPlanAssignRequest,
    StudyPlanAssignResponse,
    StudyPlanItem,
    StudyPlanResponse,
    StudyPlanSkippedItem,
)
from app.schemas.study_plans import (
    StudyPlanResource as StudyPlanResourceSchema,
)
from app.tasks.gap_tasks import update_gap_state_from_quiz
from app.tasks.study_plan_tasks import generate_bulk_study_plan_content

logger = structlog.get_logger()

# Score threshold above which a study plan is considered "mastered"
MASTERED_THRESHOLD = 0.75


class DiagnosticNotCompletedError(Exception):
    """Raised when trying to assign a study plan before diagnostic is completed."""


class CeleryDispatchError(Exception):
    """Raised when the Celery task dispatch fails after the DB commit."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def create_bulk_study_plans(
    config: StudyPlanAssignRequest,
    class_id: UUID,
    assigned_by: UUID,
    db: AsyncSession,
) -> StudyPlanAssignResponse:
    """Create one study plan per student, each individually personalised.

    Students without a completed diagnostic are skipped and returned in the
    ``skipped`` field of the response (they do not cause an error).

    Args:
        config: Assignment request (subtopic_id and optional student_ids).
        class_id: UUID of the class (from route path param — not in request body).
        assigned_by: UUID of the teacher.
        db: Async SQLAlchemy session.

    Returns:
        StudyPlanAssignResponse with created plans and skipped students.

    Raises:
        DiagnosticNotCompletedError: if no eligible students exist.
        CeleryDispatchError: if the background task cannot be dispatched.
    """

    # Build the base query: only students who have completed the diagnostic.
    # This query is used whether or not student_ids was provided — it IS the
    # source of truth for eligible students.
    base_query = (
        select(ClassEnrollment.student_id)
        .where(ClassEnrollment.class_id == class_id)
        .where(ClassEnrollment.onboarding_diagnostic_status == OnboardingStatus.COMPLETED)
        .where(ClassEnrollment.is_active.is_(True))
    )

    if config.student_ids:
        # Explicit student list — intersect with diagnostic-completed set
        base_query = base_query.where(ClassEnrollment.student_id.in_(config.student_ids))

    result = await db.execute(base_query)
    eligible_student_ids: list[UUID] = [row[0] for row in result.all()]

    if not eligible_student_ids:
        raise DiagnosticNotCompletedError(f"No students have completed the diagnostic for class {class_id}")

    # Track which students were requested but not eligible (for the skipped list)
    skipped: list[StudyPlanSkippedItem] = []
    if config.student_ids:
        eligible_set = set(eligible_student_ids)
        for sid in config.student_ids:
            if sid not in eligible_set:
                skipped.append(StudyPlanSkippedItem(student_id=sid, reason="incomplete_diagnostic"))

    # Batch-create all StudyPlan rows in a single round-trip
    plans_to_create = [
        StudyPlan(
            student_id=sid,
            subtopic_id=config.subtopic_id,
            class_id=class_id,
            assigned_by=assigned_by,
            status=StudyPlanStatus.GENERATING,
        )
        for sid in eligible_student_ids
    ]
    db.add_all(plans_to_create)
    await db.flush()  # All IDs assigned in one DB round-trip

    plan_ids = [str(plan.id) for plan in plans_to_create]
    plan_items = [
        StudyPlanItem(plan_id=plan.id, student_id=plan.student_id, status=StudyPlanStatus.GENERATING)
        for plan in plans_to_create
    ]

    await db.commit()

    # Dispatch a single Celery task for all plans — AFTER commit succeeds.
    # Raising on dispatch failure so the HTTP response correctly reflects the error;
    # the DB rows are already committed so operators can manually retry.
    try:
        generate_bulk_study_plan_content.delay(plan_ids)
    except Exception as exc:
        logger.error(
            "celery_bulk_dispatch_failed",
            class_id=str(class_id),
            plan_count=len(plan_ids),
            error=str(exc),
        )
        raise CeleryDispatchError(
            f"Study plans were created (IDs: {plan_ids}) but the background "
            f"generation task could not be dispatched: {exc}"
        ) from exc

    logger.info(
        "bulk_study_plans_created",
        count=len(plan_items),
        skipped_count=len(skipped),
        subtopic_id=str(config.subtopic_id),
        class_id=str(class_id),
    )

    return StudyPlanAssignResponse(
        class_id=class_id,
        plans=plan_items,
        skipped=skipped,
    )


async def get_study_plan(
    plan_id: UUID,
    student_id: UUID,
    school_id: UUID,
    user_role: str,
    db: AsyncSession,
) -> StudyPlanResponse:
    """Fetch a study plan by ID with role-based ownership enforcement.

    CONSTITUTION Rule 12: KaihleAdmin bypass is explicit and first.
    STUDENT: must own the plan.
    TEACHER: must be the teacher of the class the plan belongs to.
    KAIHLE_ADMIN: can access any plan.

    Args:
        plan_id: UUID of the study plan.
        student_id: Requesting user's ID.
        school_id: Requesting user's school_id.
        user_role: Requesting user's role string.
        db: Async SQLAlchemy session.

    Raises:
        ValueError: If plan not found.
        PermissionError: If caller is not authorised to view this plan.
    """

    result = await db.execute(
        select(StudyPlan)
        .where(StudyPlan.id == plan_id)
        .options(
            selectinload(StudyPlan.resources),
            selectinload(StudyPlan.quiz),
        )
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise ValueError(f"Study plan {plan_id} not found")

    # Ownership / access check
    if user_role == "KAIHLE_ADMIN":
        pass  # explicit bypass per Rule 12
    elif user_role == "STUDENT":
        if plan.student_id != student_id:
            raise PermissionError("Access denied: plan belongs to a different student")
    elif user_role == "TEACHER":
        # Teacher must own the class
        class_result = await db.execute(select(Class).where(Class.id == plan.class_id))
        class_row = class_result.scalar_one_or_none()
        if not class_row or class_row.teacher_id != student_id:
            raise PermissionError("Access denied: not the teacher for this class")
    else:
        raise PermissionError("Access denied")

    # Load subtopic info
    subtopic_result = await db.execute(select(Subtopic).where(Subtopic.id == plan.subtopic_id))
    subtopic = subtopic_result.scalar_one_or_none()
    subtopic_name = subtopic.name if subtopic else ""

    return _build_plan_response(plan, subtopic_name)


async def submit_quiz(
    plan_id: UUID,
    student_id: UUID,
    request: QuizSubmitRequest,
    db: AsyncSession,
) -> QuizSubmitResponse:
    """Submit quiz responses for a study plan.

    Scores each response, updates the quiz record and plan status,
    and triggers gap state recalculation.

    Args:
        plan_id: UUID of the study plan.
        student_id: UUID of the student submitting.
        request: Quiz responses (QuizSubmitRequest schema).
        db: Async SQLAlchemy session.

    Returns:
        QuizSubmitResponse with score and correctness breakdown.

    Raises:
        ValueError: If plan not found, not owned by student, or not ACTIVE.
    """

    # Load and validate plan
    result = await db.execute(select(StudyPlan).where(StudyPlan.id == plan_id))
    plan = result.scalar_one_or_none()
    if not plan:
        raise ValueError(f"Study plan {plan_id} not found")
    if plan.student_id != student_id:
        raise ValueError("Plan is not owned by this student")
    if plan.status != StudyPlanStatus.ACTIVE:
        raise ValueError(f"Plan is not active (status: {plan.status})")

    # Load quiz
    quiz_result = await db.execute(select(StudyPlanQuiz).where(StudyPlanQuiz.plan_id == plan_id))
    quiz = quiz_result.scalar_one_or_none()
    if not quiz:
        raise ValueError("No quiz found for this plan")

    # Score responses — guard against non-string correct_answer
    questions = quiz.questions.get("questions", [])
    scored_results: list[dict[str, Any]] = []
    correct_count = 0

    for resp in request.responses:
        if resp.question_index >= len(questions):
            scored_results.append(
                {
                    "index": resp.question_index,
                    "answer": resp.answer,
                    "is_correct": False,
                    "score": 0.0,
                }
            )
            continue

        question = questions[resp.question_index]
        correct = str(question.get("correct_answer", "")).upper()
        given = resp.answer.upper()
        is_correct = given == correct
        score = 1.0 if is_correct else 0.0
        if is_correct:
            correct_count += 1

        scored_results.append(
            {
                "index": resp.question_index,
                "answer": resp.answer,
                "is_correct": is_correct,
                "score": score,
            }
        )

    total_questions = len(questions)
    final_score = correct_count / total_questions if total_questions > 0 else 0.0

    # Update quiz record
    quiz.student_answers = scored_results
    quiz.score = final_score
    quiz.completed_at = datetime.now(UTC)

    # Update plan status
    plan.status = StudyPlanStatus.COMPLETED
    plan.completed_at = datetime.now(UTC)

    await db.commit()

    logger.info(
        "quiz_submitted",
        plan_id=str(plan_id),
        student_id=str(student_id),
        score=final_score,
        correct_count=correct_count,
        total_questions=total_questions,
    )

    # Trigger gap state recalculation (async)
    try:
        update_gap_state_from_quiz.delay(str(plan_id), str(plan.subtopic_id))
    except Exception as exc:
        logger.warning(
            "gap_recalculation_queue_failed",
            plan_id=str(plan_id),
            error=str(exc),
        )

    return QuizSubmitResponse(
        score=final_score,
        correct_count=correct_count,
        total_questions=total_questions,
        plan_status=StudyPlanStatus.COMPLETED,
    )


async def list_student_plans(
    student_id: UUID,
    school_id: UUID,
    db: AsyncSession,
    status_filter: str | None = None,
    subject_id: UUID | None = None,
    page: int = 1,
    page_size: int = 20,
) -> Page[StudyPlanResponse]:
    """List study plans for a student with optional filtering.

    School isolation is enforced via a JOIN to the classes table
    (study_plans has no school_id column — see kaihle_v2_1_schema.sql).

    Args:
        student_id: UUID of the student.
        school_id: UUID of the school (enforces isolation via Class join).
        db: Async SQLAlchemy session.
        status_filter: Optional StudyPlanStatus to filter by.
        subject_id: Optional subject UUID to filter by.
        page: Page number (1-indexed).
        page_size: Number of items per page.

    Returns:
        Page of StudyPlanResponse objects.
    """

    # Base query with school isolation via Class join (Rule 3)
    query = (
        select(StudyPlan)
        .join(Class, StudyPlan.class_id == Class.id)
        .where(StudyPlan.student_id == student_id)
        .where(Class.school_id == school_id)
        .options(
            selectinload(StudyPlan.resources),
            selectinload(StudyPlan.quiz),
        )
        .order_by(StudyPlan.created_at.desc())
    )

    if status_filter is not None:
        query = query.where(StudyPlan.status == status_filter)

    if subject_id:
        query = (
            query.join(Subtopic, Subtopic.id == StudyPlan.subtopic_id)
            .join(CurriculumTopic, CurriculumTopic.id == Subtopic.curriculum_topic_id)
            .where(CurriculumTopic.subject_id == subject_id)
        )

    # Count total (without selectinload)
    count_query = select(func.count()).select_from(query.options().with_only_columns(StudyPlan.id).subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar_one() or 0

    # Paginate
    offset = (page - 1) * page_size
    result = await db.execute(query.offset(offset).limit(page_size))
    plans = result.scalars().all()

    # Batch-load subtopic names in a single query (no N+1)
    subtopic_ids = list({p.subtopic_id for p in plans})
    subtopic_map: dict[UUID, str] = {}
    if subtopic_ids:
        st_result = await db.execute(select(Subtopic).where(Subtopic.id.in_(subtopic_ids)))
        subtopic_map = {s.id: s.name for s in st_result.scalars().all()}

    responses = [_build_plan_response(plan, subtopic_map.get(plan.subtopic_id, "")) for plan in plans]

    return Page(data=responses, total=total, page=page, page_size=page_size)


async def mark_resource_watched(
    plan_id: UUID,
    resource_id: UUID,
    student_id: UUID,
    db: AsyncSession,
) -> None:
    """Mark a study plan resource as watched by the student.

    Args:
        plan_id: UUID of the study plan.
        resource_id: UUID of the resource.
        student_id: UUID of the student (must own the plan).

    Raises:
        ValueError: If plan not found or not owned by student.
    """

    result = await db.execute(select(StudyPlan).where(StudyPlan.id == plan_id))
    plan = result.scalar_one_or_none()
    if not plan:
        raise ValueError("Study plan not found")
    if plan.student_id != student_id:
        raise PermissionError("Not authorized to update this plan")

    stmt = (
        update(StudyPlanResource)
        .where(StudyPlanResource.id == resource_id)
        .where(StudyPlanResource.plan_id == plan_id)
        .values(is_watched=True)
    )
    await db.execute(stmt)
    await db.commit()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_plan_response(plan: StudyPlan, subtopic_name: str) -> StudyPlanResponse:
    """Build a StudyPlanResponse from an ORM plan instance.

    Assumes plan.resources and plan.quiz are already loaded (via selectinload).
    """
    resources = [
        StudyPlanResourceSchema(
            resource_id=r.id,
            title=r.title,
            resource_type=r.resource_type,
            url=r.url,
            source="KAIHLE",
            duration_minutes=r.duration_seconds // 60 if r.duration_seconds else None,
            is_watched=r.is_watched,
        )
        for r in (plan.resources or [])
    ]

    quiz_questions: list[dict[str, Any]] = []
    quiz_score: float | None = None
    if plan.quiz and plan.quiz.questions:
        quiz_questions = plan.quiz.questions.get("questions", [])
        quiz_score = plan.quiz.score

    # created_at is NOT NULL on TimestampMixin; the fallback is dead code
    return StudyPlanResponse(
        id=plan.id,
        student_id=plan.student_id,
        class_id=plan.class_id,
        subtopic_id=plan.subtopic_id,
        subtopic_name=subtopic_name,
        status=plan.status,
        resources=resources,
        quiz_questions=quiz_questions,
        quiz_score=quiz_score,
        created_at=plan.created_at,  # always non-null; no fallback needed
    )
