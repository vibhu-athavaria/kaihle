"""Integration tests for user management API routes.

Fixtures provided by conftest.py.
"""

import uuid
from collections.abc import AsyncGenerator
from unittest.mock import patch

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
        with patch("app.services.user_service.UserService._send_welcome_email"):
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
        result = await db_session.execute(select(TeacherProfile).where(TeacherProfile.user_id == uuid.UUID(data["id"])))
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
        with patch("app.services.user_service.UserService._send_welcome_email"):
            response = await client.post(
                f"/api/v1/schools/{school.id}/users",
                json=payload,
                headers=headers,
            )

        # Assert
        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_invite_user_when_teacher_then_403(self, client: AsyncClient, teacher: User, school: School) -> None:
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


class TestListStudentsWithMastery:
    """Tests for GET /api/v1/schools/{school_id}/users?role=STUDENT mastery fields."""

    @pytest.mark.asyncio
    async def test_list_students_when_school_admin_then_includes_worst_mastery(
        self, client: AsyncClient, db_session: AsyncSession, school_admin: User, school: School
    ) -> None:
        """Student list response includes mastery fields when role=STUDENT."""
        # Arrange — create a student in the school
        student = User(
            id=uuid.uuid4(),
            school_id=school.id,
            email=f"student-mastery-{uuid.uuid4().hex[:8]}@example.com",
            first_name="Student",
            last_name="Mastery",
            role=UserRole.STUDENT,
            is_active=True,
        )
        db_session.add(student)
        await db_session.commit()

        headers = auth_header(school_admin)

        # Act
        response = await client.get(
            f"/api/v1/schools/{school.id}/users?role=STUDENT",
            headers=headers,
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "users" in data
        assert "total" in data
        for s in data["users"]:
            assert "worst_mastery" in s
            assert "class_count" in s
            assert "needs_work_class_count" in s
            assert "diagnostic_completed" in s

    @pytest.mark.asyncio
    async def test_list_students_when_no_assessments_then_worst_mastery_is_null(
        self, client: AsyncClient, db_session: AsyncSession, school_admin: User, school: School
    ) -> None:
        """Students with no gap_states have worst_mastery=null and class_count=0."""
        # Arrange
        student = User(
            id=uuid.uuid4(),
            school_id=school.id,
            email=f"student-nodata-{uuid.uuid4().hex[:8]}@example.com",
            first_name="NoData",
            last_name="Student",
            role=UserRole.STUDENT,
            is_active=True,
        )
        db_session.add(student)
        await db_session.commit()

        headers = auth_header(school_admin)

        # Act
        response = await client.get(
            f"/api/v1/schools/{school.id}/users?role=STUDENT",
            headers=headers,
        )

        # Assert
        assert response.status_code == 200
        students_data = response.json()["users"]
        target = next((s for s in students_data if s["id"] == str(student.id)), None)
        assert target is not None
        assert target["worst_mastery"] is None
        assert target["class_count"] == 0
        assert target["needs_work_class_count"] == 0
        assert target["diagnostic_completed"] is False

    @pytest.mark.asyncio
    async def test_list_non_students_when_role_teacher_then_no_mastery_fields(
        self, client: AsyncClient, school_admin: User, school: School, teacher: User
    ) -> None:
        """Teacher list response uses standard UserResponse without mastery fields."""
        headers = auth_header(school_admin)

        # Act
        response = await client.get(
            f"/api/v1/schools/{school.id}/users?role=TEACHER",
            headers=headers,
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        for u in data["users"]:
            assert "worst_mastery" not in u
            assert "class_count" not in u


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

    @pytest.mark.asyncio
    async def test_update_user_password_when_kaihle_admin_then_password_is_updated(
        self, client: AsyncClient, kaihle_admin: User, school: School, teacher: User, db_session: AsyncSession
    ) -> None:
        """Test that KaihleAdmin can update user password."""
        from sqlalchemy import select

        from app.core.security import verify_password

        # Act
        headers = auth_header(kaihle_admin)
        new_password = "newpass123"
        payload = {"password": new_password}

        response = await client.patch(
            f"/api/v1/schools/{school.id}/users/{teacher.id}",
            json=payload,
            headers=headers,
        )

        # Assert
        assert response.status_code == 200

        # Verify password was updated in DB
        result = await db_session.execute(select(User).where(User.id == teacher.id))
        updated_user = result.scalar_one()
        assert updated_user.hashed_password is not None
        assert verify_password(new_password, updated_user.hashed_password)

    @pytest.mark.asyncio
    async def test_update_user_password_when_school_admin_for_own_school_then_password_is_updated(
        self, client: AsyncClient, school_admin: User, school: School, teacher: User, db_session: AsyncSession
    ) -> None:
        """Test that SchoolAdmin can update password for users in their own school."""
        from sqlalchemy import select

        from app.core.security import verify_password

        # Act
        headers = auth_header(school_admin)
        new_password = "newpass123"
        payload = {"password": new_password}

        response = await client.patch(
            f"/api/v1/schools/{school.id}/users/{teacher.id}",
            json=payload,
            headers=headers,
        )

        # Assert
        assert response.status_code == 200

        # Verify password was updated
        result = await db_session.execute(select(User).where(User.id == teacher.id))
        updated_user = result.scalar_one()
        assert updated_user.hashed_password is not None
        assert verify_password(new_password, updated_user.hashed_password)

    @pytest.mark.asyncio
    async def test_update_user_password_when_password_too_short_then_returns_422(
        self, client: AsyncClient, school_admin: User, school: School, teacher: User
    ) -> None:
        """Test that password too short returns 422."""
        # Act
        headers = auth_header(school_admin)
        payload = {"password": "short"}

        response = await client.patch(
            f"/api/v1/schools/{school.id}/users/{teacher.id}",
            json=payload,
            headers=headers,
        )

        # Assert
        assert response.status_code == 422


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
