"""Security utilities for authentication: password hashing, JWT, and refresh tokens."""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import AuthToken

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ---------------------------------------------------------------------------
# Password utilities
# ---------------------------------------------------------------------------

# Bcrypt has a 72-byte limit - truncate passwords to be safe
MAX_PASSWORD_LENGTH = 72


def _normalize_password(plain: str) -> str:
    """Normalize password for bcrypt (truncate if too long)."""
    if len(plain.encode("utf-8")) > MAX_PASSWORD_LENGTH:
        return plain[:MAX_PASSWORD_LENGTH]
    return plain


def hash_password(plain: str) -> str:
    """Hash a plain-text password using bcrypt."""
    normalized = _normalize_password(plain)
    result: str = pwd_context.hash(normalized)
    return result


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if plain matches hashed."""
    normalized = _normalize_password(plain)
    result: bool = pwd_context.verify(normalized, hashed)
    return result


# ---------------------------------------------------------------------------
# JWT utilities
# ---------------------------------------------------------------------------


class InvalidTokenError(Exception):
    """Raised when a JWT cannot be decoded or has been tampered with."""

    pass


def create_access_token(
    user_id: uuid.UUID,
    school_id: uuid.UUID | None,
    role: str,
    expires_in: int = settings.access_token_expire_minutes,
) -> str:
    """
    Create a short-lived access JWT.

    Payload includes:
      sub       — user_id (string)
      school_id — school_id (string) or None for KaihleAdmin
      role      — user role string
      exp       — expiry timestamp
      iat       — issued-at timestamp
      type      — "access"
    """
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "school_id": str(school_id) if school_id else None,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=expires_in),
        "type": "access",
    }
    result: str = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return result


def create_magic_link_token(
    user_id: uuid.UUID,
    expires_in_minutes: int = 10,
) -> str:
    """
    Create a one-time magic link JWT with scope: password_setup.

    This token grants ONLY the ability to call POST /api/v1/auth/set-password.
    All other protected endpoints must reject tokens with this scope.

    Stored as a hash in auth_tokens table.
    """
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "scope": "password_setup",
        "iat": now,
        "exp": now + timedelta(minutes=expires_in_minutes),
        "type": "magic_link",
    }
    result: str = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return result


def get_token_scope(payload: dict[str, Any]) -> str | None:
    """Return the scope claim from a decoded JWT payload, or None if absent."""
    return payload.get("scope")


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT.
    Raises InvalidTokenError on any failure (expired, tampered, malformed).
    """
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except JWTError as e:
        raise InvalidTokenError(f"Token validation failed: {e}") from e


# ---------------------------------------------------------------------------
# Refresh token utilities
# ---------------------------------------------------------------------------


def generate_refresh_token() -> tuple[str, str]:
    """
    Generate a cryptographically secure refresh token.
    Returns (raw_token, hashed_token).
    raw_token  — returned to client, never stored
    hashed_token — stored in auth_tokens table
    """
    raw = secrets.token_urlsafe(64)
    hashed = hashlib.sha256(raw.encode()).hexdigest()
    return raw, hashed


def hash_token(raw: str) -> str:
    """Hash a raw token for storage comparison."""
    return hashlib.sha256(raw.encode()).hexdigest()


async def store_refresh_token(
    db: AsyncSession,
    user_id: uuid.UUID,
    token_hash: str,
    expires_days: int = settings.refresh_token_expire_days,
) -> AuthToken:
    """Store a refresh token hash in auth_tokens table."""
    expires_at = datetime.now(UTC) + timedelta(days=expires_days)
    auth_token = AuthToken(
        user_id=user_id,
        token_hash=token_hash,
        type="REFRESH",
        expires_at=expires_at,
        used_at=None,
    )
    db.add(auth_token)
    await db.flush()
    return auth_token


async def store_magic_link_token(
    db: AsyncSession,
    user_id: uuid.UUID,
    token_hash: str,
    expires_minutes: int = 10,
) -> AuthToken:
    """Store a magic link token hash in auth_tokens table."""
    expires_at = datetime.now(UTC) + timedelta(minutes=expires_minutes)
    auth_token = AuthToken(
        user_id=user_id,
        token_hash=token_hash,
        type="MAGIC_LINK",
        expires_at=expires_at,
        used_at=None,
    )
    db.add(auth_token)
    await db.flush()
    return auth_token
