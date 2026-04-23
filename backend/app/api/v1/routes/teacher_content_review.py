"""Teacher content review API routes (M3-0-T2b).

Endpoints for teachers to review AI-generated explanations for their class's subtopics.
Scoped to the class context; teacher must own the class.

Routes:
- GET  /api/v1/teacher/classes/{class_id}/explanation-review
- GET  /api/v1/teacher/classes/{class_id}/explanation-review/{subtopic_id}
- PATCH /api/v1/teacher/classes/{class_id}/explanation-review/{subtopic_id}
"""

from datetime import UTC, datetime
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.database import get_db
from app.core.deps import CurrentUser, require_role
from app.models import Class, SubtopicContent
from app.models.curriculum import Grade, Subject, Subtopic
from app.models.gap import GapState
from app.models.school import ClassEnrollment
from app.models.subtopic_content import ContentType
from app.models.user import User, UserRole
from app.schemas.teacher_content import (
    TeacherExplanationReviewDetailResponse,
    TeacherExplanationReviewItem,
    TeacherExplanationReviewListResponse,
    TeacherExplanationReviewWithClass,
    TeacherExplanationUpdateRequest,
    TeacherExplanationUpdateResponse,
)
from app.services.teacher_content_service import list_all_explanation_content, list_explanation_content

logger = structlog.get_logger()

router = APIRouter(prefix="/teacher/classes", tags=["teacher-content-review"])
teacher_router = APIRouter(prefix="/teachers", tags=["teacher-content-review"])


# --- Helpers ---


async def _verify_class_ownership(
    db: AsyncSession,
    class_id: UUID,
    teacher_id: UUID,
) -> Class:
    """Verify teacher owns the class. Raises HTTPException if not."""
    result = await db.execute(select(Class).where(Class.id == class_id))
    class_ = result.scalar_one_or_none()
    if class_ is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Class {class_id} not found",
        )
    if class_.teacher_id != teacher_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this class",
        )
    return class_


# --- Routes ---


@router.get(
    "/{class_id}/explanation-review",
    response_model=TeacherExplanationReviewListResponse,
)
async def list_explanation_review(
    class_id: UUID = Path(..., description="Class ID"),
    status_filter: str | None = Query(
        default=None,
        alias="status",
        description="Filter by status: pending, approved, rejected, or all (default)",
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER)),
    db: AsyncSession = Depends(get_db),
) -> TeacherExplanationReviewListResponse:
    """List explanation content for review for a teacher's class."""
    class_ = await _verify_class_ownership(db, class_id, current_user.id)

    items, total, pending_count = await list_explanation_content(
        db=db,
        subject_id=class_.subject_id,
        grade_id=class_.grade_id,
        status_filter=status_filter,
        page=page,
        page_size=page_size,
    )

    return TeacherExplanationReviewListResponse(
        items=[TeacherExplanationReviewItem(**item) for item in items],
        total=total,
        pending_count=pending_count,
    )


@router.get(
    "/{class_id}/explanation-review/{subtopic_id}",
    response_model=TeacherExplanationReviewDetailResponse,
)
async def get_explanation_review_detail(
    class_id: UUID = Path(..., description="Class ID"),
    subtopic_id: UUID = Path(..., description="Subtopic ID"),
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER)),
    db: AsyncSession = Depends(get_db),
) -> TeacherExplanationReviewDetailResponse:
    """Get explanation detail for a specific subtopic in a class."""
    await _verify_class_ownership(db, class_id, current_user.id)

    result = await db.execute(
        select(SubtopicContent)
        .join(Subtopic, Subtopic.id == SubtopicContent.subtopic_id)
        .options(joinedload(SubtopicContent.subtopic).joinedload(Subtopic.curriculum_topic))
        .where(
            SubtopicContent.subtopic_id == subtopic_id,
            SubtopicContent.content_type == ContentType.EXPLANATION,
        )
    )
    sc = result.unique().scalar_one_or_none()

    if sc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No explanation content found for subtopic {subtopic_id}",
        )

    subtopic = sc.subtopic
    ct = subtopic.curriculum_topic if subtopic else None

    return TeacherExplanationReviewDetailResponse(
        subtopic_content_id=sc.id,
        subtopic_id=sc.subtopic_id,
        subtopic_name=subtopic.name if subtopic else str(subtopic_id),
        learning_objective=ct.learning_objective if ct else "",
        explanation_text=sc.explanation_text,
        teacher_explanation=sc.teacher_explanation,
        review_status=sc.review_status,
        has_teacher_override=sc.teacher_explanation is not None,
        applicable_tiers=sc.applicable_tiers or [],
    )


