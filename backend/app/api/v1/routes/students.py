"""Student-specific API routes.

Endpoints for student-specific data that doesn't fit in other categories.

Routes:
- GET /api/v1/students/me/info - Get current student's info (name, grade, curriculum, etc.)
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


async def _get_student_info_by_id(
    student: User,
    db: AsyncSession,
) -> StudentInfoResponse:
    """Fetch student info by ID.

    Authorization checks (role verification, school membership) must be done
    at the API endpoint level before calling this helper.

    Args:
        student: The User model object
        db: Database session.

    Returns:
        StudentInfoResponse with student info and enrolled classes.

    Raises:
        HTTPException 404: If student is not found.
    """

    # Get all enrolled classes with their subjects using eager loading
    # to avoid N+1 query pattern
    enrollment_query = (
        select(ClassEnrollment, Class, Subject, Grade, Curriculum)
        .join(Class, Class.id == ClassEnrollment.class_id)
        .join(Subject, Subject.id == Class.subject_id)
        .join(Grade, Grade.id == Class.grade_id)
        .join(Curriculum, Curriculum.id == Class.curriculum_id)
        .where(
            ClassEnrollment.student_id == student.id,
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
        _, class_, subject, grade, curriculum = enrollment_row

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
        student_id=str(student.id),
        grade_name=grade_name,
        curriculum_name=curriculum_name,
        class_id=str(class_id) if class_id else None,
        is_enrolled=is_enrolled,
        enrolled_class_count=len(enrolled_classes),
    )

    return StudentInfoResponse(
        first_name=student.first_name or "",
        grade_name=grade_name,
        curriculum_name=curriculum_name,
        class_id=class_id,
        streak_days=None,  # Not yet implemented
        is_enrolled=is_enrolled,
        enrolled_classes=enrolled_classes,
    )


@router.get(
    "/me/info",
    response_model=StudentInfoResponse,
)
async def get_my_student_info(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StudentInfoResponse:
    """Get current student's own info.

    This endpoint uses the /me shortcut to automatically use the authenticated user's ID.
    Per CONSTITUTION.md Rule: "Never construct student ID in URLs - always use /me shortcut."

    Only students can access this endpoint. Teachers and admins should use /{student_id}/info.

    Returns:
        StudentInfoResponse with first_name, grade_name, curriculum_name, class_id, streak_days

    Raises:
        403: If user is not a student
    """
    # Only students can access this endpoint
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can access this endpoint",
        )

    logger.info(
        "my_student_info_requested",
        student_id=str(current_user.id),
    )

    return await _get_student_info_by_id(
        student=current_user,
        db=db,
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

    Authorization rules:
    - STUDENT: Can view their own info (student_id == current_user.id)
    - TEACHER/SCHOOL_ADMIN: Can view any student in the same school
    - KAIHLE_ADMIN: Can view any student

    Returns:
        StudentInfoResponse with first_name, grade_name, curriculum_name, class_id, streak_days

    Raises:
        403: If user doesn't have permission to view this student's info
        404: If student doesn't exist or is not in the same school
    """
    # Build query to find the target student
    student_query = select(User).where(User.id == student_id, User.role == UserRole.STUDENT)

    # For teachers/school admins, verify the student is in the same school
    if current_user.role in (UserRole.TEACHER, UserRole.SCHOOL_ADMIN):
        student_query = student_query.where(User.school_id == current_user.school_id)

    student_result = await db.execute(student_query)
    target_student = student_result.scalar_one_or_none()

    if not target_student:
        # Return 404 to avoid leaking information about students in other schools
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found",
        )

    # After confirming student exists, check authorization
    if current_user.role == UserRole.STUDENT:
        # Students can only view their own info
        if current_user.id != student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view your own student info",
            )
    elif current_user.role not in (UserRole.KAIHLE_ADMIN, UserRole.SCHOOL_ADMIN, UserRole.TEACHER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Required roles: KAIHLE_ADMIN, SCHOOL_ADMIN, TEACHER",
        )

    logger.info(
        "student_info_requested",
        requester_id=str(current_user.id),
        requester_role=str(current_user.role),
        target_student_id=str(student_id),
    )

    return await _get_student_info_by_id(
        student=target_student,
        db=db,
    )


# =============================================================================
# M0-7-T3-patch: Student Classes endpoint with teacher_name for dashboard
# =============================================================================


class StudentClassResponse(BaseModel):
    """Response schema for GET /students/me/classes.

    Returns enrolled classes with full details including teacher name for the
    student dashboard. Includes diagnostic status for each class.
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID = Field(..., alias="id")
    name: str = Field(..., alias="name")
    subject_id: UUID = Field(..., alias="subjectId")
    subject_name: str = Field(..., alias="subjectName")
    grade_name: str = Field(..., alias="gradeName")
    teacher_name: str = Field(..., alias="teacherName")
    curriculum_id: UUID = Field(..., alias="curriculumId")
    academic_year: str = Field(..., alias="academicYear")
    is_active: bool = Field(..., alias="isActive")
    onboarding_diagnostic_status: str = Field(..., alias="onboardingDiagnosticStatus")
    diagnostic_attempt_id: UUID | None = Field(None, alias="diagnosticAttemptId")


async def _get_student_classes(
    student: User,
    db: AsyncSession,
) -> list[StudentClassResponse]:
    """Fetch all enrolled classes for a student with full details.

    This includes teacher name from the teacher user record.
    """
    # Query enrollments with all related data including teacher
    # Include ClassEnrollment to get is_active and onboarding_diagnostic_status
    query = (
        select(
            ClassEnrollment,
            Class,
            Subject,
            Grade,
            User,  # Teacher
        )
        .join(Class, Class.id == ClassEnrollment.class_id)
        .join(Subject, Subject.id == Class.subject_id)
        .join(Grade, Grade.id == Class.grade_id)
        .join(User, User.id == Class.teacher_id)
        .where(
            ClassEnrollment.student_id == student.id,
            ClassEnrollment.is_active.is_(True),
        )
        .order_by(ClassEnrollment.enrolled_at)
    )

    result = await db.execute(query)
    rows = result.all()

    classes: list[StudentClassResponse] = []
    for enrollment, class_, subject, grade, teacher in rows:
        # Get diagnostic status from enrollment's onboarding_diagnostic_status
        diagnostic_status = enrollment.onboarding_diagnostic_status
        diagnostic_attempt_id = None  # Field not available in current schema

        classes.append(
            StudentClassResponse(
                id=class_.id,
                name=class_.name,
                subject_id=class_.subject_id,
                subject_name=subject.name if subject else "",
                grade_name=grade.name if grade else "",
                teacher_name=f"{teacher.first_name} {teacher.last_name}".strip() if teacher else "",
                curriculum_id=class_.curriculum_id,
                academic_year=class_.academic_year or "",
                is_active=enrollment.is_active,
                onboarding_diagnostic_status=diagnostic_status,
                diagnostic_attempt_id=diagnostic_attempt_id,
            )
        )

    return classes


@router.get(
    "/me/classes",
    response_model=list[StudentClassResponse],
)
async def get_my_classes(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[StudentClassResponse]:
    """Get current student's enrolled classes with full details.

    Returns:
        list[StudentClassResponse] with class details including teacher name

    Raises:
        403: If user is not a student
    """
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can access this endpoint",
        )

    logger.info(
        "my_classes_requested",
        student_id=str(current_user.id),
    )

    return await _get_student_classes(
        student=current_user,
        db=db,
    )
