"""Integration tests for authentication API routes."""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_magic_link_token,
    generate_refresh_token,
    hash_token,
    store_magic_link_token,
    store_refresh_token,
)
from app.main import app
from app.models.school import School
from app.models.user import AuthToken, User, UserRole

# Set test JWT secret
settings.jwt_secret_key = "test-secret-key-for-testing"


@pytest_asyncio.fixture
async def school(db_session: AsyncSession) -> School:
    """Create a test school."""
    school = School(
        id=uuid.uuid4(),
        name="Test School",
        slug=f"test-school-{uuid.uuid4().hex[:8]}",
        status="active",
    )
    db_session.add(school)
    await db_session.commit()
    return school


@pytest_asyncio.fixture
async def user(db_session: AsyncSession, school: School) -> User:
    """Create a test user with password."""
    from app.core.security import hash_password

    user = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"test-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=hash_password("correct-password"),
        first_name="Test",
        last_name="User",
        role=UserRole.TEACHER,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client."""
    from app.core.database import get_db

    # Override the get_db dependency
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# =============================================================================
# Register Tests
# =============================================================================


@pytest.mark.asyncio
async def test_register_creates_user_returns_user_id_email_role(client: AsyncClient, school: School) -> None:
    """Test that POST /auth/register creates user and returns user_id, email, role."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"newuser-{uuid.uuid4().hex[:8]}@example.com",
            "password": "SecurePass123!",
            "role": "TEACHER",
            "school_id": str(school.id),
            "first_name": "New",
            "last_name": "User",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert "user_id" in data
    assert "email" in data
    assert "role" in data
    assert data["role"] == "TEACHER"