@router.patch(
    "/{class_id}/explanation-review/{subtopic_id}",
    response_model=TeacherExplanationUpdateResponse,
)
async def update_explanation_review(
    class_id: UUID = Path(..., description="Class ID"),
    subtopic_id: UUID = Path(..., description="Subtopic ID"),
    body: TeacherExplanationUpdateRequest | None = None,
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER)),
    db: AsyncSession = Depends(get_db),
) -> TeacherExplanationUpdateResponse:
    """Update explanation review status and/or add teacher override explanation."""
    if body is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request body is required",
        )
    await _verify_class_ownership(db, class_id, current_user.id)

    result = await db.execute(
        select(SubtopicContent).where(
            SubtopicContent.subtopic_id == subtopic_id,
            SubtopicContent.content_type == ContentType.EXPLANATION,
        )
    )
    sc = result.scalar_one_or_none()

    if sc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No explanation content found for subtopic {subtopic_id}",
        )

    if body.review_status is not None:
        sc.review_status = body.review_status.value
        sc.reviewed_at = datetime.now(UTC)
        sc.reviewed_by_id = current_user.id

    if body.teacher_explanation is not None:
        sc.teacher_explanation = body.teacher_explanation
        sc.teacher_explanation_author_id = current_user.id

    await db.commit()
    await db.refresh(sc)

    logger.info(
        "teacher_explanation_updated",
        user_id=str(current_user.id),
        class_id=str(class_id),
        subtopic_id=str(subtopic_id),
        review_status=sc.review_status,
        has_teacher_override=sc.teacher_explanation is not None,
    )

    return TeacherExplanationUpdateResponse(
        subtopic_content_id=sc.id,
        review_status=sc.review_status,
        teacher_explanation=sc.teacher_explanation,
        has_teacher_override=sc.teacher_explanation is not None,
    )


# --- Teacher-wide endpoints (no class_id) ---


@teacher_router.get(
    "/me/explanation-review",
    response_model=list[TeacherExplanationReviewWithClass],
)
async def list_all_teacher_explanation_review(
    status_filter: str | None = Query(
        default=None,
        alias="status",
        description="Filter by status: pending, approved, rejected, or all (default)",
    ),
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER)),
    db: AsyncSession = Depends(get_db),
) -> list[TeacherExplanationReviewWithClass]:
    """List explanation content for review across all classes owned by the teacher.

    More efficient than fetching per-class. Returns items with class info included.
    """
    if not current_user.school_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no school associated",
        )

    items = await list_all_explanation_content(
        db=db,
        teacher_id=current_user.id,
        school_id=current_user.school_id,
        status_filter=status_filter,
    )

    return [TeacherExplanationReviewWithClass(**item) for item in items]


# =============================================================================
# GET /teachers/{teacher_id} — teacher detail with assigned classes
# =============================================================================


class AssignedClassSummary(BaseModel):
    """Summary of a class assigned to a teacher."""

    class_id: UUID
    class_name: str
    subject_name: str
    grade_level: int
    student_count: int
    avg_mastery: float | None


class TeacherDetailResponse(BaseModel):
    """Full teacher profile for school-admin detail view."""

    id: UUID
    first_name: str
    last_name: str
    email: str
    is_active: bool
    assigned_classes: list[AssignedClassSummary]


@teacher_router.get("/{teacher_id}", response_model=TeacherDetailResponse)
async def get_teacher_detail(
    teacher_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_role(UserRole.SCHOOL_ADMIN, UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> TeacherDetailResponse:
    """Get full teacher detail including assigned classes.

    Auth: SCHOOL_ADMIN (same school) or KAIHLE_ADMIN only.

    Raises:
        404: If teacher not found.
    """
    teacher_query = select(User).where(User.id == teacher_id, User.role == UserRole.TEACHER)
    if current_user.role == UserRole.SCHOOL_ADMIN:
        teacher_query = teacher_query.where(User.school_id == current_user.school_id)

    teacher_result = await db.execute(teacher_query)
    teacher = teacher_result.scalar_one_or_none()

    if teacher is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Teacher not found",
        )

    # Fetch all active classes for this teacher
    classes_query = (
        select(Class, Subject, Grade)
        .join(Subject, Subject.id == Class.subject_id)
        .join(Grade, Grade.id == Class.grade_id)
        .where(
            Class.teacher_id == teacher_id,
            Class.is_active.is_(True),
        )
        .order_by(Class.name)
    )
    classes_result = await db.execute(classes_query)
    class_rows = classes_result.all()

    assigned_classes: list[AssignedClassSummary] = []
    for class_, subject, grade in class_rows:
        # Count active enrollments
        count_result = await db.execute(
            select(func.count(ClassEnrollment.class_id)).where(
                ClassEnrollment.class_id == class_.id,
                ClassEnrollment.is_active.is_(True),
            )
        )
        student_count = count_result.scalar() or 0

        # Average mastery score across all gap states in this class
        avg_result = await db.execute(select(func.avg(GapState.mastery_score)).where(GapState.class_id == class_.id))
        avg_mastery: float | None = avg_result.scalar()

        assigned_classes.append(
            AssignedClassSummary(
                class_id=class_.id,
                class_name=class_.name,
                subject_name=subject.name if subject else "",
                grade_level=grade.level if grade else 0,
                student_count=student_count,
                avg_mastery=avg_mastery,
            )
        )

    logger.info(
        "teacher_detail_requested",
        requester_id=str(current_user.id),
        requester_role=str(current_user.role),
        target_teacher_id=str(teacher_id),
        class_count=len(assigned_classes),
    )

    return TeacherDetailResponse(
        id=teacher.id,
        first_name=teacher.first_name or "",
        last_name=teacher.last_name or "",
        email=teacher.email,
        is_active=teacher.is_active,
        assigned_classes=assigned_classes,
    )
