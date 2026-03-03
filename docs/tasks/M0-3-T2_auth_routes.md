# M0-3-T2 — Auth API Routes
**Milestone:** M0 — Foundations
**Epic:** M0-3 — Authentication System
**Task ID:** M0-3-T2
**Mode:** Code (MiniMax)
**Estimated effort:** 3–4 hours

---

## Context

This task implements all authentication HTTP endpoints: register, login, magic link (send + verify), token refresh, and logout. Routes are thin — they delegate all logic to an `AuthService`.

**Depends on:** M0-3-T1 (security utilities), M0-2-T2 (User and AuthToken ORM models)

---

## User Story

As any user, I want to log in with email/password or a magic link and receive a JWT so I can access protected resources.

---

## What To Build

### `/backend/app/services/auth_service.py`

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    InvalidTokenError,
    create_access_token,
    create_magic_link_token,
    decode_token,
    generate_refresh_token,
    hash_password,
    hash_token,
    store_magic_link_token,
    store_refresh_token,
    verify_password,
)
from app.models.user import AuthToken, User
from app.schemas.auth import LoginResponse, RegisterResponse, TokenResponse


class AuthService:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(
        self,
        email: str,
        password: str,
        role: str,
        school_id: uuid.UUID | None,
        first_name: str,
        last_name: str,
    ) -> RegisterResponse:
        """
        Create a new user. Does NOT issue tokens — admin must activate account.
        Raises ValueError if email already exists in school.
        """
        # Check uniqueness: email must be unique within school (or globally for KaihleAdmin)
        stmt = select(User).where(User.email == email)
        if school_id:
            stmt = stmt.where(User.school_id == school_id)
        existing = await self.db.scalar(stmt)
        if existing:
            raise ValueError("Email already registered")

        hashed = hash_password(password)
        user = User(
            email=email,
            hashed_password=hashed,
            role=role,
            school_id=school_id,
            first_name=first_name,
            last_name=last_name,
            is_active=True,
        )
        self.db.add(user)
        await self.db.flush()
        return RegisterResponse(user_id=user.id, email=user.email, role=user.role)

    async def login(self, email: str, password: str) -> LoginResponse:
        """
        Authenticate with email + password.
        Returns access + refresh tokens.
        Raises ValueError on invalid credentials or inactive account.
        """
        user = await self._get_active_user_by_email(email)
        if not verify_password(password, user.hashed_password):
            raise ValueError("Invalid credentials")

        access_token = create_access_token(user.id, user.school_id, user.role)
        raw_refresh, hashed_refresh = generate_refresh_token()
        await store_refresh_token(self.db, user.id, hashed_refresh)

        return LoginResponse(
            access_token=access_token,
            refresh_token=raw_refresh,
            token_type="bearer",
            user={"id": str(user.id), "email": user.email,
                  "role": user.role, "school_id": str(user.school_id)},
        )

    async def send_magic_link(self, email: str, base_url: str) -> None:
        """
        Generate and email a magic link.
        Always returns successfully — even if email not found (security).
        """
        user = await self.db.scalar(
            select(User).where(User.email == email, User.is_active == True)
        )
        if not user:
            return  # Silent — do not reveal whether email exists

        token = create_magic_link_token(user.id)
        token_hash = hash_token(token)
        await store_magic_link_token(self.db, user.id, token_hash)

        # Send email via Resend
        await self._send_magic_link_email(user.email, user.first_name, token, base_url)

    async def verify_magic_link(self, token: str) -> LoginResponse:
        """
        Validate magic link token, mark as used, return JWT pair.
        Raises InvalidTokenError if token is invalid, expired, or already used.
        """
        try:
            payload = decode_token(token)
        except InvalidTokenError:
            raise

        if payload.get("type") != "magic_link":
            raise InvalidTokenError("Not a magic link token")

        user_id = uuid.UUID(payload["sub"])
        token_hash = hash_token(token)

        # Find token in DB — must exist, not used, not expired
        auth_token = await self.db.scalar(
            select(AuthToken).where(
                AuthToken.user_id == user_id,
                AuthToken.token_hash == token_hash,
                AuthToken.token_type == "MAGIC_LINK",
                AuthToken.is_used == False,
                AuthToken.expires_at > datetime.now(timezone.utc),
            )
        )
        if not auth_token:
            raise InvalidTokenError("Token invalid or already used")

        # Mark as used
        auth_token.is_used = True
        await self.db.flush()

        user = await self.db.get(User, user_id)
        access_token = create_access_token(user.id, user.school_id, user.role)
        raw_refresh, hashed_refresh = generate_refresh_token()
        await store_refresh_token(self.db, user.id, hashed_refresh)

        return LoginResponse(
            access_token=access_token,
            refresh_token=raw_refresh,
            token_type="bearer",
            user={"id": str(user.id), "email": user.email,
                  "role": user.role, "school_id": str(user.school_id)},
        )

    async def refresh_access_token(self, raw_refresh_token: str) -> TokenResponse:
        """
        Exchange a valid refresh token for a new access token.
        Raises InvalidTokenError if token is invalid, expired, or already used.
        """
        token_hash = hash_token(raw_refresh_token)
        auth_token = await self.db.scalar(
            select(AuthToken).where(
                AuthToken.token_hash == token_hash,
                AuthToken.token_type == "REFRESH",
                AuthToken.is_used == False,
                AuthToken.expires_at > datetime.now(timezone.utc),
            )
        )
        if not auth_token:
            raise InvalidTokenError("Refresh token invalid or expired")

        user = await self.db.get(User, auth_token.user_id)
        new_access = create_access_token(user.id, user.school_id, user.role)
        return TokenResponse(access_token=new_access)

    async def logout(self, raw_refresh_token: str) -> None:
        """Mark refresh token as used (invalidate session)."""
        token_hash = hash_token(raw_refresh_token)
        auth_token = await self.db.scalar(
            select(AuthToken).where(
                AuthToken.token_hash == token_hash,
                AuthToken.token_type == "REFRESH",
            )
        )
        if auth_token:
            auth_token.is_used = True
            await self.db.flush()

    async def _get_active_user_by_email(self, email: str) -> User:
        user = await self.db.scalar(
            select(User).where(User.email == email)
        )
        if not user:
            raise ValueError("Invalid credentials")
        if not user.is_active:
            raise ValueError("Account is inactive")
        return user

    async def _send_magic_link_email(
        self, email: str, first_name: str, token: str, base_url: str
    ) -> None:
        """Send magic link email via Resend."""
        import resend
        from app.core.config import settings

        resend.api_key = settings.resend_api_key
        verify_url = f"{base_url}/api/v1/auth/magic-link/verify?token={token}"

        resend.Emails.send({
            "from": settings.from_email,
            "to": email,
            "subject": "Your Kaihle login link",
            "html": f"""
                <p>Hi {first_name},</p>
                <p>Click the link below to log in to Kaihle. This link expires in 10 minutes.</p>
                <p><a href="{verify_url}">Log in to Kaihle</a></p>
                <p>If you didn't request this, you can safely ignore this email.</p>
            """,
        })
