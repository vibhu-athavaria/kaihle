"""Class topics API routes.

Teacher manages which curriculum topics are included in their class, their order,
and whether each has been covered already.

Routes:
  GET    /classes/{class_id}/topics                    - List class topics
  POST   /classes/{class_id}/topics                    - Add a topic
  PUT    /classes/{class_id}/topics/{class_topic_id}   - Update is_covered / sequence_order
  DELETE /classes/{class_id}/topics/{class_topic_id}   - Remove a topic
  PUT    /classes/{class_id}/topics/reorder            - Bulk reorder after drag-and-drop
  GET    /classes/{class_id}/topics/available          - List curriculum topics not yet added
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, require_role
from app.models.school import ClassEnrollment
from app.models.user import UserRole
from app.schemas.class_topic import (
    ClassTopicAdd,
    ClassTopicReorder,
    ClassTopicResponse,
    ClassTopicUpdate,
)
from app.services.class_service import ClassService
from app.services.class_topic_service import (
    ClassTopicNotFoundError,
    ClassTopicService,
    DuplicateClassTopicError,
)

router = APIRouter(tags=["class-topics"])


async def _verify_student_enrolled(
    class_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession,
) -> None:
    """Raise 404 if the student is not enrolled in the class."""
    result = await db.execute(
        select(ClassEnrollment).where(
            ClassEnrollment.class_id == class_id,
            ClassEnrollment.student_id == current_user.id,
            ClassEnrollment.is_active.is_(True),
        )
    )
    enrollment = result.scalar_one_or_none()
    if enrollment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You are not enrolled in this class",
        )


async def _verify_teacher_owns_class(
    class_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession,
) -> None:
    """Raise 403 if the caller is not authorised to manage this class's topics.

    - KAIHLE_ADMIN: bypass (cross-school access, per Rule 12).
    - SCHOOL_ADMIN: must belong to the same school as the class.
    - TEACHER: must be the assigned teacher of the class.
    """
    if current_user.role == UserRole.KAIHLE_ADMIN:
        return
    service = ClassService(db)
    class_ = await service.get_class(class_id)
    if current_user.role == UserRole.SCHOOL_ADMIN:
        if current_user.school_id != class_.school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this class",
            )
        return
    if current_user.role == UserRole.TEACHER and class_.teacher_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this class",
        )


@router.get("/classes/{class_id}/topics", response_model=list[ClassTopicResponse])
async def list_class_topics(
    class_id: uuid.UUID,
    current_user: CurrentUser = Depends(
        require_role(UserRole.STUDENT, UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.KAIHLE_ADMIN)
    ),
    db: AsyncSession = Depends(get_db),
) -> list[ClassTopicResponse]:
    """List topics for a class, ordered by sequence_order.

    Students must be enrolled in the class to view topics.
    Teachers, admins, and Kaihle admins can view topics for their classes.
    """
    # Verify enrollment for students
    if current_user.role == UserRole.STUDENT:
        await _verify_student_enrolled(class_id, current_user, db)

    service = ClassTopicService(db)
    return await service.list_topics(class_id)


@router.get(
    "/classes/{class_id}/topics/diagnostic",
    response_model=dict[str, object],
)
async def list_topics_for_diagnostic(
    class_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """Return current and previous grade topics for the diagnostic wizard topic picker."""
    service = ClassTopicService(db)
    try:
        return await service.list_topics_for_diagnostic(class_id)
    except ClassTopicNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/classes/{class_id}/topics/available",
    response_model=list[dict[str, object]],
)
async def list_available_curriculum_topics(
    class_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, object]]:
    """List curriculum topics for the class's grade/subject/curriculum not yet added."""
    service = ClassTopicService(db)
    try:
        return await service.list_curriculum_topics_for_class(class_id)
    except ClassTopicNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/classes/{class_id}/topics",
    response_model=ClassTopicResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_class_topic(
    class_id: uuid.UUID,
    body: ClassTopicAdd,
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> ClassTopicResponse:
    """Add a curriculum topic to this class."""
    await _verify_teacher_owns_class(class_id, current_user, db)
    if current_user.school_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User has no school")
    service = ClassTopicService(db)
    try:
        return await service.add_topic(class_id, current_user.school_id, body)
    except ClassTopicNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DuplicateClassTopicError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


# NOTE: /reorder MUST be declared before /{class_topic_id} — FastAPI matches routes
# in declaration order, so "reorder" would otherwise be parsed as a UUID and fail.
@router.put(
    "/classes/{class_id}/topics/reorder",
    response_model=list[ClassTopicResponse],
)
async def reorder_class_topics(
    class_id: uuid.UUID,
    body: ClassTopicReorder,
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> list[ClassTopicResponse]:
    """Bulk-update sequence_order after drag-and-drop reordering."""
    await _verify_teacher_owns_class(class_id, current_user, db)
    service = ClassTopicService(db)
    try:
        return await service.reorder_topics(class_id, body)
    except ClassTopicNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.put(
    "/classes/{class_id}/topics/{class_topic_id}",
    response_model=ClassTopicResponse,
)
async def update_class_topic(
    class_id: uuid.UUID,
    class_topic_id: uuid.UUID,
    body: ClassTopicUpdate,
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> ClassTopicResponse:
    """Update sequence_order or is_covered on a class topic."""
    await _verify_teacher_owns_class(class_id, current_user, db)
    service = ClassTopicService(db)
    try:
        return await service.update_topic(class_id, class_topic_id, body)
    except ClassTopicNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete(
    "/classes/{class_id}/topics/{class_topic_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_class_topic(
    class_id: uuid.UUID,
    class_topic_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove a topic from this class."""
    await _verify_teacher_owns_class(class_id, current_user, db)
    service = ClassTopicService(db)
    try:
        await service.remove_topic(class_id, class_topic_id)
    except ClassTopicNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
