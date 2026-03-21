# M6-3-T1 — Rate Limiting
**Milestone:** M6 · **Epic:** M6-3 · **Task:** T1
**Depends on:** M0-1-T2 (Redis infrastructure)
**Parallel with:** M6-1-T1, M6-2-T1, M6-3-T2
**Estimated effort:** 2–3 hours

---

## Context

Rate limiting uses `slowapi` (a Starlette-compatible wrapper over the `limits` library,
backed by Redis). It is applied as a FastAPI middleware and as per-route decorators on
the four route groups that need protection. `slowapi` is already in the project
requirements — verify it is present in `pyproject.toml` before starting, add it if
missing.

The limits below are v1 pilot limits appropriate for a school of up to 40 students.
They will be revisited before the product scales beyond the pilot.

---

## Rate Limit Targets

| Route | Limit | Key |
|---|---|---|
| `POST /api/v1/auth/login` | 10 requests / minute | Per IP address |
| `POST /api/v1/auth/magic-link` | 3 requests / minute | Per email in request body |
| `POST /api/v1/attempts/{id}/responses` | 60 requests / minute | Per authenticated user |
| Any route calling an LLM (lesson plan, study plan, analytics regenerate) | 20 requests / minute | Per school_id |

---

## Files to Create / Modify

```
backend/app/core/rate_limiting.py           ← CREATE: limiter instance + helpers
backend/app/main.py                         ← MODIFY: register slowapi middleware
backend/app/api/v1/routes/auth.py           ← MODIFY: add limiters to login + magic-link
backend/app/api/v1/routes/attempts.py       ← MODIFY: add limiter to submit_response
backend/app/tests/integration/test_rate_limiting.py  ← CREATE
```

---

## `rate_limiting.py`

```python
"""Rate limiting configuration and helpers.

Uses slowapi backed by Redis. Import `limiter` and apply it as a decorator
on individual routes that need protection.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request

# Global limiter instance backed by Redis (configured in main.py)
limiter = Limiter(key_func=get_remote_address)


def get_email_key(request: Request) -> str:
    """Key function for magic-link endpoint — rate-limits per email address."""
    try:
        body = request.state.body   # set by a middleware that caches the body
        return body.get("email", get_remote_address(request))
    except Exception:
        return get_remote_address(request)


def get_user_key(request: Request) -> str:
    """Key function for authenticated endpoints — rate-limits per user ID."""
    # JWT is already validated by this point; user is in request.state
    user = getattr(request.state, "user", None)
    if user:
        return f"user:{user.id}"
    return get_remote_address(request)


def get_school_key(request: Request) -> str:
    """Key function for LLM endpoints — rate-limits per school ID."""
    user = getattr(request.state, "user", None)
    if user and user.school_id:
        return f"school:{user.school_id}"
    return get_remote_address(request)


# Convenience limiter instances with their key functions
email_limiter = Limiter(key_func=get_email_key)
user_limiter = Limiter(key_func=get_user_key)
school_limiter = Limiter(key_func=get_school_key)
```

---

## `main.py` Changes

Add the slowapi exception handler and middleware. These must be registered before any
request reaches the route handlers:

```python
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from app.core.rate_limiting import limiter

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
```

The `_rate_limit_exceeded_handler` from slowapi returns HTTP 429 with a body
containing `error` and `detail` fields. However, this does not match our `ErrorDetail`
schema from `schemas/common.py`. Override it with a custom handler that returns the
correct shape:

```python
from app.schemas.common import ErrorDetail
from fastapi.responses import JSONResponse

async def custom_rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content=ErrorDetail(
            error_code="RATE_LIMIT_EXCEEDED",
            message=f"Too many requests. Please wait before trying again.",
            details={"retry_after": str(exc.retry_after)},
        ).model_dump(),
    )

app.add_exception_handler(RateLimitExceeded, custom_rate_limit_handler)
```

---

## Route Modifications

In `routes/auth.py`, add decorators to the login and magic-link handlers:

```python
from app.core.rate_limiting import limiter, email_limiter

@router.post("/login")
@limiter.limit("10/minute")
async def login(request: Request, body: LoginRequest, ...):
    ...

@router.post("/magic-link")
@email_limiter.limit("3/minute")
async def send_magic_link(request: Request, body: MagicLinkRequest, ...):
    ...
```

Note that `request: Request` must be added as the first parameter to any route
that uses a slowapi decorator — slowapi needs access to the request object.

In `routes/attempts.py`, add the user-scoped limit:

```python
from app.core.rate_limiting import user_limiter

@router.post("/{attempt_id}/responses", status_code=204)
@user_limiter.limit("60/minute")
async def submit_response(request: Request, attempt_id: UUID, ...):
    ...
```

---

## Acceptance Criteria

**Integration tests — `test_rate_limiting.py`**

`test_login_when_11_requests_in_one_minute_then_429_on_11th` — Send 10 login
requests from the same mocked IP address. All return 400 (wrong credentials is fine).
Send an 11th. Assert HTTP 429 on the 11th request.

`test_login_rate_limit_when_different_ip_then_independent_counter` — Send 10 requests
from IP A and 10 from IP B. Assert no 429 occurs for either IP (each IP has its own
counter).

`test_magic_link_when_4_requests_same_email_in_one_minute_then_429` — Send 3 magic
link requests for `test@example.com`. Assert all return 200 or 404. Send a 4th.
Assert HTTP 429.

`test_magic_link_when_different_email_then_independent_counter` — 3 requests for
`a@example.com` and 3 for `b@example.com`. Assert no 429 occurs.

`test_rate_limit_response_has_correct_error_code` — Trigger any rate limit. Assert
the response body has `error_code: "RATE_LIMIT_EXCEEDED"` and a `details.retry_after`
field.

`test_attempt_response_when_61_requests_same_user_then_429` — Send 60 authenticated
requests to `POST /attempts/{id}/responses` as the same user. Assert all succeed.
Send the 61st. Assert HTTP 429.

---

## Do NOT Touch

`backend/app/schemas/common.py` — `ErrorDetail` is frozen.
Any existing route decorator signatures except adding `request: Request` as first
parameter where needed by slowapi.
