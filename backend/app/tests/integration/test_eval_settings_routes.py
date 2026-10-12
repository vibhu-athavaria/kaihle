"""Integration tests for GET/PUT /api/v1/platform/eval-settings (MLH-T18 slice 1)."""

import importlib.util
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.core.database import get_db
from app.core.deps import get_current_user
from app.main import app
from app.models.platform_settings import PlatformSettings
from app.models.school import School
from app.models.user import User, UserRole

URL = "/api/v1/platform/eval-settings"
AUTH = {"Authorization": "Bearer fake-token"}
MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "alembic" / "versions"


def _payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "eval_monthly_budget_usd": "25.00",
        "eval_enabled_tasks": ["question_generation"],
        "eval_sample_size_per_task": 40,
        "eval_window_days": 14,
        "eval_include_indicative": False,
        "acknowledge_student_text_tasks": [],
    }
    payload.update(overrides)
    return payload


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


async def _make_user(db_session: AsyncSession, role: UserRole, school: School) -> User:
    user = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"{role.value.lower()}-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Test",
        last_name=role.value,
        role=role,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


class TestEvalSettingsAuth:
    @pytest.mark.parametrize("method", ["get", "put"])
    @pytest.mark.parametrize(
        "role", [UserRole.SCHOOL_ADMIN, UserRole.TEACHER, UserRole.STUDENT, UserRole.PARENT], ids=lambda r: r.value
    )
    async def test_eval_settings_route_when_not_kaihle_admin_then_403(
        self, client: AsyncClient, db_session: AsyncSession, school: School, role: UserRole, method: str
    ) -> None:
        caller = await _make_user(db_session, role, school)
        app.dependency_overrides[get_current_user] = lambda: caller

        response = await client.request(method, URL, headers=AUTH, json=_payload() if method == "put" else None)

        assert response.status_code == 403
        assert (await db_session.execute(select(PlatformSettings))).first() is None

    @pytest.mark.parametrize("method", ["get", "put"])
    async def test_eval_settings_route_when_unauthenticated_then_401(self, client: AsyncClient, method: str) -> None:
        response = await client.request(method, URL, json=_payload() if method == "put" else None)

        assert response.status_code == 401


class TestEvalSettingsBehaviour:
    async def test_get_eval_settings_when_never_saved_then_defaults_returned_and_no_row_inserted(
        self, client: AsyncClient, kaihle_admin: User, db_session: AsyncSession
    ) -> None:
        app.dependency_overrides[get_current_user] = lambda: kaihle_admin

        response = await client.get(URL, headers=AUTH)

        assert response.status_code == 200
        body = response.json()
        assert body["eval_monthly_budget_usd"] == 0
        assert body["eval_enabled_tasks"] == []
        assert body["eval_sample_size_per_task"] == 50
        assert body["eval_window_days"] == 7
        assert body["eval_include_indicative"] is False
        assert "grade_open_answer" in body["tasks_with_student_text"]
        assert "question_generation" in body["available_tasks"]
        assert (await db_session.execute(select(PlatformSettings))).first() is None

    async def test_put_eval_settings_when_valid_then_get_returns_saved_values(
        self, client: AsyncClient, kaihle_admin: User
    ) -> None:
        app.dependency_overrides[get_current_user] = lambda: kaihle_admin

        put = await client.put(URL, headers=AUTH, json=_payload())
        get = await client.get(URL, headers=AUTH)

        assert put.status_code == 200
        assert get.json() == put.json()
        assert get.json()["eval_monthly_budget_usd"] == 25
        assert get.json()["eval_enabled_tasks"] == ["question_generation"]
        assert get.json()["updated_by"] == str(kaihle_admin.id)

    async def test_put_eval_settings_when_student_text_task_without_ack_then_422(
        self, client: AsyncClient, kaihle_admin: User, db_session: AsyncSession
    ) -> None:
        app.dependency_overrides[get_current_user] = lambda: kaihle_admin

        response = await client.put(URL, headers=AUTH, json=_payload(eval_enabled_tasks=["grade_open_answer"]))

        assert response.status_code == 422
        assert (await db_session.execute(select(PlatformSettings))).first() is None

    async def test_put_eval_settings_when_acknowledged_then_ack_exposed_with_actor(
        self, client: AsyncClient, kaihle_admin: User
    ) -> None:
        app.dependency_overrides[get_current_user] = lambda: kaihle_admin

        response = await client.put(
            URL,
            headers=AUTH,
            json=_payload(
                eval_enabled_tasks=["grade_open_answer"], acknowledge_student_text_tasks=["grade_open_answer"]
            ),
        )

        assert response.status_code == 200
        ack = response.json()["student_text_acknowledgements"]["grade_open_answer"]
        assert ack["acknowledged_by"] == str(kaihle_admin.id)
        assert ack["acknowledged_at"]

    @pytest.mark.parametrize(
        "override",
        [
            {"eval_monthly_budget_usd": "-1"},
            {"eval_sample_size_per_task": 201},
            {"eval_window_days": 0},
            {"eval_enabled_tasks": ["not_a_real_task"]},
        ],
        ids=["negative-budget", "sample-too-large", "window-too-small", "unknown-task"],
    )
    async def test_put_eval_settings_when_invalid_then_422_and_nothing_saved(
        self, client: AsyncClient, kaihle_admin: User, db_session: AsyncSession, override: dict[str, Any]
    ) -> None:
        app.dependency_overrides[get_current_user] = lambda: kaihle_admin

        response = await client.put(URL, headers=AUTH, json=_payload(**override))

        assert response.status_code == 422
        assert (await db_session.execute(select(PlatformSettings))).first() is None

    async def test_update_eval_settings_when_called_twice_with_same_payload_then_idempotent(
        self, client: AsyncClient, kaihle_admin: User, db_session: AsyncSession
    ) -> None:
        app.dependency_overrides[get_current_user] = lambda: kaihle_admin
        payload = _payload(
            eval_enabled_tasks=["grade_open_answer"], acknowledge_student_text_tasks=["grade_open_answer"]
        )

        first = await client.put(URL, headers=AUTH, json=payload)
        second = await client.put(URL, headers=AUTH, json=payload)

        assert first.status_code == second.status_code == 200
        assert first.json() == second.json()
        assert len((await db_session.execute(select(PlatformSettings))).all()) == 1


