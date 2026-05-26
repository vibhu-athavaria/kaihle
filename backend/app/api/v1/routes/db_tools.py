"""DB Tools API — export and import the database from Kaihle Admin (dev only)."""

from __future__ import annotations

import asyncio
import os
import subprocess
import tempfile
from collections.abc import AsyncGenerator
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.config import settings
from app.core.deps import CurrentUser, require_role
from app.core.security import hash_password
from app.models.user import UserRole

logger = structlog.get_logger()

router = APIRouter(prefix="/db-tools", tags=["db-tools"])

# ── Helpers ──────────────────────────────────────────────────────────────────


def _get_psql_url() -> str:
    """Return a plain postgresql:// URL suitable for psql/pg_dump.

    The app uses postgresql+asyncpg:// — strip the asyncpg driver prefix.
    Reads from pydantic settings (which loads .env) rather than os.environ
    directly, so it works whether DATABASE_URL is in the OS environment or
    only in the .env file.
    """
    url = settings.database_url
    return url.replace("postgresql+asyncpg://", "postgresql://")


_PG_CONTAINER = "kaihle_postgres"  # docker-compose container name


def _pg_tool_cmd(tool: str) -> list[str]:
    """Return the command prefix to run a pg tool.

    When running inside Docker (production), the pg client tools from
    postgresql-client-16 are installed directly — use them as-is.

    When running locally outside Docker, the host pg_dump version may not
    match the server version (e.g. Homebrew pg14 vs Docker pg16).  In that
    case, delegate to the postgres container where the matching version lives:
        docker exec kaihle_postgres pg_dump ...
    """
    local_result = subprocess.run([tool, "--version"], capture_output=True, text=True)
    if local_result.returncode != 0:
        # Tool not found locally — try docker exec fallback
        return ["docker", "exec", "-i", _PG_CONTAINER, tool]

    # Check version matches server (major version must match)
    local_ver_line = local_result.stdout.strip()  # e.g. "pg_dump (PostgreSQL) 14.2"
    try:
        local_major = int(local_ver_line.split("PostgreSQL")[1].strip().split(".")[0].split()[0])
    except (IndexError, ValueError):
        local_major = 0

    # Server major version from DATABASE_URL is 16 (pgvector/pgvector:pg16)
    # Check actual server version via a quick query
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
        # Version mismatch — use pg tool from inside the postgres container
        return ["docker", "exec", "-i", _PG_CONTAINER, tool]

    return [tool]


def _check_pg_tools_available() -> None:
    """Raise 503 if neither local pg tools nor docker exec are usable."""
    db_url = _get_psql_url()
    if not db_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DATABASE_URL is not configured.",
        )

    # Verify we can actually reach pg_dump (local or via docker)
    cmd = _pg_tool_cmd("pg_dump") + ["--version"]
    result = subprocess.run(cmd, capture_output=True, timeout=10)
    if result.returncode != 0:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "pg_dump not available. "
                "In Docker: ensure postgresql-client-16 is installed. "
                "Locally: ensure Docker is running with the kaihle_postgres container."
            ),
        )


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
) -> StreamingResponse:
    """Run pg_dump against the current DATABASE_URL and stream the SQL file.

    Returns a plain-SQL dump with DROP statements so the file is safe to
    re-import multiple times without conflicts.
    """
    _check_pg_tools_available()

    db_url = _get_psql_url()
    if not db_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="DATABASE_URL is not configured in settings.",
        )

    cmd = _pg_tool_cmd("pg_dump") + [
        "--format=plain",
        "--clean",
        "--if-exists",
        "--no-owner",
        "--no-acl",
        "--no-privileges",
        # Skip celery internal tables — not useful in dev
        "--exclude-table=celery*",
        db_url,
    ]

    logger.info("db_export_started")

    # Write to a temp file first so we can detect pg_dump failures before
    # sending response headers. Streaming directly from stdout means an error
    # produces an empty HTTP 200 with no way to surface the cause.
    with tempfile.NamedTemporaryFile(suffix=".sql", delete=False) as tmp:
        dump_path = tmp.name

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_bytes, stderr_bytes = await proc.communicate()

        if proc.returncode != 0:
            os.unlink(dump_path)
            logger.error("db_export_failed", returncode=proc.returncode, stderr=stderr_bytes.decode())
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"pg_dump failed (exit {proc.returncode}): {stderr_bytes.decode()[:500]}",
            )

        with open(dump_path, "wb") as f:
            f.write(stdout_bytes)

        dump_size = len(stdout_bytes)
        logger.info("db_export_complete", size_bytes=dump_size)

    except HTTPException:
        raise
    except Exception as exc:
        if os.path.exists(dump_path):
            os.unlink(dump_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    async def _stream_file() -> AsyncGenerator[bytes, None]:
        try:
            with open(dump_path, "rb") as f:
                while True:
                    chunk = f.read(65536)
                    if not chunk:
                        break
                    yield chunk
        finally:
            if os.path.exists(dump_path):
                os.unlink(dump_path)

    return StreamingResponse(
        _stream_file(),
        media_type="application/sql",
        headers={
            "Content-Disposition": 'attachment; filename="kaihle_export.sql"',
            "Content-Length": str(dump_size),
        },
    )


# ── Import ────────────────────────────────────────────────────────────────────


@router.post("/import", response_model=ImportResultResponse)
async def import_database(
    file: UploadFile,
    override_password: Annotated[str, "Password to set for all users after import"] = "test1234!",
    _: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
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

    db_url = _get_psql_url()
    if not db_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="DATABASE_URL is not configured in settings.",
        )

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
        psql_cmd = _pg_tool_cmd("psql") + [
            "--set=ON_ERROR_STOP=off",  # continue on individual statement errors
            db_url,
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

        # ── Reset passwords ────────────────────────────────────────────────
        hashed_pw = hash_password(override_password)
        reset_cmd = _pg_tool_cmd("psql") + [
            "--tuples-only",
            "--no-align",
            "--command",
            f"UPDATE users SET hashed_password = '{hashed_pw}' WHERE hashed_password IS NOT NULL; "
            f"SELECT COUNT(*) FROM users WHERE hashed_password IS NOT NULL;",
            db_url,
        ]
        reset_proc = await asyncio.create_subprocess_exec(
            *reset_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        pw_stdout, pw_stderr = await reset_proc.communicate()
        users_updated_str = pw_stdout.decode(errors="replace").strip().split("\n")[-1]
        try:
            users_updated = int(users_updated_str)
        except ValueError:
            users_updated = 0

        logger.info("db_import_passwords_reset", users_updated=users_updated)

        combined = "\n".join(s for s in [stdout_str, stderr_str] if s).strip() or None

        return ImportResultResponse(
            status="completed",
            output=combined,
            users_updated=users_updated,
        )

    finally:
        os.unlink(tmp_path)
