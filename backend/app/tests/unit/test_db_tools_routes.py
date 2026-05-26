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


def _override_as_kaihle_admin():
    app.dependency_overrides[get_current_user] = lambda: FAKE_KAIHLE_ADMIN


def _override_as_school_admin():
    app.dependency_overrides[get_current_user] = lambda: FAKE_SCHOOL_ADMIN


def _clear_overrides():
    app.dependency_overrides.clear()


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_process(stdout: bytes = b"", stderr: bytes = b"", returncode: int = 0) -> MagicMock:
    """Return a mock asyncio subprocess with communicate() returning (stdout, stderr)."""
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    return proc


# ── Export tests ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_export_when_kaihle_admin_and_pg_dump_succeeds_then_returns_sql_file() -> None:
    """POST /db-tools/export returns a downloadable SQL file on success."""
    _override_as_kaihle_admin()
    try:
        with (
            patch(
                "app.api.v1.routes.db_tools._check_pg_tools_available",
            ),
            patch(
                "app.api.v1.routes.db_tools._get_psql_url",
                return_value="postgresql://kaihle:kaihle@localhost:5433/kaihle",
            ),
            patch(
                "app.api.v1.routes.db_tools._pg_tool_cmd",
                return_value=["pg_dump"],
            ),
            patch(
                "asyncio.create_subprocess_exec",
                return_value=_make_process(stdout=SAMPLE_SQL_DUMP),
            ),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post("/api/v1/db-tools/export")

        assert response.status_code == 200
        assert response.headers["content-disposition"] == 'attachment; filename="kaihle_export.sql"'
        assert response.content == SAMPLE_SQL_DUMP
        assert response.headers["content-length"] == str(len(SAMPLE_SQL_DUMP))
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_export_when_pg_dump_fails_then_returns_500_with_detail() -> None:
    """POST /db-tools/export returns 500 when pg_dump exits non-zero."""
    _override_as_kaihle_admin()
    try:
        with (
            patch("app.api.v1.routes.db_tools._check_pg_tools_available"),
            patch(
                "app.api.v1.routes.db_tools._get_psql_url",
                return_value="postgresql://kaihle:kaihle@localhost:5433/kaihle",
            ),
            patch("app.api.v1.routes.db_tools._pg_tool_cmd", return_value=["pg_dump"]),
            patch(
                "asyncio.create_subprocess_exec",
                return_value=_make_process(
                    stdout=b"",
                    stderr=b"pg_dump: error: server version mismatch",
                    returncode=1,
                ),
            ),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post("/api/v1/db-tools/export")

        assert response.status_code == 500
        assert "pg_dump failed" in response.json()["detail"]
        assert "server version mismatch" in response.json()["detail"]
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
async def test_export_when_pg_tools_unavailable_then_returns_503() -> None:
    """POST /db-tools/export returns 503 when pg_dump is not installed."""
    _override_as_kaihle_admin()
    try:
        with patch(
            "app.api.v1.routes.db_tools._check_pg_tools_available",
            side_effect=HTTPException(status_code=503, detail="pg_dump not found"),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post("/api/v1/db-tools/export")

        assert response.status_code == 503
    finally:
        _clear_overrides()


# ── Import tests ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_import_when_kaihle_admin_and_psql_succeeds_then_returns_completed() -> None:
    """POST /db-tools/import returns completed status and users_updated count."""
    _override_as_kaihle_admin()
    try:
        # psql call returns stdout with row count; password reset returns "3"
        psql_responses = [
            _make_process(stdout=b"DROP TABLE\nCREATE TABLE\n", stderr=b""),
            _make_process(stdout=b"3\n", stderr=b""),
        ]
        call_count = 0

        async def _fake_exec(*args, **kwargs):  # type: ignore[no-untyped-def]
            nonlocal call_count
            proc = psql_responses[call_count]
            call_count += 1
            return proc

        with (
            patch("app.api.v1.routes.db_tools.settings") as mock_settings,
            patch("app.api.v1.routes.db_tools._check_pg_tools_available"),
            patch(
                "app.api.v1.routes.db_tools._get_psql_url",
                return_value="postgresql://kaihle:kaihle@localhost:5433/kaihle",
            ),
            patch("app.api.v1.routes.db_tools._pg_tool_cmd", return_value=["psql"]),
            patch("asyncio.create_subprocess_exec", side_effect=_fake_exec),
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
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_import_when_production_environment_then_returns_403() -> None:
    """POST /db-tools/import is blocked on production to prevent accidental overwrites."""
    _override_as_kaihle_admin()
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
    _override_as_kaihle_admin()
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
    _override_as_kaihle_admin()
    try:
        with (
            patch("app.api.v1.routes.db_tools.settings") as mock_settings,
            patch("app.api.v1.routes.db_tools._check_pg_tools_available"),
            patch(
                "app.api.v1.routes.db_tools._get_psql_url",
                return_value="postgresql://kaihle:kaihle@localhost:5433/kaihle",
            ),
            patch("app.api.v1.routes.db_tools._pg_tool_cmd", return_value=["psql"]),
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
    """_pg_tool_cmd returns the bare tool name when local and server versions match."""
    with (
        patch(
            "subprocess.run",
            side_effect=[
                # pg_dump --version → v16
                MagicMock(returncode=0, stdout="pg_dump (PostgreSQL) 16.2"),
                # psql SHOW server_version_num → 160013
                MagicMock(returncode=0, stdout="160013"),
            ],
        ),
        patch(
            "app.api.v1.routes.db_tools._get_psql_url",
            return_value="postgresql://localhost/kaihle",
        ),
    ):
        from app.api.v1.routes.db_tools import _pg_tool_cmd

        result = _pg_tool_cmd("pg_dump")

    assert result == ["pg_dump"]


def test_pg_tool_cmd_when_local_version_mismatches_server_then_returns_docker_exec() -> None:
    """_pg_tool_cmd falls back to docker exec when local pg_dump version mismatches server."""
    with (
        patch(
            "subprocess.run",
            side_effect=[
                # pg_dump --version → v14 (mismatch)
                MagicMock(returncode=0, stdout="pg_dump (PostgreSQL) 14.5"),
                # psql SHOW server_version_num → 160013
                MagicMock(returncode=0, stdout="160013"),
            ],
        ),
        patch(
            "app.api.v1.routes.db_tools._get_psql_url",
            return_value="postgresql://localhost/kaihle",
        ),
    ):
        from app.api.v1.routes.db_tools import _pg_tool_cmd

        result = _pg_tool_cmd("pg_dump")

    assert result == ["docker", "exec", "-i", "kaihle_postgres", "pg_dump"]


def test_pg_tool_cmd_when_tool_not_found_locally_then_returns_docker_exec() -> None:
    """_pg_tool_cmd falls back to docker exec when tool is not installed locally."""
    with patch(
        "subprocess.run",
        return_value=MagicMock(returncode=1, stdout=""),
    ):
        from app.api.v1.routes.db_tools import _pg_tool_cmd

        result = _pg_tool_cmd("pg_dump")

    assert result == ["docker", "exec", "-i", "kaihle_postgres", "pg_dump"]
