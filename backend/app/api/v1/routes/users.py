"""User management API routes."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, _check_school_access, require_full_access, require_role
from app.models.user import UserRole
from app.schemas.user import MeResponse, UserInvite, UserListResponse, UserResponse, UserSelfUpdate, UserUpdate
from app.services.user_service import UserService

router = APIRouter(prefix="/schools/{school_id}/users", tags=["users"])


@router.get("/me", response_model=MeResponse)
async def get_me(
    school_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_full_access),
    db: AsyncSession = Depends(get_db),
) -> MeResponse:
    """Get the current user's own profile."""
    _check_school_access(school_id, current_user)
    service = UserService(db)
    user = await service.get_me(current_user.id)
    return MeResponse.model_validate(user)


@router.patch("/me", response_model=MeResponse)
async def update_me(
    school_id: uuid.UUID,
    body: UserSelfUpdate,
    current_user: CurrentUser = Depends(require_full_access),
    db: AsyncSession = Depends(get_db),
) -> MeResponse:
    """Update the current user's own first_name and/or last_name."""
    _check_school_access(school_id, current_user)
    service = UserService(db)
    try:
        user = await service.update_me(current_user.id, body)
        return MeResponse.model_validate(user)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def invite_user(
    school_id: uuid.UUID,
    body: UserInvite,
    request: Request,
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN, UserRole.SCHOOL_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """
    Invite a new user to the school.

    - **email**: User's email address
    - **role**: Must be TEACHER, SCHOOL_ADMIN, or PARENT
    - **first_name**: User's first name
    - **last_name**: User's last name
    - **subjects**: Optional list of subjects (only for TEACHER role)
    """
    _check_school_access(school_id, current_user)
    service = UserService(db)
    try:
        user = await service.invite_user(
            school_id=school_id,
            data=body,
            base_url=str(request.base_url).rstrip("/"),
        )
        return UserResponse.model_validate(user)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get("", response_model=UserListResponse)
async def list_users(
    school_id: uuid.UUID,
    role: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN, UserRole.SCHOOL_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> UserListResponse:
    """List users in a school with optional role filter and pagination."""
    _check_school_access(school_id, current_user)
    service = UserService(db)
    users, total = await service.list_users(school_id, role, page, page_size)
    return UserListResponse(
        users=[UserResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    school_id: uuid.UUID,
    user_id: uuid.UUID,
    body: UserUpdate,
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN, UserRole.SCHOOL_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Update user information."""
    _check_school_access(school_id, current_user)
    service = UserService(db)
    try:
        user = await service.update_user(school_id, user_id, body)
        return UserResponse.model_validate(user)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_user(
    school_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN, UserRole.SCHOOL_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Deactivate a user (soft delete)."""
    _check_school_access(school_id, current_user)
    service = UserService(db)
    try:
        await service.deactivate_user(school_id, user_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
