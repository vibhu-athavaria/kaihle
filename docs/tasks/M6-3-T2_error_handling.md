# M6-3-T2 — Global Error Handling
**Task ID:** M6-3-T2
**Milestone:** M6 — Analytics, Billing & Launch Polish
**Epic:** M6-3 — Production Readiness
**Depends on:** M0-1-T1 (monorepo), M0-3-T2 (auth routes exist to test against)
**Blocks:** M6-3-T5 (pre-launch checklist)

---

## User Story

As a developer and end user, I want all API errors to return structured, consistent JSON responses — never raw stack traces or unhandled exceptions — so that the frontend can display meaningful messages and security is not compromised.

---

## Context

Right now every unhandled exception in FastAPI leaks Python tracebacks to the client. Before going live this must be replaced with a global exception handler that:
- Returns structured JSON for every error type
- Never exposes internal details to clients
- Logs the full traceback server-side (structlog)
- Maps common exceptions to correct HTTP status codes

---

## Files to Create / Modify

```
backend/app/core/exceptions.py          CREATE — custom exception classes
backend/app/core/error_handlers.py      CREATE — FastAPI exception handlers
backend/app/main.py                     MODIFY — register handlers on app startup
backend/app/tests/unit/test_error_handlers.py   CREATE — unit tests
```

---

## Implementation Detail

### 1. Custom Exception Classes (`exceptions.py`)

```python
class KaihleBaseException(Exception):
    def __init__(self, message: str, error_code: str, status_code: int = 400):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code

class NotFoundError(KaihleBaseException):
    def __init__(self, resource: str, resource_id: str = ""):
        super().__init__(
            message=f"{resource} not found",
            error_code="NOT_FOUND",
            status_code=404
        )

class PermissionDeniedError(KaihleBaseException):
    def __init__(self, message: str = "Permission denied"):
        super().__init__(message=message, error_code="PERMISSION_DENIED", status_code=403)

class ValidationError(KaihleBaseException):
    def __init__(self, message: str, field: str = ""):
        super().__init__(message=message, error_code="VALIDATION_ERROR", status_code=422)

class ConflictError(KaihleBaseException):
    def __init__(self, message: str):
        super().__init__(message=message, error_code="CONFLICT", status_code=409)

class PaymentRequiredError(KaihleBaseException):
    def __init__(self, message: str, upgrade_url: str = "/billing"):
        self.upgrade_url = upgrade_url
        super().__init__(message=message, error_code="PAYMENT_REQUIRED", status_code=402)

class LLMTimeoutError(KaihleBaseException):
    def __init__(self, task: str):
        super().__init__(
            message=f"AI processing timed out for task: {task}",
            error_code="LLM_TIMEOUT",
            status_code=504
        )
```

### 2. Error Response Schema

All errors return this shape — no exceptions:

```json
{
  "error_code": "NOT_FOUND",
  "message": "Assessment not found",
  "details": {},
  "request_id": "uuid-from-middleware"
}
```

- `error_code`: machine-readable string (use in frontend switch statements)
- `message`: human-readable, safe to display
- `details`: optional dict for field-level errors (validation only)
- `request_id`: injected from structlog context — helps correlate server logs

### 3. Exception Handlers (`error_handlers.py`)

Register handlers for:

| Exception type | HTTP status | error_code |
|---|---|---|
| `KaihleBaseException` (and subclasses) | from exception | from exception |
| `RequestValidationError` (Pydantic/FastAPI) | 422 | `VALIDATION_ERROR` |
| `HTTPException` (FastAPI built-in) | from exception | `HTTP_ERROR` |
| `Exception` (catch-all) | 500 | `INTERNAL_ERROR` |

For the catch-all 500 handler:
- Log full traceback via `structlog` at ERROR level, including `request_id`
- Return only: `{ "error_code": "INTERNAL_ERROR", "message": "An unexpected error occurred. Please try again.", "request_id": "..." }`
- **Never include traceback, file paths, or variable names in the response body**

### 4. Register in `main.py`

```python
from app.core.error_handlers import register_exception_handlers

app = FastAPI()
register_exception_handlers(app)
```

---

## Acceptance Criteria

- [ ] Unit test: `NotFoundError` raised in a route → response is `404` with `error_code: "NOT_FOUND"`
- [ ] Unit test: unhandled `Exception` → response is `500` with `error_code: "INTERNAL_ERROR"`, no traceback in body
- [ ] Unit test: Pydantic `RequestValidationError` → `422` with `error_code: "VALIDATION_ERROR"`, `details` contains field errors
- [ ] Unit test: `PaymentRequiredError` → `402` with `upgrade_url` in response body
- [ ] Integration test: hit a route that raises `PermissionDeniedError` → `403` JSON response
- [ ] Security test: trigger an unhandled exception → response body contains NO Python file paths, class names, or variable values
- [ ] Log test: unhandled exception produces a structlog ERROR line with `request_id`, `exc_info=True`
- [ ] All existing routes still return correct responses after handler registration

---

## Output From This Task

- `exceptions.py` — importable custom exception classes used across all services
- `error_handlers.py` — registered on the FastAPI app
- Every unhandled error returns structured JSON, never a traceback
