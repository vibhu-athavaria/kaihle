"""Onboarding API routes for learning profile questionnaire.

Endpoints:
- GET /api/v1/onboarding/status - Get current user's onboarding completion status (any authenticated user)
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


def _require_student_or_teacher_or_admin(current_user: CurrentUser) -> None:
    """Helper to allow students, teachers, and admins to access onboarding endpoints."""
    if current_user.role not in (UserRole.STUDENT, UserRole.TEACHER, UserRole.KAIHLE_ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Students, teachers, and Kaihle admins can access onboarding endpoints",
        )


@router.get("/status", response_model=OnboardingStatusResponse)
async def get_onboarding_status(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OnboardingStatusResponse:
    """Get the onboarding status for the current user.

    Returns learning profile completion status, diagnostics completion status,
    and overall onboarding status. Includes per-class diagnostic breakdown for students.
    For teachers/admins viewing their own status, returns basic onboarding info.

    Returns:
        Onboarding status with optional per-class diagnostics.
    """
    _require_student_or_teacher_or_admin(current_user)

    service = OnboardingService(db)

    # Get base onboarding status
    status_data = await service.get_onboarding_status(current_user.id)

    # Get per-class diagnostic breakdown only for students
    diagnostics_by_class = []
    if current_user.role == UserRole.STUDENT:
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
        diagnostics_status="COMPLETED" if status_data["diagnostics_complete"] else "PENDING",
        overall=status_data["overall"],
        diagnostics_by_class=diagnostics_by_class,
    )


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
        Onboarding status with per-class diagnostic breakdown for the student.
    """
    # Students can only check their own status
    if current_user.role == UserRole.STUDENT:
        if student_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Students can only view their own onboarding status",
            )
        # Redirect to self endpoint
        return await get_onboarding_status(current_user, db)

    # Teachers and admins can check others
    if current_user.role not in (UserRole.TEACHER, UserRole.KAIHLE_ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only teachers and admins can view other students' onboarding status",
        )

    # For teachers, verify they teach this student
    if current_user.role == UserRole.TEACHER:
        service = OnboardingService(db)
        is_related = await service.verify_teacher_student_relationship(current_user.id, student_id)
        if not is_related:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view onboarding status of students in your classes",
            )

    service = OnboardingService(db)

    # Get base onboarding status
    status_data = await service.get_onboarding_status(student_id)

    # Get per-class diagnostic breakdown
    diagnostics_by_class_data = await service.get_diagnostic_status_by_class(student_id)
    diagnostics_by_class = [
        DiagnosticStatusByClass(
            class_id=item["class_id"],
            class_name=item["class_name"],
            status=item["status"],
        )
        for item in diagnostics_by_class_data
    ]

    logger.debug(
        "student_onboarding_status_retrieved",
        requested_by_user_id=str(current_user.id),
        requested_by_role=current_user.role,
        target_student_id=str(student_id),
        overall=status_data["overall"],
    )

    return OnboardingStatusResponse(
        learning_profile_complete=status_data["learning_profile_complete"],
        diagnostics_status="COMPLETED" if status_data["diagnostics_complete"] else "PENDING",
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
    _require_student_or_teacher_or_admin(current_user)

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
    _require_student_or_teacher_or_admin(current_user)

    # Only students can submit questionnaires
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can submit the questionnaire",
        )

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
        student_id: Optional student ID (required for teachers/admins).

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


@router.get("/students/pending", response_model=list[OnboardingStatusResponse])
async def get_pending_onboarding_students(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of students to return"),
    offset: int = Query(0, ge=0, description="Number of students to skip"),
) -> list[OnboardingStatusResponse]:
    """Get list of students with pending onboarding (teachers and admins only).

    Returns students who have not completed their learning profile or
    have incomplete diagnostic assessments.

    Args:
        limit: Maximum number of students to return (default 50, max 100)
        offset: Number of students to skip for pagination (default 0)

    Returns:
        List of onboarding status responses for students with pending onboarding.
    """
    # Only teachers and admins can access this endpoint
    if current_user.role not in (UserRole.TEACHER, UserRole.KAIHLE_ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only teachers and admins can view pending onboarding students",
        )

    from sqlalchemy import and_, select

    from app.models.user import StudentProfile

    # Build query based on user role
    if current_user.role == UserRole.TEACHER:
        # Get students in teacher's classes
        from app.models.school import Class, ClassEnrollment

        # Subquery to get student IDs from teacher's classes
        stmt = (
            select(ClassEnrollment.student_id)
            .where(
                and_(
                    ClassEnrollment.class_id == Class.id,
                    Class.teacher_id == current_user.id,
                    ClassEnrollment.is_active.is_(True),
                )
            )
            .distinct()
        )

        # Join with student profiles to get onboarding status
        query = select(StudentProfile).where(StudentProfile.user_id.in_(stmt)).offset(offset).limit(limit)
    else:  # KAIHLE_ADMIN
        # Get all students
        query = select(StudentProfile).offset(offset).limit(limit)

    result = await db.execute(query)
    student_profiles = result.scalars().all()

    # Get onboarding status for each student
    service = OnboardingService(db)
    pending_students = []

    for profile in student_profiles:
        # Get onboarding status
        status_data = await service.get_onboarding_status(profile.user_id)

        # Only include if onboarding is not complete
        if status_data["overall"] != "COMPLETED":
            # Get per-class diagnostic breakdown
            diagnostics_by_class_data = await service.get_diagnostic_status_by_class(profile.user_id)
            diagnostics_by_class = [
                DiagnosticStatusByClass(
                    class_id=item["class_id"],
                    class_name=item["class_name"],
                    status=item["status"],
                )
                for item in diagnostics_by_class_data
            ]

            pending_students.append(
                OnboardingStatusResponse(
                    learning_profile_complete=status_data["learning_profile_complete"],
                    diagnostics_status="COMPLETED" if status_data["diagnostics_complete"] else "PENDING",
                    overall=status_data["overall"],
                    diagnostics_by_class=diagnostics_by_class,
                )
            )

    logger.info(
        "pending_onboarding_students_retrieved",
        requested_by_user_id=str(current_user.id),
        requested_by_role=current_user.role,
        count=len(pending_students),
        limit=limit,
        offset=offset,
    )

    return pending_students