@pytest.mark.asyncio
async def test_register_duplicate_email_returns_409(client: AsyncClient, user: User) -> None:
    """Test that registering with duplicate email returns 409."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": user.email,
            "password": "SecurePass123!",
            "role": "TEACHER",
            "school_id": str(user.school_id),
            "first_name": "Duplicate",
            "last_name": "User",
        },
    )

    assert response.status_code == 409


# =============================================================================
# Login Tests
# =============================================================================


@pytest.mark.asyncio
async def test_login_correct_credentials_returns_valid_jwt(client: AsyncClient, user: User) -> None:
    """Test that login with correct credentials returns valid JWT."""
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": user.email,
            "password": "correct-password",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert "user" in data

    # Verify JWT contains expected claims
    from app.core.security import decode_token

    payload = decode_token(data["access_token"])
    assert payload["sub"] == str(user.id)
    assert payload["role"] == user.role


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(client: AsyncClient, user: User) -> None:
    """Test that login with wrong password returns 401."""
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": user.email,
            "password": "wrong-password",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


@pytest.mark.asyncio
async def test_login_nonexistent_email_returns_401(client: AsyncClient) -> None:
    """Test that login with nonexistent email returns 401."""
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "nonexistent@example.com",
            "password": "any-password",
        },
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_inactive_user_returns_401(db_session: AsyncSession, client: AsyncClient, school: School) -> None:
    """Test that login with inactive user returns 401."""
    from app.core.security import hash_password

    inactive_user = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"inactive-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=hash_password("password"),
        first_name="Inactive",
        last_name="User",
        role=UserRole.TEACHER,
        is_active=False,
    )
    db_session.add(inactive_user)
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": inactive_user.email,
            "password": "password",
        },
    )

    assert response.status_code == 401


# =============================================================================
# Magic Link Tests
# =============================================================================


@pytest.mark.asyncio
async def test_magic_link_full_flow_send_verify_returns_jwt(
    client: AsyncClient, user: User, db_session: AsyncSession
) -> None:
    """Test full magic link flow - send → verify → returns JWT."""
    # Directly create and store a magic link token (bypassing email sending)
    magic_link_jwt = create_magic_link_token(user.id)
    token_hash = hash_token(magic_link_jwt)
    await store_magic_link_token(db_session, user.id, token_hash)

    # Verify magic link
    response = await client.get(
        "/api/v1/auth/magic-link/verify",
        params={"token": magic_link_jwt},
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["user"]["email"] == user.email


@pytest.mark.asyncio
async def test_magic_link_expired_returns_401(client: AsyncClient, user: User, db_session: AsyncSession) -> None:
    """Test that expired magic link returns 401."""
    # Create an expired magic link token in the database
    token = create_magic_link_token(user.id, expires_in_minutes=-1)  # Already expired
    token_hash = hash_token(token)

    auth_token = AuthToken(
        user_id=user.id,
        token_hash=token_hash,
        type="MAGIC_LINK",
        expires_at=datetime.now(UTC) - timedelta(minutes=1),  # Already expired
    )
    db_session.add(auth_token)
    await db_session.commit()

    response = await client.get(
        "/api/v1/auth/magic-link/verify",
        params={"token": token},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_magic_link_used_twice_returns_401(client: AsyncClient, user: User, db_session: AsyncSession) -> None:
    """Test that using magic link twice returns 401."""
    # Create and use a magic link token
    token = create_magic_link_token(user.id)
    token_hash = hash_token(token)

    auth_token = AuthToken(
        user_id=user.id,
        token_hash=token_hash,
        type="MAGIC_LINK",
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
        used_at=datetime.now(UTC),  # Already used
    )
    db_session.add(auth_token)
    await db_session.commit()

    response = await client.get(
        "/api/v1/auth/magic-link/verify",
        params={"token": token},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_magic_link_invalid_token_returns_401(client: AsyncClient) -> None:
    """Test that invalid magic link token returns 401."""
    response = await client.get(
        "/api/v1/auth/magic-link/verify",
        params={"token": "invalid-token"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_magic_link_nonexistent_email_returns_success(client: AsyncClient) -> None:
    """Test that requesting magic link for nonexistent email returns success (security)."""
    response = await client.post(
        "/api/v1/auth/magic-link",
        json={"email": "nonexistent@example.com"},
    )

    assert response.status_code == 200
    assert "login link has been sent" in response.json()["message"]


# =============================================================================
# Refresh Token Tests
# =============================================================================


@pytest.mark.asyncio
async def test_refresh_with_valid_token_returns_new_access_token(
    client: AsyncClient, user: User, db_session: AsyncSession
) -> None:
    """Test that refresh with valid token returns new access token."""
    # Create a valid refresh token
    raw_refresh, hashed_refresh = generate_refresh_token()
    await store_refresh_token(db_session, user.id, hashed_refresh)

    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": raw_refresh},
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data

    # Verify the new token is valid
    from app.core.security import decode_token

    payload = decode_token(data["access_token"])
    assert payload["sub"] == str(user.id)


@pytest.mark.asyncio
async def test_refresh_with_expired_token_returns_401(
    client: AsyncClient, user: User, db_session: AsyncSession
) -> None:
    """Test that refresh with expired token returns 401."""
    # Create an expired refresh token
    raw_refresh, hashed_refresh = generate_refresh_token()
    auth_token = AuthToken(
        user_id=user.id,
        token_hash=hashed_refresh,
        type="REFRESH",
        expires_at=datetime.now(UTC) - timedelta(days=1),  # Already expired
    )
    db_session.add(auth_token)
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": raw_refresh},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_with_used_token_returns_401(client: AsyncClient, user: User, db_session: AsyncSession) -> None:
    """Test that refresh with used token returns 401."""
    # Create a used refresh token
    raw_refresh, hashed_refresh = generate_refresh_token()
    auth_token = AuthToken(
        user_id=user.id,
        token_hash=hashed_refresh,
        type="REFRESH",
        expires_at=datetime.now(UTC) + timedelta(days=7),
        used_at=datetime.now(UTC),  # Already used
    )
    db_session.add(auth_token)
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": raw_refresh},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_with_invalid_token_returns_401(client: AsyncClient) -> None:
    """Test that refresh with invalid token returns 401."""
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "invalid-token"},
    )

    assert response.status_code == 401


# =============================================================================
# Logout Tests
# =============================================================================


@pytest.mark.asyncio
async def test_logout_marks_token_as_used(client: AsyncClient, user: User, db_session: AsyncSession) -> None:
    """Test that logout marks refresh token as used."""
    # Create a valid refresh token
    raw_refresh, hashed_refresh = generate_refresh_token()
    await store_refresh_token(db_session, user.id, hashed_refresh)

    # Logout
    response = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": raw_refresh},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Logged out"

    # Verify token is now marked as used
    token_record = await db_session.scalar(select(AuthToken).where(AuthToken.token_hash == hashed_refresh))
    assert token_record is not None
    assert token_record.used_at is not None

    # Verify token can no longer be used for refresh
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": raw_refresh},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_logout_invalid_token_still_returns_200(client: AsyncClient) -> None:
    """Test that logout with invalid token still returns 200 (idempotent)."""
    response = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": "invalid-token"},
    )

    assert response.status_code == 200


# =============================================================================
# Security Tests
# =============================================================================


@pytest.mark.asyncio
async def test_sql_injection_in_email_returns_422(client: AsyncClient, school: School) -> None:
    """Test that SQL injection in email field returns 422 (Pydantic rejects)."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "test' OR '1'='1@example.com",
            "password": "SecurePass123!",
            "role": "TEACHER",
            "school_id": str(school.id),
            "first_name": "Test",
            "last_name": "User",
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_with_sql_injection_email_returns_401(client: AsyncClient) -> None:
    """Test that SQL injection in login email returns 401 or 422.

    Note: Pydantic's EmailStr validation may catch this at the validation layer (422),
    which is even better security than reaching the database (401).
    """
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "' OR '1'='1@example.com",
            "password": "anything",
        },
    )

    # Either 401 (reaches DB) or 422 (Pydantic catches it) is acceptable
    assert response.status_code in [401, 422]
