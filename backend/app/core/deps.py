"""FastAPI dependencies for authentication and authorization guards."""

import uuid
from collections.abc import Callable
from typing import Annotated, Any, TypeVar, cast

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import InvalidTokenError, decode_token
from app.models.onboarding import StudentLearningProfile
from app.models.user import OnboardingStatus, StudentProfile, User, UserRole

# HTTPBearer for extracting Bearer token
security = HTTPBearer()

# Type alias for current user
CurrentUser = User

# Type variable for generic user type
T = TypeVar("T", bound=User)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CurrentUser:
    """
    Validate JWT token and load User from database.

    Args:
        credentials: HTTP Bearer token credentials
        db: Database session

    Returns:
        User object if token is valid and user exists

    Raises:
        HTTPException 401: If token is invalid, expired, or user not found/inactive
    """
    token = credentials.credentials

    # Decode token - raises InvalidTokenError if invalid/expired
    try:
        payload = decode_token(token)
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

    # Extract user_id from token payload
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID in token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Load user from database
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive user",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def require_role(*allowed_roles: str) -> Callable[..., Any]:
    """
    Factory function that returns a dependency for role-based access control.

    Args:
        *allowed_roles: Variable number of role strings (e.g., UserRole.TEACHER)

    Returns:
        A dependency function that checks if the current user has an allowed role

    Raises:
        HTTPException 403: If user's role is not in allowed_roles
    """

    async def role_checker(
        current_user: Annotated[CurrentUser, Depends(get_current_user)],
    ) -> CurrentUser:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {', '.join(allowed_roles)}",
            )
        return current_user

    return role_checker


def require_school_match(
    school_id_getter: uuid.UUID | Callable[[], uuid.UUID],
) -> Callable[..., Any]:
    """
    Factory function that returns a dependency to enforce school_id match.

    KAIHLE_ADMIN role bypasses this check.

    Args:
        school_id_getter: Either a static UUID, or a callable that returns the school_id.
                          When using a callable, it will be called with no arguments to get
                          the school_id at runtime (useful for extracting from path parameters).
                          Example: lambda: school_id_from_request

    Returns:
        A dependency function that checks if the user's school matches

    Raises:
        HTTPException 403: If user's school doesn't match (except for KAIHLE_ADMIN)
    """

    # Determine if school_id_getter is a callable (for dynamic extraction) or static UUID
    is_dynamic = callable(school_id_getter) and not isinstance(school_id_getter, uuid.UUID)

    async def school_checker(
        current_user: Annotated[CurrentUser, Depends(get_current_user)],
    ) -> CurrentUser:
        # KAIHLE_ADMIN can access any school's data
        if current_user.role == UserRole.KAIHLE_ADMIN:
            return current_user

        # Get the school_id to check against
        if is_dynamic:
            target_school_id = cast(Callable[[], uuid.UUID], school_id_getter)()
        else:
            target_school_id = cast(uuid.UUID, school_id_getter)

        # Check school match
        if current_user.school_id != target_school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this school's data",
            )

        return current_user

    return school_checker


async def require_onboarding_complete(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CurrentUser:
    """
    Dependency that enforces onboarding completion for STUDENT role.

    For STUDENT role, checks:
    - student_profiles.onboarding_diagnostic_status == 'COMPLETED'
    - student_learning_profiles.completed_at IS NOT NULL

    Non-STUDENT roles pass through without any check.

    Args:
        current_user: The authenticated user
        db: Database session

    Returns:
        The current_user if onboarding is complete (or not a student)

    Raises:
        HTTPException 403: If student onboarding is incomplete
    """
    # Non-student roles pass through without check
    if current_user.role != UserRole.STUDENT:
        return current_user

    # Check student profile for diagnostic status
    result = await db.execute(select(StudentProfile).where(StudentProfile.user_id == current_user.id))
    student_profile = result.scalar_one_or_none()

    if not student_profile:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Student profile not found",
        )

    # Check onboarding diagnostic status
    if student_profile.onboarding_diagnostic_status != OnboardingStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": "Onboarding not complete",
                "redirect": "/onboarding/diagnostic",
                "required": ["diagnostic"],
            },
        )

    # Check learning profile completion - use StudentLearningProfile.completed_at
    learning_result = await db.execute(
        select(StudentLearningProfile).where(StudentLearningProfile.student_id == current_user.id)
    )
    learning_profile = learning_result.scalar_one_or_none()

    if not learning_profile or learning_profile.completed_at is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": "Learning profile not complete",
                "redirect": "/onboarding/learning-profile",
                "required": ["learning_profile"],
            },
        )

    return current_user
