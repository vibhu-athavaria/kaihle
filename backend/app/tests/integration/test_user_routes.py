"""Integration tests for user management API routes."""

import uuid
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token
from app.main import app
from app.models.school import School
from app.models.user import TeacherProfile, User, UserRole


# Set test JWT secret
settings.jwt_secret_key = "test-secret-key-for-testing"


@pytest_asyncio.fixture
async def school(db_session: AsyncSession) -> School:
    """Create a test school."""
    school_obj = School(
        id=uuid.uuid4(),
        name="Test School",
        slug=f"test-school-{uuid.uuid4().hex[:8]}",
        status="active",
    )
    db_session.add(school_obj)
    await db_session.commit()
    return school_obj


@pytest_asyncio.fixture
async def other_school(db_session: AsyncSession) -> School:
    """Create another school for cross-school access tests."""
    school_obj = School(
        id=uuid.uuid4(),
        name="Other School",
        slug=f"other-school-{uuid.uuid4().hex[:8]}",
        status="active",
    )
    db_session.add(school_obj)
    await db_session.commit()
    return school_obj


@pytest_asyncio.fixture
async def school_admin(db_session: AsyncSession, school: School) -> User:
    """Create a SchoolAdmin user."""
    user = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"school-admin-{uuid.uuid4().hex[:8]}@example.com",
        first_name="School",
        last_name="Admin",
        role=UserRole.SCHOOL_ADMIN,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def teacher(db_session: AsyncSession, school: School) -> User:
    """Create a Teacher user in the school."""
    user = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"teacher-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Test",
        last_name="Teacher",
        role=UserRole.TEACHER,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def kaihle_admin(db_session: AsyncSession) -> User:
    """Create a KaihleAdmin user."""
    # KaihleAdmin doesn't need a school
    user = User(
        id=uuid.uuid4(),
        school_id=uuid.uuid4(),  # Dummy school_id
        email=f"kaihle-admin-{uuid.uuid4().hex[:8]}@kaihle.com",
        first_name="Kaihle",
        last_name="Admin",
        role=UserRole.KAIHLE_ADMIN,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def other_school_admin(db_session: AsyncSession, other_school: School) -> User:
    """Create a SchoolAdmin user in the other school."""
    user = User(
        id=uuid.uuid4(),
        school_id=other_school.id,
        email=f"other-admin-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Other",
        last_name="Admin",
        role=UserRole.SCHOOL_ADMIN,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client with database override."""
    from app.core.database import get_db

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


def auth_header(user: User) -> dict[str, str]:
    """Generate Authorization header with valid JWT token."""
    token = create_access_token(
        user_id=user.id,
        school_id=user.school_id,
        role=user.role,
    )
    return {"Authorization": f"Bearer {token}"}


class TestInviteUser:
    """Tests for POST /api/v1/schools/{school_id}/users"""

    @pytest.mark.asyncio
    async def test_invite_user_when_school_admin_then_creates_user(
        self, client: AsyncClient, db_session: AsyncSession, school_admin: User, school: School
    ) -> None:
        """Test that SchoolAdmin can invite a teacher."""
        # Arrange
        headers = auth_header(school_admin)
        payload = {
            "email": f"newteacher-{uuid.uuid4().hex[:8]}@school.com",
            "role": "TEACHER",
            "first_name": "New",
            "last_name": "Teacher",
            "subjects": ["Mathematics", "Science"],
        }

        # Act
        with patch("app.services.user_service.resend") as mock_resend:
            mock_resend.Emails = AsyncMock()
            response = await client.post(
                f"/api/v1/schools/{school.id}/users",
                json=payload,
                headers=headers,
            )

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == payload["email"]
        assert data["role"] == "TEACHER"
        assert data["first_name"] == payload["first_name"]
        assert data["last_name"] == payload["last_name"]
        assert data["school_id"] == str(school.id)

        # Verify TeacherProfile was created
        result = await db_session.execute(
            select(TeacherProfile).where(TeacherProfile.user_id == uuid.UUID(data["id"]))
        )
        profile = result.scalar_one_or_none()
        assert profile is not None

    @pytest.mark.asyncio
    async def test_invite_user_when_duplicate_email_then_returns_409(
        self, client: AsyncClient, school_admin: User, school: School, teacher: User
    ) -> None:
        """Test that inviting duplicate email in same school returns 409."""
        # Arrange
        headers = auth_header(school_admin)
        payload = {
            "email": teacher.email,  # Already exists
            "role": "TEACHER",
            "first_name": "Duplicate",
            "last_name": "Teacher",
        }

        # Act
        response = await client.post(
            f"/api/v1/schools/{school.id}/users",
            json=payload,
            headers=headers,
        )

        # Assert
        assert response.status_code == 409
        assert "already registered" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_invite_user_when_school_admin_different_school_then_403(
        self, client: AsyncClient, other_school_admin: User, school: School
    ) -> None:
        """Test that SchoolAdmin cannot manage users in different school."""
        # Arrange
        headers = auth_header(other_school_admin)
        payload = {
            "email": f"newteacher-{uuid.uuid4().hex[:8]}@school.com",
            "role": "TEACHER",
            "first_name": "New",
            "last_name": "Teacher",
        }

        # Act
        response = await client.post(
            f"/api/v1/schools/{school.id}/users",
            json=payload,
            headers=headers,
        )

        # Assert
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_invite_user_when_kaihle_admin_then_allows_access(
        self, client: AsyncClient, kaihle_admin: User, school: School
    ) -> None:
        """Test that KaihleAdmin can invite users to any school."""
        # Arrange
        headers = auth_header(kaihle_admin)
        payload = {
            "email": f"newteacher-{uuid.uuid4().hex[:8]}@school.com",
            "role": "TEACHER",
            "first_name": "New",
            "last_name": "Teacher",
        }

        # Act
        with patch("app.services.user_service.resend") as mock_resend:
            mock_resend.Emails = AsyncMock()
            response = await client.post(
                f"/api/v1/schools/{school.id}/users",
                json=payload,
                headers=headers,
            )

        # Assert
        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_invite_user_when_teacher_then_403(
        self, client: AsyncClient, teacher: User, school: School
    ) -> None:
        """Test that Teacher cannot invite users."""
        # Arrange
        headers = auth_header(teacher)
        payload = {
            "email": f"newteacher-{uuid.uuid4().hex[:8]}@school.com",
            "role": "TEACHER",
            "first_name": "New",
            "last_name": "Teacher",
        }

        # Act
        response = await client.post(
            f"/api/v1/schools/{school.id}/users",
            json=payload,
            headers=headers,
        )

        # Assert
        assert response.status_code == 403


class TestListUsers:
    """Tests for GET /api/v1/schools/{school_id}/users"""

    @pytest.mark.asyncio
    async def test_list_users_when_school_admin_then_returns_users(
        self, client: AsyncClient, school_admin: User, school: School, teacher: User
    ) -> None:
        """Test that SchoolAdmin can list users in their school."""
        # Arrange
        headers = auth_header(school_admin)

        # Act
        response = await client.get(
            f"/api/v1/schools/{school.id}/users",
            headers=headers,
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "users" in data
        assert "total" in data
        assert data["total"] >= 2  # school_admin + teacher

    @pytest.mark.asyncio
    async def test_list_users_when_role_filter_then_returns_only_teachers(
        self, client: AsyncClient, db_session: AsyncSession, school_admin: User, school: School
    ) -> None:
        """Test that role filter returns only users with that role."""
        # Arrange
        # Create a teacher
        teacher = User(
            id=uuid.uuid4(),
            school_id=school.id,
            email=f"teacher-{uuid.uuid4().hex[:8]}@example.com",
            first_name="Teacher",
            last_name="User",
            role=UserRole.TEACHER,
            is_active=True,
        )
        db_session.add(teacher)

        # Create a parent
        parent = User(
            id=uuid.uuid4(),
            school_id=school.id,
            email=f"parent-{uuid.uuid4().hex[:8]}@example.com",
            first_name="Parent",
            last_name="User",
            role=UserRole.PARENT,
            is_active=True,
        )
        db_session.add(parent)
        await db_session.commit()

        headers = auth_header(school_admin)

        # Act
        response = await client.get(
            f"/api/v1/schools/{school.id}/users?role=TEACHER",
            headers=headers,
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        for user in data["users"]:
            assert user["role"] == "TEACHER"

    @pytest.mark.asyncio
    async def test_list_users_when_pagination_then_returns_correct_total(
        self, client: AsyncClient, db_session: AsyncSession, school_admin: User, school: School
    ) -> None:
        """Test that pagination returns correct total count."""
        # Arrange
        # Create multiple users
        for i in range(5):
            user = User(
                id=uuid.uuid4(),
                school_id=school.id,
                email=f"user{i}-{uuid.uuid4().hex[:8]}@example.com",
                first_name=f"User{i}",
                last_name="Test",
                role=UserRole.TEACHER,
                is_active=True,
            )
            db_session.add(user)
        await db_session.commit()

        headers = auth_header(school_admin)

        # Act - request first page with 3 items
        response = await client.get(
            f"/api/v1/schools/{school.id}/users?page=1&page_size=3",
            headers=headers,
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data["users"]) == 3  # Only 3 returned (page_size)
        assert data["total"] >= 6  # school_admin + teacher + 5 new = 7+
        assert data["page"] == 1
        assert data["page_size"] == 3


class TestUpdateUser:
    """Tests for PATCH /api/v1/schools/{school_id}/users/{user_id}"""

    @pytest.mark.asyncio
    async def test_update_user_when_school_admin_then_updates_user(
        self, client: AsyncClient, school_admin: User, school: School, teacher: User
    ) -> None:
        """Test that SchoolAdmin can update user details."""
        # Arrange
        headers = auth_header(school_admin)
        payload = {"first_name": "UpdatedName"}

        # Act
        response = await client.patch(
            f"/api/v1/schools/{school.id}/users/{teacher.id}",
            json=payload,
            headers=headers,
        )

        # Assert
        assert response.status_code == 200
        assert response.json()["first_name"] == "UpdatedName"


class TestDeactivateUser:
    """Tests for DELETE /api/v1/schools/{school_id}/users/{user_id}"""

    @pytest.mark.asyncio
    async def test_deactivate_user_when_school_admin_then_soft_deletes(
        self, client: AsyncClient, db_session: AsyncSession, school_admin: User, school: School
    ) -> None:
        """Test that SchoolAdmin can deactivate a user (soft delete)."""
        # Arrange
        # Create a user to deactivate
        user_to_deactivate = User(
            id=uuid.uuid4(),
            school_id=school.id,
            email=f"deactivate-{uuid.uuid4().hex[:8]}@example.com",
            first_name="ToDeactivate",
            last_name="User",
            role=UserRole.TEACHER,
            is_active=True,
        )
        db_session.add(user_to_deactivate)
        await db_session.commit()

        headers = auth_header(school_admin)

        # Act
        response = await client.delete(
            f"/api/v1/schools/{school.id}/users/{user_to_deactivate.id}",
            headers=headers,
        )

        # Assert
        assert response.status_code == 204

        # Verify user is inactive
        await db_session.refresh(user_to_deactivate)
        assert user_to_deactivate.is_active is False
