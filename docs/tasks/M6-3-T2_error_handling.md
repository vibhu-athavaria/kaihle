# M6-3-T2 — Global Error Handling
**Milestone:** M6 · **Epic:** M6-3 · **Task:** T2
**Depends on:** M0-10-T1 (ErrorDetail schema defined in schemas/common.py)
**Parallel with:** M6-1-T1, M6-2-T1, M6-3-T1
**Estimated effort:** 2–3 hours

---

## Context

Every unhandled exception in the platform must return a structured JSON response using
the `ErrorDetail` shape from `schemas/common.py`. Stack traces must never reach the
client. Request IDs (from structlog context) must appear in every error response so
operators can correlate client-reported errors with server logs.

The `ErrorDetail` schema was deliberately defined in M0-10-T1 — months before this
task — precisely so that stub endpoints and all API responses could reference a
consistent shape from the beginning. This task is the final step that guarantees
every unhandled exception also uses that shape.

---

## User Story

As an operator, I want every API error to return a consistent structured JSON body so
I can build reliable frontend error handling and correlate errors with server logs.

---

## Files to Create / Modify

```
backend/app/core/error_handlers.py     ← CREATE: all exception handlers
backend/app/core/exceptions.py         ← CREATE: custom exception hierarchy
backend/app/main.py                    ← MODIFY: register exception handlers
backend/app/tests/integration/test_error_handling.py  ← CREATE
```

---

## Custom Exception Hierarchy (`exceptions.py`)

Define a base exception and a set of domain-specific subclasses. These are the
exceptions that services raise and route handlers map to HTTP responses. Using typed
exceptions rather than raw `HTTPException` in service code makes the intent explicit
and allows centralised mapping in the handler.

```python
"""Custom exception hierarchy for Kaihle.

Services raise these exceptions. The global error handler in error_handlers.py
maps them to HTTP status codes and ErrorDetail response bodies.
Never raise HTTPException directly from service code — only from route handlers.
"""

class KaihleBaseException(Exception):
    """Base class for all Kaihle domain exceptions.

    Attributes:
        error_code: Machine-readable code for frontend switch statements.
        message: Human-readable message, safe to display to end users.
        http_status: HTTP status code this exception maps to.
        details: Optional additional context (e.g. field-level errors).
    """
    error_code: str = "INTERNAL_ERROR"
    http_status: int = 500
    details: dict = {}

    def __init__(self, message: str, details: dict | None = None):
        self.message = message
        if details:
            self.details = details
        super().__init__(message)


class NotFoundError(KaihleBaseException):
    error_code = "NOT_FOUND"
    http_status = 404


class PermissionDeniedError(KaihleBaseException):
    error_code = "PERMISSION_DENIED"
    http_status = 403


class ValidationError(KaihleBaseException):
    error_code = "VALIDATION_ERROR"
    http_status = 422


class ConflictError(KaihleBaseException):
    error_code = "CONFLICT"
    http_status = 409


class BillingError(KaihleBaseException):
    """Raised by billing_service when a limit is exceeded."""
    error_code = "BILLING_LIMIT_EXCEEDED"
    http_status = 402
    upgrade_url: str = "https://kaihle.com/pricing"

    def __init__(self, message: str, upgrade_url: str | None = None):
        super().__init__(message)
        if upgrade_url:
            self.upgrade_url = upgrade_url
        self.details = {"upgrade_url": self.upgrade_url}
```

---

## Exception Handlers (`error_handlers.py`)

