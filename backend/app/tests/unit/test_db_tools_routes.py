"""Unit tests for the db-tools routes (export and import).

All subprocess calls are mocked — these tests verify route behaviour,
auth enforcement, error handling, and the production import guard
without actually running pg_dump or psql.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from app.core.database import get_db
from app.core.deps import get_current_user
from app.main import app
from app.models.user import UserRole

# ── Fixtures ──────────────────────────────────────────────────────────────────

FAKE_ADMIN_ID = uuid.uuid4()
FAKE_SCHOOL_ID = uuid.uuid4()

FAKE_KAIHLE_ADMIN = SimpleNamespace(
    id=FAKE_ADMIN_ID,
    email="kaihle-admin@kaihle.com",
    role=UserRole.KAIHLE_ADMIN,
    school_id=None,
    is_active=True,
)

FAKE_SCHOOL_ADMIN = SimpleNamespace(
    id=uuid.uuid4(),
    email="school-admin@school.com",
    role=UserRole.SCHOOL_ADMIN,
    school_id=FAKE_SCHOOL_ID,
    is_active=True,
)

SAMPLE_SQL_DUMP = b"-- PostgreSQL dump\nDROP TABLE IF EXISTS users;\nCREATE TABLE users (id uuid);\n"


def _make_mock_db(rowcount: int = 0, execute_return: MagicMock | None = None) -> AsyncMock:
    """Return a mock AsyncSession whose execute() returns a cursor with rowcount."""
    mock_cursor = MagicMock()
    mock_cursor.rowcount = rowcount
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=execute_return if execute_return is not None else mock_cursor)
    mock_db.commit = AsyncMock()
    # connection() returns an AsyncConnection mock that supports run_sync(meta.reflect)
    mock_conn = AsyncMock()
    mock_conn.run_sync = AsyncMock()
    mock_db.connection = AsyncMock(return_value=mock_conn)
    return mock_db


def _override_as_kaihle_admin(mock_db: AsyncMock | None = None) -> None:
    app.dependency_overrides[get_current_user] = lambda: FAKE_KAIHLE_ADMIN
    if mock_db is not None:
        app.dependency_overrides[get_db] = lambda: mock_db


def _override_as_school_admin() -> None:
    app.dependency_overrides[get_current_user] = lambda: FAKE_SCHOOL_ADMIN


def _clear_overrides() -> None:
    app.dependency_overrides.clear()


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_process(stdout: bytes = b"", stderr: bytes = b"", returncode: int = 0) -> MagicMock:
    """Return a mock asyncio subprocess with communicate() returning (stdout, stderr)."""
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    return proc


# ── Export tests ──────────────────────────────────────────────────────────────
#
# The export endpoint uses SQLAlchemy reflection (no pg_dump subprocess).
# We mock:
#   - SAMetaData so reflection returns a controlled set of tables
#   - db.execute() to return fake rows for each table
#   - db.connection() / conn.run_sync() to skip the actual DB reflection call


def _make_mock_table(name: str, columns: list[str], array_cols: set[str] | None = None) -> MagicMock:
    """Return a mock SQLAlchemy Table with the given name and column names.

    ``array_cols`` is an optional set of column names that should be typed as
    SAArray (text[], uuid[], etc.) so _pg_literal emits array literals.
    """
    from sqlalchemy import ARRAY as SAArray
    from sqlalchemy import Text

    table = MagicMock()
    table.name = name

    mock_cols = []
    for c in columns:
        col = MagicMock(name=c)
        col.name = c
        if array_cols and c in array_cols:
            col.type = SAArray(Text())
        else:
            col.type = Text()
        mock_cols.append(col)

    table.columns = mock_cols
    table.select = MagicMock(return_value=MagicMock())  # returns a selectable
    return table


@pytest.mark.asyncio
async def test_export_when_kaihle_admin_and_tables_have_rows_then_returns_sql_file() -> None:
    """POST /db-tools/export returns a SQL file containing TRUNCATE and INSERT statements."""
    mock_db = _make_mock_db()
    _override_as_kaihle_admin(mock_db=mock_db)

    fake_table = _make_mock_table("users", ["id", "email"])
    fake_rows = MagicMock()
    fake_rows.fetchall = MagicMock(return_value=[("abc123", "user@test.com")])
    mock_db.execute = AsyncMock(return_value=fake_rows)

    try:
        with patch("app.api.v1.routes.db_tools.SAMetaData") as mock_meta_cls:
            mock_meta = MagicMock()
            mock_meta.sorted_tables = [fake_table]
            mock_meta_cls.return_value = mock_meta

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post("/api/v1/db-tools/export")

        assert response.status_code == 200
        assert response.headers["content-disposition"] == 'attachment; filename="kaihle_export.sql"'
        body = response.text
        assert "TRUNCATE TABLE" in body
        assert 'INSERT INTO "users"' in body
        assert "abc123" in body
        assert "user@test.com" in body
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_export_when_tables_are_empty_then_returns_truncate_only() -> None:
    """POST /db-tools/export emits TRUNCATE but no INSERT when all tables are empty."""
    mock_db = _make_mock_db()
    _override_as_kaihle_admin(mock_db=mock_db)

    fake_table = _make_mock_table("users", ["id"])
    fake_rows = MagicMock()
    fake_rows.fetchall = MagicMock(return_value=[])
    mock_db.execute = AsyncMock(return_value=fake_rows)

    try:
        with patch("app.api.v1.routes.db_tools.SAMetaData") as mock_meta_cls:
            mock_meta = MagicMock()
            mock_meta.sorted_tables = [fake_table]
            mock_meta_cls.return_value = mock_meta

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post("/api/v1/db-tools/export")

        assert response.status_code == 200
        body = response.text
        assert "TRUNCATE TABLE" in body
        assert "INSERT" not in body
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_export_when_not_kaihle_admin_then_returns_403() -> None:
    """POST /db-tools/export is forbidden for non-KAIHLE_ADMIN roles."""
    _override_as_school_admin()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/db-tools/export")

        assert response.status_code == 403
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_export_excludes_celery_and_alembic_tables() -> None:
    """POST /db-tools/export skips celery_* and alembic_version tables."""
    mock_db = _make_mock_db()
    _override_as_kaihle_admin(mock_db=mock_db)

    users_table = _make_mock_table("users", ["id"])
    celery_table = _make_mock_table("celery_taskmeta", ["id"])
    alembic_table = _make_mock_table("alembic_version", ["version_num"])

    fake_rows = MagicMock()
    fake_rows.fetchall = MagicMock(return_value=[("row1",)])
    mock_db.execute = AsyncMock(return_value=fake_rows)

    try:
        with patch("app.api.v1.routes.db_tools.SAMetaData") as mock_meta_cls:
            mock_meta = MagicMock()
            mock_meta.sorted_tables = [users_table, celery_table, alembic_table]
            mock_meta_cls.return_value = mock_meta

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post("/api/v1/db-tools/export")

        body = response.text
        assert "celery_taskmeta" not in body
        assert "alembic_version" not in body
        assert "users" in body
    finally:
        _clear_overrides()


# ── Import tests ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_import_when_kaihle_admin_and_psql_succeeds_then_returns_completed() -> None:
    """POST /db-tools/import returns completed status and users_updated count."""
    # Password reset uses SQLAlchemy (parameterised) — mock the db session
    mock_db = _make_mock_db(rowcount=3)
    _override_as_kaihle_admin(mock_db=mock_db)

    try:
        with (
            patch("app.api.v1.routes.db_tools.settings") as mock_settings,
            patch("app.api.v1.routes.db_tools._check_pg_tools_available"),
            patch(
                "app.api.v1.routes.db_tools._get_psql_url",
                return_value="postgresql://kaihle:kaihle@localhost:5433/kaihle",
            ),
            patch("app.api.v1.routes.db_tools._pg_tool_cmd", return_value=(["psql"], False)),
            patch(
                "asyncio.create_subprocess_exec",
                return_value=_make_process(stdout=b"DROP TABLE\nCREATE TABLE\n", stderr=b""),
            ),
        ):
            mock_settings.environment = "development"
            mock_settings.database_url = "postgresql+asyncpg://kaihle:kaihle@localhost:5433/kaihle"

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/db-tools/import",
                    files={"file": ("kaihle_export.sql", SAMPLE_SQL_DUMP, "application/sql")},
                    data={"override_password": "devpass123!"},
                )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "completed"
        assert body["users_updated"] == 3

        # Verify parameterised query was used:
        # - execute() called once with a TextClause and a params dict
        # - plaintext password never appears (only the bcrypt hash under key "pw")
        mock_db.execute.assert_called_once()
        _, kwargs_or_params = mock_db.execute.call_args
        # call_args is (text_clause, params_dict) positionally
        call_params = mock_db.execute.call_args.args
        assert len(call_params) == 2
        param_dict = call_params[1]
        assert "pw" in param_dict
        assert param_dict["pw"].startswith("$2b$")  # bcrypt hash, not plaintext
        assert "devpass123!" not in str(mock_db.execute.call_args)
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_import_when_production_environment_then_returns_403() -> None:
    """POST /db-tools/import is blocked on production to prevent accidental overwrites."""
    _override_as_kaihle_admin(mock_db=_make_mock_db())
    try:
        with patch("app.api.v1.routes.db_tools.settings") as mock_settings:
            mock_settings.environment = "production"

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/db-tools/import",
                    files={"file": ("kaihle_export.sql", SAMPLE_SQL_DUMP, "application/sql")},
                    data={"override_password": "test1234!"},
                )

        assert response.status_code == 403
        assert "production" in response.json()["detail"].lower()
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_import_when_non_sql_file_then_returns_400() -> None:
    """POST /db-tools/import rejects files that don't end in .sql."""
    _override_as_kaihle_admin(mock_db=_make_mock_db())
    try:
        with (
            patch("app.api.v1.routes.db_tools.settings") as mock_settings,
            patch("app.api.v1.routes.db_tools._check_pg_tools_available"),
            patch(
                "app.api.v1.routes.db_tools._get_psql_url",
                return_value="postgresql://kaihle:kaihle@localhost:5433/kaihle",
            ),
        ):
            mock_settings.environment = "development"

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/db-tools/import",
                    files={"file": ("dump.txt", b"not sql", "text/plain")},
                    data={"override_password": "test1234!"},
                )

        assert response.status_code == 400
        assert ".sql" in response.json()["detail"]
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_import_when_psql_fails_then_returns_failed_status() -> None:
    """POST /db-tools/import returns failed status when psql exits non-zero."""
    _override_as_kaihle_admin(mock_db=_make_mock_db())
    try:
        with (
            patch("app.api.v1.routes.db_tools.settings") as mock_settings,
            patch("app.api.v1.routes.db_tools._check_pg_tools_available"),
            patch(
                "app.api.v1.routes.db_tools._get_psql_url",
                return_value="postgresql://kaihle:kaihle@localhost:5433/kaihle",
            ),
            patch("app.api.v1.routes.db_tools._pg_tool_cmd", return_value=(["psql"], False)),
            patch(
                "asyncio.create_subprocess_exec",
                return_value=_make_process(
                    stdout=b"",
                    stderr=b"psql: error: connection refused",
                    returncode=2,
                ),
            ),
        ):
            mock_settings.environment = "development"

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/db-tools/import",
                    files={"file": ("kaihle_export.sql", SAMPLE_SQL_DUMP, "application/sql")},
                    data={"override_password": "test1234!"},
                )

        assert response.status_code == 200  # HTTP 200 — failure is in the body
        body = response.json()
        assert body["status"] == "failed"
        assert body["users_updated"] == 0
        assert "connection refused" in (body["error"] or "")
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_import_when_not_kaihle_admin_then_returns_403() -> None:
    """POST /db-tools/import is forbidden for non-KAIHLE_ADMIN roles."""
    _override_as_school_admin()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/db-tools/import",
                files={"file": ("kaihle_export.sql", SAMPLE_SQL_DUMP, "application/sql")},
                data={"override_password": "test1234!"},
            )

        assert response.status_code == 403
    finally:
        _clear_overrides()


