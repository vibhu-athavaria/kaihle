"""Integration tests for study plan API routes — M3-2-T2.

Tests route decorators, auth wiring, and request/response shapes.
Database interactions are covered by unit tests for study_plan_service.py.
"""

import os
from collections.abc import AsyncGenerator
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.deps import get_current_user, require_full_access
from app.main import app
from app.models.user import UserRole

# Set test environment variables BEFORE importing app modules
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://kaihle:kaihle@localhost:5432/kaihle_test",
)
os.environ.setdefault("DATABASE_URL", TEST_DATABASE_URL)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-integration-tests")


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Create an async HTTP client for testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


def _make_student_user(school_id: str | None = None) -> MagicMock:
    """Create a mock STUDENT user."""
    mock_user = MagicMock()
    mock_user.id = str(uuid4())
    mock_user.role = UserRole.STUDENT
    mock_user.school_id = school_id or str(uuid4())
    return mock_user


def _make_teacher_user(school_id: str | None = None) -> MagicMock:
    """Create a mock TEACHER user."""
    mock_user = MagicMock()
    mock_user.id = str(uuid4())
    mock_user.role = UserRole.TEACHER
    mock_user.school_id = school_id or str(uuid4())
    return mock_user


def _make_parent_user(school_id: str | None = None) -> MagicMock:
    """Create a mock PARENT user."""
    mock_user = MagicMock()
    mock_user.id = str(uuid4())
    mock_user.role = UserRole.PARENT
    mock_user.school_id = school_id or str(uuid4())
    return mock_user


def _make_admin_user() -> MagicMock:
    """Create a mock KAIHLE_ADMIN user."""
    mock_user = MagicMock()
    mock_user.id = str(uuid4())
    mock_user.role = UserRole.KAIHLE_ADMIN
    mock_user.school_id = str(uuid4())
    return mock_user


