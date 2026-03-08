"""Integration tests for authentication routes."""

import uuid
from unittest.mock import AsyncMock, Mock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.user import UserRole
from app.services.auth_service import AuthService


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def mock_school_id():
    """Create a mock school UUID."""
    return uuid.uuid4()


class TestSchoolAdminRegistration:
    """Tests for school admin registration endpoint."""

    @pytest.mark.asyncio
    async def test_register_school_admin_when_valid_data_then_returns_201(self, mock_school_id):
        """Test successful school admin registration."""
        # Arrange
        with patch("app.api.v1.routes.auth.AuthService") as MockAuthService:
            mock_service = AsyncMock(spec=AuthService)
            mock_service.register_school_admin.return_value = Mock(
                user_id=uuid.uuid4(),
                email="admin@school.com",
                role=UserRole.SCHOOL_ADMIN,
            )
            MockAuthService.return_value = mock_service

            # Use httpx AsyncClient with ASGITransport for testing
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                # Act
                response = await client.post(
                    "/auth/register/school-admin",
                    json={
                        "email": "admin@school.com",
                        "password": "securepass123",
                        "school_id": str(mock_school_id),
                        "first_name": "John",
                        "last_name": "Admin",
                    },
                )

                # Assert
                assert response.status_code == 201
                data = response.json()
                assert data["email"] == "admin@school.com"
                assert data["role"] == UserRole.SCHOOL_ADMIN

    @pytest.mark.asyncio
    async def test_register_school_admin_when_duplicate_email_then_returns_409(self, mock_school_id):
        """Test school admin registration with duplicate email."""
        with patch("app.api.v1.routes.auth.AuthService") as MockAuthService:
            mock_service = AsyncMock(spec=AuthService)
            mock_service.register_school_admin.side_effect = ValueError("Email already registered")
            MockAuthService.return_value = mock_service

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/auth/register/school-admin",
                    json={
                        "email": "existing@school.com",
                        "password": "securepass123",
                        "school_id": str(mock_school_id),
                        "first_name": "John",
                        "last_name": "Admin",
                    },
                )

                assert response.status_code == 409
                assert "Email already registered" in response.json()["detail"]


class TestTeacherRegistration:
    """Tests for teacher registration endpoint."""

    @pytest.mark.asyncio
    async def test_register_teacher_when_valid_data_then_returns_201(self, mock_school_id):
        """Test successful teacher registration."""
        with patch("app.api.v1.routes.auth.AuthService") as MockAuthService:
            mock_service = AsyncMock(spec=AuthService)
            mock_service.register_teacher.return_value = Mock(
                user_id=uuid.uuid4(),
                email="teacher@school.com",
                role=UserRole.TEACHER,
            )
            MockAuthService.return_value = mock_service

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/auth/register/teacher",
                    json={
                        "email": "teacher@school.com",
                        "password": "securepass123",
                        "school_id": str(mock_school_id),
                        "first_name": "Jane",
                        "last_name": "Teacher",
                    },
                )

                assert response.status_code == 201
                data = response.json()
                assert data["email"] == "teacher@school.com"
                assert data["role"] == UserRole.TEACHER


class TestStudentRegistration:
    """Tests for student registration endpoint."""

    @pytest.mark.asyncio
    async def test_register_student_when_valid_data_then_returns_201(self, mock_school_id):
        """Test successful student registration."""
        with patch("app.api.v1.routes.auth.AuthService") as MockAuthService:
            mock_service = AsyncMock(spec=AuthService)
            mock_service.register_student.return_value = Mock(
                user_id=uuid.uuid4(),
                email="student@school.com",
                role=UserRole.STUDENT,
            )
            MockAuthService.return_value = mock_service

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/auth/register/student",
                    json={
                        "email": "student@school.com",
                        "password": "securepass123",
                        "school_id": str(mock_school_id),
                        "first_name": "Bob",
                        "last_name": "Student",
                    },
                )

                assert response.status_code == 201
                data = response.json()
                assert data["email"] == "student@school.com"
                assert data["role"] == UserRole.STUDENT


class TestParentRegistration:
    """Tests for parent registration endpoint."""

    @pytest.mark.asyncio
    async def test_register_parent_when_valid_data_then_returns_201(self):
        """Test successful parent registration."""
        with patch("app.api.v1.routes.auth.AuthService") as MockAuthService:
            mock_service = AsyncMock(spec=AuthService)
            mock_service.register_parent.return_value = Mock(
                user_id=uuid.uuid4(),
                email="parent@email.com",
                role=UserRole.PARENT,
            )
            MockAuthService.return_value = mock_service

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/auth/register/parent",
                    json={
                        "email": "parent@email.com",
                        "password": "securepass123",
                        "first_name": "Alice",
                        "last_name": "Parent",
                    },
                )

                assert response.status_code == 201
                data = response.json()
                assert data["email"] == "parent@email.com"
                assert data["role"] == UserRole.PARENT


class TestKaihleAdminRegistration:
    """Tests for Kaihle admin registration endpoint."""

    @pytest.mark.asyncio
    async def test_register_kaihle_admin_when_valid_data_then_returns_201(self):
        """Test successful Kaihle admin registration."""
        with patch("app.api.v1.routes.auth.AuthService") as MockAuthService:
            mock_service = AsyncMock(spec=AuthService)
            mock_service.register_kaihle_admin.return_value = Mock(
                user_id=uuid.uuid4(),
                email="admin@kaihle.ai",
                role=UserRole.KAIHLE_ADMIN,
            )
            MockAuthService.return_value = mock_service

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/auth/register/kaihle-admin",
                    json={
                        "email": "admin@kaihle.ai",
                        "password": "securepass123",
                        "first_name": "Super",
                        "last_name": "Admin",
                    },
                )

                assert response.status_code == 201
                data = response.json()
                assert data["email"] == "admin@kaihle.ai"
                assert data["role"] == UserRole.KAIHLE_ADMIN


class TestLogin:
    """Tests for unified login endpoint."""

    @pytest.mark.asyncio
    async def test_login_when_valid_credentials_then_returns_tokens(self):
        """Test successful login with valid credentials."""
        with patch("app.api.v1.routes.auth.AuthService") as MockAuthService:
            mock_service = AsyncMock(spec=AuthService)
            mock_service.login.return_value = Mock(
                access_token="access_token",
                refresh_token="refresh_token",
                token_type="bearer",
                user={
                    "id": str(uuid.uuid4()),
                    "email": "user@school.com",
                    "role": UserRole.TEACHER,
                    "school_id": str(uuid.uuid4()),
                },
            )
            MockAuthService.return_value = mock_service

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/auth/login",
                    json={
                        "email": "user@school.com",
                        "password": "securepass123",
                    },
                )

                assert response.status_code == 200
                data = response.json()
                assert "access_token" in data
                assert "refresh_token" in data
                assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_login_when_invalid_credentials_then_returns_401(self):
        """Test login with invalid credentials."""
        with patch("app.api.v1.routes.auth.AuthService") as MockAuthService:
            mock_service = AsyncMock(spec=AuthService)
            mock_service.login.side_effect = ValueError("Invalid credentials")
            MockAuthService.return_value = mock_service

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/auth/login",
                    json={
                        "email": "wrong@school.com",
                        "password": "wrongpass",
                    },
                )

                assert response.status_code == 401
                assert "Invalid credentials" in response.json()["detail"]
