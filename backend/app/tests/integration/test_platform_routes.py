"""Integration tests for platform endpoints."""

import os
from collections.abc import AsyncGenerator
from unittest.mock import MagicMock, patch

# Set test environment variables BEFORE importing app modules
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://kaihle:kaihle@localhost:5432/kaihle_test",
)
os.environ.setdefault("DATABASE_URL", TEST_DATABASE_URL)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-integration-tests")

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.main import app  # noqa: E402
from app.models.user import UserRole  # noqa: E402


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Create an async HTTP client for testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


def _make_admin_user() -> MagicMock:
    """Create a mock KAIHLE_ADMIN user."""
    mock_user = MagicMock()
    mock_user.id = "test-user-id"
    mock_user.role = UserRole.KAIHLE_ADMIN
    return mock_user


class TestPlatformStatsAuth:
    """Tests for /platform/stats authentication and authorization."""

    @pytest.mark.asyncio
    async def test_stats_when_no_auth_token_then_401(self, client: AsyncClient) -> None:
        """Stats endpoint requires authentication — returns 401 without token."""
        response = await client.get("/api/v1/platform/stats")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_stats_when_non_admin_role_then_403(self, client: AsyncClient) -> None:
        """Stats endpoint requires KAIHLE_ADMIN role — returns 403 for other roles."""
        mock_user = MagicMock()
        mock_user.id = "test-user-id"
        mock_user.role = UserRole.TEACHER

        with patch("app.core.deps.get_current_user", return_value=mock_user):
            response = await client.get(
                "/api/v1/platform/stats",
                headers={"Authorization": "Bearer fake-token"},
            )
            assert response.status_code == 403


class TestPlatformUsersAuth:
    """Tests for /platform/users authentication and authorization."""

    @pytest.mark.asyncio
    async def test_users_when_no_auth_token_then_401(self, client: AsyncClient) -> None:
        """Users endpoint requires authentication — returns 401 without token."""
        response = await client.get("/api/v1/platform/users")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_users_when_non_admin_role_then_403(self, client: AsyncClient) -> None:
        """Users endpoint requires KAIHLE_ADMIN role — returns 403 for other roles."""
        mock_user = MagicMock()
        mock_user.id = "test-user-id"
        mock_user.role = UserRole.SCHOOL_ADMIN

        with patch("app.core.deps.get_current_user", return_value=mock_user):
            response = await client.get(
                "/api/v1/platform/users",
                headers={"Authorization": "Bearer fake-token"},
            )
            assert response.status_code == 403


class TestPlatformStatsConfig:
    """Tests for /platform/stats config wiring."""

    @pytest.mark.asyncio
    async def test_stats_when_kaihle_admin_then_returns_config_values(self, client: AsyncClient) -> None:
        """Stats endpoint returns values from config.py when accessed by KAIHLE_ADMIN."""
        from app.core.config import settings

        mock_user = _make_admin_user()

        with patch("app.core.deps.get_current_user", return_value=mock_user):
            response = await client.get(
                "/api/v1/platform/stats",
                headers={"Authorization": "Bearer fake-token"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["llm_provider"] == settings.platform_llm_provider
            assert data["runpod_status"] == settings.platform_runpod_status
            assert data["trial_days"] == settings.platform_trial_days
            assert data["trial_students_limit"] == settings.platform_trial_students_limit
            assert data["rate_limit_requests_per_minute"] == settings.platform_rate_limit_requests_per_minute
            assert data["rate_limit_concurrent_users"] == settings.platform_rate_limit_concurrent_users

    @pytest.mark.asyncio
    async def test_stats_when_called_then_no_hardcoded_defaults_in_response(self, client: AsyncClient) -> None:
        """Stats endpoint does not return hardcoded defaults — values come from config."""
        mock_user = _make_admin_user()

        with patch("app.core.deps.get_current_user", return_value=mock_user):
            response = await client.get(
                "/api/v1/platform/stats",
                headers={"Authorization": "Bearer fake-token"},
            )
            assert response.status_code == 200
            data = response.json()
            # Verify all fields are present (no missing fields that would use Pydantic defaults)
            assert "llm_provider" in data
            assert "runpod_status" in data
            assert "trial_days" in data
            assert "trial_students_limit" in data
            assert "rate_limit_requests_per_minute" in data
            assert "rate_limit_concurrent_users" in data


class TestPlatformUsersResponse:
    """Tests for /platform/users response structure."""

    @pytest.mark.asyncio
    async def test_users_when_kaihle_admin_then_returns_paginated_response(self, client: AsyncClient) -> None:
        """Users endpoint returns paginated response structure when accessed by KAIHLE_ADMIN."""
        mock_user = _make_admin_user()

        with patch("app.core.deps.get_current_user", return_value=mock_user):
            response = await client.get(
                "/api/v1/platform/users",
                headers={"Authorization": "Bearer fake-token"},
            )
            assert response.status_code == 200
            data = response.json()
            assert "users" in data
            assert "total" in data
            assert "page" in data
            assert "page_size" in data
            assert isinstance(data["users"], list)
            assert data["page"] == 1
            assert data["page_size"] == 25


class TestPlatformLogging:
    """Tests for structlog logging on platform endpoints."""

    @pytest.mark.asyncio
    async def test_stats_when_requested_then_logs_request(self, client: AsyncClient) -> None:
        """Stats endpoint logs request with structlog when accessed."""
        mock_user = _make_admin_user()

        with (
            patch("app.core.deps.get_current_user", return_value=mock_user),
            patch("app.api.v1.routes.platform.logger") as mock_logger,
        ):
            await client.get(
                "/api/v1/platform/stats",
                headers={"Authorization": "Bearer fake-token"},
            )
            mock_logger.info.assert_called()
            call_args = mock_logger.info.call_args
            assert call_args is not None
            assert call_args[0][0] == "platform.stats.requested"

    @pytest.mark.asyncio
    async def test_users_when_requested_then_logs_request(self, client: AsyncClient) -> None:
        """Users endpoint logs request with structlog when accessed."""
        mock_user = _make_admin_user()

        with (
            patch("app.core.deps.get_current_user", return_value=mock_user),
            patch("app.api.v1.routes.platform.logger") as mock_logger,
        ):
            await client.get(
                "/api/v1/platform/users",
                headers={"Authorization": "Bearer fake-token"},
            )
            mock_logger.info.assert_called()
            call_args = mock_logger.info.call_args
            assert call_args is not None
            assert call_args[0][0] == "platform.users.requested"
