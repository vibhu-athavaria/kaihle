# M0-4-T2 — User Management API (SchoolAdmin)
**Milestone:** M0 — Foundations
**Epic:** M0-4 — School & User Management
**Task ID:** M0-4-T2
**Mode:** Code (MiniMax)
**Estimated effort:** 3–4 hours

---

## Context

School Admins invite teachers, other admins, and parents to join the platform. New users are created in an inactive state and activated via the magic link email. Students are enrolled through the class enrollment flow (M0-4-T3), not here.

**Depends on:** M0-4-T1 (SchoolService), M0-3-T2 (magic link email via AuthService)

---

## User Story

As a School Admin, I want to invite users to my school so that teachers and parents can access the platform.

---

## What To Build

### `/backend/app/services/user_service.py`

```python
import uuid
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User, TeacherProfile
from app.schemas.user import UserInvite, UserUpdate
from app.core.security import hash_password
import secrets


class UserService:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def invite_user(
        self,
        school_id: uuid.UUID,
        data: UserInvite,
        base_url: str,
    ) -> User:
        """
        Create a user record and send a magic link to activate their account.
        User is created with is_active=True and a random unusable password.
        They activate via the magic link.
        """
        # Validate role is allowed for invitation
        allowed_roles = {"TEACHER", "SCHOOL_ADMIN", "PARENT"}
        if data.role not in allowed_roles:
            raise ValueError(f"Cannot invite user with role '{data.role}'")

        # Check email uniqueness within school
        existing = await self.db.scalar(
            select(User).where(
                User.email == data.email,
                User.school_id == school_id,
            )
        )
        if existing:
            raise ValueError(f"Email '{data.email}' is already registered at this school")

        # Create user with a random unusable password (they log in via magic link)
        user = User(
            email=data.email,
            hashed_password=hash_password(secrets.token_hex(32)),
            role=data.role,
            school_id=school_id,
            first_name=data.first_name,
            last_name=data.last_name,
            is_active=True,
        )
        self.db.add(user)
        await self.db.flush()

        # Create role-specific profile
        if data.role == "TEACHER":
            profile = TeacherProfile(
                user_id=user.id,
                subjects=data.subjects or [],
            )
            self.db.add(profile)
            await self.db.flush()

        # Send magic link welcome email
        from app.services.auth_service import AuthService
        from app.core.security import create_magic_link_token, hash_token, store_magic_link_token
        token = create_magic_link_token(user.id, expires_in_minutes=72 * 60)  # 72-hour welcome link
        token_hash = hash_token(token)
        await store_magic_link_token(self.db, user.id, token_hash, expires_minutes=72 * 60)
        await self._send_welcome_email(user, token, base_url)

        return user

    async def list_users(
        self,
        school_id: uuid.UUID,
        role: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[User], int]:
        stmt = select(User).where(
            User.school_id == school_id,
            User.is_active == True,
        )
        if role:
            stmt = stmt.where(User.role == role)

        offset = (page - 1) * page_size
        result = await self.db.execute(
            stmt.order_by(User.last_name, User.first_name)
            .offset(offset).limit(page_size)
        )
        users = result.scalars().all()

        count_stmt = select(func.count()).select_from(User).where(
            User.school_id == school_id, User.is_active == True
        )
        total = await self.db.scalar(count_stmt) or 0
        return list(users), total

    async def get_user(self, school_id: uuid.UUID, user_id: uuid.UUID) -> User:
        user = await self.db.get(User, user_id)
        if not user or user.school_id != school_id:
            raise ValueError("User not found")
        return user

    async def update_user(
        self,
        school_id: uuid.UUID,
        user_id: uuid.UUID,
        data: UserUpdate,
    ) -> User:
        user = await self.get_user(school_id, user_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(user, field, value)
        await self.db.flush()
        return user

    async def deactivate_user(
        self, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        """Soft delete — sets is_active=False. User cannot log in after this."""
        user = await self.get_user(school_id, user_id)
        user.is_active = False
        await self.db.flush()

    async def _send_welcome_email(
        self, user: User, token: str, base_url: str
    ) -> None:
        import resend
        from app.core.config import settings
        resend.api_key = settings.resend_api_key
        verify_url = f"{base_url}/api/v1/auth/magic-link/verify?token={token}"
        resend.Emails.send({
            "from": settings.from_email,
            "to": user.email,
            "subject": "Welcome to Kaihle — activate your account",
            "html": f"""
                <p>Hi {user.first_name},</p>
                <p>You've been invited to Kaihle. Click the link below to set up your account.</p>
                <p>This link is valid for 72 hours.</p>
                <p><a href="{verify_url}">Activate my account</a></p>
            """,
        })
```