```python
"""FastAPI exception handlers.

Registered in main.py via register_exception_handlers(app).
Every handler returns a consistent ErrorDetail JSON body — never a stack trace.
"""

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import KaihleBaseException
from app.schemas.common import ErrorDetail

logger = structlog.get_logger()


def register_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers on the FastAPI app instance.

    Call this in main.py after creating the app instance:
        register_exception_handlers(app)
    """
    app.add_exception_handler(KaihleBaseException, _kaihle_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(Exception, _unhandled_exception_handler)


async def _kaihle_exception_handler(
    request: Request,
    exc: KaihleBaseException,
) -> JSONResponse:
    """Handle domain exceptions raised by services."""
    return JSONResponse(
        status_code=exc.http_status,
        content=ErrorDetail(
            error_code=exc.error_code,
            message=exc.message,
            details=exc.details,
        ).model_dump(),
    )


async def _validation_error_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Handle Pydantic validation errors (422 Unprocessable Entity)."""
    field_errors = {
        " → ".join(str(loc) for loc in err["loc"]): err["msg"]
        for err in exc.errors()
    }
    return JSONResponse(
        status_code=422,
        content=ErrorDetail(
            error_code="VALIDATION_ERROR",
            message="Request validation failed. Check the details for field errors.",
            details=field_errors,
        ).model_dump(),
    )


async def _http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    """Handle FastAPI/Starlette HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorDetail(
            error_code="HTTP_ERROR",
            message=str(exc.detail),
            details={},
        ).model_dump(),
    )


async def _unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Catch-all handler for unexpected exceptions.

    Logs the full traceback at ERROR level with the request_id for correlation.
    Returns a safe, opaque error message to the client.
    NEVER includes traceback, file paths, or variable names in the response.
    """
    request_id = structlog.contextvars.get_contextvars().get("request_id", "unknown")
    logger.error(
        "unhandled_exception",
        request_id=request_id,
        path=request.url.path,
        method=request.method,
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content=ErrorDetail(
            error_code="INTERNAL_ERROR",
            message=(
                "An unexpected error occurred. "
                f"If this persists, contact support with reference ID: {request_id}"
            ),
            details={},
        ).model_dump(),
    )
```

---

## `main.py` Change

Add this call after the FastAPI app is created but before any routes are registered:

```python
from app.core.error_handlers import register_exception_handlers
register_exception_handlers(app)
```

---

## Acceptance Criteria

**Integration tests — `test_error_handling.py`**

`test_not_found_error_returns_404_with_error_code` — Create a route that raises
`NotFoundError("Test resource not found")`. Call it. Assert HTTP 404 and the response
body has `error_code: "NOT_FOUND"` and the `message` field contains the error text.

`test_validation_error_returns_422_with_field_details` — Send a request to any
endpoint with a missing required field. Assert HTTP 422, `error_code: "VALIDATION_ERROR"`,
and the `details` dict contains the field name that failed.

`test_unhandled_exception_returns_500_without_traceback` — Create a route that raises
a bare `Exception("internal failure")`. Call it. Assert HTTP 500 and
`error_code: "INTERNAL_ERROR"`. Assert the response body contains no Python file
paths (no `.py` substrings), no class names from the traceback, and no variable names.
The assertion uses: `assert ".py" not in json.dumps(response.json())`.

`test_unhandled_exception_logs_at_error_level` — Using `caplog`, verify that the
unhandled exception handler emits a log record at ERROR level containing `exc_info`.

`test_http_exception_returns_correct_status_and_error_code` — Raise
`HTTPException(status_code=403, detail="Access denied")`. Assert HTTP 403 and
`error_code: "HTTP_ERROR"`.

`test_all_error_responses_have_error_code_and_message_fields` — For each of the
four handlers, assert the response always contains both `error_code` and `message`
fields. Neither field should ever be null or missing.

`test_existing_routes_still_work_after_handler_registration` — Call
`GET /health` after registering the handlers. Assert HTTP 200. This guards against
accidental breakage from middleware ordering.

---

## Do NOT Touch

`backend/app/schemas/common.py` — `ErrorDetail` is frozen from M0-10-T1. Use it
exactly as defined. Do not add fields to it here. Any existing route file — do not
change how routes raise HTTPException; that can be a gradual migration in a future
task.
