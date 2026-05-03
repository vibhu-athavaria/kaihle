"""User management API routes."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, _check_school_access, require_full_access, require_role
from app.models.curriculum import Grade
from app.models.user import StudentProfile, UserRole
from app.schemas.user import (
    MeResponse,
    StudentListItem,
    StudentListResponse,
    UserDirectCreate,
    UserInvite,
    UserListResponse,
    UserResponse,
    UserSelfUpdate,
    UserUpdate,
)
from app.services.analytics_service import AnalyticsService
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


@router.post(
    "/create",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_user_direct(
    school_id: uuid.UUID,
    body: UserDirectCreate,
    request: Request,
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN, UserRole.SCHOOL_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Create a user with an admin-supplied password. No magic link is sent.

    Only SCHOOL_ADMIN and KAIHLE_ADMIN may call this endpoint.
    """
    _check_school_access(school_id, current_user)

    service = UserService(db=db)
    try:
        user = await service.create_user_direct(school_id=school_id, data=body)
        await db.commit()
        return UserResponse.model_validate(user)
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


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


@router.get("", response_model=UserListResponse | StudentListResponse)
async def list_users(
    request: Request,
    school_id: uuid.UUID,
    role: UserRole | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    # require_full_access guards against password_setup-scoped tokens (security gap fix).
    # require_role enforces that only SCHOOL_ADMIN or KAIHLE_ADMIN may list users.
    _full: CurrentUser = Depends(require_full_access),
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN, UserRole.SCHOOL_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> UserListResponse | StudentListResponse:
    """List users in a school with optional role filter and pagination.

    When role=STUDENT, returns a StudentListResponse enriched with worst_mastery
    and diagnostic_completed derived from two single-query AnalyticsService calls
    (no N+1).
    """
    _check_school_access(school_id, current_user)
    service = UserService(db)
    users, total = await service.list_users(school_id, role, page, page_size)

    if role == UserRole.STUDENT:
        analytics = AnalyticsService(db, request.app.state.redis)
        student_ids = [u.id for u in users]
        summaries = await analytics.get_student_mastery_summaries(school_id, student_ids=student_ids)
        summary_map = {s.student_id: s for s in summaries}
        completed_ids = await analytics.get_diagnostic_completed_student_ids(school_id, student_ids)

        # Bulk-fetch grade levels from student_profiles — the single source of truth for student grade.
        grade_level_map: dict[uuid.UUID, int] = {}
        if student_ids:
            profile_rows = (
                await db.execute(
                    select(StudentProfile.user_id, Grade.level)
                    .join(Grade, Grade.id == StudentProfile.grade_id)
                    .where(StudentProfile.user_id.in_(student_ids))
                )
            ).all()
            for user_id, level in profile_rows:
                grade_level_map[user_id] = level

        return StudentListResponse(
            users=[
                StudentListItem(
                    id=u.id,
                    first_name=u.first_name,
                    last_name=u.last_name,
                    email=u.email,
                    is_active=u.is_active,
                    last_login_at=u.last_login_at,
                    worst_mastery=summary_map[u.id].worst_mastery if u.id in summary_map else None,
                    class_count=summary_map[u.id].class_count if u.id in summary_map else 0,
                    needs_work_class_count=summary_map[u.id].needs_work_class_count if u.id in summary_map else 0,
                    diagnostic_completed=u.id in completed_ids,
                    grade_level=grade_level_map.get(u.id),
                )
                for u in users
            ],
            total=total,
            page=page,
            page_size=page_size,
        )

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
    # KAIHLE_ADMIN may set passwords for any user in any school.
    # SCHOOL_ADMIN may set passwords for users in their own school only
    # (enforced by _check_school_access above — no additional guard needed).
    # TEACHER and PARENT cannot reach this route (blocked by require_role).
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
