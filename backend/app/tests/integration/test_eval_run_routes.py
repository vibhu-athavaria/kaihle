"""Integration tests for the Kaihle Admin evaluation-run routes (MLH-T18 slice 5b-ii). Real Postgres.

The Celery enqueue is replaced by a recorder (no broker in tests); everything else is real.
"""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.routes import platform as platform_routes
from app.core.database import get_db
from app.core.deps import get_current_user
from app.main import app
from app.models.eval_results import EvalRun
from app.models.school import School
from app.models.user import User, UserRole
from app.services.platform_settings_service import PlatformSettingsService

URL = "/api/v1/platform/eval-runs"
AUTH = {"Authorization": "Bearer fake-token"}
TASK = "question_generation"
WINDOW = {"window_start": "2026-10-01T00:00:00Z", "window_end": "2026-10-08T00:00:00Z"}
# Fields that would indicate leaked text; the response must expose none of them.
TEXT_FIELDS = {"prompt_text", "response_text", "evidence", "error", "message"}


@pytest_asyncio.fixture
async def enqueued(monkeypatch: pytest.MonkeyPatch) -> list[uuid.UUID]:
    calls: list[uuid.UUID] = []
    monkeypatch.setattr(platform_routes, "enqueue_eval_run", calls.append)
    return calls


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


async def _enable(db: AsyncSession, admin: User, tasks: list[str] | None = None) -> None:
    await PlatformSettingsService(db).update_eval_settings(
        actor_id=admin.id,
        monthly_budget_usd=Decimal("50"),
        enabled_tasks=[TASK] if tasks is None else tasks,
        sample_size_per_task=10,
        window_days=7,
        include_indicative=False,
        acknowledge_student_text_tasks=[],
    )


def _as(user: User) -> None:
    app.dependency_overrides[get_current_user] = lambda: user


async def _add_run(db: AsyncSession, seed: str, created_at: datetime) -> EvalRun:
    run = EvalRun(
        id=uuid.uuid4(),
        task=TASK,
        window_start=datetime(2026, 10, 1, tzinfo=UTC),
        window_end=datetime(2026, 10, 8, tzinfo=UTC),
        seed=seed,
        trigger="manual",
        created_at=created_at,
    )
    db.add(run)
    await db.commit()
    return run


@pytest.mark.parametrize(
    ("method", "path"),
    [("post", ""), ("get", ""), ("get", "/00000000-0000-4000-8000-000000000001")],
    ids=["post_create", "get_list", "get_one"],
)
async def test_eval_run_routes_when_unauthenticated_then_401(client: AsyncClient, method: str, path: str) -> None:
    response = await getattr(client, method)(URL + path)
    assert response.status_code == 401


@pytest.mark.parametrize(
    "role", [UserRole.SCHOOL_ADMIN, UserRole.TEACHER, UserRole.STUDENT, UserRole.PARENT], ids=lambda r: r.value
)
async def test_post_eval_run_when_not_kaihle_admin_then_403(
    client: AsyncClient, db_session: AsyncSession, school: School, role: UserRole, enqueued: list[uuid.UUID]
) -> None:
    caller = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"{role.value.lower()}-{uuid.uuid4().hex[:8]}@test.com",
        first_name="T",
        last_name=role.value,
        role=role,
        is_active=True,
    )
    db_session.add(caller)
    await db_session.commit()
    _as(caller)

    for response in (
        await client.post(URL, json={"task": TASK}, headers=AUTH),
        await client.get(URL, headers=AUTH),
        await client.get(f"{URL}/{uuid.uuid4()}", headers=AUTH),
    ):
        assert response.status_code == 403
    assert enqueued == []
    assert (await db_session.execute(select(func.count()).select_from(EvalRun))).scalar_one() == 0


async def test_post_eval_run_when_task_not_enabled_then_422(
    client: AsyncClient, db_session: AsyncSession, kaihle_admin: User, enqueued: list[uuid.UUID]
) -> None:
    await _enable(db_session, kaihle_admin, tasks=[])
    _as(kaihle_admin)

    response = await client.post(URL, json={"task": TASK, **WINDOW, "seed": "s1"}, headers=AUTH)

    assert response.status_code == 422
    assert TASK not in response.text  # generic message, input not echoed
    assert enqueued == []
    assert (await db_session.execute(select(func.count()).select_from(EvalRun))).scalar_one() == 0


@pytest.mark.parametrize(
    "body",
    [
        {"task": ""},
        {"task": TASK, "seed": ""},
        {"task": TASK, "window_start": "2026-10-08T00:00:00Z", "window_end": "2026-10-01T00:00:00Z"},
        {"task": TASK, "window_start": "2026-10-01T00:00:00", "window_end": "2026-10-08T00:00:00Z"},
    ],
    ids=["blank_task", "blank_seed", "unordered_window", "naive_start"],
)
async def test_post_eval_run_when_input_invalid_then_422_and_nothing_created(
    client: AsyncClient, db_session: AsyncSession, kaihle_admin: User, body: dict[str, str], enqueued: list[uuid.UUID]
) -> None:
    await _enable(db_session, kaihle_admin)
    _as(kaihle_admin)

    response = await client.post(URL, json=body, headers=AUTH)

    assert response.status_code == 422
    assert enqueued == []


