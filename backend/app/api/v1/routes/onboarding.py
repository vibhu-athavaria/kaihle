"""Onboarding API routes for learning profile questionnaire.

Endpoints:
- GET /api/v1/onboarding/status/{student_id} - Get specific student's onboarding status (teachers/admins only)
- GET /api/v1/onboarding/questionnaire - Get questionnaire definition
- POST /api/v1/onboarding/questionnaire/submit - Submit questionnaire responses
- GET /api/v1/onboarding/learning-profile/{student_id} - Get student's learning profile (with role-based access)
- GET /api/v1/onboarding/students/pending - Get list of students pending onboarding (teachers/admins only)
"""

from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, get_current_user, require_role
from app.core.questionnaire_config import get_questionnaire_definition
from app.models.onboarding import StudentLearningProfile
from app.models.user import StudentProfile, User, UserRole
from app.schemas.onboarding import (
    OnboardingPendingResponse,
    OnboardingStatusResponse,
    QuestionnaireDefinition,
    QuestionnaireSubmitRequest,
    StudentLearningProfileResponse,
)
from app.services.onboarding_service import OnboardingService
from app.services.user_service import UserService

logger = structlog.get_logger()

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.get("/status/{student_id}", response_model=OnboardingStatusResponse)
async def get_student_onboarding_status(
    student_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OnboardingStatusResponse:
    """Get onboarding status for a specific student.

    Teachers can view status of students in their classes.
    Admins can view any student's status.
    Students can only view their own status (redirects to /status).

    Args:
        student_id: The student user ID to check.

    Returns:
        is_learning_profile_complete from student_profile
        Onboarding status with per-class diagnostic breakdown for the student's enrolled classes.
    """
    # Students can only check their own status
    if current_user.role == UserRole.STUDENT and student_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Students can only view their own onboarding status",
        )

    try:
        student = await UserService(db).get_user(student_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid student id",
        )

    # For school admins can check other if student is the same school
    if current_user.role == UserRole.SCHOOL_ADMIN and current_user.school_id != student.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="School admins can only view students' onboarding status of your school",
        )

    service = OnboardingService(db)

    # For teachers, verify they teach this student
    if current_user.role == UserRole.TEACHER:
        is_related = await service.verify_teacher_student_relationship(current_user.id, student_id)
        if not is_related:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view onboarding status of students in your classes",
            )

    # Get base onboarding status
    status_data = await service.get_onboarding_status(student_id)

    logger.debug(
        "student_onboarding_status_retrieved",
        requested_by_user_id=str(current_user.id),
        requested_by_role=current_user.role,
        target_student_id=str(student_id),
        data=status_data,
    )

    return OnboardingStatusResponse(
        learning_profile_complete=status_data["learning_profile_complete"],
        diagnostics_by_class=status_data["diagnostics_by_class"],
    )


@router.get("/questionnaire", response_model=QuestionnaireDefinition)
async def get_questionnaire(
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN, UserRole.STUDENT)),
) -> dict[str, Any]:
    """Get the learning profile questionnaire definition.

    Returns the full questionnaire with 10 questions including options
    and scoring mappings. No database call required.

    Returns:
        Questionnaire definition dictionary.
    """

    questionnaire = get_questionnaire_definition()

    logger.debug(
        "questionnaire_retrieved",
        user_id=str(current_user.id),
        version=questionnaire["version"],
    )

    return questionnaire


