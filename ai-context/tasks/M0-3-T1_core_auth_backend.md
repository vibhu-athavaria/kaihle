# M0-3-T1 — Core Auth Backend (JWT & Password Utilities)
**Milestone:** M0 — Foundations
**Epic:** M0-3 — Authentication System
**Task ID:** M0-3-T1
**Mode:** Code (MiniMax)
**Estimated effort:** 2–3 hours

---

## Context

This task implements the low-level security utilities used by all authentication flows: password hashing/verification, JWT creation/decoding, and refresh token management. These utilities are called by M0-3-T2 (auth routes) — they contain no HTTP logic themselves.

**Depends on:** M0-2-T2 (ORM models, specifically `AuthToken`)

---

## User Story

As any user, I want my password stored securely and my session managed via short-lived JWTs with refresh token support.

---

## What To Build

### `/backend/app/core/security.py`

```python
import uuid
from datetime import datetime, timedelta, timezone
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

def hash_password(plain: str) -> str:
    """Hash a plain-text password using bcrypt."""
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if plain matches hashed."""
    return pwd_context.verify(plain, hashed)


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
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "school_id": str(school_id) if school_id else None,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=expires_in),
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret_key,
                      algorithm=settings.jwt_algorithm)


def create_magic_link_token(
    user_id: uuid.UUID,
    expires_in_minutes: int = 10,
) -> str:
    """
    Create a one-time magic link JWT (10-minute expiry).
    Stored as a hash in auth_tokens table.
    """
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=expires_in_minutes),
        "type": "magic_link",
    }
    return jwt.encode(payload, settings.jwt_secret_key,
                      algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT.
    Raises InvalidTokenError on any failure (expired, tampered, malformed).
    """
    try:
        payload = jwt.decode(
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

import hashlib
import secrets


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
    from datetime import timezone
    expires_at = datetime.now(timezone.utc) + timedelta(days=expires_days)
    auth_token = AuthToken(
        user_id=user_id,
        token_hash=token_hash,
        token_type="REFRESH",
        expires_at=expires_at,
        is_used=False,
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
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    auth_token = AuthToken(
        user_id=user_id,
        token_hash=token_hash,
        token_type="MAGIC_LINK",
        expires_at=expires_at,
        is_used=False,
    )
    db.add(auth_token)
    await db.flush()
    return auth_token
```

---

## Files To Create

```
/backend/app/core/security.py
```

---

## Tests To Write

**`/backend/app/tests/unit/test_security.py`:**

```python
import time
import uuid
from datetime import timedelta

import pytest

from app.core.security import (
    InvalidTokenError,
    create_access_token,
    decode_token,
    generate_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)


def test_hash_password_and_verify_password_round_trip():
    plain = "MySecurePassword123!"
    hashed = hash_password(plain)
    assert hashed != plain
    assert verify_password(plain, hashed) is True


def test_verify_password_when_wrong_password_then_returns_false():
    hashed = hash_password("correct-password")
    assert verify_password("wrong-password", hashed) is False


def test_create_access_token_when_decoded_then_contains_required_claims():
    user_id = uuid.uuid4()
    school_id = uuid.uuid4()
    token = create_access_token(user_id, school_id, "STUDENT")
    payload = decode_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["school_id"] == str(school_id)
    assert payload["role"] == "STUDENT"
    assert "exp" in payload
    assert "iat" in payload


def test_create_access_token_when_kaihle_admin_then_school_id_is_none():
    user_id = uuid.uuid4()
    token = create_access_token(user_id, None, "KAIHLE_ADMIN")
    payload = decode_token(token)
    assert payload["school_id"] is None


def test_decode_token_when_expired_then_raises_invalid_token_error():
    user_id = uuid.uuid4()
    # Create token that expired 1 minute ago
    token = create_access_token(user_id, None, "STUDENT", expires_in=-1)
    with pytest.raises(InvalidTokenError):
        decode_token(token)


def test_decode_token_when_tampered_signature_then_raises_invalid_token_error():
    user_id = uuid.uuid4()
    token = create_access_token(user_id, uuid.uuid4(), "STUDENT")
    tampered = token[:-5] + "XXXXX"
    with pytest.raises(InvalidTokenError):
        decode_token(tampered)


def test_generate_refresh_token_returns_raw_and_hash():
    raw, hashed = generate_refresh_token()
    assert len(raw) > 32
    assert hashed == hash_token(raw)
    assert raw != hashed


def test_generate_refresh_token_each_call_produces_unique_tokens():
    raw1, _ = generate_refresh_token()
    raw2, _ = generate_refresh_token()
    assert raw1 != raw2
```

---

## Acceptance Criteria

- [ ] `hash_password` + `verify_password` round-trip passes for any input
- [ ] `verify_password` returns `False` for wrong passwords
- [ ] `create_access_token` output contains `sub`, `school_id`, `role`, `exp`, `iat`
- [ ] `decode_token` on an expired token raises `InvalidTokenError`
- [ ] `decode_token` on a tampered token raises `InvalidTokenError`
- [ ] `generate_refresh_token` returns different values on each call
- [ ] All unit tests pass with `pytest`
- [ ] `mypy app/core/security.py` passes with zero errors

---

## Dependencies

- M0-2-T2 — `AuthToken` model must exist for `store_refresh_token`
- M0-1-T1 — `python-jose`, `passlib[bcrypt]` in `pyproject.toml`

## Output (What Next Tasks Can Use)

- `hash_password()`, `verify_password()` — used by M0-3-T2 (login route)
- `create_access_token()` — used by M0-3-T2 on successful login
- `create_magic_link_token()` — used by M0-3-T2 magic link route
- `decode_token()` — used by M0-3-T3 (middleware)
- `generate_refresh_token()`, `store_refresh_token()` — used by M0-3-T2
- `InvalidTokenError` — caught by M0-3-T3 middleware to return 401
