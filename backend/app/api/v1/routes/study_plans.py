"""Study plan API routes — M3-2-T2.

Replaces M0-10-T4 stubs with real service calls.
Route decorators, paths, response models, and status codes are frozen (CONSTITUTION Rule 19).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, require_full_access, require_role
from app.models import Class, ClassEnrollment
from app.models.user import UserRole
from app.schemas.common import Page
from app.schemas.study_plans import (
    QuizSubmitRequest,
    QuizSubmitResponse,
    StudyPlanAssignRequest,
    StudyPlanAssignResponse,
    StudyPlanResponse,
)
from app.services import study_plan_service as sp_service

router = APIRouter(tags=["study-plans"])


# ── Teacher: assign plans to students ────────────────────────────────────────


@router.post(
    "/classes/{class_id}/study-plans",
    response_model=StudyPlanAssignResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def assign_study_plans(
    class_id: UUID,
    body: StudyPlanAssignRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER)),
    db: AsyncSession = Depends(get_db),
) -> StudyPlanAssignResponse:
    # Verify class ownership (same pattern as AssessmentService)
    class_result = await db.execute(
        select(Class).where(
            Class.id == class_id,
            Class.school_id == current_user.school_id,
        )
    )
    class_ = class_result.scalar_one_or_none()
    if not class_:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")
    if class_.teacher_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not own this class")

    plans = await sp_service.create_bulk_study_plans(
        config=body,
        class_id=class_id,
        assigned_by=current_user.id,
        db=db,
    )

    return StudyPlanAssignResponse(plans=plans)


# ── Student: view own plans ───────────────────────────────────────────────────


@router.get("/students/me/study-plans", response_model=Page[StudyPlanResponse])
async def list_my_study_plans(
    status_filter: str | None = Query(None, alias="status"),
    subject_id: UUID | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: CurrentUser = Depends(require_role(UserRole.STUDENT)),
    db: AsyncSession = Depends(get_db),
) -> Page[StudyPlanResponse]:
    """List the current student's own study plans.

    Authorization: STUDENT role — no further check (JWT identifies the student).
    """
    if current_user.school_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User has no school_id")

    return await sp_service.list_student_plans(
        student_id=current_user.id,
        school_id=current_user.school_id,
        db=db,
        status_filter=status_filter,
        subject_id=subject_id,
        page=page,
        page_size=page_size,
    )


@router.get("/students/{student_id}/study-plans", response_model=Page[StudyPlanResponse])
async def list_student_study_plans(
    student_id: UUID,
    status_filter: str | None = Query(None, alias="status"),
    subject_id: UUID | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: CurrentUser = Depends(require_full_access),
    db: AsyncSession = Depends(get_db),
) -> Page[StudyPlanResponse]:
    """List study plans for a specific student.

    Authorization:
    - STUDENT may only list their own plans.
    - TEACHER may list plans for students enrolled in their classes.
    - PARENT / KAIHLE_ADMIN: always allowed (require_full_access).
    """
    # Students can only see their own plans
    if current_user.role == UserRole.STUDENT and current_user.id != student_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot view another student's plans")

    # Teachers: verify class membership
    if current_user.role == UserRole.TEACHER:
        enrollment = await db.execute(
            select(ClassEnrollment.class_id)
            .join(Class, Class.id == ClassEnrollment.class_id)
            .where(
                ClassEnrollment.student_id == student_id,
                Class.teacher_id == current_user.id,
            )
        )
        if enrollment.scalar_one_or_none() is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Student not in your class")

    # Use the student's school_id for the query
    student_school_result = await db.execute(
        select(Class.school_id)
        .join(ClassEnrollment, ClassEnrollment.class_id == Class.id)
        .where(ClassEnrollment.student_id == student_id)
        .limit(1)
    )
    school_id = student_school_result.scalar_one_or_none() or current_user.school_id
    if school_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot determine school for student")

    return await sp_service.list_student_plans(
        student_id=student_id,
        school_id=school_id,
        db=db,
        status_filter=status_filter,
        subject_id=subject_id,
        page=page,
        page_size=page_size,
    )


# ── Plan-scoped operations ────────────────────────────────────────────────────


@router.get("/study-plans/{plan_id}", response_model=StudyPlanResponse)
async def get_study_plan(
    plan_id: UUID,
    current_user: CurrentUser = Depends(require_full_access),
    db: AsyncSession = Depends(get_db),
) -> StudyPlanResponse:
    """Get a single study plan by ID.

    Authorization:
    - STUDENT: must own the plan.
    - TEACHER: must own the class the plan belongs to.
    - PARENT / KAIHLE_ADMIN: always allowed.
    """
    school_id = current_user.school_id
    if school_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User has no school_id")
    try:
        plan = await sp_service.get_study_plan(
            plan_id=plan_id,
            student_id=current_user.id,
            school_id=school_id,
            user_role=current_user.role,
            db=db,
        )
        return plan
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch(
    "/study-plans/{plan_id}/resources/{resource_id}/watched",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def mark_resource_watched(
    plan_id: UUID,
    resource_id: UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.STUDENT)),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Mark a study plan resource as watched by the current student."""
    try:
        await sp_service.mark_resource_watched(
            plan_id=plan_id,
            resource_id=resource_id,
            student_id=current_user.id,
            db=db,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/study-plans/{plan_id}/quiz", response_model=QuizSubmitResponse)
async def submit_study_plan_quiz(
    plan_id: UUID,
    body: QuizSubmitRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.STUDENT)),
    db: AsyncSession = Depends(get_db),
) -> QuizSubmitResponse:
    """Submit quiz answers for a study plan.

    The plan must be ACTIVE and the current user must own it.
    Triggers async gap state recalculation after scoring.
    """
    try:
        return await sp_service.submit_quiz(
            plan_id=plan_id,
            request=body,
            student_id=current_user.id,
            db=db,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
