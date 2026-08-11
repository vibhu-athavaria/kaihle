"""Authentication service with all auth operations."""

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    InvalidTokenError,
    create_access_token,
    create_impersonation_handoff_token,
    create_magic_link_token,
    decode_token,
    generate_refresh_token,
    hash_password,
    hash_token,
    store_impersonation_token,
    store_magic_link_token,
    store_password_reset_token,
    store_refresh_token,
    verify_password,
)
from app.models.school import School
from app.models.user import AuthToken, AuthTokenType, User, UserRole
from app.schemas.auth import (
    ImpersonationStartResponse,
    LoginResponse,
    RegisterResponse,
    TokenResponse,
)
from app.services.email_service import EmailService

logger = structlog.get_logger()


def app_url_for_role(role: str) -> str:
    """Return the frontend app base URL that serves the given role.

    Each role has exactly one app (CONSTITUTION §6). Used to build both password
    reset links and impersonation handoff links.
    """
    role_url_map: dict[str, str] = {
        UserRole.TEACHER.value: settings.teacher_app_url,
        UserRole.STUDENT.value: settings.student_app_url,
        UserRole.PARENT.value: settings.parent_app_url,
        UserRole.SCHOOL_ADMIN.value: settings.school_admin_app_url,
        UserRole.KAIHLE_ADMIN.value: settings.kaihle_admin_app_url,
    }
    return role_url_map.get(role, settings.school_admin_app_url)


class SchoolNotFoundError(Exception):
    """Raised when a school is not found."""

    pass


class ImpersonationNotAllowedError(Exception):
    """Raised when a user may not be impersonated (inactive, or a Kaihle Admin)."""

    pass


