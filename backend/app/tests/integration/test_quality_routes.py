"""Integration tests for the Kaihle Admin Quality read APIs (MLH-T18 slice 6). Real Postgres."""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.main import app
from app.models.eval_results import EvalResult, EvalRun
from app.models.llm_usage import LlmUsageEvent
from app.models.school import School
from app.models.user import User, UserRole

BASE = "/api/v1/platform/quality"
AUTH = {"Authorization": "Bearer fake-token"}
# Mondays (UTC ISO week starts): 2026-10-05 and 2026-10-12.
WEEK_1 = datetime(2026, 10, 7, 12, tzinfo=UTC)
WEEK_2 = datetime(2026, 10, 14, 12, tzinfo=UTC)
WINDOW = {"window_start": "2026-10-01T00:00:00Z", "window_end": "2026-10-29T00:00:00Z"}


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


async def _run(db: AsyncSession, task: str = "question_generation", seed: str | None = None) -> EvalRun:
    run = EvalRun(
        id=uuid.uuid4(),
        task=task,
        window_start=datetime(2026, 10, 1, tzinfo=UTC),
        window_end=datetime(2026, 10, 8, tzinfo=UTC),
        seed=seed or uuid.uuid4().hex,
        trigger="manual",
    )
    db.add(run)
    await db.commit()
    return run


async def _usage_event(db: AsyncSession) -> uuid.UUID:
    row = LlmUsageEvent(
        id=uuid.uuid4(), task="question_generation", model="test/model-a", latency_ms=1, created_at=WEEK_1
    )
    db.add(row)
    await db.commit()
    return row.id


async def _result(
    db: AsyncSession,
    run: EvalRun,
    *,
    passed: bool | None,
    when: datetime = WEEK_1,
    check_name: str = "mcq_has_four_options",
    rubric_status: str | None = None,
    usage_event_id: uuid.UUID | None = None,
) -> None:
    judge = rubric_status is not None
    values: dict[str, Any] = {
        "id": uuid.uuid4(),
        "run_id": run.id,
        "usage_event_id": usage_event_id,
        "check_name": check_name,
        "kind": "judge" if judge else "deterministic",
        "passed": passed,
        "indeterminate": passed is None,
        "rubric_hash": "h" * 64 if judge else None,
        "rubric_status": rubric_status,
        "created_at": when,
    }
    db.add(EvalResult(**values))
    await db.commit()


async def _as(user: User) -> None:
    app.dependency_overrides[get_current_user] = lambda: user


