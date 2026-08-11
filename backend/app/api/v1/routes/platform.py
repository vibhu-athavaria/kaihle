"""Platform-level endpoints for Kaihle Admin operations."""

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import CurrentUser, require_role
from app.models.user import UserRole
from app.schemas.auth import ImpersonationStartResponse
from app.services.auth_service import (
    AuthService,
    ImpersonationNotAllowedError,
    UserNotFoundError,
)
from app.services.user_service import UserService

router = APIRouter(prefix="/platform", tags=["platform"])
logger = structlog.get_logger()


class PlatformStatsResponse(BaseModel):
    """Platform configuration and statistics."""

    llm_provider: str
    runpod_status: str
    trial_days: int
    trial_students_limit: int
    rate_limit_requests_per_minute: int
    rate_limit_concurrent_users: int


class PlatformUserSummary(BaseModel):
    """Summary of a platform user."""

    id: str
    school_id: str | None
    first_name: str
    last_name: str
    email: str
    username: str | None = None
    role: str
    is_active: bool
    last_active: str | None
    school_name: str | None = None


class PlatformUsersResponse(BaseModel):
    """Paginated list of platform users."""

    users: list[PlatformUserSummary]
    total: int
    page: int
    page_size: int


@router.get("/stats")
async def get_platform_stats(
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
) -> PlatformStatsResponse:
    """Get platform configuration and statistics.

    Returns platform-wide configuration values including LLM provider settings,
    trial settings, and rate limits.
    """
    logger.info("platform.stats.requested", user_id=str(current_user.id))
    return PlatformStatsResponse(
        llm_provider=settings.platform_llm_provider,
        runpod_status=settings.platform_runpod_status,
        trial_days=settings.platform_trial_days,
        trial_students_limit=settings.platform_trial_students_limit,
        rate_limit_requests_per_minute=settings.platform_rate_limit_requests_per_minute,
        rate_limit_concurrent_users=settings.platform_rate_limit_concurrent_users,
    )


@router.post("/users/{user_id}/impersonate", response_model=ImpersonationStartResponse)
async def impersonate_user(
    user_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> ImpersonationStartResponse:
    """Mint a single-use link that opens a session as the given user.

    KAIHLE_ADMIN only. The link points at the app that serves the target's role
    and is redeemed by POST /api/v1/auth/impersonate/redeem.
    Returns 404 if the user does not exist, 403 if they may not be impersonated.
    """
    service = AuthService(db)
    try:
        return await service.start_impersonation(current_user, user_id)
    except UserNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ImpersonationNotAllowedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.get("/users")
async def get_platform_users(
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    q: str | None = Query(None, description="Search query (name or email)"),
    role: str | None = Query(None, description="Filter by role"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(25, ge=1, le=100, description="Page size"),
    db: AsyncSession = Depends(get_db),
) -> PlatformUsersResponse:
    """Get paginated list of platform users.

    Returns a list of all users across all schools with optional filtering.
    KAIHLE_ADMIN bypass - no school_id filter applied (Rule 12 explicit).
    """
    logger.info(
        "platform.users.requested",
        user_id=str(current_user.id),
        q=q,
        role=role,
        page=page,
        page_size=page_size,
    )

    service = UserService(db)
    users, total = await service.list_platform_users(q, role, page, page_size)

    return PlatformUsersResponse(
        users=[
            PlatformUserSummary(
                id=str(user.id),
                school_id=str(user.school_id) if user.school_id else None,
                first_name=user.first_name or "",
                last_name=user.last_name or "",
                email=user.email or "",
                username=user.username or "",
                role=user.role,
                is_active=user.is_active,
                last_active=user.last_login_at.isoformat() if user.last_login_at else None,
                school_name=user.school_name if hasattr(user, "school_name") else None,  # type: ignore[attr-defined]
            )
            for user in users
        ],
        total=total,
        page=page,
        page_size=page_size,
    )
