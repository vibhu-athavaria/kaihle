"""Authentication service with all auth operations."""

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
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
from app.models.school import School
from app.models.user import AuthToken, AuthTokenType, User
from app.schemas.auth import LoginResponse, RegisterResponse, TokenResponse

logger = structlog.get_logger()


class SchoolNotFoundError(Exception):
    """Raised when a school is not found."""

    pass


class AuthServiceError(Exception):
    """Base exception for auth service errors."""

    pass


class AuthService:
    """Service for all authentication operations."""

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
        Create a new user. Does NOT issue tokens — user is created as inactive
        and must be activated by an admin before they can log in.
        Raises ValueError if email already exists (globally unique).
        """
        # Email is globally unique across all schools
        stmt = select(User).where(User.email == email)
        existing = await self.db.scalar(stmt)
        if existing:
            raise ValueError("Email already registered")

        # Validate school exists if provided
        if school_id:
            school = await self.db.get(School, school_id)
            if not school:
                raise SchoolNotFoundError(f"School with id {school_id} not found")

        hashed = hash_password(password)
        user = User(
            email=email,
            hashed_password=hashed,
            role=role,
            school_id=school_id,
            first_name=first_name,
            last_name=last_name,
            is_active=False,
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
        if not user.hashed_password or not verify_password(password, user.hashed_password):
            raise ValueError("Invalid credentials")

        user.last_login_at = datetime.now(UTC)
        await self.db.flush()

        access_token = create_access_token(user.id, user.school_id, user.role)
        raw_refresh, hashed_refresh = generate_refresh_token()
        await store_refresh_token(self.db, user.id, hashed_refresh)

        return LoginResponse(
            access_token=access_token,
            refresh_token=raw_refresh,
            token_type="bearer",
            user={
                "id": str(user.id),
                "email": user.email,
                "first_name": user.first_name,
                "role": user.role,
                "school_id": str(user.school_id) if user.school_id else None,
            },
        )

    async def send_magic_link(self, email: str, base_url: str) -> None:
        """
        Generate and email a magic link.
        Always returns successfully — even if email not found (security).
        """
        user = await self.db.scalar(select(User).where(User.email == email, User.is_active.is_(True)))
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
                AuthToken.type == AuthTokenType.MAGIC_LINK,
                AuthToken.used_at.is_(None),
                AuthToken.expires_at > datetime.now(UTC),
            )
        )
        if not auth_token:
            raise InvalidTokenError("Token invalid or already used")

        # Mark as used
        auth_token.used_at = datetime.now(UTC)
        await self.db.flush()

        user = await self.db.get(User, user_id)
        if not user:
            raise InvalidTokenError("User not found")

        user.last_login_at = datetime.now(UTC)
        await self.db.flush()

        access_token = create_access_token(user.id, user.school_id, user.role)
        raw_refresh, hashed_refresh = generate_refresh_token()
        await store_refresh_token(self.db, user.id, hashed_refresh)

        return LoginResponse(
            access_token=access_token,
            refresh_token=raw_refresh,
            token_type="bearer",
            user={
                "id": str(user.id),
                "email": user.email,
                "first_name": user.first_name,
                "role": user.role,
                "school_id": str(user.school_id) if user.school_id else None,
            },
        )

    async def verify_magic_link_get_token(self, token: str) -> str:
        """
        Validate magic link token, mark as used, return the SAME scoped JWT token.
        This is used when the user clicks the magic link - we return the token
        that already has scope: password_setup.
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
                AuthToken.type == AuthTokenType.MAGIC_LINK,
                AuthToken.used_at.is_(None),
                AuthToken.expires_at > datetime.now(UTC),
            )
        )
        if not auth_token:
            raise InvalidTokenError("Token invalid or already used")

        # Mark as used
        auth_token.used_at = datetime.now(UTC)
        await self.db.flush()

        user = await self.db.get(User, user_id)
        if not user:
            raise InvalidTokenError("User not found")

        # Issue a NEW magic link JWT with the same scope: password_setup.
        # The original token from the URL is a one-time use token; this new JWT
        # is what the frontend receives to complete password setup.
        scoped_token = create_magic_link_token(user.id)
        return scoped_token

    async def set_password_from_scoped_token(self, token_payload: dict[str, Any], new_password: str) -> LoginResponse:
        """
        Set password for a user who was invited via magic link.
        The token payload must have scope: password_setup and type: magic_link.
        Returns full-access JWT tokens after password is set.
        Raises ValueError if user already has a password set.
        """
        if token_payload.get("type") != "magic_link":
            raise ValueError("Invalid token type - expected magic link token")

        if token_payload.get("scope") != "password_setup":
            raise ValueError("Token does not have password_setup scope")

        user_id = uuid.UUID(token_payload["sub"])

        user = await self.db.get(User, user_id)
        if not user:
            raise InvalidTokenError("User not found")

        if user.hashed_password is not None:
            raise ValueError("Password already set for this user")

        # Hash and set the new password
        user.hashed_password = hash_password(new_password)
        user.last_login_at = datetime.now(UTC)
        await self.db.flush()

        # Generate full-access tokens
        access_token = create_access_token(user.id, user.school_id, user.role)
        raw_refresh, hashed_refresh = generate_refresh_token()
        await store_refresh_token(self.db, user.id, hashed_refresh)

        return LoginResponse(
            access_token=access_token,
            refresh_token=raw_refresh,
            token_type="bearer",
            user={
                "id": str(user.id),
                "email": user.email,
                "first_name": user.first_name,
                "role": user.role,
                "school_id": str(user.school_id) if user.school_id else None,
            },
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
                AuthToken.type == AuthTokenType.REFRESH,
                AuthToken.used_at.is_(None),
                AuthToken.expires_at > datetime.now(UTC),
            )
        )
        if not auth_token:
            raise InvalidTokenError("Refresh token invalid or expired")

        user = await self.db.get(User, auth_token.user_id)
        if not user:
            raise InvalidTokenError("User not found")

        new_access = create_access_token(user.id, user.school_id, user.role)
        return TokenResponse(access_token=new_access)

    async def logout(self, raw_refresh_token: str) -> None:
        """Mark refresh token as used (invalidate session)."""
        token_hash = hash_token(raw_refresh_token)
        auth_token = await self.db.scalar(
            select(AuthToken).where(
                AuthToken.token_hash == token_hash,
                AuthToken.type == AuthTokenType.REFRESH,
            )
        )
        if auth_token:
            auth_token.used_at = datetime.now(UTC)
            await self.db.flush()

    async def _get_active_user_by_email(self, email: str) -> User:
        user = await self.db.scalar(select(User).where(User.email == email))
        if not user:
            raise ValueError("Invalid credentials")
        if not user.is_active:
            raise ValueError("Account is inactive")
        return user

    async def _send_magic_link_email(self, email: str, first_name: str, token: str, base_url: str) -> None:
        """Send magic link email via Resend."""
        try:
            import resend

            from app.core.config import settings

            resend.api_key = settings.resend_api_key
            verify_url = f"{base_url}/api/v1/auth/magic-link/verify?token={token}"

            resend.Emails.send(
                {
                    "from": settings.from_email,
                    "to": email,
                    "subject": "Your Kaihle login link",
                    "html": f"""
                    <p>Hi {first_name},</p>
                    <p>Click the link below to log in to Kaihle. This link expires in 10 minutes.</p>
                    <p><a href="{verify_url}">Log in to Kaihle</a></p>
                    <p>If you didn't request this, you can safely ignore this email.</p>
                """,
                }
            )
        except Exception:
            # In test environment or if Resend fails, we still want to succeed
            # because the token is already stored in the database
            pass

    async def change_password(self, user_id: uuid.UUID, current_password: str, new_password: str) -> None:
        """
        Change a user's password after verifying the current password.

        Raises ValueError if user not found or current password is incorrect.
        """
        user = await self.db.get(User, user_id)
        if not user:
            raise ValueError("User not found")
        if user.hashed_password is None:
            raise ValueError("User has no password set")
        if not verify_password(current_password, user.hashed_password):
            raise ValueError("Current password is incorrect")

        logger.info(
            "user_password_changed",
            user_id=str(user_id),
        )

        user.hashed_password = hash_password(new_password)
        await self.db.flush()
