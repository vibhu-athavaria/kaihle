"""Study plan API routes.

Three sections:
1. Class-scoped assignment — POST /classes/{id}/study-plans (teacher assigns)
2. Student-scoped list — GET /students/me/study-plans and GET /students/{id}/study-plans
3. Plan-scoped operations — /study-plans/{plan_id}/...

Stub implementations. Real implementation: M3-2-T2.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, require_full_access, require_role
from app.models.user import UserRole
from app.schemas.common import Page
from app.schemas.study_plans import (
    QuizSubmitRequest,
    QuizSubmitResponse,
    StudyPlanAssignRequest,
    StudyPlanAssignResponse,
    StudyPlanResponse,
)

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
    # STUB — M0-10-T4 | Real implementation: M3-2-T2
    # 202 Accepted is correct — generation is async (Celery).
    # M3 adds: create StudyPlan rows, queue generation Celery tasks per student.
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Study plan assignment is available from M3.",
    )


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
    # STUB — M0-10-T4 | Real implementation: M3-2-T2
    # /me shortcut — resolves to authenticated student's own plans.
    return Page(data=[], total=0, page=page, page_size=page_size)


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
    # STUB — M0-10-T4 | Real implementation: M3-2-T2
    # M3 adds: student sees own only, teacher sees class students only,
    # parent sees linked child only.
    return Page(data=[], total=0, page=page, page_size=page_size)


# ── Plan-scoped operations ────────────────────────────────────────────────────


@router.get("/study-plans/{plan_id}", response_model=StudyPlanResponse)
async def get_study_plan(
    plan_id: UUID,
    current_user: CurrentUser = Depends(require_full_access),
    db: AsyncSession = Depends(get_db),
) -> StudyPlanResponse:
    # STUB — M0-10-T4 | Real implementation: M3-2-T2
    # M3 adds: ownership check, resource list, quiz questions (no correct_answer).
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="No study plans assigned yet.",
    )


@router.patch(
    "/study-plans/{plan_id}/resources/{resource_id}/watched",
    response_model=dict[str, object],
)
async def mark_resource_watched(
    plan_id: UUID,
    resource_id: UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.STUDENT)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    # STUB — M0-10-T4 | Real implementation: M3-2-T2
    # Plausible stub response — the shape is simple enough to stub meaningfully.
    # M3 adds: verify student owns plan, upsert watched record in DB.
    return {"resource_id": str(resource_id), "is_watched": True}


@router.post("/study-plans/{plan_id}/quiz/submit", response_model=QuizSubmitResponse)
async def submit_study_plan_quiz(
    plan_id: UUID,
    body: QuizSubmitRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.STUDENT)),
    db: AsyncSession = Depends(get_db),
) -> QuizSubmitResponse:
    # STUB — M0-10-T4 | Real implementation: M3-2-T2
    # M3 adds: score MCQ responses, update gap_states, update plan status.
    return QuizSubmitResponse(
        score=0.0,
        correct_count=0,
        total_questions=0,
        plan_status="IN_PROGRESS",
    )
