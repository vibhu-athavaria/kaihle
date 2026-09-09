"""Integration tests for GET /api/v1/platform/llm-usage.

The load-bearing test here is `test_llm_usage_route_response_matches_cli_report_for_same_window`:
it seeds real rows and calls the route and `summarise_usage()` directly for the same window,
then asserts the totals agree. Both paths go through the same `llm_usage_service` function, so
this is what proves the "one query, two callers" refactor actually happened.
"""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.main import app
from app.models.llm_usage import LlmUsageEvent
from app.models.user import User
from app.services.llm_usage_service import summarise_usage


def _event(**overrides: object) -> LlmUsageEvent:
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "task": "question_generation",
        "model": "test/model-a",
        "component": "script:generate_gap_questions",
        "run_id": None,
        "prompt_tokens": 100,
        "completion_tokens": 200,
        "total_tokens": 300,
        "latency_ms": 500,
        "estimated_cost_usd": Decimal("0.001500"),
        "streamed": False,
        "succeeded": True,
        "error_type": None,
        "correlation_id": "corr-1",
        "school_id": None,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return LlmUsageEvent(**defaults)


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    from httpx import ASGITransport

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


class TestLlmUsageRouteAuth:
    async def test_llm_usage_route_when_caller_is_kaihle_admin_then_200(
        self, client: AsyncClient, kaihle_admin: User
    ) -> None:
        app.dependency_overrides[get_current_user] = lambda: kaihle_admin

        response = await client.get("/api/v1/platform/llm-usage", headers={"Authorization": "Bearer fake-token"})
        assert response.status_code == 200

    async def test_llm_usage_route_when_caller_is_school_admin_then_403(
        self, client: AsyncClient, school_admin: User
    ) -> None:
        app.dependency_overrides[get_current_user] = lambda: school_admin

        response = await client.get("/api/v1/platform/llm-usage", headers={"Authorization": "Bearer fake-token"})
        assert response.status_code == 403

    async def test_llm_usage_route_when_caller_is_teacher_then_403(self, client: AsyncClient, teacher: User) -> None:
        app.dependency_overrides[get_current_user] = lambda: teacher

        response = await client.get("/api/v1/platform/llm-usage", headers={"Authorization": "Bearer fake-token"})
        assert response.status_code == 403

    async def test_llm_usage_route_when_unauthenticated_then_401(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/platform/llm-usage")
        assert response.status_code == 401


class TestLlmUsageRouteEmptyWindow:
    async def test_llm_usage_route_when_no_events_then_returns_empty_summary_with_200(
        self, client: AsyncClient, kaihle_admin: User
    ) -> None:
        app.dependency_overrides[get_current_user] = lambda: kaihle_admin

        response = await client.get("/api/v1/platform/llm-usage", headers={"Authorization": "Bearer fake-token"})
        assert response.status_code == 200
        data = response.json()
        assert data["buckets"] == []
        assert data["summary"]["calls"] == 0
        assert data["summary"]["unpriced_percent"] == 0.0
        assert data["summary"]["unattributed_percent"] == 0.0


class TestLlmUsageRoutePagination:
    async def test_llm_usage_route_when_run_id_grouping_requested_then_paginated(
        self, client: AsyncClient, kaihle_admin: User, db_session: AsyncSession
    ) -> None:
        app.dependency_overrides[get_current_user] = lambda: kaihle_admin

        for i in range(5):
            db_session.add(_event(run_id=f"run-{i}", estimated_cost_usd=Decimal("0.01") * (i + 1)))
        await db_session.commit()

        response = await client.get(
            "/api/v1/platform/llm-usage",
            params={"group_by": "run_id", "page": 1, "page_size": 2},
            headers={"Authorization": "Bearer fake-token"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["buckets"]) == 2
        assert data["total_buckets"] == 5
        assert data["page"] == 1
        assert data["page_size"] == 2

        page_two = await client.get(
            "/api/v1/platform/llm-usage",
            params={"group_by": "run_id", "page": 2, "page_size": 2},
            headers={"Authorization": "Bearer fake-token"},
        )
        assert len(page_two.json()["buckets"]) == 2


class TestLlmUsageRouteMatchesService:
    async def test_llm_usage_route_response_matches_cli_report_for_same_window(
        self, client: AsyncClient, kaihle_admin: User, db_session: AsyncSession
    ) -> None:
        app.dependency_overrides[get_current_user] = lambda: kaihle_admin

        since = datetime.now(UTC) - timedelta(days=1)
        db_session.add(_event(component="api:diagnostic", estimated_cost_usd=Decimal("0.005000")))
        db_session.add(_event(component="celery:mini_course", estimated_cost_usd=None, succeeded=True))
        db_session.add(_event(component=None, succeeded=False, error_type="RateLimitError"))
        await db_session.commit()

        response = await client.get(
            "/api/v1/platform/llm-usage",
            params={"since": since.date().isoformat(), "group_by": "component"},
            headers={"Authorization": "Bearer fake-token"},
        )
        assert response.status_code == 200
        route_data = response.json()

        service_report = await summarise_usage(db_session, since, "component")

        assert route_data["summary"]["calls"] == service_report.summary.calls
        assert route_data["summary"]["failures"] == service_report.summary.failures
        assert route_data["summary"]["unpriced_count"] == service_report.summary.unpriced_count
        assert route_data["summary"]["unpriced_percent"] == pytest.approx(service_report.summary.unpriced_percent)
        assert route_data["summary"]["unattributed_count"] == service_report.summary.unattributed_count
        assert route_data["summary"]["unattributed_percent"] == pytest.approx(
            service_report.summary.unattributed_percent
        )
        route_cost = route_data["summary"]["cost"]
        service_cost = float(service_report.summary.cost) if service_report.summary.cost is not None else None
        assert route_cost == pytest.approx(service_cost) if service_cost is not None else route_cost is None