# ── _pg_tool_cmd unit tests ────────────────────────────────────────────────────


def test_pg_tool_cmd_when_local_version_matches_server_then_returns_local_tool() -> None:
    """_pg_tool_cmd returns (bare_tool, via_docker=False) when local and server versions match."""
    with (
        patch(
            "subprocess.run",
            side_effect=[
                MagicMock(returncode=0, stdout="pg_dump (PostgreSQL) 16.2"),
                MagicMock(returncode=0, stdout="160013"),
            ],
        ),
        patch(
            "app.api.v1.routes.db_tools._get_psql_url",
            return_value="postgresql://localhost/kaihle",
        ),
    ):
        from app.api.v1.routes.db_tools import _pg_tool_cmd

        cmd, via_docker = _pg_tool_cmd("pg_dump")

    assert cmd == ["pg_dump"]
    assert via_docker is False


def test_pg_tool_cmd_when_local_version_mismatches_server_then_returns_docker_exec() -> None:
    """_pg_tool_cmd returns (docker_exec_cmd, via_docker=True) on version mismatch."""
    with (
        patch(
            "subprocess.run",
            side_effect=[
                MagicMock(returncode=0, stdout="pg_dump (PostgreSQL) 14.5"),
                MagicMock(returncode=0, stdout="160013"),
            ],
        ),
        patch(
            "app.api.v1.routes.db_tools._get_psql_url",
            return_value="postgresql://localhost/kaihle",
        ),
    ):
        from app.api.v1.routes.db_tools import _pg_tool_cmd

        cmd, via_docker = _pg_tool_cmd("pg_dump")

    assert cmd == ["docker", "exec", "-i", "kaihle_postgres", "pg_dump"]
    assert via_docker is True


