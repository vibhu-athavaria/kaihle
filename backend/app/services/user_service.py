"""User management service layer."""

import secrets
import uuid

import resend
import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_magic_link_token,
    hash_password,
    hash_token,
    store_magic_link_token,
)
from app.models.user import TeacherProfile, User, UserRole
from app.schemas.user import UserInvite, UserSelfUpdate, UserUpdate

logger = structlog.get_logger()


class UserService:
    """Service for managing users within a school."""

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
        allowed_roles = {UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.PARENT}
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
        if data.role == UserRole.TEACHER:
            profile = TeacherProfile(
                user_id=user.id,
                qualifications={"subjects": data.subjects or []},
            )
            self.db.add(profile)
            await self.db.flush()

        # Send magic link welcome email
        token = create_magic_link_token(user.id, expires_in_minutes=72 * 60)  # 72-hour welcome link
        token_hash = hash_token(token)
        await store_magic_link_token(self.db, user.id, token_hash, expires_minutes=72 * 60)

        logger.info(
            "user_invited",
            user_id=str(user.id),
            school_id=str(school_id),
            role=user.role,
            email=user.email,
        )

        await self._send_welcome_email(user, token, base_url)

        return user

    async def list_users(
        self,
        school_id: uuid.UUID,
        role: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[User], int]:
        """List active users in a school with optional role filter and pagination."""
        stmt = select(User).where(
            User.school_id == school_id,
            User.is_active.is_(True),
        )
        if role:
            # Convert to string for type-safe comparison with User.role column
            stmt = stmt.where(User.role == role)

        offset = (page - 1) * page_size
        result = await self.db.execute(stmt.order_by(User.last_name, User.first_name).offset(offset).limit(page_size))
        users = result.scalars().all()

        count_stmt = select(func.count()).select_from(User).where(User.school_id == school_id, User.is_active.is_(True))
        if role:
            count_stmt = count_stmt.where(User.role == role)
        total = await self.db.scalar(count_stmt) or 0
        return list(users), total

    async def get_user(self, user_id: uuid.UUID, school_id: uuid.UUID | None = None) -> User:
        """Get a user by ID, ensuring they belong to the specified school."""
        # Fetch user with both user_id and school_id in single query
        stmt = select(User).where(User.id == user_id)
        if school_id is not None:
            stmt = stmt.where(User.school_id == school_id)

        user = await self.db.scalar(stmt)
        if not user:
            raise ValueError("User not found")
        return user

    async def update_user(
        self,
        school_id: uuid.UUID,
        user_id: uuid.UUID,
        data: UserUpdate,
    ) -> User:
        """Update user information."""
        user = await self.get_user(user_id, school_id)
        previous_state = {"first_name": user.first_name, "last_name": user.last_name, "is_active": user.is_active}

        # Extract password separately - don't let it pass through the generic loop
        update_data = data.model_dump(exclude_unset=True)
        new_password = update_data.pop("password", None)

        for field, value in update_data.items():
            setattr(user, field, value)

        # Handle password update - hash and store separately
        if new_password is not None:
            user.hashed_password = hash_password(new_password)

        await self.db.flush()

        logger.info(
            "user_updated",
            user_id=str(user.id),
            school_id=str(school_id),
            previous_state=previous_state,
            new_state={"first_name": user.first_name, "last_name": user.last_name, "is_active": user.is_active},
            password_changed=new_password is not None,
        )

        return user

    async def deactivate_user(self, school_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Soft delete — sets is_active=False. User cannot log in after this."""
        user = await self.get_user(user_id, school_id)
        previous_state = user.is_active
        user.is_active = False
        await self.db.flush()

        logger.info(
            "user_deactivated",
            user_id=str(user.id),
            school_id=str(school_id),
            previous_state=previous_state,
            new_state=False,
        )

    async def _send_welcome_email(self, user: User, token: str, base_url: str) -> None:
        """Send welcome email with magic link to activate account."""
        try:
            resend.api_key = settings.resend_api_key
            verify_url = f"{base_url}/api/v1/auth/magic-link/verify?token={token}"
            resend.Emails.send(
                {
                    "from": settings.from_email,
                    "to": user.email,
                    "subject": "Welcome to Kaihle — activate your account",
                    "html": f"""
                        <p>Hi {user.first_name},</p>
                        <p>You've been invited to Kaihle. Click the link below to set up your account.</p>
                        <p>This link is valid for 72 hours.</p>
                        <p><a href="{verify_url}">Activate my account</a></p>
                    """,
                }
            )
        except Exception as e:
            # Log the error with full details - never silently fail
            logger.error(
                "failed_to_send_welcome_email",
                user_id=str(user.id),
                email=user.email,
                error_type=type(e).__name__,
                error_message=str(e),
            )

    async def get_me(self, user_id: uuid.UUID) -> User:
        """Get the current user's own record."""
        user = await self.db.get(User, user_id)
        if not user:
            raise ValueError("User not found")
        return user

    async def update_me(self, user_id: uuid.UUID, data: UserSelfUpdate) -> User:
        """Update the current user's own first_name and/or last_name.

        Email, role, and school_id are NOT updatable here — never touch them.
        """
        user = await self.db.get(User, user_id)
        if not user:
            raise ValueError("User not found")
        if data.first_name is not None:
            user.first_name = data.first_name
        if data.last_name is not None:
            user.last_name = data.last_name
        # email, role, school_id are NOT updatable here — never touch them
        await self.db.flush()
        return user