class TestPlatformSettingsConstraints:
    async def test_platform_settings_when_second_row_inserted_then_integrity_error(
        self, db_session: AsyncSession
    ) -> None:
        db_session.add(PlatformSettings(id=1))
        await db_session.commit()

        db_session.add(PlatformSettings(id=2))
        with pytest.raises(IntegrityError):
            await db_session.commit()

    @pytest.mark.parametrize(
        "column,value",
        [
            ("eval_monthly_budget_usd", -1),
            ("eval_sample_size_per_task", 0),
            ("eval_sample_size_per_task", 201),
            ("eval_window_days", 0),
            ("eval_window_days", 91),
        ],
    )
    async def test_platform_settings_when_value_out_of_range_then_integrity_error(
        self, db_session: AsyncSession, column: str, value: int
    ) -> None:
        db_session.add(PlatformSettings(id=1, **{column: value}))

        with pytest.raises(IntegrityError):
            await db_session.commit()

    async def test_platform_settings_when_inspected_then_has_no_school_id_column(self, engine: AsyncEngine) -> None:
        async with engine.connect() as conn:
            columns = await conn.run_sync(
                lambda c: {col["name"] for col in inspect(c).get_columns("platform_settings")}
            )

        assert "school_id" not in columns  # deliberate Rule 2 deviation (T18 D13)


def _load_migration() -> Any:
    matches = sorted(MIGRATIONS_DIR.glob("*add_platform_settings*.py"))
    assert len(matches) == 1, "expected exactly one platform_settings migration"
    spec = importlib.util.spec_from_file_location("platform_settings_migration", matches[0])
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def test_platform_settings_migration_when_applied_and_downgraded_then_clean(
    engine: AsyncEngine, db_session: AsyncSession
) -> None:
    """Runs the migration's own upgrade()/downgrade() against the real test database.

    The suite builds its schema with create_all, so the table is dropped first and the
    migration is the only thing that recreates it; the final upgrade leaves the schema as
    the other tests expect it.
    """
    migration = _load_migration()

    def table_exists(sync_conn: Any) -> bool:
        return bool(inspect(sync_conn).has_table("platform_settings"))

    def run(sync_conn: Any, step: str) -> None:
        with Operations.context(MigrationContext.configure(sync_conn)):
            getattr(migration, step)()

    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE platform_settings"))
        await conn.run_sync(run, "upgrade")
        assert await conn.run_sync(table_exists)
        await conn.run_sync(run, "downgrade")
        assert not await conn.run_sync(table_exists)
        await conn.run_sync(run, "upgrade")
        assert await conn.run_sync(table_exists)