def test_pg_tool_cmd_when_tool_not_found_locally_then_returns_docker_exec() -> None:
    """_pg_tool_cmd returns docker exec fallback when tool exits non-zero."""
    with patch(
        "subprocess.run",
        return_value=MagicMock(returncode=1, stdout=""),
    ):
        from app.api.v1.routes.db_tools import _pg_tool_cmd

        cmd, via_docker = _pg_tool_cmd("pg_dump")

    assert cmd == ["docker", "exec", "-i", "kaihle_postgres", "pg_dump"]
    assert via_docker is True


def test_pg_tool_cmd_when_tool_raises_file_not_found_then_returns_docker_exec() -> None:
    """_pg_tool_cmd returns docker exec fallback when binary is not installed (FileNotFoundError)."""
    with patch(
        "subprocess.run",
        side_effect=FileNotFoundError("pg_dump: No such file or directory"),
    ):
        from app.api.v1.routes.db_tools import _pg_tool_cmd

        cmd, via_docker = _pg_tool_cmd("pg_dump")

    assert cmd == ["docker", "exec", "-i", "kaihle_postgres", "pg_dump"]
    assert via_docker is True


def test_check_pg_tools_available_when_binary_missing_raises_503() -> None:
    """_check_pg_tools_available raises HTTP 503 when pg_dump binary is not found (e.g. on Render)."""
    with (
        patch(
            "app.api.v1.routes.db_tools._pg_tool_cmd",
            return_value=(["pg_dump"], False),
        ),
        patch(
            "app.api.v1.routes.db_tools._get_psql_url",
            return_value="postgresql://localhost/kaihle",
        ),
        patch(
            "subprocess.run",
            side_effect=FileNotFoundError("pg_dump: No such file or directory"),
        ),
    ):
        from app.api.v1.routes.db_tools import _check_pg_tools_available

        with pytest.raises(HTTPException) as exc_info:
            _check_pg_tools_available()

    assert exc_info.value.status_code == 503
    assert "pg_dump not available" in exc_info.value.detail


