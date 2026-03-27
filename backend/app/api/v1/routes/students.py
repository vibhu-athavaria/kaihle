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
from app.models.curriculum import Curriculum, Grade, Subject
from app.models.school import Class, ClassEnrollment
from app.models.user import User, UserRole

logger = structlog.get_logger()

router = APIRouter(prefix="/students", tags=["students"])


class EnrolledClassInfo(BaseModel):
    """Info about a single enrolled class with its subject."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    class_id: UUID = Field(..., alias="classId")
    class_name: str = Field(..., alias="className")
    subject_id: UUID = Field(..., alias="subjectId")
    subject_name: str = Field(..., alias="subjectName")
    grade_name: str = Field(..., alias="gradeName")


class StudentInfoResponse(BaseModel):
    """Response schema for GET /students/{student_id}/info.

    Returns basic student info including name, grade, curriculum, class, and streak days.
    Also includes enrollment status and list of enrolled classes.

    Note: streak_days is not yet implemented in the backend and will always be null.
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    first_name: str = Field(..., alias="firstName")
    grade_name: str = Field(..., alias="gradeName")  # Empty string if not enrolled in any class
    curriculum_name: str = Field(..., alias="curriculumName")  # Empty string if school has no primary curriculum
    class_id: UUID | None = Field(None, alias="classId")
    streak_days: int | None = Field(None, alias="streakDays")  # Not yet implemented - always null
    is_enrolled: bool = Field(..., alias="isEnrolled")  # True if student has at least one active enrollment
    enrolled_classes: list[EnrolledClassInfo] = Field(
        default_factory=list,
        alias="enrolledClasses",
    )


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

    # Get all enrolled classes with their subjects using eager loading
    # to avoid N+1 query pattern
    enrollment_query = (
        select(ClassEnrollment, Class, Subject, Grade, Curriculum)
        .join(Class, Class.id == ClassEnrollment.class_id)
        .join(Subject, Subject.id == Class.subject_id)
        .join(Grade, Grade.id == Class.grade_id)
        .join(Curriculum, Curriculum.id == Class.curriculum_id)
        .where(
            ClassEnrollment.student_id == student_id,
            ClassEnrollment.is_active.is_(True),
        )
        .order_by(ClassEnrollment.enrolled_at)
    )
    enrollment_result = await db.execute(enrollment_query)
    enrollment_rows = enrollment_result.all()

    grade_name = ""
    curriculum_name = ""
    class_id = None
    enrolled_classes: list[EnrolledClassInfo] = []

    for enrollment_row in enrollment_rows:
        enrollment, class_, subject, grade, curriculum = enrollment_row

        # Get first class_id for backwards compatibility
        if class_id is None:
            class_id = class_.id

        # Get curriculum name from class (for backwards compatibility)
        if curriculum_name == "":
            curriculum_name = curriculum.name if curriculum else ""

        # Set grade name from first class for backwards compatibility
        if grade_name == "" and grade:
            grade_name = grade.name

        enrolled_classes.append(
            EnrolledClassInfo(
                class_id=class_.id,
                class_name=class_.name,
                subject_id=class_.subject_id,
                subject_name=subject.name if subject else "",
                grade_name=grade.name if grade else "",
            )
        )

    is_enrolled = len(enrolled_classes) > 0

    logger.debug(
        "student_info_retrieved",
        requester_id=str(current_user.id),
        requester_role=str(current_user.role),
        student_id=str(student_id),
        grade_name=grade_name,
        curriculum_name=curriculum_name,
        class_id=str(class_id) if class_id else None,
        is_enrolled=is_enrolled,
        enrolled_class_count=len(enrolled_classes),
    )

    return StudentInfoResponse(
        first_name=user.first_name or "",
        grade_name=grade_name,
        curriculum_name=curriculum_name,
        class_id=class_id,
        streak_days=None,  # Not yet implemented
        is_enrolled=is_enrolled,
        enrolled_classes=enrolled_classes,
    )