@router.post(
    "/questionnaire/submit",
    response_model=StudentLearningProfileResponse,
    status_code=status.HTTP_200_OK,
)
async def submit_questionnaire(
    submit_data: QuestionnaireSubmitRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN, UserRole.STUDENT)),
    db: AsyncSession = Depends(get_db),
) -> StudentLearningProfile:
    """Submit questionnaire responses and update learning profile.

    Calculates modality scores, work style preferences, and interests
    from the submitted answers. Creates or updates the student's
    learning profile (idempotent).

    Args:
        submit_data: Questionnaire responses.

    Returns:
        Updated student learning profile.
    """

    service = OnboardingService(db)

    try:
        # Convert Pydantic models to dicts for service
        responses = [r.model_dump() for r in submit_data.responses]
        profile = await service.save_questionnaire_response(
            student_id=current_user.id,
            responses=responses,
        )

        logger.info(
            "questionnaire_submitted",
            user_id=str(current_user.id),
            profile_id=str(profile.id),
        )

        return profile

    except ValueError as e:
        logger.error(
            "questionnaire_submit_failed",
            user_id=str(current_user.id),
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/learning-profile", response_model=StudentLearningProfileResponse)
async def get_learning_profile(
    current_user: CurrentUser = Depends(
        require_role(UserRole.KAIHLE_ADMIN, UserRole.SCHOOL_ADMIN, UserRole.TEACHER, UserRole.STUDENT)
    ),
    student_id: UUID | None = Query(None, description="Student ID (required for teachers/admins)"),
    db: AsyncSession = Depends(get_db),
) -> StudentLearningProfile:
    """Get a student's learning profile.

    Students can only access their own profile.
    Teachers can access profiles of students in their classes.
    SchoolAdmins can access profiles of their school students
    KaihleAdmins can access any student's profile.

    Args:
        student_id: Optional student ID (required for teachers/admins).

    Returns:
        Student learning profile.
    """
    # Resolve target student ID
    target_id = _resolve_target_student(current_user, student_id)

    # Service handles all authorization
    service = OnboardingService(db)
    try:
        profile = await service.get_learning_profile_authorized(
            requester_id=current_user.id,
            requester_role=current_user.role,
            requester_school_id=current_user.school_id,
            target_student_id=target_id,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    logger.debug(
        "learning_profile_retrieved",
        requester_id=str(current_user.id),
        requester_role=current_user.role,
        student_id=str(target_id),
    )

    return profile


def _resolve_target_student(current_user: CurrentUser, student_id: UUID | None) -> UUID:
    """Resolve target student ID based on role.

    Students always get their own profile.
    Teachers/admins must provide student_id.
    """
    if current_user.role == UserRole.STUDENT:
        # Students can only view their own profile
        if student_id is not None and student_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Students can only view their own learning profile",
            )
        return current_user.id
    if student_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="student_id query parameter is required",
        )
    return student_id


@router.get("/students/pending", response_model=list[OnboardingPendingResponse])
async def get_pending_onboarding_students(
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN, UserRole.SCHOOL_ADMIN)),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of students to return"),
    offset: int = Query(0, ge=0, description="Number of students to skip"),
) -> list[OnboardingPendingResponse]:
    """Get list of students with pending onboarding (admins only).

    Returns students who have not completed their learning profile
    StudentProfile.is_learning_profile_complete == False

    Args:
        limit: Maximum number of students to return (default 50, max 100)
        offset: Number of students to skip for pagination (default 0)

    Returns:
        List of pending onboarding responses for students with incomplete learning profiles.
    """

    query = (
        select(StudentProfile, User)
        .join(User, User.id == StudentProfile.user_id)
        .where(StudentProfile.is_learning_profile_complete.is_(False))
    )

    # SCHOOL_ADMIN: only their school's students
    if current_user.role == UserRole.SCHOOL_ADMIN:
        query = query.where(User.school_id == current_user.school_id)

    query = query.order_by(StudentProfile.updated_at.desc()).offset(offset).limit(limit)

    result = await db.execute(query)
    rows = result.all()

    pending_students = [
        OnboardingPendingResponse(
            student_id=student_profile.user_id,
            student_name=f"{user.first_name} {user.last_name}",
            learning_profile_complete=student_profile.is_learning_profile_complete,
        )
        for student_profile, user in rows
    ]

    logger.info(
        "pending_onboarding_students_retrieved",
        requested_by_user_id=str(current_user.id),
        requested_by_role=current_user.role,
        count=len(pending_students),
        limit=limit,
        offset=offset,
    )

    return pending_students
