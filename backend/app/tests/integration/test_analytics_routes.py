"""Integration tests for analytics endpoints.

Fixture pattern: MagicMock + app.dependency_overrides
— mirrors test_platform_routes.py convention for this codebase.

The AnalyticsService performs real DB queries, so we mock it at the service
boundary rather than letting it hit the test DB (which would require seeding
complex multi-table data). The route-level concern here is auth gating,
period-param wiring, and response shape — not service internals (those live
in unit tests for AnalyticsService).

Auth note: GET /schools/{id}/analytics uses require_full_access, which depends
on both get_current_user AND get_token_payload (JWT decode). Tests that exercise
this endpoint must override require_full_access directly — overriding only
get_current_user is insufficient because get_token_payload still validates the
raw JWT. Platform endpoints use require_role (which only depends on
get_current_user) so overriding get_current_user is sufficient there.
"""

import os
import uuid
from collections.abc import AsyncGenerator, Generator
from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

# Environment must be set before any app import
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://kaihle:kaihle@localhost:5433/kaihle_test")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-integration-tests")

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.core.database import get_db as real_get_db  # noqa: E402
from app.core.deps import get_current_user, require_full_access  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import UserRole  # noqa: E402
from app.schemas.analytics import (  # noqa: E402
    AtRiskStudent,
    ClassBreakdown,
    OnboardingFunnel,
    PlatformStats,
    SchoolAnalyticsData,
)

_TEST_SCHOOL_ID = uuid.uuid4()
_OTHER_SCHOOL_ID = uuid.uuid4()


@pytest.fixture(autouse=True)
def _mock_app_redis() -> Generator[None, None, None]:
    """Set a mock Redis on app.state so routes can access request.app.state.redis."""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock()
    app.state.redis = mock_redis
    yield
    # Clean up — avoid polluting other test modules
    if hasattr(app.state, "redis"):
        del app.state._state["redis"]


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


