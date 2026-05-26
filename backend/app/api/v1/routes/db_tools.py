"""DB Tools API — export and import the database from Kaihle Admin (dev only)."""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import tempfile
from collections.abc import AsyncGenerator
from datetime import date, datetime, time
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import MetaData as SAMetaData
from sqlalchemy import text
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import CurrentUser, require_role
from app.core.security import hash_password
from app.models.user import UserRole

logger = structlog.get_logger()

router = APIRouter(prefix="/db-tools", tags=["db-tools"])

# ── Helpers ──────────────────────────────────────────────────────────────────


def _get_psql_url(for_docker_exec: bool = False) -> str:
    """Return a plain postgresql:// URL suitable for psql/pg_dump.

    The app uses postgresql+asyncpg:// — strip the asyncpg driver prefix.
    Reads from pydantic settings (which loads .env) rather than os.environ
    directly, so it works whether DATABASE_URL is in the OS environment or
    only in the .env file.

    When ``for_docker_exec=True`` the URL is rewritten so the host:port point
    to localhost:5432 — the address postgres listens on *inside its own
    container*.  This is needed when psql runs via ``docker exec`` into the
    kaihle_postgres container: from inside that container, the host machine's
    ``localhost:5433`` does not resolve.
    """
    url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    if for_docker_exec:
        # Replace whatever host:port the app uses with the container-internal
        # address.  Pattern: postgresql://user:pass@HOST:PORT/db
        url = re.sub(r"@[^/]+/", "@localhost:5432/", url)
    return url


_PG_CONTAINER = "kaihle_postgres"  # docker-compose container name


def _pg_tool_cmd(tool: str) -> tuple[list[str], bool]:
    """Return (command_prefix, via_docker_exec) for a pg tool.

    ``via_docker_exec=True`` means the command will run inside the
    kaihle_postgres container — callers must use the container-internal DB URL
    (localhost:5432) rather than the host-facing URL.

    Precedence:
    1. Local tool present and version matches server → use it directly.
    2. Local tool missing or version mismatches → docker exec fallback.
    """
    try:
        local_result = subprocess.run([tool, "--version"], capture_output=True, text=True)
    except FileNotFoundError:
        return ["docker", "exec", "-i", _PG_CONTAINER, tool], True

    if local_result.returncode != 0:
        return ["docker", "exec", "-i", _PG_CONTAINER, tool], True

    # Check version matches server (major version must match).
    # pg_dump --version output: "pg_dump (PostgreSQL) 16.2" — extract first integer.
    local_ver_line = local_result.stdout.strip()
    ver_match = re.search(r"(\d+)\.\d+", local_ver_line)
    local_major = int(ver_match.group(1)) if ver_match else 0

    db_url = _get_psql_url()
    ver_result = subprocess.run(
        ["psql", db_url, "--tuples-only", "--no-align", "--command", "SHOW server_version_num;"],
        capture_output=True,
        text=True,
        timeout=5,
    )
    try:
        server_major = int(ver_result.stdout.strip()[:2])  # e.g. "160013" → 16
    except (ValueError, IndexError):
        server_major = 0

    if local_major != server_major and server_major > 0:
        return ["docker", "exec", "-i", _PG_CONTAINER, tool], True

    return [tool], False


def _check_pg_tools_available() -> None:
    """Raise 503 if neither local pg tools nor docker exec are usable."""
    db_url = _get_psql_url()
    if not db_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DATABASE_URL is not configured.",
        )

    # Verify we can actually reach pg_dump (local or via docker)
    cmd, _ = _pg_tool_cmd("pg_dump")
    cmd = cmd + ["--version"]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=10)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "pg_dump not available. "
                "On Render: ensure postgresql-client-16 is in the build command. "
                "In Docker: ensure postgresql-client-16 is installed. "
                "Locally: ensure Docker is running with the kaihle_postgres container."
            ),
        )
    if result.returncode != 0:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "pg_dump not available. "
                "On Render: ensure postgresql-client-16 is in the build command. "
                "In Docker: ensure postgresql-client-16 is installed. "
                "Locally: ensure Docker is running with the kaihle_postgres container."
            ),
        )


# Tables to skip in export — internal bookkeeping, not useful in dev
_EXPORT_EXCLUDED_PREFIXES = ("celery", "alembic_version")


def _pg_literal(value: Any) -> str:
    """Format a Python value as a PostgreSQL literal for INSERT statements.

    Handles all common Python types returned by SQLAlchemy row results.
    Single quotes inside strings are escaped as '' (standard SQL escaping).
    """
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        # bool must come before int — bool is a subclass of int in Python
        return "TRUE" if value else "FALSE"
    if isinstance(value, int | float | Decimal):
        return str(value)
    if isinstance(value, UUID):
        return f"'{value}'"
    if isinstance(value, datetime | date | time):
        return f"'{value.isoformat()}'"
    if isinstance(value, dict | list):
        escaped = json.dumps(value).replace("'", "''")
        return f"'{escaped}'"
    if isinstance(value, bytes):
        return f"'\\x{value.hex()}'"
    # str and any other type — stringify and escape single quotes
    escaped = str(value).replace("'", "''")
    return f"'{escaped}'"


# ── Schemas ───────────────────────────────────────────────────────────────────


class ImportResultResponse(BaseModel):
    status: str  # "completed" | "failed"
    output: str | None = None
    error: str | None = None
    users_updated: int = 0


# ── Export ────────────────────────────────────────────────────────────────────


