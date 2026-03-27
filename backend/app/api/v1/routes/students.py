"""Student-specific API routes.

Endpoints for student-specific data that doesn't fit in other categories.

Routes:
- GET /api/v1/students/{student_id}/info - Get student info (name, grade, curriculum, etc.)
"""

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, get_current_user
from app.models.curriculum import Curriculum, Grade
from app.models.school import Class, ClassEnrollment
from app.models.user import User, UserRole

logger = structlog.get_logger()

router = APIRouter(prefix="/students", tags=["students"])


class StudentInfoResponse(BaseModel):
    """Response schema for GET /students/{student_id}/info.

    Returns basic student info including name, grade, curriculum, class, and streak days.
    Note: streak_days is not yet implemented in the backend and will always be null.
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    first_name: str = Field(..., alias="firstName")
    grade_name: str = Field(..., alias="gradeName")  # Empty string if not enrolled in any class
    curriculum_name: str = Field(..., alias="curriculumName")  # Empty string if school has no primary curriculum
    class_id: UUID | None = Field(None, alias="classId")
    streak_days: int | None = Field(None, alias="streakDays")  # Not yet implemented - always null


@router.get(
    "/{student_id}/info",
    response_model=StudentInfoResponse,
)
async def get_student_info(
    student_id: UUID = Path(..., description="Student ID"),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StudentInfoResponse:
    """Get basic info for a student.

    Students can only view their own info.
    Teachers and admins can view any student's info within their school.

    Returns:
        StudentInfoResponse with first_name, grade_name, curriculum_name, class_id, streak_days

    Raises:
        403: If user doesn't have permission to view this student's info
        404: If student doesn't exist
    """
    # Authorization: students can only view themselves
    if current_user.role == UserRole.STUDENT:
        if current_user.id != student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Students can only view their own info",
            )

    # For teachers/admins, verify the student belongs to their school
    if current_user.role in (UserRole.TEACHER, UserRole.SCHOOL_ADMIN):
        student_query = select(User).where(User.id == student_id)
        student_result = await db.execute(student_query)
        student = student_result.scalar_one_or_none()

        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student not found",
            )

        if student.school_id != current_user.school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot view student from another school",
            )

    # Get the student user
    user_query = select(User).where(User.id == student_id)
    user_result = await db.execute(user_query)
    user = user_result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found",
        )

    # Get student's enrolled class (first active enrollment)
    enrollment_query = (
        select(ClassEnrollment, Class)
        .join(Class, Class.id == ClassEnrollment.class_id)
        .where(
            ClassEnrollment.student_id == student_id,
            ClassEnrollment.is_active.is_(True),
        )
        .order_by(ClassEnrollment.enrolled_at)
        .limit(1)
    )
    enrollment_result = await db.execute(enrollment_query)
    enrollment_row = enrollment_result.first()

    grade_name = ""
    curriculum_name = ""
    class_id = None

    if enrollment_row:
        enrollment, class_ = enrollment_row
        class_id = class_.id

        # Get grade name
        grade_query = select(Grade).where(Grade.id == class_.grade_id)
        grade_result = await db.execute(grade_query)
        grade = grade_result.scalar_one_or_none()
        if grade:
            grade_name = grade.name

        # Get curriculum name from class
        curriculum_query = select(Curriculum).where(Curriculum.id == class_.curriculum_id)
        curriculum_result = await db.execute(curriculum_query)
        curriculum = curriculum_result.scalar_one_or_none()
        if curriculum:
            curriculum_name = curriculum.name

    logger.debug(
        "student_info_retrieved",
        requester_id=str(current_user.id),
        requester_role=str(current_user.role),
        student_id=str(student_id),
        grade_name=grade_name,
        curriculum_name=curriculum_name,
        class_id=str(class_id) if class_id else None,
    )

    return StudentInfoResponse(
        first_name=user.first_name or "",
        grade_name=grade_name,
        curriculum_name=curriculum_name,
        class_id=class_id,
        streak_days=None,  # Not yet implemented
    )
