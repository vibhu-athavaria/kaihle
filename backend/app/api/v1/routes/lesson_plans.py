"""Lesson plan API routes.

Two sections:
1. Class-scoped list + generate — /classes/{class_id}/lesson-plans
   (teacher generates on-demand, views all plans for a class)
2. Plan-scoped operations — /lesson-plans/{plan_id}/...
   (fetch, edit, regenerate, mark status on a specific plan)

Lesson plans are generated on-demand by the teacher.
No weekly auto-gen — teachers trigger generation per class topic.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, require_role
from app.models.user import UserRole
from app.schemas.common import Page
from app.schemas.lesson_plans import (
    GenerateLessonPlanRequest,
    LessonPlanEditRequest,
    LessonPlanResponse,
    LessonPlanStatusRequest,
)

router = APIRouter(tags=["lesson-plans"])


# ── Class-scoped ──────────────────────────────────────────────────────────────


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
    from app.services import lesson_plan_service

    plan = await lesson_plan_service.generate_lesson_plan(
        class_id=class_id,
        teacher_id=current_user.id,
        school_id=current_user.school_id,
        focus_subtopic_ids=body.focus_subtopic_ids,
        db=db,
    )
    return lesson_plan_service._to_response(plan)


@router.get("/classes/{class_id}/lesson-plans", response_model=Page[LessonPlanResponse])
async def list_class_lesson_plans(
    class_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER, UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> Page[LessonPlanResponse]:
    from app.services import lesson_plan_service

    return await lesson_plan_service.list_class_lesson_plans(
        class_id=class_id,
        teacher_id=current_user.id,
        school_id=current_user.school_id,
        page=page,
        page_size=page_size,
        db=db,
    )


# ── Plan-scoped ───────────────────────────────────────────────────────────────


@router.get("/lesson-plans/{plan_id}", response_model=LessonPlanResponse)
async def get_lesson_plan(
    plan_id: UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER, UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> LessonPlanResponse:
    from app.services import lesson_plan_service

    return await lesson_plan_service.get_lesson_plan(
        plan_id=plan_id,
        teacher_id=current_user.id,
        school_id=current_user.school_id,
        db=db,
    )


@router.patch("/lesson-plans/{plan_id}", response_model=LessonPlanResponse)
async def edit_lesson_plan(
    plan_id: UUID,
    body: LessonPlanEditRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER, UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> LessonPlanResponse:
    from app.services import lesson_plan_service

    return await lesson_plan_service.edit_lesson_plan(
        plan_id=plan_id,
        teacher_id=current_user.id,
        school_id=current_user.school_id,
        body=body,
        db=db,
    )


@router.post("/lesson-plans/{plan_id}/regenerate", response_model=LessonPlanResponse)
async def regenerate_lesson_plan(
    plan_id: UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER, UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> LessonPlanResponse:
    from app.services import lesson_plan_service

    return await lesson_plan_service.regenerate_lesson_plan(
        plan_id=plan_id,
        teacher_id=current_user.id,
        school_id=current_user.school_id,
        db=db,
    )


@router.patch("/lesson-plans/{plan_id}/status", response_model=LessonPlanResponse)
async def update_lesson_plan_status(
    plan_id: UUID,
    body: LessonPlanStatusRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER, UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> LessonPlanResponse:
    from app.services import lesson_plan_service

    return await lesson_plan_service.update_lesson_plan_status(
        plan_id=plan_id,
        teacher_id=current_user.id,
        school_id=current_user.school_id,
        new_status=body.status,
        db=db,
    )
