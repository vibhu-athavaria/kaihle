"""Integration tests for GET /api/v1/platform/llm-logs and /llm-logs/{id}."""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from decimal import Decimal

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.main import app
from app.models.llm_usage import LlmUsageEvent
from app.models.user import User


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
        "prompt_text": "[user] What is 2+2?",
        "response_text": "4",
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return LlmUsageEvent(**defaults)


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


class TestLlmLogsListAuth:
    async def test_llm_logs_when_caller_is_kaihle_admin_then_200(self, client: AsyncClient, kaihle_admin: User) -> None:
        app.dependency_overrides[get_current_user] = lambda: kaihle_admin

        response = await client.get("/api/v1/platform/llm-logs", headers={"Authorization": "Bearer fake-token"})
        assert response.status_code == 200

    async def test_llm_logs_when_caller_is_school_admin_then_403(self, client: AsyncClient, school_admin: User) -> None:
        app.dependency_overrides[get_current_user] = lambda: school_admin

        response = await client.get("/api/v1/platform/llm-logs", headers={"Authorization": "Bearer fake-token"})
        assert response.status_code == 403

    async def test_llm_logs_when_caller_is_teacher_then_403(self, client: AsyncClient, teacher: User) -> None:
        app.dependency_overrides[get_current_user] = lambda: teacher

        response = await client.get("/api/v1/platform/llm-logs", headers={"Authorization": "Bearer fake-token"})
        assert response.status_code == 403

    async def test_llm_logs_when_unauthenticated_then_401(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/platform/llm-logs")
        assert response.status_code == 401


class TestLlmLogsListBehaviour:
    async def test_llm_logs_when_no_events_then_returns_empty_list_with_200(
        self, client: AsyncClient, kaihle_admin: User
    ) -> None:
        app.dependency_overrides[get_current_user] = lambda: kaihle_admin

        response = await client.get("/api/v1/platform/llm-logs", headers={"Authorization": "Bearer fake-token"})
        assert response.status_code == 200
        data = response.json()
        assert data["logs"] == []
        assert data["total"] == 0

    async def test_llm_logs_when_events_present_then_summary_excludes_prompt_text(
        self, client: AsyncClient, kaihle_admin: User, db_session: AsyncSession
    ) -> None:
        app.dependency_overrides[get_current_user] = lambda: kaihle_admin

        db_session.add(_event())
        await db_session.commit()

        response = await client.get("/api/v1/platform/llm-logs", headers={"Authorization": "Bearer fake-token"})
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["logs"]) == 1
        assert "prompt_text" not in data["logs"][0]
        assert "response_text" not in data["logs"][0]
        assert data["logs"][0]["task"] == "question_generation"

    async def test_llm_logs_when_paginated_then_genuinely_bounded(
        self, client: AsyncClient, kaihle_admin: User, db_session: AsyncSession
    ) -> None:
        app.dependency_overrides[get_current_user] = lambda: kaihle_admin

        for _ in range(5):
            db_session.add(_event())
        await db_session.commit()

        response = await client.get(
            "/api/v1/platform/llm-logs",
            params={"page": 1, "page_size": 2},
            headers={"Authorization": "Bearer fake-token"},
        )
        data = response.json()
        assert len(data["logs"]) == 2
        assert data["total"] == 5


class TestLlmLogDetail:
    async def test_llm_log_detail_when_found_then_includes_prompt_and_response_text(
        self, client: AsyncClient, kaihle_admin: User, db_session: AsyncSession
    ) -> None:
        app.dependency_overrides[get_current_user] = lambda: kaihle_admin

        event = _event()
        db_session.add(event)
        await db_session.commit()

        response = await client.get(
            f"/api/v1/platform/llm-logs/{event.id}", headers={"Authorization": "Bearer fake-token"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["prompt_text"] == "[user] What is 2+2?"
        assert data["response_text"] == "4"

    async def test_llm_log_detail_when_not_found_then_404(self, client: AsyncClient, kaihle_admin: User) -> None:
        app.dependency_overrides[get_current_user] = lambda: kaihle_admin

        response = await client.get(
            f"/api/v1/platform/llm-logs/{uuid.uuid4()}", headers={"Authorization": "Bearer fake-token"}
        )
        assert response.status_code == 404

    async def test_llm_log_detail_when_caller_is_teacher_then_403(
        self, client: AsyncClient, teacher: User, db_session: AsyncSession
    ) -> None:
        app.dependency_overrides[get_current_user] = lambda: teacher

        event = _event()
        db_session.add(event)
        await db_session.commit()

        response = await client.get(
            f"/api/v1/platform/llm-logs/{event.id}", headers={"Authorization": "Bearer fake-token"}
        )
        assert response.status_code == 403