class TestListMyStudyPlans:
    """Tests for GET /api/v1/students/me/study-plans."""

    @pytest.fixture(autouse=True)
    def _cleanup(self):
        yield
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_returns_401_without_auth(self, client: AsyncClient) -> None:
        """Endpoint requires authentication."""
        response = await client.get("/api/v1/students/me/study-plans")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_returns_403_for_teacher(self, client: AsyncClient) -> None:
        """Only STUDENT role may use /me shortcut."""
        teacher = _make_teacher_user()
        app.dependency_overrides[get_current_user] = lambda: teacher

        response = await client.get(
            "/api/v1/students/me/study-plans",
            headers={"Authorization": "Bearer fake-token"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_returns_400_when_no_school_id(self, client: AsyncClient) -> None:
        """Student without school_id gets 400."""
        student = _make_student_user(school_id=None)
        student.school_id = None
        app.dependency_overrides[get_current_user] = lambda: student

        response = await client.get(
            "/api/v1/students/me/study-plans",
            headers={"Authorization": "Bearer fake-token"},
        )
        assert response.status_code == 400


class TestListStudentStudyPlans:
    """Tests for GET /api/v1/students/{student_id}/study-plans."""

    @pytest.fixture(autouse=True)
    def _cleanup(self):
        yield
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_returns_401_without_auth(self, client: AsyncClient) -> None:
        """Endpoint requires authentication."""
        student_id = str(uuid4())
        response = await client.get(f"/api/v1/students/{student_id}/study-plans")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_student_cannot_view_other_student_plans(self, client: AsyncClient) -> None:
        """Student role may not view another student's plans."""
        my_student = _make_student_user()
        other_student_id = str(uuid4())
        # Route uses require_full_access — must override that dependency, not get_current_user
        app.dependency_overrides[require_full_access] = lambda: my_student

        response = await client.get(
            f"/api/v1/students/{other_student_id}/study-plans",
            headers={"Authorization": "Bearer fake-token"},
        )
        assert response.status_code == 403


class TestGetStudyPlan:
    """Tests for GET /api/v1/study-plans/{plan_id}."""

    @pytest.fixture(autouse=True)
    def _cleanup(self):
        yield
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_returns_401_without_auth(self, client: AsyncClient) -> None:
        """Endpoint requires authentication."""
        plan_id = str(uuid4())
        response = await client.get(f"/api/v1/study-plans/{plan_id}")
        assert response.status_code == 401


class TestMarkResourceWatched:
    """Tests for PATCH /api/v1/study-plans/{plan_id}/resources/{resource_id}/watched."""

    @pytest.fixture(autouse=True)
    def _cleanup(self):
        yield
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_returns_401_without_auth(self, client: AsyncClient) -> None:
        """Endpoint requires authentication."""
        plan_id = str(uuid4())
        resource_id = str(uuid4())
        response = await client.patch(f"/api/v1/study-plans/{plan_id}/resources/{resource_id}/watched")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_returns_403_for_teacher(self, client: AsyncClient) -> None:
        """Only STUDENT role may mark resources as watched."""
        teacher = _make_teacher_user()
        app.dependency_overrides[get_current_user] = lambda: teacher

        plan_id = str(uuid4())
        resource_id = str(uuid4())
        response = await client.patch(
            f"/api/v1/study-plans/{plan_id}/resources/{resource_id}/watched",
            headers={"Authorization": "Bearer fake-token"},
        )
        assert response.status_code == 403


class TestSubmitStudyPlanQuiz:
    """Tests for POST /api/v1/study-plans/{plan_id}/quiz."""

    @pytest.fixture(autouse=True)
    def _cleanup(self):
        yield
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_returns_401_without_auth(self, client: AsyncClient) -> None:
        """Endpoint requires authentication."""
        plan_id = str(uuid4())
        response = await client.post(
            f"/api/v1/study-plans/{plan_id}/quiz",
            json={"responses": []},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_returns_403_for_teacher(self, client: AsyncClient) -> None:
        """Only STUDENT role may submit quiz answers."""
        teacher = _make_teacher_user()
        app.dependency_overrides[get_current_user] = lambda: teacher

        plan_id = str(uuid4())
        response = await client.post(
            f"/api/v1/study-plans/{plan_id}/quiz",
            json={"responses": []},
            headers={"Authorization": "Bearer fake-token"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_accepts_valid_quiz_request_shape(self, client: AsyncClient) -> None:
        """Valid quiz submission request is accepted (404 for non-existent plan)."""
        student = _make_student_user()
        app.dependency_overrides[get_current_user] = lambda: student

        plan_id = str(uuid4())
        response = await client.post(
            f"/api/v1/study-plans/{plan_id}/quiz",
            json={
                "responses": [
                    {"question_index": 0, "answer": "A"},
                    {"question_index": 1, "answer": "B"},
                ]
            },
            headers={"Authorization": "Bearer fake-token"},
        )
        # 404 because plan doesn't exist (not 422 validation error)
        assert response.status_code == 404


class TestAssignStudyPlans:
    """Tests for POST /api/v1/classes/{class_id}/study-plans."""

    @pytest.fixture(autouse=True)
    def _cleanup(self):
        yield
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_returns_401_without_auth(self, client: AsyncClient) -> None:
        """Endpoint requires authentication."""
        class_id = str(uuid4())
        response = await client.post(
            f"/api/v1/classes/{class_id}/study-plans",
            json={"subtopic_id": str(uuid4()), "student_ids": None},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_returns_403_for_student(self, client: AsyncClient) -> None:
        """Only TEACHER role may assign study plans."""
        student = _make_student_user()
        app.dependency_overrides[get_current_user] = lambda: student

        class_id = str(uuid4())
        response = await client.post(
            f"/api/v1/classes/{class_id}/study-plans",
            json={"subtopic_id": str(uuid4()), "student_ids": None},
            headers={"Authorization": "Bearer fake-token"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_returns_403_for_parent(self, client: AsyncClient) -> None:
        """Only TEACHER role may assign study plans."""
        parent = _make_parent_user()
        app.dependency_overrides[get_current_user] = lambda: parent

        class_id = str(uuid4())
        response = await client.post(
            f"/api/v1/classes/{class_id}/study-plans",
            json={"subtopic_id": str(uuid4()), "student_ids": None},
            headers={"Authorization": "Bearer fake-token"},
        )
        assert response.status_code == 403
