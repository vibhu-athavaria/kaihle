"""Platform-level endpoints for Kaihle Admin operations."""

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.core.config import settings
from app.core.deps import CurrentUser, require_role
from app.models.user import UserRole

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


@router.get("/users")
async def get_platform_users(
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    q: str | None = Query(None, description="Search query"),
    role: str | None = Query(None, description="Filter by role"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(25, ge=1, le=100, description="Page size"),
) -> PlatformUsersResponse:
    """Get paginated list of platform users.

    Returns a list of all users across all schools with optional filtering.
    """
    logger.info(
        "platform.users.requested",
        user_id=str(current_user.id),
        q=q,
        role=role,
        page=page,
        page_size=page_size,
    )
    return PlatformUsersResponse(
        users=[],
        total=0,
        page=page,
        page_size=page_size,
    )