@router.post("/export")
async def export_database(
    _: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Export all table data as SQL INSERT statements using SQLAlchemy reflection.

    Does NOT require pg_dump — works on any environment including Render's
    native Python runtime.  The output is a data-only dump (no DDL); schema
    is managed by Alembic so run ``alembic upgrade head`` after importing if
    the source DB is ahead of the target's migrations.

    Export format:
      1. TRUNCATE all tables (CASCADE handles FK order automatically).
      2. INSERT all rows in FK-dependency order (parents before children).
    """
    logger.info("db_export_started", method="python_reflection")

    async def _generate() -> AsyncGenerator[bytes, None]:
        yield b"-- Kaihle data export (data-only; schema managed by Alembic)\n"
        yield b"-- After importing, run: docker compose exec backend alembic upgrade head\n\n"

        # Reflect the live schema to discover tables and FK relationships.
        # run_sync wraps the synchronous MetaData.reflect() call so it executes
        # on the thread pool without blocking the event loop.
        meta = SAMetaData()
        conn = await db.connection()
        await conn.run_sync(meta.reflect)

        tables = [
            t
            for t in meta.sorted_tables  # parents before children (FK order)
            if not any(t.name.startswith(p) for p in _EXPORT_EXCLUDED_PREFIXES)
        ]

        if not tables:
            yield b"-- No tables found.\n"
            return

        # TRUNCATE in reverse dependency order (children first) so FK
        # constraints are not violated.  CASCADE handles any remaining deps.
        reversed_names = ", ".join(f'"{t.name}"' for t in reversed(tables))
        yield f"TRUNCATE TABLE {reversed_names} CASCADE;\n\n".encode()

        total_rows = 0
        for table in tables:
            rows_result = await db.execute(table.select())
            rows = rows_result.fetchall()

            if not rows:
                continue

            cols = [c.name for c in table.columns]
            col_list = ", ".join(f'"{c}"' for c in cols)

            yield f"-- {table.name} ({len(rows)} rows)\n".encode()
            for row in rows:
                values = ", ".join(_pg_literal(v) for v in row)
                yield f'INSERT INTO "{table.name}" ({col_list}) VALUES ({values});\n'.encode()
            yield b"\n"
            total_rows += len(rows)

        logger.info("db_export_complete", method="python_reflection", total_rows=total_rows)

    return StreamingResponse(
        _generate(),
        media_type="application/sql",
        headers={"Content-Disposition": 'attachment; filename="kaihle_export.sql"'},
    )


# ── Import ────────────────────────────────────────────────────────────────────


@router.post("/import", response_model=ImportResultResponse)
async def import_database(
    file: UploadFile,
    override_password: Annotated[str, "Password to set for all users after import"] = "test1234!",
    _: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> ImportResultResponse:
    """Import a plain-SQL dump into the current database.

    Steps:
    1. Write the uploaded SQL file to a temp location.
    2. Pipe it through ``psql`` against DATABASE_URL.
    3. Hash ``override_password`` with bcrypt and UPDATE all users.

    Intended for dev environments only — importing onto a production
    DATABASE_URL is not blocked here; use environment discipline.
    """
    if settings.environment == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Database import is disabled in production. Run this against a dev environment only.",
        )

    _check_pg_tools_available()

    if not file.filename or not file.filename.endswith(".sql"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .sql files are accepted. Export using the Export button above.",
        )

    logger.info("db_import_started", filename=file.filename)

    # ── Write upload to temp file ──────────────────────────────────────────
    with tempfile.NamedTemporaryFile(suffix=".sql", delete=False) as tmp:
        tmp_path = tmp.name
        content = await file.read()
        tmp.write(content)

    try:
        # ── Run psql ──────────────────────────────────────────────────────
        # Always pipe via stdin so the approach works identically whether
        # psql runs locally or inside a Docker container via docker exec -i.
        # (docker exec -i reads from the subprocess's stdin, so piping works;
        #  --file with a host path would fail inside the container.)
        #
        # When using docker exec into kaihle_postgres, rewrite the URL to
        # localhost:5432 — the host-facing port (5433) does not resolve from
        # inside the container.
        psql_prefix, via_docker = _pg_tool_cmd("psql")
        psql_url = _get_psql_url(for_docker_exec=via_docker)
        psql_cmd = psql_prefix + [
            "--set=ON_ERROR_STOP=off",  # continue on individual statement errors
            psql_url,
        ]

        with open(tmp_path, "rb") as sql_file:
            proc = await asyncio.create_subprocess_exec(
                *psql_cmd,
                stdin=sql_file,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        stdout_bytes, stderr_bytes = await proc.communicate()
        stdout_str = stdout_bytes.decode(errors="replace").strip()
        stderr_str = stderr_bytes.decode(errors="replace").strip()

        if proc.returncode not in (0, 3):  # 3 = psql warnings-only exit
            logger.error("db_import_failed", returncode=proc.returncode, stderr=stderr_str)
            return ImportResultResponse(
                status="failed",
                output=stdout_str or None,
                error=stderr_str or None,
                users_updated=0,
            )

        logger.info("db_import_psql_done", returncode=proc.returncode)

        # ── Reset passwords via SQLAlchemy (parameterised — no injection risk) ──
        # Never interpolate the hash into a SQL string; bcrypt hashes contain
        # $ and other characters that are unsafe in shell-interpolated psql --command.
        hashed_pw = hash_password(override_password)
        cursor: CursorResult[Any] = await db.execute(  # type: ignore[assignment]
            text("UPDATE users SET hashed_password = :pw WHERE hashed_password IS NOT NULL"),
            {"pw": hashed_pw},
        )
        await db.commit()
        users_updated = cursor.rowcount

        logger.info("db_import_passwords_reset", users_updated=users_updated)

        combined = "\n".join(s for s in [stdout_str, stderr_str] if s).strip() or None

        return ImportResultResponse(
            status="completed",
            output=combined,
            users_updated=users_updated,
        )

    finally:
        os.unlink(tmp_path)