def test_pg_literal_when_list_and_array_column_then_emits_pg_array_literal() -> None:
    """_pg_literal formats Python list as PostgreSQL array literal '{val1,val2}' for ARRAY columns."""
    from sqlalchemy import ARRAY as SAArray
    from sqlalchemy import Text

    from app.api.v1.routes.db_tools import _pg_literal

    col = MagicMock()
    col.type = SAArray(Text())

    result = _pg_literal(["MCQ", "TRUE_FALSE"], col)

    assert result == '\'{"MCQ","TRUE_FALSE"}\''


def test_pg_literal_when_list_and_non_array_column_then_emits_json_string() -> None:
    """_pg_literal formats Python list as JSON string for JSONB columns."""
    from sqlalchemy import JSON

    from app.api.v1.routes.db_tools import _pg_literal

    col = MagicMock()
    col.type = JSON()

    result = _pg_literal(["a", "b"], col)

    assert result == '\'["a", "b"]\''


def test_get_psql_url_when_for_docker_exec_then_rewrites_host_to_localhost() -> None:
    """_get_psql_url rewrites host:port to localhost:5432 when for_docker_exec=True."""
    with patch("app.api.v1.routes.db_tools.settings") as mock_settings:
        mock_settings.database_url = "postgresql+asyncpg://kaihle:secret@localhost:5433/kaihle"
        from app.api.v1.routes.db_tools import _get_psql_url

        normal = _get_psql_url(for_docker_exec=False)
        docker = _get_psql_url(for_docker_exec=True)

    assert normal == "postgresql://kaihle:secret@localhost:5433/kaihle"
    assert docker == "postgresql://kaihle:secret@localhost:5432/kaihle"