async def test_post_eval_run_when_enabled_then_201_run_returned_and_enqueued_once(
    client: AsyncClient, db_session: AsyncSession, kaihle_admin: User, enqueued: list[uuid.UUID]
) -> None:
    await _enable(db_session, kaihle_admin)
    _as(kaihle_admin)

    response = await client.post(URL, json={"task": TASK, **WINDOW, "seed": "s1"}, headers=AUTH)

    assert response.status_code == 201
    body = response.json()
    assert body["task"] == TASK and body["status"] == "pending" and body["trigger"] == "manual"
    assert body["seed"] == "s1" and body["requested_by"] == str(kaihle_admin.id)
    assert body["spend_usd"] == "0.000000" and body["judge_model"] is None
    assert body["sampled_count"] == 0 and body["started_at"] is None
    assert TEXT_FIELDS.isdisjoint(body)
    assert enqueued == [uuid.UUID(body["id"])]


async def test_post_eval_run_when_repeated_then_existing_run_returned_and_not_enqueued_again(
    client: AsyncClient, db_session: AsyncSession, kaihle_admin: User, enqueued: list[uuid.UUID]
) -> None:
    await _enable(db_session, kaihle_admin)
    _as(kaihle_admin)
    payload = {"task": TASK, **WINDOW, "seed": "s1"}

    first = await client.post(URL, json=payload, headers=AUTH)
    second = await client.post(URL, json=payload, headers=AUTH)

    assert (first.status_code, second.status_code) == (201, 200)
    assert second.json()["id"] == first.json()["id"]
    assert len(enqueued) == 1
    assert (await db_session.execute(select(func.count()).select_from(EvalRun))).scalar_one() == 1


async def test_post_eval_run_when_bounds_and_seed_omitted_then_defaults_applied_and_each_call_is_new(
    client: AsyncClient, db_session: AsyncSession, kaihle_admin: User, enqueued: list[uuid.UUID]
) -> None:
    await _enable(db_session, kaihle_admin)
    _as(kaihle_admin)

    first = await client.post(URL, json={"task": TASK}, headers=AUTH)
    second = await client.post(URL, json={"task": TASK}, headers=AUTH)

    assert first.status_code == second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
    start = datetime.fromisoformat(first.json()["window_start"])
    end = datetime.fromisoformat(first.json()["window_end"])
    assert end - start == timedelta(days=7)
    assert len(enqueued) == 2


async def test_post_eval_run_when_enqueue_fails_then_503_without_leaking_cause(
    client: AsyncClient, db_session: AsyncSession, kaihle_admin: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(run_id: uuid.UUID) -> None:
        raise ConnectionError("redis://user:password@host")

    monkeypatch.setattr(platform_routes, "enqueue_eval_run", boom)
    await _enable(db_session, kaihle_admin)
    _as(kaihle_admin)

    response = await client.post(URL, json={"task": TASK, "seed": "s2"}, headers=AUTH)

    assert response.status_code == 503
    assert "password" not in response.text


async def test_get_eval_runs_when_called_then_paginated_newest_first(
    client: AsyncClient, db_session: AsyncSession, kaihle_admin: User
) -> None:
    base = datetime(2026, 10, 10, tzinfo=UTC)
    ids = [(await _add_run(db_session, f"seed-{i}", base + timedelta(hours=i))).id for i in range(5)]
    _as(kaihle_admin)

    page1 = (await client.get(URL, params={"page": 1, "page_size": 2}, headers=AUTH)).json()
    page3 = (await client.get(URL, params={"page": 3, "page_size": 2}, headers=AUTH)).json()

    assert [r["id"] for r in page1["runs"]] == [str(ids[4]), str(ids[3])]
    assert [r["id"] for r in page3["runs"]] == [str(ids[0])]
    assert (page1["total"], page1["page"], page1["page_size"]) == (5, 1, 2)


async def test_get_eval_runs_when_page_size_over_cap_or_page_zero_then_422(
    client: AsyncClient, kaihle_admin: User
) -> None:
    _as(kaihle_admin)

    assert (await client.get(URL, params={"page_size": 101}, headers=AUTH)).status_code == 422
    assert (await client.get(URL, params={"page": 0}, headers=AUTH)).status_code == 422


async def test_get_eval_runs_when_none_exist_then_empty_list(client: AsyncClient, kaihle_admin: User) -> None:
    _as(kaihle_admin)

    response = await client.get(URL, headers=AUTH)

    assert response.status_code == 200
    assert response.json()["runs"] == [] and response.json()["total"] == 0


async def test_get_eval_run_when_known_then_returns_it_and_when_unknown_then_404(
    client: AsyncClient, db_session: AsyncSession, kaihle_admin: User
) -> None:
    run = await _add_run(db_session, "seed-x", datetime(2026, 10, 10, tzinfo=UTC))
    _as(kaihle_admin)

    found = await client.get(f"{URL}/{run.id}", headers=AUTH)
    missing = await client.get(f"{URL}/{uuid.uuid4()}", headers=AUTH)

    assert found.status_code == 200 and found.json()["id"] == str(run.id)
    assert missing.status_code == 404
