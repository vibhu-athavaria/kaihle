"""Assessment API routes.

Two logical sections:
1. Class-scoped list — GET /classes/{class_id}/assessments
   (teacher sees assessments for their class dashboard)
2. Assessment-scoped operations — /assessments/{assessment_id}/...
   (operate on a specific assessment by ID)
"""

from datetime import datetime
from uuid import UUID

import structlog
from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, require_role
from app.models.assessment import Assessment
from app.models.user import UserRole
from app.schemas.assessments import (
    AssessmentCreateRequest,
    AssessmentResponse,
    AssessmentResultsSummary,
)
from app.schemas.common import Page
from app.services.assessment_service import (
    AssessmentAccessDeniedError,
    AssessmentService,
    InsufficientQuestionsError,
    TeacherNotClassOwnerError,
)

logger = structlog.get_logger()

router = APIRouter(tags=["assessments"])


class PublishRequest(BaseModel):
    deadline: datetime | None = None


def _assessment_to_response(assessment: Assessment) -> AssessmentResponse:
    """Convert an Assessment ORM model to AssessmentResponse schema.

    Note: topic_ids is not stored directly on the Assessment model — it is stored
    in the request body at creation time but not persisted as a top-level column.
    We return an empty list here as the schema requires the field but the model
    does not carry it; a future task (M1-3-T*) may add a persisted topics column.
    """
    return AssessmentResponse(
        id=assessment.id,
        class_id=assessment.class_id,
        title=assessment.title,
        assessment_type=assessment.assessment_type,
        is_system_generated=assessment.is_system_generated,
        status=assessment.status,
        topic_ids=[],  # not stored on model; see docstring
        question_count=assessment.question_count or 0,
        created_at=assessment.created_at,
        published_at=assessment.published_at,
        deadline=assessment.deadline,
    )


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
    service = AssessmentService(db)
    try:
        items, total = await service.list_class_assessments(
            class_id=class_id,
            school_id=current_user.school_id,
            requesting_user_id=current_user.id,
            requesting_user_role=current_user.role,
            status_filter=status_filter,
            page=page,
            page_size=page_size,
        )
    except TeacherNotClassOwnerError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this class.",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    return Page(
        data=[_assessment_to_response(a) for a in items],
        total=total,
        page=page,
        page_size=page_size,
    )


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
    service = AssessmentService(db)
    try:
        assessment = await service.create_assessment(
            school_id=current_user.school_id,
            teacher_id=current_user.id,
            class_id=class_id,
            body=body,
        )
        await db.commit()
    except TeacherNotClassOwnerError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this class.",
        )
    except InsufficientQuestionsError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Insufficient questions in the question bank for this assessment.",
                "available": exc.available,
                "requested": exc.requested,
            },
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    return _assessment_to_response(assessment)


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
    service = AssessmentService(db)
    try:
        assessment, _questions = await service.get_assessment(
            assessment_id=assessment_id,
            school_id=current_user.school_id,
            requesting_user_id=current_user.id,
            requesting_user_role=current_user.role,
        )
    except AssessmentAccessDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied.",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    return _assessment_to_response(assessment)


@router.post("/assessments/{assessment_id}/publish", response_model=AssessmentResponse)
async def publish_assessment(
    assessment_id: UUID,
    body: PublishRequest | None = Body(None),
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER)),
    db: AsyncSession = Depends(get_db),
) -> AssessmentResponse:
    service = AssessmentService(db)
    deadline = body.deadline if body else None
    try:
        assessment = await service.publish_assessment(
            assessment_id=assessment_id,
            school_id=current_user.school_id,
            teacher_id=current_user.id,
            deadline=deadline,
        )
        await db.commit()
    except TeacherNotClassOwnerError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to publish this assessment.",
        )
    except ValueError as exc:
        msg = str(exc)
        if "not found" in msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
        # Status conflict (already ACTIVE/CLOSED)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=msg)

    return _assessment_to_response(assessment)


@router.get("/assessments/{assessment_id}/results", response_model=AssessmentResultsSummary)
async def get_assessment_results(
    assessment_id: UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> AssessmentResultsSummary:
    """Return all student attempt summaries for an assessment (class overview).

    Distinct from GET /attempts/{id}/results which returns per-question breakdown
    for a single student attempt.
    """
    service = AssessmentService(db)
    try:
        return await service.get_assessment_results(
            assessment_id=assessment_id,
            school_id=current_user.school_id,
            requesting_user_id=current_user.id,
            requesting_user_role=current_user.role,
        )
    except AssessmentAccessDeniedError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/assessments/{assessment_id}/close", response_model=AssessmentResponse)
async def close_assessment(
    assessment_id: UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER)),
    db: AsyncSession = Depends(get_db),
) -> AssessmentResponse:
    service = AssessmentService(db)
    try:
        assessment = await service.close_assessment(
            assessment_id=assessment_id,
            school_id=current_user.school_id,
            teacher_id=current_user.id,
        )
        await db.commit()
    except TeacherNotClassOwnerError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to close this assessment.",
        )
    except ValueError as exc:
        msg = str(exc)
        if "not found" in msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
        # Status conflict (not ACTIVE)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=msg)

    return _assessment_to_response(assessment)
