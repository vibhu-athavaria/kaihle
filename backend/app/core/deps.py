"""FastAPI dependencies for authentication and authorization guards."""

import uuid
from collections.abc import Callable
from typing import Annotated, Any, TypeVar, cast

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import InvalidTokenError, decode_token, get_token_scope
from app.models.school import ClassEnrollment
from app.models.user import StudentProfile, User, UserRole

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


async def get_token_payload(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> dict[str, Any]:
    """
    Get the raw token payload without requiring user lookup.
    Used by require_full_access to check token scope.
    """
    token = credentials.credentials
    try:
        payload = decode_token(token)
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    return payload


async def require_full_access(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    token_payload: Annotated[dict[str, Any], Depends(get_token_payload)],
) -> CurrentUser:
    """Reject tokens that only have password_setup scope.

    Apply this dependency to all protected endpoints that should not be
    accessible until after the user has set their password.
    """
    if get_token_scope(token_payload) == "password_setup":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "PASSWORD_SETUP_REQUIRED",
                "message": "You must set your password before accessing this resource.",
            },
        )
    return current_user


def require_role(*allowed_roles: UserRole) -> Callable[..., Any]:
    """
    Factory function that returns a dependency for role-based access control.

    Args:
        *allowed_roles: Variable number of UserRole enum values that are allowed

    Returns:
        A dependency function that checks if the current user has an allowed role

    Raises:
        HTTPException 403: If user's role is not in allowed_roles
    """

    async def role_checker(
        current_user: Annotated[CurrentUser, Depends(get_current_user)],
    ) -> CurrentUser:
        # Convert allowed_roles to strings for comparison with User.role (which is str)
        allowed_role_values = tuple(role.value if hasattr(role, "value") else role for role in allowed_roles)
        if current_user.role not in allowed_role_values:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {', '.join(str(r) for r in allowed_roles)}",
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


async def require_diagnostic_complete(
    class_id: uuid.UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ClassEnrollment | None:
    """Gate class content access behind Tier 1 diagnostic completion.

    Checks class_enrollments.onboarding_diagnostic_status for the specific
    (student_id, class_id) pair. Returns the enrollment row on success.
    Raises 403 with a structured error body if diagnostic is not yet COMPLETED.

    Only applies to STUDENT role. Teachers and admins bypass this gate.
    """
    # Teachers and admins bypass the gate entirely
    if current_user.role in (UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.KAIHLE_ADMIN):
        return None

    result = await db.execute(
        select(ClassEnrollment).where(
            ClassEnrollment.class_id == class_id,
            ClassEnrollment.student_id == current_user.id,
            ClassEnrollment.is_active.is_(True),
        )
    )
    enrollment = result.scalar_one_or_none()

    if enrollment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You are not enrolled in this class",
        )

    if enrollment.onboarding_diagnostic_status != "COMPLETED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "DIAGNOSTIC_INCOMPLETE",
                "message": "Complete the diagnostic assessment to access class content.",
                "class_id": str(class_id),
                "diagnostic_status": enrollment.onboarding_diagnostic_status,
            },
        )

    return enrollment


async def require_onboarding_complete(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CurrentUser:
    """
    Dependency that enforces onboarding completion for STUDENT role.

    For STUDENT role, checks:
    - student_profiles.is_learning_profile_complete == TRUE

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

    # Check student profile exists
    result = await db.execute(select(StudentProfile).where(StudentProfile.user_id == current_user.id))
    student_profile = result.scalar_one_or_none()

    if not student_profile:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Student profile not found",
        )

    # Check learning profile completion (v2.1)
    # Student can access dashboard as soon as learning profile is complete
    if not student_profile.is_learning_profile_complete:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": "Learning profile not complete",
                "redirect": "/onboarding/learning-profile",
                "required": ["learning_profile"],
            },
        )

    return current_user
