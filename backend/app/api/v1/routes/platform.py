"""Platform-level endpoints for Kaihle Admin operations."""

import uuid
from datetime import date
from typing import Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import CurrentUser, require_role
from app.models.user import UserRole
from app.schemas.auth import ImpersonationStartResponse
from app.schemas.llm_usage import LlmUsageBucket, LlmUsageResponse, LlmUsageSummary
from app.services.auth_service import (
    AuthService,
    ImpersonationNotAllowedError,
    UserNotFoundError,
)
from app.services.llm_usage_service import (
    InvalidGroupByError,
    compute_unit_costs,
    resolve_since,
    summarise_usage,
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
                id=str(row.user.id),
                school_id=str(row.user.school_id) if row.user.school_id else None,
                first_name=row.user.first_name or "",
                last_name=row.user.last_name or "",
                email=row.user.email or "",
                username=row.user.username or "",
                role=row.user.role,
                is_active=row.user.is_active,
                last_active=row.user.last_login_at.isoformat() if row.user.last_login_at else None,
                school_name=row.school_name,
            )
            for row in users
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/llm-usage")
async def get_llm_usage(
    since: date | None = Query(None),
    group_by: Literal["task", "component", "model", "run_id"] = Query("component"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    include_unit_costs: bool = Query(
        True, description="Set false to skip the unit-cost queries when the caller won't render them"
    ),
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> LlmUsageResponse:
    """LLM spend, grouped and paginated — the same figures `scripts/llm_cost_report.py`
    prints, computed by the same `llm_usage_service` functions so the two can never
    disagree about a number.
    """
    since_dt = resolve_since(since)

    logger.info(
        "platform.llm_usage.requested",
        user_id=str(current_user.id),
        since=since_dt.isoformat(),
        group_by=group_by,
        page=page,
        page_size=page_size,
    )

    try:
        report = await summarise_usage(db, since_dt, group_by, page=page, page_size=page_size)
    except InvalidGroupByError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e
    unit_costs = await compute_unit_costs(db, since_dt) if include_unit_costs else []

    return LlmUsageResponse(
        since=since_dt.date(),
        group_by=group_by,
        buckets=[
            LlmUsageBucket(
                bucket=b.bucket,
                calls=b.calls,
                failures=b.failures,
                tokens=b.tokens,
                cost=float(b.cost) if b.cost is not None else None,
                p50_ms=b.p50_ms,
                p95_ms=b.p95_ms,
            )
            for b in report.buckets
        ],
        summary=LlmUsageSummary(
            calls=report.summary.calls,
            tokens=report.summary.tokens,
            cost=float(report.summary.cost) if report.summary.cost is not None else None,
            unpriced_count=report.summary.unpriced_count,
            unpriced_percent=report.summary.unpriced_percent,
            unpriced_models=report.summary.unpriced_models,
            unattributed_count=report.summary.unattributed_count,
            unattributed_percent=report.summary.unattributed_percent,
            failures=report.summary.failures,
            p95_ms=report.summary.p95_ms,
        ),
        unit_costs=unit_costs,
        page=page,
        page_size=page_size,
        total_buckets=report.total_buckets,
    )
