"""Lesson plan API routes.

Two sections:
1. Class-scoped list + generate — /classes/{class_id}/lesson-plans
   (teacher generates on-demand, views all plans for a class)
2. Plan-scoped operations — /lesson-plans/{plan_id}/...
   (fetch, edit, regenerate, mark status on a specific plan)

Lesson plans are generated on-demand by the teacher (M4-1-T1).
No weekly auto-gen — teachers trigger generation per class topic.

Stub implementations. Real implementation: M4-1-T3.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, require_role
from app.models.user import UserRole
from app.schemas.common import Page
from app.schemas.lesson_plans import (
    LessonPlanEditRequest,
    LessonPlanResponse,
    LessonPlanStatusRequest,
)

router = APIRouter(tags=["lesson-plans"])


class GenerateLessonPlanRequest(BaseModel):
    """Request body for on-demand lesson plan generation."""

    focus_subtopic_ids: list[UUID]


# ── Class-scoped list ─────────────────────────────────────────────────────────


@router.post(
    "/classes/{class_id}/lesson-plans/generate",
    response_model=LessonPlanResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate_lesson_plan(
    class_id: UUID,
    body: GenerateLessonPlanRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER, UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> LessonPlanResponse:
    # STUB — M4-1-T3
    # Real implementation:
    # 1. Verify teacher owns class.
    # 2. Build gap_summary snapshot from GapState for body.focus_subtopic_ids.
    # 3. Dispatch Celery task: generate_lesson_plan_task.delay(class_id, subtopic_ids, gap_summary).
    # 4. Create LessonPlan row with status=GENERATING and return it immediately (202).
    # Cache key: (class_id, sorted(focus_subtopic_ids)).
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Lesson plan generation not yet implemented."
    )


@router.get("/classes/{class_id}/lesson-plans", response_model=Page[LessonPlanResponse])
async def list_class_lesson_plans(
    class_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER, UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> Page[LessonPlanResponse]:
    # STUB — M0-10-T5 | Real implementation: M4-1-T3
    # M4 adds: teacher-owns-class check, real lesson_plans DB query.
    return Page(data=[], total=0, page=page, page_size=page_size)


# ── Plan-scoped operations ────────────────────────────────────────────────────


@router.get("/lesson-plans/{plan_id}", response_model=LessonPlanResponse)
async def get_lesson_plan(
    plan_id: UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER, UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> LessonPlanResponse:
    # STUB — M0-10-T5 | Real implementation: M4-1-T3
    # M4 note: response merges teacher_edits over generated_plan before returning.
    # The merge happens in the service layer — this route just calls the service.
    raise HTTPException(status_code=404, detail="No lesson plans generated yet.")


@router.patch("/lesson-plans/{plan_id}", response_model=LessonPlanResponse)
async def edit_lesson_plan(
    plan_id: UUID,
    body: LessonPlanEditRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER, UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> LessonPlanResponse:
    # STUB — M0-10-T5 | Real implementation: M4-1-T3
    # M4 adds: accumulate edits in teacher_edits JSONB column (never overwrite
    # generated_plan), set status to EDITED.
    raise HTTPException(status_code=404, detail="No lesson plans to edit yet.")


@router.post("/lesson-plans/{plan_id}/regenerate", response_model=LessonPlanResponse)
async def regenerate_lesson_plan(
    plan_id: UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER, UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> LessonPlanResponse:
    # STUB — M0-10-T5 | Real implementation: M4-1-T3
    # M4 adds: queue regeneration Celery task, clear previous generated_plan
    # and teacher_edits, set status back to GENERATING.
    raise HTTPException(status_code=404, detail="No lesson plans to regenerate yet.")


@router.patch("/lesson-plans/{plan_id}/status", response_model=LessonPlanResponse)
async def update_lesson_plan_status(
    plan_id: UUID,
    body: LessonPlanStatusRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER, UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> LessonPlanResponse:
    # STUB — M0-10-T5 | Real implementation: M4-1-T3
    # M4 adds: validate status transition (GENERATED|EDITED → USED|ARCHIVED only).
    raise HTTPException(status_code=404, detail="No lesson plans to update yet.")
