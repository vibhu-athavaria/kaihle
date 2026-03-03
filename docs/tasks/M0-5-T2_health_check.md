# M0-5-T2 — Health Check Endpoints
**Milestone:** M0 · **Epic:** M0-5 · **Task:** T2
**Depends on:** M0-2-T1 (DB migration), M0-1-T2 (Docker Compose with Redis)

---

## User Story
As an operator, I want `/health` and `/ready` endpoints so that Render's health probes know when the service is up and connected to its dependencies.

---

## Files to Create / Modify

```
backend/app/api/v1/routes/health.py
backend/app/main.py                   # register health router (no auth prefix)
backend/tests/integration/test_health.py
```

---

## Endpoints

### `GET /health`
Used by: monitoring, uptime checks, manual verification.

Response `200 OK`:
```json
{
  "status": "ok",
  "version": "2.1.0",
  "db": "connected",
  "redis": "connected"
}
```

Response `503 Service Unavailable` (if DB or Redis unreachable):
```json
{
  "status": "degraded",
  "version": "2.1.0",
  "db": "error",
  "redis": "connected"
}
```

### `GET /ready`
Used by: Render readiness probe (only routes traffic when ready).
Same logic as `/health`. Returns 200 only when BOTH db and redis are connected. Returns 503 otherwise.

---

## Implementation Notes

- Both endpoints are **unauthenticated** — no `require_role` dependency
- Register at **root level**, not under `/api/v1/` prefix, so Render probe works with plain `/health`
- DB check: run `SELECT 1` via async SQLAlchemy session — catch `OperationalError`
- Redis check: run `await redis_client.ping()` — catch `ConnectionError`
- Version string: read from `pyproject.toml` or `settings.APP_VERSION` env var
- These endpoints must NOT be logged at INFO level (too noisy) — log at DEBUG only

---

## Acceptance Criteria

- [ ] `GET /health` returns 200 with all fields when stack is healthy
- [ ] `GET /health` returns 503 with `"db": "error"` when PostgreSQL is stopped
- [ ] `GET /health` returns 503 with `"redis": "error"` when Redis is stopped
- [ ] `GET /ready` returns 200 only when both DB and Redis are connected
- [ ] Both endpoints require no authentication token
- [ ] Health checks do not appear in INFO-level logs (only DEBUG)

---

## Tests to Write

```python
test_health_when_all_services_up_then_200_ok()
test_health_when_db_down_then_503_with_db_error()
test_health_when_redis_down_then_503_with_redis_error()
test_ready_when_db_down_then_503()
test_health_when_no_auth_token_then_200_not_401()
```