class UserNotFoundError(Exception):
    """Raised when a target user does not exist."""

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
        email: str | None,
        password: str,
        role: str,
        school_id: uuid.UUID | None,
        first_name: str,
        last_name: str,
        username: str | None = None,
    ) -> RegisterResponse:
        """
        Create a new user. Does NOT issue tokens — user is created as inactive
        and must be activated by an admin before they can log in.
        Raises ValueError if email or username already exists.
        """
        # Check email uniqueness (global, across all schools)
        if email:
            stmt = select(User).where(User.email == email)
            existing = await self.db.scalar(stmt)
            if existing:
                raise ValueError("Email already registered")

        # Check username uniqueness (global, across all schools)
        if username:
            stmt = select(User).where(User.username == username)
            existing = await self.db.scalar(stmt)
            if existing:
                raise ValueError("Username already taken")

        # Validate school exists if provided
        if school_id:
            school = await self.db.get(School, school_id)
            if not school:
                raise SchoolNotFoundError(f"School with id {school_id} not found")

        hashed = hash_password(password)
        user = User(
            email=email,
            username=username,
            hashed_password=hashed,
            role=role,
            school_id=school_id,
            first_name=first_name,
            last_name=last_name,
            is_active=False,
        )
        self.db.add(user)
        await self.db.flush()
        return RegisterResponse(user_id=user.id, email=user.email, username=user.username, role=user.role)

    async def login(self, email_or_username: str, password: str) -> LoginResponse:
        """
        Authenticate with email or username + password.
        Returns access + refresh tokens.
        Raises ValueError on invalid credentials or inactive account.
        """
        user = await self._get_active_user_by_login(email_or_username)
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
            must_change_password=bool(user.must_change_password),
            user={
                "id": str(user.id),
                "email": user.email or "",
                "username": user.username or "",
                "first_name": user.first_name,
                "role": user.role,
                "school_id": str(user.school_id) if user.school_id else None,
                "permissions": user.permissions,
            },
        )

    async def send_magic_link(self, email: str, base_url: str) -> None:
        """
        Generate and email a magic link.
        Always returns successfully — even if email not found (security).
        """
        user: User | None = await self.db.scalar(select(User).where(User.email == email, User.is_active.is_(True)))
        if not user:
            return  # Silent — do not reveal whether email exists

        token = create_magic_link_token(user.id)
        token_hash = hash_token(token)
        await store_magic_link_token(self.db, user.id, token_hash)

        # Send email via Resend — user was found by email, so it's non-null
        if user.email:
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
            must_change_password=bool(user.must_change_password),
            user={
                "id": str(user.id),
                "email": user.email or "",
                "username": user.username or "",
                "first_name": user.first_name,
                "role": user.role,
                "school_id": str(user.school_id) if user.school_id else None,
                "permissions": user.permissions,
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
            must_change_password=False,
            user={
                "id": str(user.id),
                "email": user.email or "",
                "username": user.username or "",
                "first_name": user.first_name,
                "role": user.role,
                "school_id": str(user.school_id) if user.school_id else None,
                "permissions": user.permissions,
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

    async def start_impersonation(
        self,
        impersonator: User,
        target_user_id: uuid.UUID,
    ) -> ImpersonationStartResponse:
        """Mint a single-use handoff link that opens a session as target_user_id.

        Caller must already be authorised as KAIHLE_ADMIN (enforced at the route).

        Raises UserNotFoundError if the target does not exist, and
        ImpersonationNotAllowedError if the target is inactive, is the caller, or
        is another KAIHLE_ADMIN — one platform admin acting as another would be
        indistinguishable in the audit trail.
        """
        target = await self.db.get(User, target_user_id)
        if not target:
            raise UserNotFoundError("User not found")
        if target.id == impersonator.id:
            raise ImpersonationNotAllowedError("You are already signed in as this user")
        if not target.is_active:
            raise ImpersonationNotAllowedError("Cannot impersonate an inactive user")
        if target.role == UserRole.KAIHLE_ADMIN:
            raise ImpersonationNotAllowedError("Cannot impersonate another Kaihle Admin")

        raw_token = create_impersonation_handoff_token(target.id, impersonator.id)
        await store_impersonation_token(self.db, target.id, hash_token(raw_token))

        app_url = app_url_for_role(target.role)

        logger.info(
            "impersonation.started",
            impersonator_id=str(impersonator.id),
            target_user_id=str(target.id),
            target_role=target.role,
            target_school_id=str(target.school_id) if target.school_id else None,
        )

        return ImpersonationStartResponse(
            redirect_url=f"{app_url}/impersonate?token={raw_token}",
            target_app_url=app_url,
            target_user_id=target.id,
            target_role=target.role,
            expires_in_seconds=settings.impersonation_handoff_seconds,
        )

    async def redeem_impersonation(self, raw_token: str) -> LoginResponse:
        """Exchange a handoff token for an impersonated session.

        Returns a LoginResponse whose access token carries `act` (the acting
        admin's id) and no refresh token — see LoginResponse.refresh_token for why.

        Raises InvalidTokenError if the token is malformed, expired, already used,
        or if the target is no longer impersonable.
        """
        payload = decode_token(raw_token)
        if payload.get("type") != "impersonation_handoff":
            raise InvalidTokenError("Not an impersonation token")

        token_hash = hash_token(raw_token)
        auth_token = await self.db.scalar(
            select(AuthToken).where(
                AuthToken.token_hash == token_hash,
                AuthToken.type == AuthTokenType.IMPERSONATION,
                AuthToken.used_at.is_(None),
                AuthToken.expires_at > datetime.now(UTC),
            )
        )
        if not auth_token:
            raise InvalidTokenError("Impersonation link is invalid, expired, or already used")

        # Single-use: burn it on the FIRST attempt, and commit that immediately.
        # The checks below raise InvalidTokenError, which get_db turns into a
        # rollback — so a burn that was merely flushed would be discarded and the
        # link would stay redeemable for the rest of its TTL. Committing here
        # makes consumption unconditional: one attempt, success or not, spends
        # the token. This is the only write in this method, so nothing else is
        # prematurely committed.
        auth_token.used_at = datetime.now(UTC)
        await self.db.commit()

        target = await self.db.get(User, auth_token.user_id)
        if not target:
            raise InvalidTokenError("User not found")

        # Re-check authorisation at redemption — the target could have been
        # deactivated or promoted to KAIHLE_ADMIN since the token was minted.
        if not target.is_active or target.role == UserRole.KAIHLE_ADMIN:
            raise InvalidTokenError("This user can no longer be impersonated")

        impersonator_id = payload.get("act")
        impersonator = await self.db.get(User, uuid.UUID(impersonator_id)) if impersonator_id else None
        if not impersonator or impersonator.role != UserRole.KAIHLE_ADMIN or not impersonator.is_active:
            raise InvalidTokenError("Impersonating admin is no longer authorised")

        # Deliberately does NOT set target.last_login_at — that column reflects
        # the real user's own activity and must not be polluted by support access.
        access_token = create_access_token(
            target.id,
            target.school_id,
            target.role,
            expires_in=settings.impersonation_session_minutes,
            extra_claims={"act": str(impersonator.id), "impersonated": True},
        )

        logger.info(
            "impersonation.redeemed",
            impersonator_id=str(impersonator.id),
            target_user_id=str(target.id),
            target_role=target.role,
            target_school_id=str(target.school_id) if target.school_id else None,
        )

        return LoginResponse(
            access_token=access_token,
            refresh_token=None,
            token_type="bearer",
            # Never force a password change inside an impersonated session — the
            # admin does not know the user's password and must not set one.
            must_change_password=False,
            user={
                "id": str(target.id),
                "email": target.email or "",
                "username": target.username or "",
                "first_name": target.first_name,
                "role": target.role,
                "school_id": str(target.school_id) if target.school_id else None,
                "permissions": target.permissions,
            },
            impersonator={
                "id": str(impersonator.id),
                "name": f"{impersonator.first_name} {impersonator.last_name}".strip(),
            },
        )

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

    async def _get_active_user_by_login(self, login_id: str) -> User:
        """Find an active user by email or username.

        Tries email match first, then username fallback. This avoids
        non-deterministic results when one user's email happens to match
        another user's username.
        """
        user: User | None = await self.db.scalar(
            select(User).where(
                User.email == login_id,
                User.is_active.is_(True),
            )
        )
        if user:
            return user
        user = await self.db.scalar(
            select(User).where(
                User.username == login_id,
                User.is_active.is_(True),
            )
        )
        if not user:
            raise ValueError("Invalid credentials")
        return user

    async def _get_active_user_by_email(self, email: str) -> User:
        """Find an active user by email."""
        user: User | None = await self.db.scalar(select(User).where(User.email == email))
        if not user:
            raise ValueError("Invalid credentials")
        if not user.is_active:
            raise ValueError("Account is inactive")
        return user

    async def _send_magic_link_email(self, email: str, first_name: str, token: str, base_url: str) -> None:
        """Send magic link email via EmailService."""
        verify_url = f"{base_url}/api/v1/auth/magic-link/verify?token={token}"
        email_service = EmailService()
        try:
            await email_service.send(
                to=email,
                subject="Your Kaihle login link",
                template="magic_link.html.jinja2",
                ctx={"first_name": first_name, "verify_url": verify_url},
            )
        except Exception:
            # Token is already stored — email failure should not block the flow
            pass

    async def send_password_reset_email(self, email: str) -> None:
        """Generate a password reset token and email the reset link.

        Always returns silently — never reveals whether the email exists.
        """
        user: User | None = await self.db.scalar(select(User).where(User.email == email, User.is_active.is_(True)))
        if not user:
            return

        raw_token, token_hash = generate_refresh_token()

        reset_url = f"{app_url_for_role(user.role)}/reset-password?token={raw_token}"

        # Send email before persisting the token — if email fails the token never
        # enters the DB, so the user isn't left with an unusable dead token.
        assert user.email is not None  # user was found by email
        email_service = EmailService()
        try:
            await email_service.send(
                to=user.email,
                subject="Reset your Kaihle password",
                template="password_reset.html.jinja2",
                ctx={"first_name": user.first_name, "reset_url": reset_url},
            )
        except Exception:
            logger.error(
                "failed_to_send_password_reset_email",
                user_id=str(user.id),
                exc_info=True,
            )
            return

        await store_password_reset_token(self.db, user.id, token_hash)

    async def reset_password(self, token: str, new_password: str) -> None:
        """Validate a password reset token and set the new password.

        Raises InvalidTokenError if token is invalid, expired, or already used.
        """
        token_hash = hash_token(token)
        auth_token = await self.db.scalar(
            select(AuthToken).where(
                AuthToken.token_hash == token_hash,
                AuthToken.type == AuthTokenType.PASSWORD_RESET,
                AuthToken.used_at.is_(None),
                AuthToken.expires_at > datetime.now(UTC),
            )
        )
        if not auth_token:
            raise InvalidTokenError("Password reset link is invalid or has expired")

        user = await self.db.get(User, auth_token.user_id)
        if not user:
            raise InvalidTokenError("User not found")

        auth_token.used_at = datetime.now(UTC)
        user.hashed_password = hash_password(new_password)
        user.must_change_password = False
        await self.db.flush()

        logger.info("user_password_reset", user_id=str(user.id))

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
        user.must_change_password = False
        await self.db.flush()
