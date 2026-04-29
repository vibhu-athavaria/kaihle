"""Integration tests for platform users endpoint.

Per Rule 20 (TDD): platform users endpoint has named integration tests.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.school import School
from app.models.user import User, UserRole


def make_auth_header(user: User) -> dict[str, str]:
    """Create auth header for user."""
    token = create_access_token(
        user_id=user.id,
        school_id=user.school_id,
        role=user.role,
        expires_in=3600,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_get_platform_users_route_when_kaihle_admin_then_200_with_real_data(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test that KAIHLE_ADMIN can list platform users with real data."""
    # Arrange - Create a school
    school = School(
        id=uuid.uuid4(),
        name="Test School",
        slug=f"test-{uuid.uuid4().hex[:8]}",
        status="active",
    )
    db_session.add(school)

    # Create KAIHLE_ADMIN
    admin = User(
        id=uuid.uuid4(),
        school_id=None,
        email=f"admin-{uuid.uuid4().hex[:8]}@kaihle.ai",
        first_name="Kaihle",
        last_name="Admin",
        role=UserRole.KAIHLE_ADMIN,
        is_active=True,
    )
    db_session.add(admin)

    # Create some users
    for i in range(3):
        user = User(
            id=uuid.uuid4(),
            school_id=school.id,
            email=f"user{i}@{uuid.uuid4().hex[:4]}.com",
            first_name=f"User{i}",
            last_name="Test",
            role=UserRole.TEACHER if i % 2 == 0 else UserRole.STUDENT,
            is_active=True,
        )
        db_session.add(user)

    await db_session.commit()

    headers = make_auth_header(admin)

    # Act
    response = await client.get("/api/v1/platform/users", headers=headers)

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert "users" in data
    assert "total" in data
    assert data["page"] == 1
    assert data["page_size"] == 25
    # Should have at least the 3 users we created
    assert data["total"] >= 3
    assert len(data["users"]) >= 3

    # Verify user fields
    user = data["users"][0]
    assert "id" in user
    assert "email" in user
    assert "first_name" in user
    assert "last_name" in user
    assert "role" in user
    assert "school_name" in user


@pytest.mark.asyncio
async def test_get_platform_users_route_when_teacher_then_403(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test that non-admin gets 403."""
    # Arrange
    school = School(
        id=uuid.uuid4(),
        name="Test School",
        slug=f"test-{uuid.uuid4().hex[:8]}",
        status="active",
    )
    db_session.add(school)

    teacher = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"teacher-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Test",
        last_name="Teacher",
        role=UserRole.TEACHER,
        is_active=True,
    )
    db_session.add(teacher)
    await db_session.commit()

    headers = make_auth_header(teacher)

    # Act
    response = await client.get("/api/v1/platform/users", headers=headers)

    # Assert
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_platform_users_with_q_filter(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test searching platform users."""
    # Arrange
    school = School(
        id=uuid.uuid4(),
        name="Test School",
        slug=f"test-{uuid.uuid4().hex[:8]}",
        status="active",
    )
    db_session.add(school)

    admin = User(
        id=uuid.uuid4(),
        school_id=None,
        email=f"admin-{uuid.uuid4().hex[:8]}@kaihle.ai",
        first_name="Kaihle",
        last_name="Admin",
        role=UserRole.KAIHLE_ADMIN,
        is_active=True,
    )
    db_session.add(admin)

    # Create a user with unique name
    unique_name = f"Alice{uuid.uuid4().hex[:4]}"
    user = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"{unique_name.lower()}@test.com",
        first_name=unique_name,
        last_name="Smith",
        role=UserRole.TEACHER,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    headers = make_auth_header(admin)

    # Act
    response = await client.get(
        f"/api/v1/platform/users?q={unique_name}",
        headers=headers,
    )

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    # The search should find our user
    found_emails = [u["email"] for u in data["users"]]
    assert f"{unique_name.lower()}@test.com" in found_emails


@pytest.mark.asyncio
async def test_get_platform_users_with_role_filter(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test filtering platform users by role."""
    # Arrange
    school = School(
        id=uuid.uuid4(),
        name="Test School",
        slug=f"test-{uuid.uuid4().hex[:8]}",
        status="active",
    )
    db_session.add(school)

    admin = User(
        id=uuid.uuid4(),
        school_id=None,
        email=f"admin-{uuid.uuid4().hex[:8]}@kaihle.ai",
        first_name="Kaihle",
        last_name="Admin",
        role=UserRole.KAIHLE_ADMIN,
        is_active=True,
    )
    db_session.add(admin)

    # Create teachers and students
    for i in range(2):
        teacher = User(
            id=uuid.uuid4(),
            school_id=school.id,
            email=f"teacher{i}-{uuid.uuid4().hex[:4]}@test.com",
            first_name=f"Teacher{i}",
            last_name="Test",
            role=UserRole.TEACHER,
            is_active=True,
        )
        db_session.add(teacher)

    student = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"student-{uuid.uuid4().hex[:4]}@test.com",
        first_name="Student",
        last_name="Test",
        role=UserRole.STUDENT,
        is_active=True,
    )
    db_session.add(student)
    await db_session.commit()

    headers = make_auth_header(admin)

    # Act
    response = await client.get(
        "/api/v1/platform/users?role=TEACHER",
        headers=headers,
    )

    # Assert
    assert response.status_code == 200
    data = response.json()
    # All returned users should be teachers
    for user in data["users"]:
        assert user["role"] == "TEACHER"


@pytest.mark.asyncio
async def test_get_platform_users_with_pagination(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test paginated results."""
    # Arrange
    school = School(
        id=uuid.uuid4(),
        name="Test School",
        slug=f"test-{uuid.uuid4().hex[:8]}",
        status="active",
    )
    db_session.add(school)

    admin = User(
        id=uuid.uuid4(),
        school_id=None,
        email=f"admin-{uuid.uuid4().hex[:8]}@kaihle.ai",
        first_name="Kaihle",
        last_name="Admin",
        role=UserRole.KAIHLE_ADMIN,
        is_active=True,
    )
    db_session.add(admin)

    # Create multiple users
    for i in range(5):
        user = User(
            id=uuid.uuid4(),
            school_id=school.id,
            email=f"user{i}-{uuid.uuid4().hex[:4]}@test.com",
            first_name=f"User{i}",
            last_name="Test",
            role=UserRole.STUDENT,
            is_active=True,
        )
        db_session.add(user)
    await db_session.commit()

    headers = make_auth_header(admin)

    # Act
    response = await client.get(
        "/api/v1/platform/users?page=1&page_size=2",
        headers=headers,
    )

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert len(data["users"]) <= 2
    assert data["total"] >= 5