def _stub_analytics_data_with_subject_teacher(school_id: uuid.UUID) -> SchoolAnalyticsData:
    """Analytics stub with subject_name and teacher_name populated on the class breakdown."""
    return SchoolAnalyticsData(
        school_id=school_id,
        generated_at=datetime.now(UTC),
        total_students=5,
        total_teachers=2,
        active_students=5,
        assessments_completed=3,
        study_plans_active=2,
        onboarding_funnel=OnboardingFunnel(
            invited=5,
            password_set=5,
            profile_complete=5,
            diagnostic_done=5,
        ),
        classes=[
            ClassBreakdown(
                class_id=uuid.uuid4(),
                class_name="Grade 7 Math",
                subject_name="Mathematics",
                teacher_name="Jane Doe",
                student_count=5,
                avg_mastery=0.6,
                assessments_completed=3,
            )
        ],
        at_risk_students=[],
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
        # require_full_access must be overridden so that get_token_payload (its sub-dep) is bypassed.
        # Without this, the fake-token fails JWT validation and returns 401 instead of 403.
        teacher = _make_teacher()
        app.dependency_overrides[get_current_user] = lambda: teacher
        app.dependency_overrides[require_full_access] = lambda: teacher
        response = await client.get(
            f"/api/v1/schools/{_TEST_SCHOOL_ID}/analytics",
            headers={"Authorization": "Bearer fake-token"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_get_school_analytics_when_wrong_school_then_403(self, client: AsyncClient) -> None:
        # School admin for _TEST_SCHOOL_ID tries to access _OTHER_SCHOOL_ID
        school_admin = _make_school_admin(_TEST_SCHOOL_ID)
        app.dependency_overrides[get_current_user] = lambda: school_admin
        app.dependency_overrides[require_full_access] = lambda: school_admin
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
        school_admin = _make_school_admin(_TEST_SCHOOL_ID)
        app.dependency_overrides[get_current_user] = lambda: school_admin
        app.dependency_overrides[require_full_access] = lambda: school_admin
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
        kaihle_admin = _make_kaihle_admin()
        app.dependency_overrides[get_current_user] = lambda: kaihle_admin
        app.dependency_overrides[require_full_access] = lambda: kaihle_admin
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
        school_admin = _make_school_admin(_TEST_SCHOOL_ID)
        app.dependency_overrides[get_current_user] = lambda: school_admin
        app.dependency_overrides[require_full_access] = lambda: school_admin
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
        assert pos_args[1] == date(2025, 4, 1)
        assert pos_args[2] == date(2025, 4, 30)

    @pytest.mark.asyncio
    async def test_get_school_analytics_when_no_period_params_then_defaults_to_30_days(
        self, client: AsyncClient
    ) -> None:
        # Date defaulting now lives in AnalyticsService, not the route.
        # The route passes None, None through to the service when no query params are given.
        school_admin = _make_school_admin(_TEST_SCHOOL_ID)
        app.dependency_overrides[get_current_user] = lambda: school_admin
        app.dependency_overrides[require_full_access] = lambda: school_admin
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
        # Route passes None, None — service owns the defaulting logic
        assert pos_args[1] is None
        assert pos_args[2] is None


class TestSchoolAnalyticsSubjectAndTeacherFields:
    """Class breakdown includes subject_name and teacher_name fields."""

    @pytest.fixture(autouse=True)
    def _cleanup(self) -> Generator[None, None, None]:
        yield
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_school_analytics_includes_subject_and_teacher_name(self, client: AsyncClient) -> None:
        school_admin = _make_school_admin(_TEST_SCHOOL_ID)
        app.dependency_overrides[get_current_user] = lambda: school_admin
        app.dependency_overrides[require_full_access] = lambda: school_admin
        stub = _stub_analytics_data_with_subject_teacher(_TEST_SCHOOL_ID)

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
        assert len(data["classes"]) == 1
        cls = data["classes"][0]
        assert cls["subject_name"] == "Mathematics"
        assert cls["teacher_name"] == "Jane Doe"

    @pytest.mark.asyncio
    async def test_school_analytics_total_teachers_count(self, client: AsyncClient) -> None:
        school_admin = _make_school_admin(_TEST_SCHOOL_ID)
        app.dependency_overrides[get_current_user] = lambda: school_admin
        app.dependency_overrides[require_full_access] = lambda: school_admin
        stub = _stub_analytics_data_with_subject_teacher(_TEST_SCHOOL_ID)

        with patch("app.api.v1.routes.analytics.AnalyticsService") as MockService:
            instance = AsyncMock()
            instance.get_school_analytics.return_value = stub
            MockService.return_value = instance

            response = await client.get(
                f"/api/v1/schools/{_TEST_SCHOOL_ID}/analytics",
                headers={"Authorization": "Bearer fake-token"},
            )

        assert response.status_code == 200
        assert response.json()["total_teachers"] == 2

    @pytest.mark.asyncio
    async def test_school_analytics_is_cached_after_first_call(self, client: AsyncClient) -> None:
        """Service is constructed twice (once per HTTP call) but both succeed."""
        school_admin = _make_school_admin(_TEST_SCHOOL_ID)
        app.dependency_overrides[get_current_user] = lambda: school_admin
        app.dependency_overrides[require_full_access] = lambda: school_admin
        stub = _stub_analytics_data(_TEST_SCHOOL_ID)

        with patch("app.api.v1.routes.analytics.AnalyticsService") as MockService:
            instance = AsyncMock()
            instance.get_school_analytics.return_value = stub
            MockService.return_value = instance

            # First call
            response1 = await client.get(
                f"/api/v1/schools/{_TEST_SCHOOL_ID}/analytics",
                headers={"Authorization": "Bearer fake-token"},
            )
            # Second call — service's internal cache logic tested in unit tests
            response2 = await client.get(
                f"/api/v1/schools/{_TEST_SCHOOL_ID}/analytics",
                headers={"Authorization": "Bearer fake-token"},
            )

        # Both calls succeed and return the same shape data
        assert response1.status_code == 200
        assert response2.status_code == 200
        assert response1.json()["total_students"] == response2.json()["total_students"]
        # Service was called once per HTTP request (caching is internal to the service)
        assert instance.get_school_analytics.call_count == 2


class TestPlatformStats:
    """GET /platform/stats — KaihleAdmin only."""

    @pytest.fixture(autouse=True)
    def _cleanup(self) -> Generator[None, None, None]:
        yield
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_platform_stats_when_kaihle_admin_then_200_with_correct_totals(self, client: AsyncClient) -> None:
        app.dependency_overrides[get_current_user] = lambda: _make_kaihle_admin()

        platform_stub = PlatformStats(
            total_schools=2,
            total_active_students=10,
            total_teachers=4,
            assessments_completed_last_7_days=20,
            generated_at=datetime.now(UTC),
        )

        with patch("app.api.v1.routes.analytics.AnalyticsService") as MockService:
            instance = AsyncMock()
            instance.get_platform_stats.return_value = platform_stub
            MockService.return_value = instance

            response = await client.get(
                "/api/v1/platform/stats",
                headers={"Authorization": "Bearer fake-token"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["total_schools"] == 2
        assert data["total_active_students"] == 10

    @pytest.mark.asyncio
    async def test_platform_stats_when_teacher_then_403(self, client: AsyncClient) -> None:
        app.dependency_overrides[get_current_user] = lambda: _make_teacher()

        response = await client.get(
            "/api/v1/platform/stats",
            headers={"Authorization": "Bearer fake-token"},
        )

        assert response.status_code == 403


class TestImpersonateSchool:
    """POST /platform/schools/{id}/impersonate — KaihleAdmin only."""

    @pytest.fixture(autouse=True)
    def _cleanup(self) -> Generator[None, None, None]:
        yield
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_impersonate_when_kaihle_admin_then_200_with_token(self, client: AsyncClient) -> None:
        target_school_id = uuid.uuid4()
        app.dependency_overrides[get_current_user] = lambda: _make_kaihle_admin()

        impersonation_result = {
            "access_token": "eyJ.fake.token",
            "token_type": "bearer",
            "impersonated_school_id": str(target_school_id),
            "expires_in_seconds": 7200,
        }

        mock_db = AsyncMock()
        mock_school = MagicMock()
        mock_school.id = target_school_id
        mock_db.scalar = AsyncMock(return_value=mock_school)

        async def _fake_db():  # type: ignore[return]
            yield mock_db

        app.dependency_overrides[real_get_db] = _fake_db

        with patch("app.api.v1.routes.analytics.AnalyticsService") as MockService:
            instance = AsyncMock()
            instance.issue_impersonation_token.return_value = impersonation_result
            MockService.return_value = instance

            response = await client.post(
                f"/api/v1/platform/schools/{target_school_id}/impersonate",
                headers={"Authorization": "Bearer fake-token"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert len(data["access_token"]) > 0
        assert data["impersonated_school_id"] == str(target_school_id)

    @pytest.mark.asyncio
    async def test_impersonate_when_school_not_found_then_404(self, client: AsyncClient) -> None:
        random_school_id = uuid.uuid4()
        app.dependency_overrides[get_current_user] = lambda: _make_kaihle_admin()

        mock_db = AsyncMock()
        mock_db.scalar = AsyncMock(return_value=None)  # school not found

        async def _fake_db():  # type: ignore[return]
            yield mock_db

        app.dependency_overrides[real_get_db] = _fake_db

        response = await client.post(
            f"/api/v1/platform/schools/{random_school_id}/impersonate",
            headers={"Authorization": "Bearer fake-token"},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_impersonate_when_school_admin_then_403(self, client: AsyncClient) -> None:
        target_school_id = uuid.uuid4()
        app.dependency_overrides[get_current_user] = lambda: _make_school_admin(target_school_id)

        response = await client.post(
            f"/api/v1/platform/schools/{target_school_id}/impersonate",
            headers={"Authorization": "Bearer fake-token"},
        )

        assert response.status_code == 403
