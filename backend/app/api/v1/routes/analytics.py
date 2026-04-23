"""Analytics and platform management routes.

Three sections:
1. School analytics — GET /schools/{id}/analytics (SchoolAdmin sees own school)
2. Platform stats  — GET /platform/stats (KaihleAdmin only)
3. Platform actions — POST /platform/schools/{id}/impersonate (KaihleAdmin only)

Note on the /platform prefix: platform-level endpoints are not nested under
/schools because they operate across all schools, not within one. This mirrors
the separation between tenant-scoped and platform-scoped concerns.
"""

from datetime import date
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, _check_school_access, require_full_access, require_role
from app.models.school import School
from app.models.user import UserRole
from app.schemas.analytics import PlatformStats, SchoolAnalytics
from app.services.analytics_service import AnalyticsService

router = APIRouter(tags=["analytics"])
logger = structlog.get_logger()


@router.get("/schools/{school_id}/analytics", response_model=SchoolAnalytics)
async def get_school_analytics(
    request: Request,
    school_id: UUID,
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    current_user: CurrentUser = Depends(require_full_access),
    _role_check: CurrentUser = Depends(require_role(UserRole.SCHOOL_ADMIN, UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> SchoolAnalytics:
    # Check school access - KAIHLE_ADMIN bypasses, others must match (Rule 12)
    _check_school_access(school_id, current_user)

    service = AnalyticsService(db, request.app.state.redis)
    data = await service.get_school_analytics(school_id, from_date, to_date)
    logger.info("analytics.school.requested", school_id=str(school_id), user_id=str(current_user.id))
    # SchoolAnalytics is an alias for SchoolAnalyticsData — model_validate handles the cast
    return SchoolAnalytics.model_validate(data.model_dump())


@router.get("/platform/stats", response_model=PlatformStats)
async def get_platform_stats(
    request: Request,
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> PlatformStats:
    service = AnalyticsService(db, request.app.state.redis)
    logger.info("platform.stats.requested", user_id=str(current_user.id))
    return await service.get_platform_stats()


@router.post("/platform/schools/{school_id}/impersonate", response_model=dict[str, object])
async def impersonate_school(
    request: Request,
    school_id: UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    school = await db.scalar(select(School).where(School.id == school_id))
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    service = AnalyticsService(db, request.app.state.redis)
    logger.info("platform.impersonate.requested", school_id=str(school_id), user_id=str(current_user.id))
    return await service.issue_impersonation_token(school_id=school_id, kaihle_admin_id=current_user.id)