```

---

### `/backend/app/schemas/auth.py`

```python
import uuid
from typing import Any
from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    role: str
    school_id: uuid.UUID | None = None
    first_name: str
    last_name: str


class RegisterResponse(BaseModel):
    user_id: uuid.UUID
    email: str
    role: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    user: dict[str, Any]


class TokenResponse(BaseModel):
    access_token: str


class MagicLinkRequest(BaseModel):
    email: EmailStr


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str
```

---

### `/backend/app/api/v1/routes/auth.py`

```python
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import InvalidTokenError
from app.schemas.auth import (
    LoginRequest, LoginResponse, LogoutRequest, MagicLinkRequest,
    RefreshRequest, RegisterRequest, RegisterResponse, TokenResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse,
             status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    try:
        return await service.register(
            email=body.email,
            password=body.password,
            role=body.role,
            school_id=body.school_id,
            first_name=body.first_name,
            last_name=body.last_name,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    try:
        return await service.login(body.email, body.password)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )


@router.post("/magic-link")
async def send_magic_link(
    body: MagicLinkRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)
    base_url = str(request.base_url).rstrip("/")
    await service.send_magic_link(body.email, base_url)
    # Always return success — never reveal whether email exists
    return {"message": "If that email is registered, a login link has been sent."}


@router.get("/magic-link/verify", response_model=LoginResponse)
async def verify_magic_link(token: str, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    try:
        return await service.verify_magic_link(token)
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Magic link is invalid or has expired",
        )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    try:
        return await service.refresh_access_token(body.refresh_token)
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is invalid or expired",
        )


@router.post("/logout")
async def logout(body: LogoutRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    await service.logout(body.refresh_token)
    return {"message": "Logged out"}
```

---

### Register Router in `main.py`

Update `/backend/app/main.py`:
```python
from app.api.v1.routes import auth

app.include_router(auth.router, prefix="/api/v1")
```

---

## Files To Create / Modify

```
/backend/app/services/auth_service.py     ← CREATE
/backend/app/schemas/auth.py              ← CREATE
/backend/app/api/v1/routes/auth.py        ← CREATE
/backend/app/main.py                      ← MODIFY (register router)
```

---

## Acceptance Criteria

- [ ] Integration test: `POST /api/v1/auth/register` creates user, returns `user_id`, `email`, `role`
- [ ] Integration test: `POST /api/v1/auth/login` with correct credentials returns valid JWT with `sub`, `school_id`, `role`
- [ ] Integration test: `POST /api/v1/auth/login` with wrong password returns 401
- [ ] Integration test: full magic link flow — send → verify → returns JWT
- [ ] Integration test: expired magic link returns 401
- [ ] Integration test: used magic link returns 401 on second use
- [ ] Integration test: `POST /api/v1/auth/refresh` with valid refresh token returns new access token
- [ ] Integration test: `POST /api/v1/auth/refresh` with expired/used token returns 401
- [ ] Integration test: `POST /api/v1/auth/logout` marks refresh token as used
- [ ] Security test: `POST /api/v1/auth/register` with SQL injection in email field returns 422 (Pydantic rejects)

---

## Dependencies

- M0-3-T1 — all security utilities must be implemented
- M0-2-T2 — `User`, `AuthToken` ORM models

## Output (What Next Tasks Can Use)

- `AuthService` — used and extended by other services
- All auth endpoints live at `/api/v1/auth/*`
- Tokens issued here are validated by M0-3-T3 middleware
