"""Lesson plan service — on-demand generation and management."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.curriculum import CurriculumTopic, Subtopic, Topic
from app.models.gap import GapState
from app.models.lesson_plan import LessonPlan, LessonPlanStatus
from app.models.school import Class
from app.schemas.common import Page
from app.schemas.lesson_plans import LessonPlanEditRequest, LessonPlanResponse, SubtopicContext

logger = structlog.get_logger(__name__)

_ALLOWED_STATUS_TRANSITIONS: dict[str, set[str]] = {
    LessonPlanStatus.GENERATED: {LessonPlanStatus.USED, LessonPlanStatus.ARCHIVED},
    LessonPlanStatus.EDITED: {LessonPlanStatus.USED, LessonPlanStatus.ARCHIVED},
}


async def generate_lesson_plan(
    class_id: UUID,
    teacher_id: UUID,
    school_id: UUID | None,
    focus_subtopic_ids: list[UUID],
    duration_minutes: int,
    db: AsyncSession,
) -> LessonPlan:
    """Create a LessonPlan row (status=GENERATING) and dispatch the Celery task.

    Returns the LessonPlan immediately — generation happens asynchronously.
    """
    from app.tasks.lesson_plan_tasks import generate_lesson_plan_task

    await _require_teacher_class(class_id, teacher_id, school_id, db)

    gap_summary = await _build_gap_summary(class_id, focus_subtopic_ids, db)

    plan = LessonPlan(
        class_id=class_id,
        teacher_id=teacher_id,
        focus_subtopic_ids=focus_subtopic_ids,
        gap_summary=gap_summary,
        generated_plan={},
        status=LessonPlanStatus.GENERATING,
        generated_at=datetime.now(UTC),
    )
    db.add(plan)
    await db.flush()
    await db.refresh(plan)

    generate_lesson_plan_task.delay(
        str(plan.id),
        str(class_id),
        [str(s) for s in focus_subtopic_ids],
        gap_summary,
        duration_minutes,
    )

    await db.commit()
    await db.refresh(plan)

    logger.info(
        "lesson_plan_generation_dispatched",
        plan_id=str(plan.id),
        class_id=str(class_id),
        teacher_id=str(teacher_id),
        subtopic_count=len(focus_subtopic_ids),
    )
    return plan  # caller converts to response with subtopic context


async def list_class_lesson_plans(
    class_id: UUID,
    teacher_id: UUID,
    school_id: UUID | None,
    page: int,
    page_size: int,
    db: AsyncSession,
) -> Page[LessonPlanResponse]:
    await _require_teacher_class(class_id, teacher_id, school_id, db)

    count_result = await db.execute(
        select(func.count()).where(
            LessonPlan.class_id == class_id,
            LessonPlan.teacher_id == teacher_id,
        )
    )
    total = count_result.scalar_one()

    result = await db.execute(
        select(LessonPlan)
        .where(LessonPlan.class_id == class_id, LessonPlan.teacher_id == teacher_id)
        .order_by(LessonPlan.generated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    plans = list(result.scalars().all())

    # Batch subtopic context for all plans in one query
    all_subtopic_ids = list({sid for p in plans for sid in p.focus_subtopic_ids})
    all_context = await _fetch_subtopic_context(all_subtopic_ids, db)
    context_by_id = {str(sc.subtopic_id): sc for sc in all_context}

    return Page(
        data=[
            _to_response(p, [context_by_id[str(sid)] for sid in p.focus_subtopic_ids if str(sid) in context_by_id])
            for p in plans
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


async def get_lesson_plan(
    plan_id: UUID,
    teacher_id: UUID,
    school_id: UUID | None,
    db: AsyncSession,
) -> LessonPlanResponse:
    plan = await _require_plan(plan_id, teacher_id, school_id, db)
    context = await _fetch_subtopic_context(list(plan.focus_subtopic_ids), db)
    return _to_response(plan, context)


async def edit_lesson_plan(
    plan_id: UUID,
    teacher_id: UUID,
    school_id: UUID | None,
    body: LessonPlanEditRequest,
    db: AsyncSession,
) -> LessonPlanResponse:
    plan = await _require_plan(plan_id, teacher_id, school_id, db)

    if plan.status == LessonPlanStatus.GENERATING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot edit a lesson plan that is still being generated.",
        )

    edits = body.model_dump(exclude_none=True)
    existing = dict(plan.teacher_edits or {})
    existing.update(edits)
    plan.teacher_edits = existing
    plan.status = LessonPlanStatus.EDITED
    plan.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(plan)
    context = await _fetch_subtopic_context(list(plan.focus_subtopic_ids), db)
    return _to_response(plan, context)


async def regenerate_lesson_plan(
    plan_id: UUID,
    teacher_id: UUID,
    school_id: UUID | None,
    db: AsyncSession,
) -> LessonPlanResponse:
    from app.tasks.lesson_plan_tasks import generate_lesson_plan_task

    plan = await _require_plan(plan_id, teacher_id, school_id, db)

    plan.generated_plan = {}
    plan.teacher_edits = None
    plan.status = LessonPlanStatus.GENERATING
    plan.generated_at = datetime.now(UTC)
    plan.updated_at = datetime.now(UTC)
    await db.flush()

    generate_lesson_plan_task.delay(
        str(plan.id),
        str(plan.class_id),
        [str(s) for s in plan.focus_subtopic_ids],
        plan.gap_summary,
    )

    await db.commit()
    await db.refresh(plan)
    context = await _fetch_subtopic_context(list(plan.focus_subtopic_ids), db)
    return _to_response(plan, context)


async def update_lesson_plan_status(
    plan_id: UUID,
    teacher_id: UUID,
    school_id: UUID | None,
    new_status: str,
    db: AsyncSession,
) -> LessonPlanResponse:
    plan = await _require_plan(plan_id, teacher_id, school_id, db)

    allowed = _ALLOWED_STATUS_TRANSITIONS.get(plan.status, set())
    if new_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot transition from {plan.status} to {new_status}.",
        )

    plan.status = new_status
    plan.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(plan)
    context = await _fetch_subtopic_context(list(plan.focus_subtopic_ids), db)
    return _to_response(plan, context)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _require_teacher_class(
    class_id: UUID,
    teacher_id: UUID,
    school_id: UUID | None,
    db: AsyncSession,
) -> Class:
    q = select(Class).where(Class.id == class_id)
    if school_id is not None:
        q = q.where(Class.school_id == school_id)
    result = await db.execute(q)
    class_ = result.scalar_one_or_none()
    if not class_:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found.")
    if school_id is not None and class_.teacher_id != teacher_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
    return class_


async def _require_plan(
    plan_id: UUID,
    teacher_id: UUID,
    school_id: UUID | None,
    db: AsyncSession,
) -> LessonPlan:
    q = select(LessonPlan).where(LessonPlan.id == plan_id)
    if school_id is not None:
        q = q.where(LessonPlan.teacher_id == teacher_id)
    result = await db.execute(q)
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson plan not found.")

    if school_id is not None:
        class_result = await db.execute(select(Class).where(Class.id == plan.class_id, Class.school_id == school_id))
        if not class_result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    return plan


async def _build_gap_summary(
    class_id: UUID,
    focus_subtopic_ids: list[UUID],
    db: AsyncSession,
) -> dict[str, Any]:
    """Average mastery per subtopic across all enrolled students."""
    if not focus_subtopic_ids:
        return {}

    rows = await db.execute(
        select(
            GapState.subtopic_id,
            func.avg(GapState.mastery_score).label("class_avg"),
            func.count(GapState.student_id).label("student_count"),
        )
        .where(
            GapState.class_id == class_id,
            GapState.subtopic_id.in_(focus_subtopic_ids),
        )
        .group_by(GapState.subtopic_id)
    )
    rows_list = rows.all()

    subtopic_ids = [r.subtopic_id for r in rows_list]
    subtopics_result = await db.execute(select(Subtopic).where(Subtopic.id.in_(subtopic_ids)))
    subtopics_map = {s.id: s for s in subtopics_result.scalars().all()}

    summary: dict[str, Any] = {}
    for row in rows_list:
        subtopic = subtopics_map.get(row.subtopic_id)
        summary[str(row.subtopic_id)] = {
            "name": subtopic.name if subtopic else str(row.subtopic_id),
            "learning_objective": subtopic.learning_objective if subtopic else "",
            "class_avg": float(row.class_avg),
            "student_count": int(row.student_count),
        }
    return summary


async def _fetch_subtopic_context(
    subtopic_ids: list[UUID],
    db: AsyncSession,
) -> list[SubtopicContext]:
    """Fetch subtopic names and their parent topic names for a list of IDs."""
    if not subtopic_ids:
        return []

    rows = await db.execute(
        select(Subtopic.id, Subtopic.name, Topic.name.label("topic_name"))
        .join(CurriculumTopic, CurriculumTopic.id == Subtopic.curriculum_topic_id)
        .join(Topic, Topic.id == CurriculumTopic.topic_id)
        .where(Subtopic.id.in_(subtopic_ids))
    )
    id_order = {sid: i for i, sid in enumerate(subtopic_ids)}
    results = sorted(rows.all(), key=lambda r: id_order.get(r.id, 9999))
    return [SubtopicContext(subtopic_id=r.id, name=r.name, topic_name=r.topic_name) for r in results]


def _to_response(
    plan: LessonPlan,
    focus_subtopics: list[SubtopicContext],
) -> LessonPlanResponse:
    generated = dict(plan.generated_plan or {})
    if plan.teacher_edits:
        generated.update(plan.teacher_edits)

    return LessonPlanResponse(
        id=plan.id,
        class_id=plan.class_id,
        week_start=plan.week_start,
        status=plan.status,
        generated_plan=generated if generated else None,
        teacher_edits=plan.teacher_edits,
        gap_summary=plan.gap_summary or {},
        focus_subtopics=focus_subtopics,
        generated_at=plan.generated_at,
        failure_code=plan.failure_code,
        failure_reason=plan.failure_reason,
    )
