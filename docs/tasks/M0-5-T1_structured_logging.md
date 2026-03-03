# M0-5-T1 — Structured Logging
**Milestone:** M0 · **Epic:** M0-5 · **Task:** T1
**Depends on:** M0-2-T2 (models), M0-1-T1 (monorepo — pyproject.toml)

---

## User Story
As a developer and operator, I want every backend request to produce a structured JSON log line so I can search, filter, and alert on production issues without parsing unstructured text.

---

## Files to Create / Modify

```
backend/app/core/logging.py          # structlog configuration
backend/app/core/middleware.py       # request logging middleware
backend/app/main.py                  # register middleware
backend/tests/unit/test_logging.py
```

---

## Implementation

### `backend/app/core/logging.py`
```python
import structlog

def configure_logging(log_level: str = "INFO"):
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )
```

Call `configure_logging()` in `main.py` at startup before any routes load.

### Request Logging Middleware
Every request must produce one log line on completion containing ALL of these fields:

```json
{
  "timestamp": "2026-03-02T06:00:00Z",
  "level": "info",
  "event": "request_completed",
  "service": "kaihle-api",
  "request_id": "uuid4-generated-per-request",
  "method": "POST",
  "path": "/api/v1/auth/login",
  "status_code": 200,
  "duration_ms": 42,
  "user_id": "uuid-or-null",
  "school_id": "uuid-or-null"
}
```

`request_id` → generated as `uuid4()` at request start, injected into `structlog.contextvars` so it appears in all log lines during that request.

`user_id` / `school_id` → extracted from JWT if present, else `null`. Do NOT raise on missing token — logging middleware must never block a request.

### Usage in service layer
```python
import structlog
log = structlog.get_logger()

# Bind extra context
log.info("gap_states_calculated", student_id=str(student_id), subtopic_count=5)
log.error("llm_timeout", task="question_generation", duration_ms=8100)
```

---

## Log Levels Policy

| Level | When to use |
|---|---|
| `DEBUG` | Internal state, only in development |
| `INFO` | Normal operations (request completed, task started) |
| `WARNING` | Unexpected but recoverable (LLM retry, cache miss) |
| `ERROR` | Failures that need attention (LLM timeout, DB error) |

`LOG_LEVEL` env var controls minimum level. Default: `INFO` in prod, `DEBUG` in dev.

---

## Acceptance Criteria

- [ ] `docker-compose up` — every HTTP request produces a single JSON log line on stdout
- [ ] Log line contains all required fields: `timestamp`, `level`, `event`, `service`, `request_id`, `method`, `path`, `status_code`, `duration_ms`, `user_id`, `school_id`
- [ ] `request_id` is unique per request (UUID4)
- [ ] `user_id` is populated for authenticated requests, null for unauthenticated
- [ ] Log middleware never raises an exception or blocks a request
- [ ] `LOG_LEVEL=DEBUG` env var enables debug logs
- [ ] Service layer can call `structlog.get_logger().info(...)` and fields appear in output

---

## Tests to Write

```python
test_request_logging_when_authenticated_then_user_id_in_log()
test_request_logging_when_unauthenticated_then_user_id_null()
test_request_logging_when_request_completes_then_duration_ms_present()
test_request_id_when_two_requests_then_different_ids()
test_logging_middleware_when_handler_raises_then_request_still_logged()
```