class TestAuth:
    @pytest.mark.parametrize("path", ["/summary", "/failures", "/budget"])
    @pytest.mark.parametrize(
        "role", [UserRole.SCHOOL_ADMIN, UserRole.TEACHER, UserRole.STUDENT, UserRole.PARENT], ids=lambda r: r.value
    )
    async def test_quality_routes_when_not_kaihle_admin_then_403(
        self, client: AsyncClient, db_session: AsyncSession, school: School, role: UserRole, path: str
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
        await _as(caller)

        assert (await client.get(BASE + path, headers=AUTH)).status_code == 403

    @pytest.mark.parametrize("path", ["/summary", "/failures", "/budget"])
    async def test_quality_routes_when_unauthenticated_then_401(self, client: AsyncClient, path: str) -> None:
        assert (await client.get(BASE + path)).status_code == 401


class TestSummary:
    async def test_summary_when_no_results_then_empty_list_not_error(
        self, client: AsyncClient, kaihle_admin: User
    ) -> None:
        await _as(kaihle_admin)

        response = await client.get(BASE + "/summary", params=WINDOW, headers=AUTH)

        assert response.status_code == 200
        assert response.json()["rates"] == []

    async def test_summary_when_window_given_then_buckets_by_week(
        self, client: AsyncClient, kaihle_admin: User, db_session: AsyncSession
    ) -> None:
        run = await _run(db_session)
        await _result(db_session, run, passed=True, when=WEEK_1)
        await _result(db_session, run, passed=False, when=WEEK_1 + timedelta(days=1))
        await _result(db_session, run, passed=True, when=WEEK_2)
        await _result(db_session, run, passed=True, when=datetime(2026, 11, 20, tzinfo=UTC))  # outside window
        await _as(kaihle_admin)

        rates = (await client.get(BASE + "/summary", params=WINDOW, headers=AUTH)).json()["rates"]

        assert [(r["week_start"], r["passed"], r["failed"]) for r in rates] == [
            ("2026-10-05T00:00:00Z", 1, 1),
            ("2026-10-12T00:00:00Z", 1, 0),
        ]

    async def test_summary_when_bucket_none_then_one_row_for_whole_window(
        self, client: AsyncClient, kaihle_admin: User, db_session: AsyncSession
    ) -> None:
        run = await _run(db_session)
        await _result(db_session, run, passed=True, when=WEEK_1)
        await _result(db_session, run, passed=False, when=WEEK_2)
        await _as(kaihle_admin)

        rates = (await client.get(BASE + "/summary", params={**WINDOW, "bucket": "none"}, headers=AUTH)).json()["rates"]

        assert len(rates) == 1
        assert (rates[0]["week_start"], rates[0]["n"], rates[0]["pass_rate"]) == (None, 2, 0.5)

    async def test_summary_when_results_exist_then_pass_rate_per_task_and_check_with_n_and_wilson_interval(
        self, client: AsyncClient, kaihle_admin: User, db_session: AsyncSession
    ) -> None:
        run_a = await _run(db_session, task="question_generation")
        run_b = await _run(db_session, task="lesson_plan")
        for passed in (True, True, True, False):
            await _result(db_session, run_a, passed=passed)
        await _result(db_session, run_b, passed=True)
        await _as(kaihle_admin)

        rates = (await client.get(BASE + "/summary", params={**WINDOW, "bucket": "none"}, headers=AUTH)).json()["rates"]
        by_task = {r["task"]: r for r in rates}

        assert by_task["question_generation"]["n"] == 4
        assert by_task["question_generation"]["pass_rate"] == 0.75
        assert 0 < by_task["question_generation"]["ci_low"] < 0.75 < by_task["question_generation"]["ci_high"] < 1
        assert by_task["lesson_plan"]["n"] == 1

        filtered = (await client.get(BASE + "/summary", params={**WINDOW, "task": "lesson_plan"}, headers=AUTH)).json()[
            "rates"
        ]
        assert [r["task"] for r in filtered] == ["lesson_plan"]

    async def test_summary_when_indeterminate_present_then_reported_separately_and_excluded_from_denominator(
        self, client: AsyncClient, kaihle_admin: User, db_session: AsyncSession
    ) -> None:
        run = await _run(db_session)
        await _result(db_session, run, passed=True)
        await _result(db_session, run, passed=None, rubric_status="CALIBRATED", check_name="r1")
        await _result(db_session, run, passed=None, rubric_status="CALIBRATED", check_name="r1", usage_event_id=None)
        await _as(kaihle_admin)

        rates = (await client.get(BASE + "/summary", params={**WINDOW, "bucket": "none"}, headers=AUTH)).json()["rates"]
        judge = next(r for r in rates if r["check_name"] == "r1")

        assert (judge["indeterminate"], judge["n"], judge["pass_rate"]) == (2, 0, None)

    async def test_summary_when_rubric_indicative_then_status_returned_with_each_rate(
        self, client: AsyncClient, kaihle_admin: User, db_session: AsyncSession
    ) -> None:
        run = await _run(db_session)
        await _result(db_session, run, passed=True, rubric_status="INDICATIVE", check_name="r1")
        await _result(db_session, run, passed=True, rubric_status="CALIBRATED", check_name="r1")
        await _result(db_session, run, passed=True)
        await _as(kaihle_admin)

        rates = (await client.get(BASE + "/summary", params={**WINDOW, "bucket": "none"}, headers=AUTH)).json()["rates"]

        assert sorted((r["rubric_status"] or "", r["is_indicative"]) for r in rates) == [
            ("", False),
            ("CALIBRATED", False),
            ("INDICATIVE", True),
        ]

    async def test_summary_when_window_invalid_then_422(self, client: AsyncClient, kaihle_admin: User) -> None:
        await _as(kaihle_admin)

        response = await client.get(
            BASE + "/summary",
            params={"window_start": "2026-10-29T00:00:00Z", "window_end": "2026-10-01T00:00:00Z"},
            headers=AUTH,
        )

        assert response.status_code == 422

    async def test_summary_when_no_window_then_defaults_to_recent_and_succeeds(
        self, client: AsyncClient, kaihle_admin: User
    ) -> None:
        await _as(kaihle_admin)

        assert (await client.get(BASE + "/summary", headers=AUTH)).status_code == 200

    async def test_summary_query_when_run_then_uses_indexes_and_no_n_plus_one(
        self, client: AsyncClient, kaihle_admin: User, db_session: AsyncSession
    ) -> None:
        for task in ("question_generation", "lesson_plan", "concept_guide"):
            run = await _run(db_session, task=task)
            for check in ("a", "b", "c"):
                await _result(db_session, run, passed=True, check_name=check)
        await _as(kaihle_admin)
        statements: list[str] = []

        def record(conn: Any, cursor: Any, statement: str, *args: Any) -> None:
            statements.append(statement)

        sync_engine = db_session.get_bind()
        event.listen(sync_engine, "before_cursor_execute", record)
        try:
            response = await client.get(BASE + "/summary", params=WINDOW, headers=AUTH)
        finally:
            event.remove(sync_engine, "before_cursor_execute", record)

        assert len(response.json()["rates"]) == 9
        assert len([s for s in statements if "eval_results" in s]) == 1


class TestFailures:
    async def test_failures_when_called_then_returns_usage_event_ids_and_check_names_only(
        self, client: AsyncClient, kaihle_admin: User, db_session: AsyncSession
    ) -> None:
        run = await _run(db_session)
        event_id = await _usage_event(db_session)
        await _result(db_session, run, passed=False, usage_event_id=event_id, check_name="no_banned_phrase")
        await _result(db_session, run, passed=True, usage_event_id=await _usage_event(db_session))
        await _result(
            db_session,
            run,
            passed=None,
            rubric_status="CALIBRATED",
            usage_event_id=await _usage_event(db_session),
            check_name="r1",
        )
        await _result(db_session, run, passed=False, usage_event_id=None, check_name="purged")
        await _as(kaihle_admin)

        body = (await client.get(BASE + "/failures", params=WINDOW, headers=AUTH)).json()

        assert body["total"] == 1
        assert body["failures"] == [
            {
                "usage_event_id": str(event_id),
                "check_name": "no_banned_phrase",
                "task": "question_generation",
                "created_at": "2026-10-07T12:00:00Z",
            }
        ]

    async def test_failures_when_called_then_paginated_and_bounded(
        self, client: AsyncClient, kaihle_admin: User, db_session: AsyncSession
    ) -> None:
        run = await _run(db_session)
        for i in range(5):
            await _result(
                db_session,
                run,
                passed=False,
                usage_event_id=await _usage_event(db_session),
                when=WEEK_1 + timedelta(hours=i),
            )
        await _as(kaihle_admin)

        page_1 = (await client.get(BASE + "/failures", params={**WINDOW, "page_size": 2}, headers=AUTH)).json()
        page_3 = (
            await client.get(BASE + "/failures", params={**WINDOW, "page_size": 2, "page": 3}, headers=AUTH)
        ).json()

        assert (page_1["total"], len(page_1["failures"]), len(page_3["failures"])) == (5, 2, 1)
        assert page_1["failures"][0]["created_at"] > page_1["failures"][1]["created_at"]
        for too_big in (0, 101):
            response = await client.get(BASE + "/failures", params={**WINDOW, "page_size": too_big}, headers=AUTH)
            assert response.status_code == 422

    async def test_failures_when_check_filter_given_then_only_that_check(
        self, client: AsyncClient, kaihle_admin: User, db_session: AsyncSession
    ) -> None:
        run = await _run(db_session)
        await _result(db_session, run, passed=False, usage_event_id=await _usage_event(db_session), check_name="a")
        await _result(db_session, run, passed=False, usage_event_id=await _usage_event(db_session), check_name="b")
        await _as(kaihle_admin)

        body = (await client.get(BASE + "/failures", params={**WINDOW, "check_name": "b"}, headers=AUTH)).json()

        assert [f["check_name"] for f in body["failures"]] == ["b"]


class TestBudget:
    async def test_budget_when_never_configured_then_zero_everything(
        self, client: AsyncClient, kaihle_admin: User
    ) -> None:
        await _as(kaihle_admin)

        response = await client.get(BASE + "/budget", headers=AUTH)

        assert response.json() == {"monthly_budget_usd": 0, "month_to_date_spend_usd": 0, "remaining_usd": 0}

    async def test_budget_when_spend_recorded_then_remaining_reflects_it(
        self, client: AsyncClient, kaihle_admin: User, db_session: AsyncSession
    ) -> None:
        await _as(kaihle_admin)
        put = await client.put(
            "/api/v1/platform/eval-settings",
            headers=AUTH,
            json={
                "eval_monthly_budget_usd": "10.00",
                "eval_enabled_tasks": [],
                "eval_sample_size_per_task": 50,
                "eval_window_days": 7,
                "eval_include_indicative": False,
                "acknowledge_student_text_tasks": [],
            },
        )
        assert put.status_code == 200
        db_session.add(
            LlmUsageEvent(
                id=uuid.uuid4(),
                task="eval_judge",
                model="test/judge",
                component="eval_prod_sample",
                latency_ms=1,
                succeeded=True,
                estimated_cost_usd=Decimal("2.5"),
                created_at=datetime.now(UTC),
            )
        )
        await db_session.commit()

        body = (await client.get(BASE + "/budget", headers=AUTH)).json()

        assert body == {"monthly_budget_usd": 10, "month_to_date_spend_usd": 2.5, "remaining_usd": 7.5}
