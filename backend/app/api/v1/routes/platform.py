"""Platform-level endpoints for Kaihle Admin operations."""

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import CurrentUser, require_role
from app.models.user import UserRole
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
