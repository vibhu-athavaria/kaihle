"""School management API routes for KaihleAdmin."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, _check_school_access, require_role
from app.models.user import UserRole
from app.schemas.school import (
    SchoolCreate,
    SchoolCurriculumCreate,
    SchoolCurriculumResponse,
    SchoolListResponse,
    SchoolResponse,
    SchoolUpdate,
)
from app.services.school_service import SchoolService

router = APIRouter(prefix="/schools", tags=["schools"])


def _school_to_response(school: Any, admin_user: Any = None) -> SchoolResponse:
    """Convert School model to SchoolResponse schema.

    Handles the mapping from status field to is_active boolean.
    """
    return SchoolResponse(
        id=school.id,
        name=school.name,
        slug=school.slug,
        country=school.country,
        timezone=school.timezone,
        is_active=school.status == "active",
        joined=school.created_at.isoformat(),
        admin_user_id=admin_user.id if admin_user else None,
        admin_email=admin_user.email if admin_user else None,
    )


@router.post("", response_model=SchoolResponse, status_code=status.HTTP_201_CREATED)
async def create_school(
    body: SchoolCreate,
    _: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> SchoolResponse:
    """Create a new school. KaihleAdmin only."""
    service = SchoolService(db)
    try:
        school = await service.create_school(body)
        return _school_to_response(school)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get("", response_model=SchoolListResponse)
async def list_schools(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> SchoolListResponse:
    """List all schools with pagination. KaihleAdmin only."""
    service = SchoolService(db)
    schools, total = await service.list_schools(page, page_size)
    return SchoolListResponse(
        schools=[_school_to_response(s) for s in schools],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{school_id}", response_model=SchoolResponse)
async def get_school(
    school_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN, UserRole.SCHOOL_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> SchoolResponse:
    """Get a single school. KaihleAdmin sees any school. SchoolAdmin sees own only."""
    import structlog

    logger = structlog.get_logger()
    logger.info("get_school_request", school_id=str(school_id), user_id=str(current_user.id))

    _check_school_access(school_id, current_user)
    service = SchoolService(db)
    try:
        school, admin_user = await service.get_school_with_admin(school_id)
        logger.info(
            "get_school_response",
            school_id=str(school.id),
            admin_user_id=str(admin_user.id) if admin_user else None,
            has_city=hasattr(school, "city"),
            city=getattr(school, "city", None),
        )
        return _school_to_response(school, admin_user)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="School not found")


@router.patch("/{school_id}", response_model=SchoolResponse)
async def update_school(
    school_id: uuid.UUID,
    body: SchoolUpdate,
    _: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> SchoolResponse:
    """Update a school. KaihleAdmin only."""
    service = SchoolService(db)
    try:
        school = await service.update_school(school_id, body)
        return _school_to_response(school)
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# ---------------------------------------------------------------------------
# Curriculum subscription endpoints
# ---------------------------------------------------------------------------


def _sc_to_response(sc: Any, curriculum: Any) -> SchoolCurriculumResponse:
    """Map a (SchoolCurriculum, Curriculum) pair to the response schema."""
    return SchoolCurriculumResponse(
        curriculum_id=sc.curriculum_id,
        curriculum_name=curriculum.name,
        curriculum_code=curriculum.code,
        curriculum_description=curriculum.description,
        is_primary=sc.is_primary,
        adopted_at=sc.adopted_at.isoformat(),
    )


@router.get("/{school_id}/curricula", response_model=list[SchoolCurriculumResponse])
async def list_school_curricula(
    school_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN, UserRole.SCHOOL_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> list[SchoolCurriculumResponse]:
    """List curricula a school is subscribed to. KaihleAdmin sees any school; SchoolAdmin sees own only."""
    _check_school_access(school_id, current_user)
    service = SchoolService(db)
    pairs = await service.list_school_curricula(school_id)
    return [_sc_to_response(sc, c) for sc, c in pairs]


@router.post(
    "/{school_id}/curricula",
    response_model=SchoolCurriculumResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_school_curriculum(
    school_id: uuid.UUID,
    body: SchoolCurriculumCreate,
    _: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> SchoolCurriculumResponse:
    """Subscribe a school to a curriculum. KaihleAdmin only."""
    service = SchoolService(db)
    try:
        sc, curriculum = await service.add_school_curriculum(school_id, body.curriculum_id, body.is_primary)
        return _sc_to_response(sc, curriculum)
    except ValueError as e:
        msg = str(e)
        if "not found" in msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
        if "already subscribed" in msg.lower():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)


@router.delete("/{school_id}/curricula/{curriculum_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_school_curriculum(
    school_id: uuid.UUID,
    curriculum_id: uuid.UUID,
    _: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove a school's curriculum subscription. KaihleAdmin only."""
    service = SchoolService(db)
    try:
        await service.remove_school_curriculum(school_id, curriculum_id)
    except ValueError as e:
        msg = str(e)
        if "not subscribed" in msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=msg)


@router.patch("/{school_id}/curricula/{curriculum_id}/primary", response_model=SchoolCurriculumResponse)
async def set_primary_curriculum(
    school_id: uuid.UUID,
    curriculum_id: uuid.UUID,
    _: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> SchoolCurriculumResponse:
    """Set a curriculum as the school's primary. KaihleAdmin only."""
    service = SchoolService(db)
    try:
        sc, curriculum = await service.set_primary_curriculum(school_id, curriculum_id)
        return _sc_to_response(sc, curriculum)
    except ValueError as e:
        msg = str(e)
        if "not subscribed" in msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg)
