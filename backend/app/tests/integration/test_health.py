"""Integration tests for health check endpoints."""

import os
from collections.abc import AsyncGenerator

# Set test environment variables BEFORE importing app modules
# This is critical because app.core.database creates engine at import time
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://kaihle:kaihle@localhost:5432/kaihle_test",
)
os.environ.setdefault("DATABASE_URL", TEST_DATABASE_URL)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-integration-tests")

from unittest.mock import AsyncMock, patch  # noqa: E402

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Create an async HTTP client for testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


class TestHealthEndpoint:
    """Tests for GET /health endpoint."""

    @pytest.mark.asyncio
    async def test_health_when_all_services_up_then_200_ok(self, client: AsyncClient) -> None:
        """Health endpoint returns 200 with all services connected."""
        with (
            patch("app.api.v1.routes.health._check_database", new_callable=AsyncMock) as mock_db,
            patch("app.api.v1.routes.health._check_redis", new_callable=AsyncMock) as mock_redis,
        ):
            mock_db.return_value = "connected"
            mock_redis.return_value = "connected"

            response = await client.get("/health")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert data["version"] == "2.1.0"
            assert data["db"] == "connected"
            assert data["redis"] == "connected"

    @pytest.mark.asyncio
    async def test_health_when_db_down_then_503_with_db_error(self, client: AsyncClient) -> None:
        """Health endpoint returns 503 when database is unreachable."""
        with (
            patch("app.api.v1.routes.health._check_database", new_callable=AsyncMock) as mock_db,
            patch("app.api.v1.routes.health._check_redis", new_callable=AsyncMock) as mock_redis,
        ):
            mock_db.return_value = "error"
            mock_redis.return_value = "connected"

            response = await client.get("/health")

            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "degraded"
            assert data["db"] == "error"
            assert data["redis"] == "connected"

    @pytest.mark.asyncio
    async def test_health_when_redis_down_then_503_with_redis_error(self, client: AsyncClient) -> None:
        """Health endpoint returns 503 when Redis is unreachable."""
        with (
            patch("app.api.v1.routes.health._check_database", new_callable=AsyncMock) as mock_db,
            patch("app.api.v1.routes.health._check_redis", new_callable=AsyncMock) as mock_redis,
        ):
            mock_db.return_value = "connected"
            mock_redis.return_value = "error"

            response = await client.get("/health")

            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "degraded"
            assert data["db"] == "connected"
            assert data["redis"] == "error"

    @pytest.mark.asyncio
    async def test_health_when_no_auth_token_then_200_not_401(self, client: AsyncClient) -> None:
        """Health endpoint does not require authentication."""
        with (
            patch("app.api.v1.routes.health._check_database", new_callable=AsyncMock) as mock_db,
            patch("app.api.v1.routes.health._check_redis", new_callable=AsyncMock) as mock_redis,
        ):
            mock_db.return_value = "connected"
            mock_redis.return_value = "connected"

            response = await client.get("/health")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"


class TestReadyEndpoint:
    """Tests for GET /ready endpoint."""

    @pytest.mark.asyncio
    async def test_ready_when_all_services_up_then_200_ok(self, client: AsyncClient) -> None:
        """Ready endpoint returns 200 when all services are connected."""
        with (
            patch("app.api.v1.routes.health._check_database", new_callable=AsyncMock) as mock_db,
            patch("app.api.v1.routes.health._check_redis", new_callable=AsyncMock) as mock_redis,
        ):
            mock_db.return_value = "connected"
            mock_redis.return_value = "connected"

            response = await client.get("/ready")

            assert response.status_code == 200
            data = response.json()
            assert data["ready"] is True

    @pytest.mark.asyncio
    async def test_ready_when_db_down_then_503(self, client: AsyncClient) -> None:
        """Ready endpoint returns 503 when database is down."""
        with (
            patch("app.api.v1.routes.health._check_database", new_callable=AsyncMock) as mock_db,
            patch("app.api.v1.routes.health._check_redis", new_callable=AsyncMock) as mock_redis,
        ):
            mock_db.return_value = "error"
            mock_redis.return_value = "connected"

            response = await client.get("/ready")

            assert response.status_code == 503
            data = response.json()
            assert data["ready"] is False

    @pytest.mark.asyncio
    async def test_ready_when_no_auth_token_then_200_not_401(self, client: AsyncClient) -> None:
        """Ready endpoint does not require authentication."""
        with (
            patch("app.api.v1.routes.health._check_database", new_callable=AsyncMock) as mock_db,
            patch("app.api.v1.routes.health._check_redis", new_callable=AsyncMock) as mock_redis,
        ):
            mock_db.return_value = "connected"
            mock_redis.return_value = "connected"

            response = await client.get("/ready")

            assert response.status_code == 200
            data = response.json()
            assert data["ready"] is True
