"""Security utilities: JWT, password hashing, token management."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
from jose import jwt
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings


class TokenPayload(BaseModel):
    """JWT token payload."""

    sub: str  # user_id
    exp: int
    type: str  # access, refresh, magic_link


class InvalidTokenError(Exception):
    """Raised when token is invalid or expired."""

    pass


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_access_token(user_id: uuid.UUID, school_id: uuid.UUID | None, role: str) -> str:
    """Create a JWT access token."""
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "school_id": str(school_id) if school_id else None,
        "role": role,
        "type": "access",
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
        "iat": now,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)  # type: ignore[no-any-return]


def generate_refresh_token() -> tuple[str, str]:
    """Generate a raw refresh token and its hash."""
    raw = uuid.uuid4().hex + uuid.uuid4().hex
    hashed = hash_token(raw)
    return raw, hashed


def create_magic_link_token(user_id: uuid.UUID) -> str:
    """Create a magic link token."""
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "type": "magic_link",
        "exp": now + timedelta(minutes=10),
        "iat": now,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)  # type: ignore[no-any-return]


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return payload  # type: ignore[no-any-return]
    except jwt.ExpiredSignatureError:
        raise InvalidTokenError("Token has expired")
    except jwt.InvalidTokenError:
        raise InvalidTokenError("Invalid token")


def hash_token(token: str) -> str:
    """Hash a token for storage."""
    return bcrypt.hashpw(token.encode(), bcrypt.gensalt()).decode()


async def store_refresh_token(db: AsyncSession, user_id: uuid.UUID, hashed_token: str) -> None:
    """Store a refresh token in the database."""
    from app.models.user import AuthToken

    expires_at = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)
    auth_token = AuthToken(
        user_id=user_id,
        token_hash=hashed_token,
        type="REFRESH",
        expires_at=expires_at,
    )
    db.add(auth_token)
    await db.flush()


async def store_magic_link_token(db: AsyncSession, user_id: uuid.UUID, hashed_token: str) -> None:
    """Store a magic link token in the database."""
    from app.models.user import AuthToken

    expires_at = datetime.now(UTC) + timedelta(minutes=10)
    auth_token = AuthToken(
        user_id=user_id,
        token_hash=hashed_token,
        type="MAGIC_LINK",
        expires_at=expires_at,
    )
    db.add(auth_token)
    await db.flush()
