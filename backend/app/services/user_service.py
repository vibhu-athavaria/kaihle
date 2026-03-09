"""User management service layer."""

import secrets
import uuid

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_magic_link_token,
    hash_password,
    hash_token,
    store_magic_link_token,
)
from app.models.user import TeacherProfile, User
from app.schemas.user import UserInvite, UserUpdate

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
                qualifications={"subjects": data.subjects or []},
            )
            self.db.add(profile)
            await self.db.flush()

        # Send magic link welcome email
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
        """List active users in a school with optional role filter and pagination."""
        stmt = select(User).where(
            User.school_id == school_id,
            User.is_active.is_(True),
        )
        if role:
            stmt = stmt.where(User.role == role)

        offset = (page - 1) * page_size
        result = await self.db.execute(stmt.order_by(User.last_name, User.first_name).offset(offset).limit(page_size))
        users = result.scalars().all()

        count_stmt = select(func.count()).select_from(User).where(User.school_id == school_id, User.is_active.is_(True))
        if role:
            count_stmt = count_stmt.where(User.role == role)
        total = await self.db.scalar(count_stmt) or 0
        return list(users), total

    async def get_user(self, school_id: uuid.UUID, user_id: uuid.UUID) -> User:
        """Get a user by ID, ensuring they belong to the specified school."""
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
        """Update user information."""
        user = await self.get_user(school_id, user_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(user, field, value)
        await self.db.flush()
        return user

    async def deactivate_user(self, school_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Soft delete — sets is_active=False. User cannot log in after this."""
        user = await self.get_user(school_id, user_id)
        user.is_active = False
        await self.db.flush()

    async def _send_welcome_email(self, user: User, token: str, base_url: str) -> None:
        """Send welcome email with magic link to activate account."""
        try:
            import resend

            from app.core.config import settings

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
            # Log the error but don't fail user creation if email fails
            logger.error(
                "failed_to_send_welcome_email",
                user_id=str(user.id),
                email=user.email,
                error=str(e),
            )