---

### `/backend/app/schemas/user.py`

```python
import uuid
from typing import Optional
from pydantic import BaseModel, EmailStr


class UserInvite(BaseModel):
    email: EmailStr
    role: str           # TEACHER | SCHOOL_ADMIN | PARENT
    first_name: str
    last_name: str
    subjects: Optional[list[str]] = None   # for TEACHER role only


class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    first_name: str
    last_name: str
    is_active: bool
    school_id: Optional[uuid.UUID]

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    users: list[UserResponse]
    total: int
    page: int
    page_size: int
```

---

### `/backend/app/api/v1/routes/users.py`

```python
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_role, get_current_user
from app.schemas.user import UserInvite, UserListResponse, UserResponse, UserUpdate
from app.services.user_service import UserService

router = APIRouter(prefix="/schools/{school_id}/users", tags=["users"])


def _check_school_access(school_id: uuid.UUID, current_user):
    """KaihleAdmin can access any school. SchoolAdmin can only access own school."""
    if current_user.role == "KAIHLE_ADMIN":
        return
    if current_user.role != "SCHOOL_ADMIN" or current_user.school_id != school_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def invite_user(
    school_id: uuid.UUID,
    body: UserInvite,
    request: Request,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _check_school_access(school_id, current_user)
    service = UserService(db)
    try:
        user = await service.invite_user(
            school_id=school_id,
            data=body,
            base_url=str(request.base_url).rstrip("/"),
        )
        return user
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get("", response_model=UserListResponse)
async def list_users(
    school_id: uuid.UUID,
    role: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _check_school_access(school_id, current_user)
    service = UserService(db)
    users, total = await service.list_users(school_id, role, page, page_size)
    return UserListResponse(users=users, total=total, page=page, page_size=page_size)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    school_id: uuid.UUID,
    user_id: uuid.UUID,
    body: UserUpdate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _check_school_access(school_id, current_user)
    service = UserService(db)
    try:
        return await service.update_user(school_id, user_id, body)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_user(
    school_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _check_school_access(school_id, current_user)
    service = UserService(db)
    try:
        await service.deactivate_user(school_id, user_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
```

Register in `main.py`:
```python
from app.api.v1.routes import users
app.include_router(users.router, prefix="/api/v1")
```

---

## Acceptance Criteria

- [ ] Integration test: SchoolAdmin invites teacher → user created, welcome email sent (mock Resend)
- [ ] Integration test: inviting duplicate email in same school returns 409
- [ ] Integration test: SchoolAdmin cannot manage users in a different school (403)
- [ ] Integration test: KaihleAdmin can manage users in any school
- [ ] Integration test: deactivated user cannot log in (401 on login attempt)
- [ ] Integration test: list users with `role=TEACHER` filter returns only teachers
- [ ] Integration test: pagination — correct `total` count returned

---

## Dependencies

- M0-4-T1 — school must exist before users can belong to it
- M0-3-T2 — `create_magic_link_token`, `store_magic_link_token` from security module

## Output (What Next Tasks Can Use)

- Teachers and admins can be created in the system
- Invitation email flow working end-to-end
- `UserService` reusable by other services (e.g. reporting, analytics in M6)
