"""Assessment API routes.

Two logical sections:
1. Class-scoped list — GET /classes/{class_id}/assessments
   (teacher sees assessments for their class dashboard)
2. Assessment-scoped operations — /assessments/{assessment_id}/...
   (operate on a specific assessment by ID)

Stub implementations. Real implementation: M1-3-T2.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, require_role
from app.models.user import UserRole
from app.schemas.assessments import (
    AssessmentCreateRequest,
    AssessmentResponse,
)
from app.schemas.common import Page

router = APIRouter(tags=["assessments"])


# ── Class-scoped list ─────────────────────────────────────────────────────────


@router.get("/classes/{class_id}/assessments", response_model=Page[AssessmentResponse])
async def list_class_assessments(
    class_id: UUID,
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: CurrentUser = Depends(
        require_role(UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.KAIHLE_ADMIN, UserRole.STUDENT)
    ),
    db: AsyncSession = Depends(get_db),
) -> Page[AssessmentResponse]:
    # STUB — M0-10-T3 | Real implementation: M1-3-T2
    # M1 adds: teacher-owns-class check, real DB query filtered by class_id + status.
    return Page(data=[], total=0, page=page, page_size=page_size)


@router.post(
    "/classes/{class_id}/assessments",
    response_model=AssessmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_assessment(
    class_id: UUID,
    body: AssessmentCreateRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER)),
    db: AsyncSession = Depends(get_db),
) -> AssessmentResponse:
    # STUB — M0-10-T3 | Real implementation: M1-3-T2
    # Returns 501 for write operations — no data model to create against yet.
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Assessment creation is available from M1.",
    )


# ── Assessment-scoped operations ──────────────────────────────────────────────


@router.get("/assessments/{assessment_id}", response_model=AssessmentResponse)
async def get_assessment(
    assessment_id: UUID,
    current_user: CurrentUser = Depends(
        require_role(
            UserRole.TEACHER,
            UserRole.SCHOOL_ADMIN,
            UserRole.KAIHLE_ADMIN,
            UserRole.STUDENT,
        )
    ),
    db: AsyncSession = Depends(get_db),
) -> AssessmentResponse:
    # STUB — M0-10-T3 | Real implementation: M1-3-T2
    # M1 note: teacher/admin response includes correct_answer via
    # AssessmentQuestionWithAnswer; student response uses AssessmentQuestion (no answer).
    # Role-based field filtering is implemented in the service layer, not here.
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="No assessments exist yet.",
    )


@router.post("/assessments/{assessment_id}/publish", response_model=AssessmentResponse)
async def publish_assessment(
    assessment_id: UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER)),
    db: AsyncSession = Depends(get_db),
) -> AssessmentResponse:
    # STUB — M0-10-T3 | Real implementation: M1-3-T2
    # M1 adds: DRAFT → ACTIVE transition, deadline validation, empty-question guard.
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="No assessments exist yet.",
    )


@router.post("/assessments/{assessment_id}/close", response_model=AssessmentResponse)
async def close_assessment(
    assessment_id: UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER)),
    db: AsyncSession = Depends(get_db),
) -> AssessmentResponse:
    # STUB — M0-10-T3 | Real implementation: M1-3-T2
    # M1 adds: ACTIVE → CLOSED transition, prevents new attempts after close.
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="No assessments exist yet.",
    )
