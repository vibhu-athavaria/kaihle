"""Gap map API routes.

Real implementation: M2-1-T2 (gap_map_routes.md).
"""

import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, _check_school_access, require_full_access, require_role
from app.models.school import Class, ClassEnrollment
from app.models.user import User, UserRole
from app.schemas.gap_map import ClassGapMap, ClassSummary, StudentGapMap
from app.services.gap_service import GapService

router = APIRouter(tags=["gap-map"])


async def _check_teacher_enrollment(
    teacher_id: uuid.UUID,
    student_id: uuid.UUID,
    db: AsyncSession,
) -> bool:
    """Return True if the teacher owns at least one active class the student is enrolled in.

    TODO: This check belongs in the service layer (CONSTITUTION Rule 1).
    Tracked as a follow-up refactor — move into GapService.get_student_gap_map
    so routes remain free of DB queries.
    """
    result = await db.execute(
        select(ClassEnrollment.class_id)
        .join(Class, Class.id == ClassEnrollment.class_id)
        .where(
            ClassEnrollment.student_id == student_id,
            ClassEnrollment.is_active.is_(True),
            Class.teacher_id == teacher_id,
        )
    )
    return result.scalar_one_or_none() is not None


@router.get("/classes/{class_id}/gap-map", response_model=ClassGapMap)
async def get_class_gap_map(
    class_id: UUID,
    subject_id: UUID = Query(..., description="Filter gap map by subject"),
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> ClassGapMap:
    """Return per-student, per-subtopic mastery heatmap for a class filtered by subject."""
    class_: Class | None = await db.get(Class, class_id)
    if class_ is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")

    _check_school_access(class_.school_id, current_user)

    if current_user.role == UserRole.TEACHER and class_.teacher_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view gap maps for your own classes",
        )

    service = GapService(db)
    return await service.get_class_gap_map(class_id, class_.school_id, subject_id)


@router.get("/classes/{class_id}/summary", response_model=ClassSummary)
async def get_class_summary(
    class_id: UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> ClassSummary:
    """Return aggregate mastery summary across all subjects for a class card."""
    class_: Class | None = await db.get(Class, class_id)
    if class_ is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")

    _check_school_access(class_.school_id, current_user)

    if current_user.role == UserRole.TEACHER and class_.teacher_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view summaries for your own classes",
        )

    service = GapService(db)
    return await service.get_class_summary(class_id, class_.school_id)


@router.get("/students/me/gap-map", response_model=StudentGapMap)
async def get_my_gap_map(
    subject_id: UUID = Query(...),
    current_user: CurrentUser = Depends(require_role(UserRole.STUDENT)),
    db: AsyncSession = Depends(get_db),
) -> StudentGapMap:
    """Return the authenticated student's own gap map for the requested subject."""
    if current_user.school_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No school associated with account")
    service = GapService(db)
    return await service.get_student_gap_map(current_user.id, current_user.school_id, subject_id)


@router.get("/students/{student_id}/gap-map", response_model=StudentGapMap)
async def get_student_gap_map(
    student_id: UUID,
    subject_id: UUID = Query(...),
    current_user: CurrentUser = Depends(require_full_access),
    db: AsyncSession = Depends(get_db),
) -> StudentGapMap:
    """Return a specific student's gap map, enforcing role-based access control."""
    student: User | None = await db.get(User, student_id)
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    if student.role != UserRole.STUDENT:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target user is not a student")

    if current_user.role == UserRole.STUDENT:
        if current_user.id != student_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only view your own gap map")
    elif current_user.role == UserRole.TEACHER:
        if not await _check_teacher_enrollment(current_user.id, student_id, db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view gap maps for students in your own classes",
            )
    elif current_user.role == UserRole.PARENT:
        from app.models.user import ParentStudent

        parent_link = await db.execute(
            select(ParentStudent).where(
                ParentStudent.parent_id == current_user.id,
                ParentStudent.student_id == student_id,
            )
        )
        if parent_link.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view gap maps for students linked to your account",
            )
    elif current_user.role not in (UserRole.SCHOOL_ADMIN, UserRole.KAIHLE_ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    # Issue 5 fix: None check BEFORE _check_school_access to avoid passing None into the helper.
    if student.school_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student has no school")

    _check_school_access(student.school_id, current_user)

    service = GapService(db)
    return await service.get_student_gap_map(student_id, student.school_id, subject_id)
