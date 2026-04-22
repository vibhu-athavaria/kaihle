"""Analytics and platform management routes.

Three sections:
1. School analytics — GET /schools/{id}/analytics (SchoolAdmin sees own school)
2. Platform stats  — GET /platform/stats (KaihleAdmin only)
3. Platform actions — POST /platform/schools/{id}/impersonate (KaihleAdmin only)

Note on the /platform prefix: platform-level endpoints are not nested under
/schools because they operate across all schools, not within one. This mirrors
the separation between tenant-scoped and platform-scoped concerns.
"""

from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, _check_school_access, require_role
from app.models.user import UserRole
from app.schemas.analytics import PlatformStats, SchoolAnalytics
from app.services.analytics_service import AnalyticsService

router = APIRouter(tags=["analytics"])
logger = structlog.get_logger()


@router.get("/schools/{school_id}/analytics", response_model=SchoolAnalytics)
async def get_school_analytics(
    school_id: UUID,
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    current_user: CurrentUser = Depends(require_role(UserRole.SCHOOL_ADMIN, UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> SchoolAnalytics:
    # Check school access - KAIHLE_ADMIN bypasses, others must match (Rule 12)
    _check_school_access(school_id, current_user)

    today = date.today()
    effective_from = from_date or (today - timedelta(days=30))
    effective_to = to_date or today

    service = AnalyticsService(db)
    data = await service.get_school_analytics(school_id, effective_from, effective_to)
    # SchoolAnalytics is a subclass of SchoolAnalyticsData — model_validate handles the cast
    return SchoolAnalytics.model_validate(data.model_dump())


@router.get("/platform/stats", response_model=PlatformStats)
async def get_platform_stats(
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> PlatformStats:
    logger.info("platform.stats.requested", user_id=str(current_user.id))
    # STUB — M0-10-T6 | Real implementation: M6-1-T1
    # KaihleAdmin only — cross-school aggregation.
    return PlatformStats(
        total_schools=0,
        total_active_students=0,
        total_teachers=0,
        assessments_completed_last_7_days=0,
        generated_at=datetime.now(UTC),
    )


@router.post("/platform/schools/{school_id}/impersonate", response_model=dict[str, object])
async def impersonate_school(
    school_id: UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    # STUB — M0-10-T6 | Real implementation: M6 (no task file yet — added in M6 update)
    # Will issue a scoped JWT carrying the target school's school_id so KaihleAdmin
    # can browse a school's data as if they were that school's admin.
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="School impersonation is available from M6.",
    )
