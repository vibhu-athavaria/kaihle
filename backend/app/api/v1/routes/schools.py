"""School management API routes for KaihleAdmin."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, get_current_user, require_role
from app.schemas.school import (
    SchoolCreate,
    SchoolListResponse,
    SchoolResponse,
    SchoolUpdate,
)
from app.services.school_service import SchoolService

router = APIRouter(prefix="/admin/schools", tags=["schools"])


def _school_to_response(school: Any) -> SchoolResponse:
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
    )


@router.post("", response_model=SchoolResponse, status_code=status.HTTP_201_CREATED)
async def create_school(
    body: SchoolCreate,
    _: CurrentUser = Depends(require_role("KAIHLE_ADMIN")),
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
    _: CurrentUser = Depends(require_role("KAIHLE_ADMIN")),
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
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SchoolResponse:
    """Get a single school by ID.

    KaihleAdmin can see any school.
    SchoolAdmin can see only their own school.
    """
    # Check permissions
    if current_user.role not in ("KAIHLE_ADMIN", "SCHOOL_ADMIN"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    if current_user.role == "SCHOOL_ADMIN" and current_user.school_id != school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access school from different organization",
        )

    service = SchoolService(db)
    try:
        school = await service.get_school(school_id)
        return _school_to_response(school)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School not found",
        )


@router.patch("/{school_id}", response_model=SchoolResponse)
async def update_school(
    school_id: uuid.UUID,
    body: SchoolUpdate,
    _: CurrentUser = Depends(require_role("KAIHLE_ADMIN")),
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
