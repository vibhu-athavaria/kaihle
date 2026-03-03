# M6-3-T1 — Rate Limiting

**Milestone:** M6 — Analytics, Billing & Launch Polish
**Epic:** M6-3 — Production Readiness
**Task ID:** M6-3-T1
**Depends on:** M0-1-T2 (Redis running), M0-3-T2 (auth routes to protect)
**Blocks:** Nothing — can run in parallel with other M6 tasks

---

## User Story

As the platform, I want rate limiting on sensitive routes so that brute-force attacks, LLM cost abuse, and assessment spamming are prevented in production.

---

## What To Build

Add `slowapi` rate limiting to four route categories using Redis as the backend store. Each limit is per-IP or per-user depending on the route.

---

## Files To Modify

```
/backend/app/main.py              ← add SlowAPI middleware
/backend/app/core/rate_limit.py   ← NEW — limiter instance + limit decorators
/backend/app/api/v1/routes/
  auth.py                         ← add limits to login + magic-link routes
  assessments.py                  ← add limit to response submission
```

---

## Implementation

### `core/rate_limit.py`

```python
from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request

def get_school_id_from_request(request: Request) -> str:
    """
    Rate limit key for school-scoped LLM routes.
    Falls back to IP if school_id not in JWT (unauthenticated).
    """
    user = getattr(request.state, "user", None)
    if user and hasattr(user, "school_id") and user.school_id:
        return f"school:{user.school_id}"
    return get_remote_address(request)

def get_user_id_from_request(request: Request) -> str:
    """Rate limit key for per-user routes."""
    user = getattr(request.state, "user", None)
    if user:
        return f"user:{user.id}"
    return get_remote_address(request)

# Two limiters — one per IP, one per user/school
ip_limiter = Limiter(key_func=get_remote_address, storage_uri=settings.REDIS_URL)
user_limiter = Limiter(key_func=get_user_id_from_request, storage_uri=settings.REDIS_URL)
school_limiter = Limiter(key_func=get_school_id_from_request, storage_uri=settings.REDIS_URL)
```

### `main.py` additions

```python
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.core.rate_limit import ip_limiter

app.state.limiter = ip_limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

---

## Rate Limits Per Route

### Auth routes (`routes/auth.py`)

```python
from app.core.rate_limit import ip_limiter

@router.post("/login")
@ip_limiter.limit("10/minute")
async def login(request: Request, ...):
    ...

@router.post("/magic-link")
@ip_limiter.limit("3/minute", key_func=lambda req: req.body_email)
async def magic_link(request: Request, ...):
    # Key by email to prevent email enumeration at scale
    # Fallback: by IP if email not parseable
    ...
```

### Assessment response submission (`routes/assessments.py`)

```python
from app.core.rate_limit import user_limiter

@router.post("/attempts/{attempt_id}/responses")
@user_limiter.limit("60/minute")
async def submit_response(request: Request, attempt_id: UUID, ...):
    ...
```

### LLM-backed routes (study plans, lesson plan regeneration)

```python
from app.core.rate_limit import school_limiter

# Applied to:
# POST /classes/{class_id}/study-plans
# POST /lesson-plans/{plan_id}/regenerate

@router.post("/classes/{class_id}/study-plans")
@school_limiter.limit("20/minute")
async def assign_study_plans(request: Request, ...):
    ...
```

---

## Rate Limit Table

| Route | Limit | Key |
|---|---|---|
| `POST /auth/login` | 10 req/min | Per IP |
| `POST /auth/magic-link` | 3 req/min | Per email (fallback: IP) |
| `POST /attempts/{id}/responses` | 60 req/min | Per user |
| `POST /classes/{id}/study-plans` | 20 req/min | Per school |
| `POST /lesson-plans/{id}/regenerate` | 20 req/min | Per school |

---

## 429 Response Format

`slowapi` returns a default 429. Override to match Kaihle's structured error format:

```python
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse

async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={
            "error_code": "RATE_LIMIT_EXCEEDED",
            "message": f"Too many requests. Limit: {exc.limit}.",
            "retry_after_seconds": exc.retry_after,
        },
        headers={"Retry-After": str(exc.retry_after)},
    )

app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
```

---

## Acceptance Criteria

- [ ] Integration test: `POST /auth/login` 11 times in 60 seconds from same IP → 11th returns 429
- [ ] Integration test: 10 login attempts from IP-A + 10 from IP-B → all 20 succeed (limits are per-IP)
- [ ] Integration test: `POST /auth/magic-link` 4 times with same email in 60s → 4th returns 429
- [ ] Integration test: 61 `POST /attempts/{id}/responses` from same user in 60s → 61st returns 429
- [ ] Integration test: 429 response body contains `error_code`, `message`, `retry_after_seconds`
- [ ] Integration test: `Retry-After` header present on 429 response
- [ ] Integration test: LLM route `POST /study-plans` — 21 requests from same school in 60s → 21st returns 429
- [ ] Unit test: `get_school_id_from_request` returns school-scoped key for authenticated user
- [ ] Unit test: `get_school_id_from_request` falls back to IP for unauthenticated request

---

## Output (what M6-3-T5 needs)

- All four rate limit categories active in production
- 429 responses in correct Kaihle structured error format
- Redis confirmed as rate limit backend (same Redis used for caching + Celery)
