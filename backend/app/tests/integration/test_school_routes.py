"""Integration tests for school management routes."""

import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.main import app
from app.models.school import School
from app.models.user import User, UserRole


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Create an async HTTP client."""
    from httpx import ASGITransport

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def kaihle_admin_user(db_session: AsyncSession) -> User:
    """Create a KaihleAdmin user."""
    # First create a school for the admin
    school = School(
        id=uuid.uuid4(),
        name="Admin School",
        slug=f"admin-school-{uuid.uuid4().hex[:8]}",
        status="active",
    )
    db_session.add(school)
    await db_session.commit()

    user = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"admin-{uuid.uuid4().hex[:8]}@kaihle.com",
        first_name="Kaihle",
        last_name="Admin",
        role=UserRole.KAIHLE_ADMIN,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def school_admin_user(db_session: AsyncSession, test_school: School) -> User:
    """Create a SchoolAdmin user."""
    user = User(
        id=uuid.uuid4(),
        school_id=test_school.id,
        email=f"school-admin-{uuid.uuid4().hex[:8]}@example.com",
        first_name="School",
        last_name="Admin",
        role=UserRole.SCHOOL_ADMIN,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def teacher_user(db_session: AsyncSession, test_school: School) -> User:
    """Create a Teacher user."""
    user = User(
        id=uuid.uuid4(),
        school_id=test_school.id,
        email=f"teacher-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Test",
        last_name="Teacher",
        role=UserRole.TEACHER,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def other_school(db_session: AsyncSession) -> School:
    """Create another school for cross-school access tests."""
    school = School(
        id=uuid.uuid4(),
        name="Other School",
        slug=f"other-school-{uuid.uuid4().hex[:8]}",
        status="active",
    )
    db_session.add(school)
    await db_session.commit()
    return school


def auth_header(user: User) -> dict[str, str]:
    """Generate Authorization header with real JWT for a user."""
    token = create_access_token(user.id, user.school_id, user.role)
    return {"Authorization": f"Bearer {token}"}


class TestCreateSchool:
    """Tests for POST /api/v1/admin/schools"""

    @pytest.mark.asyncio
    async def test_create_school_when_kaihle_admin_then_201(self, client: AsyncClient, kaihle_admin_user: User) -> None:
        """Test that KaihleAdmin can create a school."""
        # Arrange
        headers = auth_header(kaihle_admin_user)
        payload = {
            "name": "New School",
            "slug": f"new-school-{uuid.uuid4().hex[:8]}",
            "country": "Indonesia",
            "timezone": "Asia/Jakarta",
        }

        # Act
        response = await client.post("/api/v1/admin/schools", json=payload, headers=headers)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["name"] == "New School"
        assert data["slug"] == payload["slug"]
        assert data["country"] == "Indonesia"
        assert data["timezone"] == "Asia/Jakarta"
        assert data["is_active"] is True

    @pytest.mark.asyncio
    async def test_create_school_when_teacher_then_403(self, client: AsyncClient, teacher_user: User) -> None:
        """Test that Teacher cannot create a school."""
        # Arrange
        headers = auth_header(teacher_user)
        payload = {
            "name": "New School",
            "slug": f"new-school-{uuid.uuid4().hex[:8]}",
        }

        # Act
        response = await client.post("/api/v1/admin/schools", json=payload, headers=headers)

        # Assert
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_create_school_when_duplicate_slug_then_409(
        self, client: AsyncClient, kaihle_admin_user: User, test_school: School
    ) -> None:
        """Test that duplicate slug returns 409."""
        # Arrange
        headers = auth_header(kaihle_admin_user)
        payload = {
            "name": "Another School",
            "slug": test_school.slug,  # Use existing slug
        }

        # Act
        response = await client.post("/api/v1/admin/schools", json=payload, headers=headers)

        # Assert
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_school_when_unauthenticated_then_401(self, client: AsyncClient) -> None:
        """Test that unauthenticated request returns 401."""
        # Arrange
        payload = {
            "name": "New School",
            "slug": f"new-school-{uuid.uuid4().hex[:8]}",
        }

        # Act
        response = await client.post("/api/v1/admin/schools", json=payload)

        # Assert
        assert response.status_code == 401


class TestListSchools:
    """Tests for GET /api/v1/admin/schools"""

    @pytest.mark.asyncio
    async def test_list_schools_when_kaihle_admin_then_returns_paginated_list(
        self, client: AsyncClient, kaihle_admin_user: User, db_session: AsyncSession
    ) -> None:
        """Test that KaihleAdmin can list schools with pagination."""
        # Arrange - Create some schools
        for i in range(5):
            school = School(
                id=uuid.uuid4(),
                name=f"School {i}",
                slug=f"school-{i}-{uuid.uuid4().hex[:8]}",
                status="active",
            )
            db_session.add(school)
        await db_session.commit()

        headers = auth_header(kaihle_admin_user)

        # Act
        response = await client.get("/api/v1/admin/schools?page=1&page_size=3", headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "schools" in data
        assert "total" in data
        assert data["page"] == 1
        assert data["page_size"] == 3
        assert len(data["schools"]) <= 3
        assert data["total"] >= 5

    @pytest.mark.asyncio
    async def test_list_schools_when_teacher_then_403(self, client: AsyncClient, teacher_user: User) -> None:
        """Test that Teacher cannot list schools."""
        # Arrange
        headers = auth_header(teacher_user)

        # Act
        response = await client.get("/api/v1/admin/schools", headers=headers)

        # Assert
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_list_schools_when_school_admin_then_403(self, client: AsyncClient, school_admin_user: User) -> None:
        """Test that SchoolAdmin cannot list all schools."""
        # Arrange
        headers = auth_header(school_admin_user)

        # Act
        response = await client.get("/api/v1/admin/schools", headers=headers)

        # Assert
        assert response.status_code == 403


class TestGetSchool:
    """Tests for GET /api/v1/admin/schools/{school_id}"""

    @pytest.mark.asyncio
    async def test_get_school_when_kaihle_admin_then_200(
        self, client: AsyncClient, kaihle_admin_user: User, test_school: School
    ) -> None:
        """Test that KaihleAdmin can get any school."""
        # Arrange
        headers = auth_header(kaihle_admin_user)

        # Act
        response = await client.get(f"/api/v1/admin/schools/{test_school.id}", headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_school.id)
        assert data["name"] == test_school.name

    @pytest.mark.asyncio
    async def test_get_school_when_school_admin_own_school_then_200(
        self, client: AsyncClient, school_admin_user: User, test_school: School
    ) -> None:
        """Test that SchoolAdmin can get their own school."""
        # Arrange
        headers = auth_header(school_admin_user)

        # Act
        response = await client.get(f"/api/v1/admin/schools/{test_school.id}", headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_school.id)

    @pytest.mark.asyncio
    async def test_get_school_when_school_admin_other_school_then_403(
        self,
        client: AsyncClient,
        school_admin_user: User,
        other_school: School,
    ) -> None:
        """Test that SchoolAdmin cannot get other schools."""
        # Arrange
        headers = auth_header(school_admin_user)

        # Act
        response = await client.get(f"/api/v1/admin/schools/{other_school.id}", headers=headers)

        # Assert
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_get_school_when_teacher_then_403(
        self, client: AsyncClient, teacher_user: User, test_school: School
    ) -> None:
        """Test that Teacher cannot get school details."""
        # Arrange
        headers = auth_header(teacher_user)

        # Act
        response = await client.get(f"/api/v1/admin/schools/{test_school.id}", headers=headers)

        # Assert
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_get_school_when_not_exists_then_404(self, client: AsyncClient, kaihle_admin_user: User) -> None:
        """Test that getting non-existent school returns 404."""
        # Arrange
        headers = auth_header(kaihle_admin_user)
        non_existent_id = uuid.uuid4()

        # Act
        response = await client.get(f"/api/v1/admin/schools/{non_existent_id}", headers=headers)

        # Assert
        assert response.status_code == 404


class TestUpdateSchool:
    """Tests for PATCH /api/v1/admin/schools/{school_id}"""

    @pytest.mark.asyncio
    async def test_update_school_when_kaihle_admin_then_200(
        self, client: AsyncClient, kaihle_admin_user: User, test_school: School
    ) -> None:
        """Test that KaihleAdmin can update a school."""
        # Arrange
        headers = auth_header(kaihle_admin_user)
        payload = {
            "name": "Updated School Name",
            "country": "Singapore",
        }

        # Act
        response = await client.patch(
            f"/api/v1/admin/schools/{test_school.id}",
            json=payload,
            headers=headers,
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated School Name"
        assert data["country"] == "Singapore"
        assert data["slug"] == test_school.slug  # unchanged

    @pytest.mark.asyncio
    async def test_update_school_when_school_admin_then_403(
        self, client: AsyncClient, school_admin_user: User, test_school: School
    ) -> None:
        """Test that SchoolAdmin cannot update a school."""
        # Arrange
        headers = auth_header(school_admin_user)
        payload = {"name": "Updated Name"}

        # Act
        response = await client.patch(
            f"/api/v1/admin/schools/{test_school.id}",
            json=payload,
            headers=headers,
        )

        # Assert
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_update_school_when_teacher_then_403(
        self, client: AsyncClient, teacher_user: User, test_school: School
    ) -> None:
        """Test that Teacher cannot update a school."""
        # Arrange
        headers = auth_header(teacher_user)
        payload = {"name": "Updated Name"}

        # Act
        response = await client.patch(
            f"/api/v1/admin/schools/{test_school.id}",
            json=payload,
            headers=headers,
        )

        # Assert
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_update_school_when_not_exists_then_404(self, client: AsyncClient, kaihle_admin_user: User) -> None:
        """Test that updating non-existent school returns 404."""
        # Arrange
        headers = auth_header(kaihle_admin_user)
        non_existent_id = uuid.uuid4()
        payload = {"name": "Updated Name"}

        # Act
        response = await client.patch(
            f"/api/v1/admin/schools/{non_existent_id}",
            json=payload,
            headers=headers,
        )

        # Assert
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_school_when_deactivate_then_status_updated(
        self, client: AsyncClient, kaihle_admin_user: User, test_school: School
    ) -> None:
        """Test that deactivating a school updates is_active."""
        # Arrange
        headers = auth_header(kaihle_admin_user)
        payload = {"is_active": False}

        # Act
        response = await client.patch(
            f"/api/v1/admin/schools/{test_school.id}",
            json=payload,
            headers=headers,
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is False
