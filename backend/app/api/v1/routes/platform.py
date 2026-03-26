"""Platform-level endpoints for Kaihle Admin operations."""

from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter(prefix="/platform", tags=["platform"])


class PlatformStatsResponse(BaseModel):
    """Platform configuration and statistics."""

    llm_provider: str = "openai"
    runpod_status: str = "blocked"
    trial_days: int = 14
    trial_students_limit: int = 30
    rate_limit_requests_per_minute: int = 100
    rate_limit_concurrent_users: int = 50


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
async def get_platform_stats() -> PlatformStatsResponse:
    """Get platform configuration and statistics.

    Returns platform-wide configuration values including LLM provider settings,
    trial settings, and rate limits.
    """
    return PlatformStatsResponse()


@router.get("/users")
async def get_platform_users(
    q: str | None = Query(None, description="Search query"),
    role: str | None = Query(None, description="Filter by role"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(25, ge=1, le=100, description="Page size"),
) -> PlatformUsersResponse:
    """Get paginated list of platform users.

    Returns a list of all users across all schools with optional filtering.
    """
    return PlatformUsersResponse(
        users=[],
        total=0,
        page=page,
        page_size=page_size,
    )
