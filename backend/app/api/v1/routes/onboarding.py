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
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, get_current_user
from app.core.questionnaire_config import get_questionnaire_definition
from app.models.onboarding import StudentLearningProfile
from app.models.user import UserRole
from app.schemas.onboarding import (
    DiagnosticStatusByClass,
    OnboardingStatusResponse,
    QuestionnaireDefinition,
    QuestionnaireSubmitRequest,
    StudentLearningProfileResponse,
)
from app.services.onboarding_service import OnboardingService

logger = structlog.get_logger()

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


def _require_student_role(current_user: CurrentUser) -> None:
    """Helper to enforce student role on endpoints."""
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can access this endpoint",
        )


@router.get("/status", response_model=OnboardingStatusResponse)
async def get_onboarding_status(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OnboardingStatusResponse:
    """Get the onboarding status for the current user.

    Returns learning profile completion status, diagnostics completion status,
    and overall onboarding status. Includes per-class diagnostic breakdown.

    Returns:
        Onboarding status with per-class diagnostics.
    """
    _require_student_role(current_user)

    service = OnboardingService(db)

    # Get base onboarding status
    status_data = await service.get_onboarding_status(current_user.id)

    # Get per-class diagnostic breakdown
    diagnostics_by_class_data = await service.get_diagnostic_status_by_class(current_user.id)
    diagnostics_by_class = [
        DiagnosticStatusByClass(
            class_id=item["class_id"],
            class_name=item["class_name"],
            status=item["status"],
        )
        for item in diagnostics_by_class_data
    ]

    logger.debug(
        "onboarding_status_retrieved",
        user_id=str(current_user.id),
        overall=status_data["overall"],
    )

    return OnboardingStatusResponse(
        learning_profile_complete=status_data["learning_profile_complete"],
        diagnostics_status=status_data["diagnostics_complete"]
        and "COMPLETED"
        or ("IN_PROGRESS" if any(d.status != "PENDING" for d in diagnostics_by_class) else "PENDING"),
        overall=status_data["overall"],
        diagnostics_by_class=diagnostics_by_class,
    )


@router.get("/questionnaire", response_model=QuestionnaireDefinition)
async def get_questionnaire(
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Get the learning profile questionnaire definition.

    Returns the full questionnaire with 10 questions including options
    and scoring mappings. No database call required.

    Returns:
        Questionnaire definition dictionary.
    """
    _require_student_role(current_user)

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
    current_user: CurrentUser = Depends(get_current_user),
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
    _require_student_role(current_user)

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
    current_user: CurrentUser = Depends(get_current_user),
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
    service = OnboardingService(db)

    # Determine which student profile to retrieve
    target_student_id: UUID

    if current_user.role == UserRole.STUDENT:
        # Students can only view their own profile
        if student_id is not None and student_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Students can only view their own learning profile",
            )
        target_student_id = current_user.id

    elif current_user.role == UserRole.TEACHER:
        # Teachers must provide student_id and must teach that student
        if student_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="student_id query parameter is required for teachers",
            )

        # Verify teacher-student relationship
        is_related = await service.verify_teacher_student_relationship(current_user.id, student_id)
        if not is_related:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view profiles of students in your classes",
            )

        target_student_id = student_id

    elif current_user.role == UserRole.KAIHLE_ADMIN:
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
        requester_id=str(current_user.id),
        requester_role=current_user.role,
        student_id=str(target_student_id),
    )

    return profile
