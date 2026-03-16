"""Integration tests for authentication API endpoints.

Tests cover registration (POST /api/v1/auth/register) and login (POST /api/v1/auth/login).
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.school import School
from app.models.user import User, UserRole

# =============================================================================
# Registration Tests - Happy Path
# =============================================================================


@pytest.mark.asyncio
async def test_register_valid_email_password_role_student_school_returns_201(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """REG-01: Register with valid email, password, role=STUDENT, valid school_id."""
    school = School(
        id=uuid.uuid4(),
        name="Test School",
        slug=f"test-school-{uuid.uuid4().hex[:8]}",
        status="active",
    )
    db_session.add(school)
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"student-{uuid.uuid4().hex[:8]}@example.com",
            "password": "SecurePass123!",
            "role": "STUDENT",
            "school_id": str(school.id),
            "first_name": "John",
            "last_name": "Doe",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert "user_id" in data
    assert "email" in data
    assert data["role"] == "STUDENT"


@pytest.mark.asyncio
async def test_register_student_with_first_name_last_name_returns_201(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """REG-02: Register student with first_name, last_name."""
    school = School(
        id=uuid.uuid4(),
        name="Test School",
        slug=f"test-school-{uuid.uuid4().hex[:8]}",
        status="active",
    )
    db_session.add(school)
    await db_session.commit()

    email = f"student-{uuid.uuid4().hex[:8]}@example.com"
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "SecurePass123!",
            "role": "STUDENT",
            "school_id": str(school.id),
            "first_name": "John",
            "last_name": "Doe",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert "user_id" in data
    assert data["email"] == email


@pytest.mark.asyncio
async def test_register_multiple_students_same_school_returns_201_each(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """REG-03: Register multiple students to same school."""
    school = School(
        id=uuid.uuid4(),
        name="Test School",
        slug=f"test-school-{uuid.uuid4().hex[:8]}",
        status="active",
    )
    db_session.add(school)
    await db_session.commit()

    for i in range(3):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": f"student{i}-{uuid.uuid4().hex[:8]}@example.com",
                "password": "SecurePass123!",
                "role": "STUDENT",
                "school_id": str(school.id),
                "first_name": f"Student{i}",
                "last_name": "Test",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["role"] == "STUDENT"


# =============================================================================
# Registration Tests - Bad Behavior
# =============================================================================


@pytest.mark.asyncio
async def test_register_duplicate_email_returns_409(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """REG-04: Duplicate email returns 409 Conflict."""
    school = School(
        id=uuid.uuid4(),
        name="Test School",
        slug=f"test-school-{uuid.uuid4().hex[:8]}",
        status="active",
    )
    db_session.add(school)
    await db_session.commit()

    email = f"duplicate-{uuid.uuid4().hex[:8]}@example.com"

    response1 = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "SecurePass123!",
            "role": "STUDENT",
            "school_id": str(school.id),
            "first_name": "John",
            "last_name": "Doe",
        },
    )
    assert response1.status_code == 201

    response2 = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "SecurePass123!",
            "role": "STUDENT",
            "school_id": str(school.id),
            "first_name": "John",
            "last_name": "Doe",
        },
    )
    assert response2.status_code == 409


@pytest.mark.asyncio
async def test_register_invalid_email_format_returns_422(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """REG-05: Invalid email format returns 422."""
    school = School(
        id=uuid.uuid4(),
        name="Test School",
        slug=f"test-school-{uuid.uuid4().hex[:8]}",
        status="active",
    )
    db_session.add(school)
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "not-an-email",
            "password": "SecurePass123!",
            "role": "STUDENT",
            "school_id": str(school.id),
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_weak_password_returns_422(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """REG-06: Weak password (<8 chars) returns 422."""
    school = School(
        id=uuid.uuid4(),
        name="Test School",
        slug=f"test-school-{uuid.uuid4().hex[:8]}",
        status="active",
    )
    db_session.add(school)
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"student-{uuid.uuid4().hex[:8]}@example.com",
            "password": "short",
            "role": "STUDENT",
            "school_id": str(school.id),
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_missing_required_fields_returns_422(
    client: AsyncClient,
) -> None:
    """REG-07: Missing required fields returns 422."""
    response = await client.post(
        "/api/v1/auth/register",
        json={},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_invalid_role_returns_422(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """REG-08: Invalid role returns 422."""
    school = School(
        id=uuid.uuid4(),
        name="Test School",
        slug=f"test-school-{uuid.uuid4().hex[:8]}",
        status="active",
    )
    db_session.add(school)
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"student-{uuid.uuid4().hex[:8]}@example.com",
            "password": "SecurePass123!",
            "role": "INVALID_ROLE",
            "school_id": str(school.id),
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_nonexistent_school_id_returns_404(
    client: AsyncClient,
) -> None:
    """REG-09: Non-existent school_id returns 404."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"student-{uuid.uuid4().hex[:8]}@example.com",
            "password": "SecurePass123!",
            "role": "STUDENT",
            "school_id": str(uuid.uuid4()),
            "first_name": "John",
            "last_name": "Doe",
        },
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_register_student_without_school_id_returns_422(
    client: AsyncClient,
) -> None:
    """REG-10: STUDENT without school_id returns 422."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"student-{uuid.uuid4().hex[:8]}@example.com",
            "password": "SecurePass123!",
            "role": "STUDENT",
        },
    )

    assert response.status_code == 422


# =============================================================================
# Login Tests - Happy Path
# =============================================================================


@pytest.mark.asyncio
async def test_login_valid_credentials_returns_200_with_tokens(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """LOGIN-01: Valid credentials returns 200 with tokens."""
    from app.core.security import hash_password

    school = School(
        id=uuid.uuid4(),
        name="Test School",
        slug=f"test-school-{uuid.uuid4().hex[:8]}",
        status="active",
    )
    db_session.add(school)
    await db_session.commit()

    email = f"login-{uuid.uuid4().hex[:8]}@example.com"
    password = "SecurePass123!"

    user = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=email,
        hashed_password=hash_password(password),
        first_name="Test",
        last_name="User",
        role=UserRole.STUDENT,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": password,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_after_registration_returns_200(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """LOGIN-02: Login after registration returns 200."""
    school = School(
        id=uuid.uuid4(),
        name="Test School",
        slug=f"test-school-{uuid.uuid4().hex[:8]}",
        status="active",
    )
    db_session.add(school)
    await db_session.commit()

    email = f"reg-login-{uuid.uuid4().hex[:8]}@example.com"
    password = "SecurePass123!"

    register_response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "role": "STUDENT",
            "school_id": str(school.id),
            "first_name": "John",
            "last_name": "Doe",
        },
    )
    assert register_response.status_code == 201
    user_id = register_response.json()["user_id"]

    user = await db_session.get(User, user_id)
    assert user is not None
    user.is_active = True
    await db_session.commit()

    login_response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": password,
        },
    )
    assert login_response.status_code == 200
    data = login_response.json()
    assert "access_token" in data
    assert "refresh_token" in data


# =============================================================================
# Login Tests - Bad Behavior
# =============================================================================


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """LOGIN-03: Wrong password returns 401."""
    from app.core.security import hash_password

    school = School(
        id=uuid.uuid4(),
        name="Test School",
        slug=f"test-school-{uuid.uuid4().hex[:8]}",
        status="active",
    )
    db_session.add(school)
    await db_session.commit()

    email = f"wrongpass-{uuid.uuid4().hex[:8]}@example.com"

    user = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=email,
        hashed_password=hash_password("correct-password"),
        first_name="Test",
        last_name="User",
        role=UserRole.STUDENT,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "wrong-password",
        },
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_email_returns_401(
    client: AsyncClient,
) -> None:
    """LOGIN-04: Non-existent email returns 401."""
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "nonexistent@example.com",
            "password": "any-password",
        },
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_empty_email_returns_422(
    client: AsyncClient,
) -> None:
    """LOGIN-05: Empty email returns 422."""
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "",
            "password": "password123",
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_empty_password_returns_401(
    client: AsyncClient,
) -> None:
    """LOGIN-06: Empty password returns 401."""
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "test@example.com",
            "password": "",
        },
    )

    assert response.status_code == 401
