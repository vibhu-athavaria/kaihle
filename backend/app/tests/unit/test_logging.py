"""Unit tests for structured logging and request logging middleware."""

import json
import logging
import uuid
from collections.abc import Callable, Coroutine
from typing import Any

import pytest
import structlog
from httpx import ASGITransport, AsyncClient
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from app.core.middleware import RequestLoggingMiddleware
from app.core.security import create_access_token


def _build_test_app(
    handler: Callable[..., Response | Coroutine[Any, Any, Response]] | None = None,
) -> Starlette:
    """Build a minimal Starlette app with RequestLoggingMiddleware for testing.

    We avoid importing the full FastAPI app to keep these tests isolated and fast.
    Using a lightweight Starlette app lets us test the middleware without hitting
    the database or other dependencies.
    """

    async def default_handler(request: Request) -> Response:
        return JSONResponse({"ok": True})

    routes = [
        Route("/test", handler or default_handler, methods=["GET", "POST"]),
    ]
    app = Starlette(routes=routes)
    app.add_middleware(RequestLoggingMiddleware)
    return app


@pytest.fixture(autouse=True)
def _setup_logging() -> None:
    """Ensure structlog is configured before each test.

    Use reset_defaults() to clear both the configuration AND the logger cache,
    then reconfigure with our test settings.
    """
    structlog.reset_defaults()
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )


# ---------------------------------------------------------------------------
# Tests required by the task file
# ---------------------------------------------------------------------------


async def test_request_logging_when_authenticated_then_user_id_in_log(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Authenticated request should include user_id and school_id in log."""
    user_id = uuid.uuid4()
    school_id = uuid.uuid4()
    token = create_access_token(user_id, school_id, "TEACHER")

    app = _build_test_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/test", headers={"Authorization": f"Bearer {token}"})

    captured = capsys.readouterr()
    log_line = _find_request_completed_log(captured.out)
    assert log_line is not None, f"No request_completed log found. Output:\n{captured.out}"
    assert log_line["user_id"] == str(user_id)
    assert log_line["school_id"] == str(school_id)


async def test_request_logging_when_unauthenticated_then_user_id_null(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Unauthenticated request should have null user_id and school_id."""
    app = _build_test_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/test")

    captured = capsys.readouterr()
    log_line = _find_request_completed_log(captured.out)
    assert log_line is not None, f"No request_completed log found. Output:\n{captured.out}"
    assert log_line["user_id"] is None
    assert log_line["school_id"] is None


async def test_request_logging_when_request_completes_then_duration_ms_present(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Completed request should include a non-negative duration_ms field."""
    app = _build_test_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/test")

    captured = capsys.readouterr()
    log_line = _find_request_completed_log(captured.out)
    assert log_line is not None, f"No request_completed log found. Output:\n{captured.out}"
    assert "duration_ms" in log_line
    assert isinstance(log_line["duration_ms"], int | float)
    assert log_line["duration_ms"] >= 0


async def test_request_id_when_two_requests_then_different_ids(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Each request should receive a unique request_id (UUID4)."""
    app = _build_test_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/test")
        await client.get("/test")

    captured = capsys.readouterr()
    logs = _find_all_request_completed_logs(captured.out)
    assert len(logs) >= 2, f"Expected >=2 request_completed logs, got {len(logs)}"

    request_ids = [log["request_id"] for log in logs]
    # Both should be valid UUIDs
    for rid in request_ids:
        uuid.UUID(rid)  # raises ValueError if not a valid UUID
    assert request_ids[0] != request_ids[1]


async def test_logging_middleware_when_handler_raises_then_request_still_logged(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """If the route handler raises, the middleware must still emit a log line."""

    async def failing_handler(request: Request) -> Response:
        raise RuntimeError("Intentional test failure")

    app = _build_test_app(handler=failing_handler)
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/test")
        # The server should return 500 (or similar) — we don't assert the exact
        # code because Starlette's error handling may vary, but the log MUST exist.
        assert response.status_code >= 500

    captured = capsys.readouterr()
    log_line = _find_request_completed_log(captured.out)
    assert log_line is not None, f"No request_completed log after exception. Output:\n{captured.out}"
    assert log_line["status_code"] == 500


# ---------------------------------------------------------------------------
# Additional coverage: log line field completeness
# ---------------------------------------------------------------------------


async def test_request_log_when_post_request_then_all_required_fields_present(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Every request_completed log must contain ALL fields from the spec."""
    app = _build_test_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/test")

    captured = capsys.readouterr()
    log_line = _find_request_completed_log(captured.out)
    assert log_line is not None

    required_fields = [
        "timestamp",
        "level",
        "event",
        "service",
        "request_id",
        "method",
        "path",
        "status_code",
        "duration_ms",
        "user_id",
        "school_id",
    ]
    for field in required_fields:
        assert field in log_line, f"Missing required field: {field}"

    assert log_line["event"] == "request_completed"
    assert log_line["service"] == "kaihle-api"
    assert log_line["method"] == "POST"
    assert log_line["path"] == "/test"
    assert log_line["status_code"] == 200


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_request_completed_log(output: str) -> dict[str, Any] | None:
    """Find the first request_completed JSON log line in captured output."""
    for line in output.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed: dict[str, Any] = json.loads(line)
            if parsed.get("event") == "request_completed":
                return parsed
        except json.JSONDecodeError:
            continue
    return None


def _find_all_request_completed_logs(output: str) -> list[dict[str, Any]]:
    """Find all request_completed JSON log lines in captured output."""
    results: list[dict[str, Any]] = []
    for line in output.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed: dict[str, Any] = json.loads(line)
            if parsed.get("event") == "request_completed":
                results.append(parsed)
        except json.JSONDecodeError:
            continue
    return results
