"""Integration tests for GET /schools/{school_id}/analytics.

Fixture pattern: MagicMock + app.dependency_overrides[get_current_user]
— mirrors test_platform_routes.py convention for this codebase.

The AnalyticsService performs real DB queries, so we mock it at the service
boundary rather than letting it hit the test DB (which would require seeding
complex multi-table data). The route-level concern here is auth gating,
period-param wiring, and response shape — not service internals (those live
in unit tests for AnalyticsService).
"""

import os
import uuid
from collections.abc import AsyncGenerator, Generator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

# Environment must be set before any app import
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://kaihle:kaihle@localhost:5433/kaihle_test")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-integration-tests")

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.core.deps import get_current_user  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import UserRole  # noqa: E402
from app.schemas.analytics import (  # noqa: E402
    AtRiskStudent,
    ClassBreakdown,
    OnboardingFunnel,
    SchoolAnalyticsData,
)

_TEST_SCHOOL_ID = uuid.uuid4()
_OTHER_SCHOOL_ID = uuid.uuid4()


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _make_school_admin(school_id: uuid.UUID = _TEST_SCHOOL_ID) -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    user.school_id = school_id
    user.role = UserRole.SCHOOL_ADMIN
    return user


def _make_kaihle_admin() -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    user.school_id = None
    user.role = UserRole.KAIHLE_ADMIN
    return user


def _make_teacher(school_id: uuid.UUID = _TEST_SCHOOL_ID) -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    user.school_id = school_id
    user.role = UserRole.TEACHER
    return user


def _stub_analytics_data(school_id: uuid.UUID) -> SchoolAnalyticsData:
    return SchoolAnalyticsData(
        school_id=school_id,
        generated_at=datetime.now(UTC),
        total_students=10,
        active_students=8,
        assessments_completed=5,
        study_plans_active=3,
        onboarding_funnel=OnboardingFunnel(
            invited=10,
            password_set=9,
            profile_complete=8,
            diagnostic_done=7,
        ),
        classes=[
            ClassBreakdown(
                class_id=uuid.uuid4(),
                class_name="Grade 7 Math",
                student_count=10,
                avg_mastery=0.65,
                assessments_completed=5,
            )
        ],
        at_risk_students=[
            AtRiskStudent(
                student_id=uuid.uuid4(),
                first_name="Alice",
                last_name="Smith",
                worst_mastery=0.2,
                needs_work_class_count=1,
            )
        ],
    )


class TestSchoolAnalyticsAuth:
    """Auth gating for GET /schools/{id}/analytics."""

    @pytest.fixture(autouse=True)
    def _cleanup(self) -> Generator[None, None, None]:
        yield
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_school_analytics_when_no_token_then_401(self, client: AsyncClient) -> None:
        response = await client.get(f"/api/v1/schools/{_TEST_SCHOOL_ID}/analytics")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_school_analytics_when_teacher_role_then_403(self, client: AsyncClient) -> None:
        app.dependency_overrides[get_current_user] = lambda: _make_teacher()
        response = await client.get(
            f"/api/v1/schools/{_TEST_SCHOOL_ID}/analytics",
            headers={"Authorization": "Bearer fake-token"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_get_school_analytics_when_wrong_school_then_403(self, client: AsyncClient) -> None:
        # School admin for _TEST_SCHOOL_ID tries to access _OTHER_SCHOOL_ID
        app.dependency_overrides[get_current_user] = lambda: _make_school_admin(_TEST_SCHOOL_ID)
        response = await client.get(
            f"/api/v1/schools/{_OTHER_SCHOOL_ID}/analytics",
            headers={"Authorization": "Bearer fake-token"},
        )
        assert response.status_code == 403


class TestSchoolAnalyticsResponse:
    """Response shape and service wiring for GET /schools/{id}/analytics."""

    @pytest.fixture(autouse=True)
    def _cleanup(self) -> Generator[None, None, None]:
        yield
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_school_analytics_when_authenticated_school_admin_then_returns_200(
        self, client: AsyncClient
    ) -> None:
        app.dependency_overrides[get_current_user] = lambda: _make_school_admin(_TEST_SCHOOL_ID)
        stub = _stub_analytics_data(_TEST_SCHOOL_ID)

        with patch("app.api.v1.routes.analytics.AnalyticsService") as MockService:
            instance = AsyncMock()
            instance.get_school_analytics.return_value = stub
            MockService.return_value = instance

            response = await client.get(
                f"/api/v1/schools/{_TEST_SCHOOL_ID}/analytics",
                headers={"Authorization": "Bearer fake-token"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "total_students" in data
        assert "onboarding_funnel" in data
        assert "classes" in data
        assert "at_risk_students" in data
        assert data["total_students"] == 10

    @pytest.mark.asyncio
    async def test_get_school_analytics_when_kaihle_admin_then_can_access_any_school(self, client: AsyncClient) -> None:
        app.dependency_overrides[get_current_user] = lambda: _make_kaihle_admin()
        stub = _stub_analytics_data(_OTHER_SCHOOL_ID)

        with patch("app.api.v1.routes.analytics.AnalyticsService") as MockService:
            instance = AsyncMock()
            instance.get_school_analytics.return_value = stub
            MockService.return_value = instance

            response = await client.get(
                f"/api/v1/schools/{_OTHER_SCHOOL_ID}/analytics",
                headers={"Authorization": "Bearer fake-token"},
            )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_school_analytics_when_period_params_given_then_forwarded_to_service(
        self, client: AsyncClient
    ) -> None:
        app.dependency_overrides[get_current_user] = lambda: _make_school_admin(_TEST_SCHOOL_ID)
        stub = _stub_analytics_data(_TEST_SCHOOL_ID)

        with patch("app.api.v1.routes.analytics.AnalyticsService") as MockService:
            instance = AsyncMock()
            instance.get_school_analytics.return_value = stub
            MockService.return_value = instance

            response = await client.get(
                f"/api/v1/schools/{_TEST_SCHOOL_ID}/analytics?from_date=2025-04-01&to_date=2025-04-30",
                headers={"Authorization": "Bearer fake-token"},
            )

        assert response.status_code == 200
        # Verify the service was called with the parsed date objects
        call_args = instance.get_school_analytics.call_args
        assert call_args is not None
        _, kwargs = call_args
        # Positional args: school_id, from_date, to_date
        pos_args = call_args.args
        from datetime import date

        assert pos_args[1] == date(2025, 4, 1)
        assert pos_args[2] == date(2025, 4, 30)

    @pytest.mark.asyncio
    async def test_get_school_analytics_when_no_period_params_then_defaults_to_30_days(
        self, client: AsyncClient
    ) -> None:
        app.dependency_overrides[get_current_user] = lambda: _make_school_admin(_TEST_SCHOOL_ID)
        stub = _stub_analytics_data(_TEST_SCHOOL_ID)

        with patch("app.api.v1.routes.analytics.AnalyticsService") as MockService:
            instance = AsyncMock()
            instance.get_school_analytics.return_value = stub
            MockService.return_value = instance

            response = await client.get(
                f"/api/v1/schools/{_TEST_SCHOOL_ID}/analytics",
                headers={"Authorization": "Bearer fake-token"},
            )

        assert response.status_code == 200
        call_args = instance.get_school_analytics.call_args
        assert call_args is not None
        pos_args = call_args.args
        from datetime import date

        today = date.today()
        # from_date should be ~30 days ago, to_date should be today
        assert pos_args[2] == today
        assert (today - pos_args[1]).days == 30
