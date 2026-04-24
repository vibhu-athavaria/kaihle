"""Student-specific API routes.

Endpoints for student-specific data that doesn't fit in other categories.

Routes:
- GET /api/v1/students/me/info - Get current student's info (name, grade, curriculum, etc.)
- GET /api/v1/students/{student_id}/info - Get student info (name, grade, curriculum, etc.)
- GET /api/v1/students/me/classes - Get current student's enrolled classes
- POST /api/v1/students/me/concept-guide - Get an AI-generated concept explanation
"""

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, get_current_user, require_role
from app.models.curriculum import Curriculum, Grade, Subject
from app.models.school import Class, ClassEnrollment
from app.models.user import User, UserRole
from app.schemas.user_detail import StudentDetailResponse

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
    last_name: str = Field(..., alias="lastName")
    email: str = Field(..., alias="email")
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
        last_name=student.last_name or "",
        email=student.email,
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


# =============================================================================
# AI Concept Guide endpoint
# =============================================================================


class ConceptGuideRequest(BaseModel):
    """Request body for POST /students/me/concept-guide."""

    subtopic_id: UUID = Field(..., description="UUID of the subtopic to explain")
    question: str | None = Field(
        None,
        max_length=500,
        description="Optional specific question from the student",
    )


class CheckQuestion(BaseModel):
    """MCQ check question returned alongside the explanation."""

    question: str
    options: list[str]
    correct: str


class ConceptGuideResponse(BaseModel):
    """Response for POST /students/me/concept-guide."""

    explanation: str
    subtopic_name: str
    check_question: CheckQuestion | None = None


class McqAnswerRequest(BaseModel):
    """Request body for POST /students/me/concept-guide/answer."""

    subtopic_name: str
    question: str
    options: list[str]
    correct: str
    student_answer: str = Field(..., max_length=10)


class McqAnswerResponse(BaseModel):
    """Response for POST /students/me/concept-guide/answer."""

    is_correct: bool
    response: str


@router.post(
    "/me/concept-guide",
    response_model=ConceptGuideResponse,
)
async def get_concept_guide(
    body: ConceptGuideRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConceptGuideResponse:
    """Generate a personalised AI explanation for a subtopic the student is struggling with.

    Uses the student's learning profile (modality scores, interests) to personalise
    the explanation. Falls back to generic explanation if profile is not complete.

    Args:
        body: subtopic_id (required) and optional question string.

    Returns:
        ConceptGuideResponse with explanation text and subtopic_name.

    Raises:
        403: If user is not a student.
        404: If subtopic not found.
        502: If LLM call fails.
    """
    from app.services.concept_guide_service import generate_concept_explanation

    if current_user.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can access this endpoint",
        )

    logger.info(
        "concept_guide_requested",
        student_id=str(current_user.id),
        subtopic_id=str(body.subtopic_id),
        has_question=body.question is not None,
    )

    try:
        result = await generate_concept_explanation(
            student=current_user,
            subtopic_id=body.subtopic_id,
            question=body.question,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.error(
            "concept_guide_generation_failed",
            student_id=str(current_user.id),
            subtopic_id=str(body.subtopic_id),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to generate explanation. Please try again.",
        ) from exc

    check_question_data = result.get("check_question")
    check_question = (
        CheckQuestion(
            question=check_question_data.get("question"),
            options=check_question_data.get("options"),
            correct=check_question_data.get("correct"),
        )
        if isinstance(check_question_data, dict)
        else None
    )

    return ConceptGuideResponse(
        explanation=result["explanation"],
        subtopic_name=result["subtopic_name"],
        check_question=check_question,
    )


@router.post(
    "/me/concept-guide/answer",
    response_model=McqAnswerResponse,
)
async def submit_concept_guide_answer(
    body: McqAnswerRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> McqAnswerResponse:
    """Submit a student's MCQ answer and get a follow-up response.

    Correct answer → warm acknowledgement + suggestion to try assessment.
    Incorrect answer → re-explanation from a different angle (never says "wrong").

    Args:
        body: MCQ context (question, options, correct) + student_answer.

    Returns:
        McqAnswerResponse with is_correct flag and follow-up text.
    """
    from app.services.concept_guide_service import evaluate_mcq_answer

    if current_user.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can access this endpoint",
        )

    try:
        result = await evaluate_mcq_answer(
            subtopic_name=body.subtopic_name,
            question=body.question,
            options=body.options,
            correct=body.correct,
            student_answer=body.student_answer,
        )
    except Exception as exc:
        logger.error(
            "concept_guide_answer_failed",
            student_id=str(current_user.id),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to evaluate answer. Please try again.",
        ) from exc

    return McqAnswerResponse(
        is_correct=result["is_correct"] == "true",
        response=result["response"],
    )


# =============================================================================
# GET /students/{student_id} — full student detail for school admin
# =============================================================================


@router.get(
    "/{student_id}",
    response_model=StudentDetailResponse,
)
async def get_student_detail(
    student_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_role(UserRole.SCHOOL_ADMIN, UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> StudentDetailResponse:
    """Get full student detail including class enrollments and gap states.

    Auth: SCHOOL_ADMIN (same school) or KAIHLE_ADMIN only.

    Raises:
        403: If SCHOOL_ADMIN tries to access a student in another school.
        404: If student not found.
    """
    from app.services.user_service import CrossSchoolAccessError, UserNotFoundError, UserService

    caller_school = current_user.school_id if current_user.role == UserRole.SCHOOL_ADMIN else None
    try:
        return await UserService(db).get_student_detail(student_id, caller_school)
    except CrossSchoolAccessError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    except UserNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
