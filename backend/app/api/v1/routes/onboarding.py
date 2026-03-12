"""Onboarding API routes for learning profile questionnaire.

Endpoints:
- GET /api/v1/onboarding/status - Get onboarding completion status
- GET /api/v1/onboarding/questionnaire - Get questionnaire definition
- POST /api/v1/onboarding/questionnaire/submit - Submit questionnaire responses
- GET /api/v1/onboarding/learning-profile - Get learning profile (with auth checks)
"""

from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.questionnaire_config import get_questionnaire_definition
from app.models.onboarding import StudentLearningProfile
from app.models.user import UserRole
from app.schemas.onboarding import (
    OnboardingStatus as OnboardingStatusSchema,
)
from app.schemas.onboarding import (
    QuestionnaireDefinition,
    QuestionnaireSubmitRequest,
    StudentLearningProfileResponse,
)
from app.services.onboarding_service import OnboardingService

logger = structlog.get_logger()

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


def get_current_user(request: Request) -> dict[str, Any]:
    """Extract current user from request state (set by auth middleware).

    This is a temporary implementation until M0-3-T3 auth middleware is complete.
    The middleware will set request.state.user with user details.

    Args:
        request: FastAPI request object.

    Returns:
        Dictionary with user details (id, role, school_id).

    Raises:
        HTTPException: If user is not authenticated.
    """
    user: dict[str, Any] | None = getattr(request.state, "user", None)
    if not user:
        # For development, allow testing without auth
        # In production, this should raise 401
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return user


@router.get("/status", response_model=OnboardingStatusSchema)
async def get_onboarding_status(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get the onboarding status for the current user.

    Returns learning profile completion status, diagnostics completion status,
    and overall onboarding status.

    Returns:
        Onboarding status dictionary.
    """
    current_user = get_current_user(request)

    role_str = current_user.get("role")
    if role_str is None or UserRole(role_str) != UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can access onboarding status",
        )

    service = OnboardingService(db)
    status_data = await service.get_onboarding_status(current_user["id"])

    logger.debug(
        "onboarding_status_retrieved",
        user_id=str(current_user["id"]),
        overall=status_data["overall"],
    )

    return status_data


@router.get("/questionnaire", response_model=QuestionnaireDefinition)
async def get_questionnaire(
    request: Request,
) -> dict[str, Any]:
    """Get the learning profile questionnaire definition.

    Returns the full questionnaire with 10 questions including options
    and scoring mappings. No database call required.

    Returns:
        Questionnaire definition dictionary.
    """
    current_user = get_current_user(request)

    role_str = current_user.get("role")
    if role_str is None or UserRole(role_str) != UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can access the questionnaire",
        )

    questionnaire = get_questionnaire_definition()

    logger.debug(
        "questionnaire_retrieved",
        user_id=str(current_user["id"]),
        version=questionnaire["version"],
    )

    return questionnaire


@router.post(
    "/questionnaire/submit",
    response_model=StudentLearningProfileResponse,
    status_code=status.HTTP_200_OK,
)
async def submit_questionnaire(
    request: Request,
    submit_data: QuestionnaireSubmitRequest,
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
    current_user = get_current_user(request)

    role_str = current_user.get("role")
    if role_str is None or UserRole(role_str) != UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can submit the questionnaire",
        )

    service = OnboardingService(db)

    try:
        # Convert Pydantic models to dicts for service
        responses = [r.model_dump() for r in submit_data.responses]
        profile = await service.save_questionnaire_response(
            student_id=current_user["id"],
            responses=responses,
        )

        logger.info(
            "questionnaire_submitted",
            user_id=str(current_user["id"]),
            profile_id=str(profile.id),
        )

        return profile

    except ValueError as e:
        logger.error(
            "questionnaire_submit_failed",
            user_id=str(current_user["id"]),
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/learning-profile", response_model=StudentLearningProfileResponse)
async def get_learning_profile(
    request: Request,
    student_id: UUID | None = Query(None, description="Student ID (required for teachers/admins)"),
    db: AsyncSession = Depends(get_db),
) -> StudentLearningProfile:
    """Get a student's learning profile.

    Students can only access their own profile.
    Teachers can access profiles of students in their classes.
    KaihleAdmins can access any student's profile.

    Args:
        student_id: Optional student ID (required for non-students).

    Returns:
        Student learning profile.
    """
    current_user = get_current_user(request)
    user_id = current_user["id"]
    user_role_str = current_user.get("role")

    if user_role_str is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User role not found",
        )

    user_role = UserRole(user_role_str)

    service = OnboardingService(db)

    # Determine which student profile to retrieve
    target_student_id: UUID

    if user_role == UserRole.STUDENT:
        # Students can only view their own profile
        if student_id is not None and student_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Students can only view their own learning profile",
            )
        target_student_id = user_id

    elif user_role == UserRole.TEACHER:
        # Teachers must provide student_id and must teach that student
        if student_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="student_id query parameter is required for teachers",
            )

        # Verify teacher-student relationship
        is_related = await service.verify_teacher_student_relationship(user_id, student_id)
        if not is_related:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view profiles of students in your classes",
            )

        target_student_id = student_id

    elif user_role == UserRole.KAIHLE_ADMIN:
        # Admins can view any student's profile
        if student_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="student_id query parameter is required",
            )
        target_student_id = student_id

    else:
        # Other roles (e.g., SCHOOL_ADMIN, PARENT) not allowed
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view learning profiles",
        )

    # Retrieve the profile
    profile = await service.get_learning_profile(target_student_id)

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Learning profile not found",
        )

    logger.debug(
        "learning_profile_retrieved",
        requester_id=str(user_id),
        requester_role=user_role,
        student_id=str(target_student_id),
    )

    return profile
