# M6-1-T4 — Platform Operations Endpoints
**Milestone:** M6 · **Epic:** M6-1 · **Task:** T4
**Authors:** Kramer (engineering) · Pixel (design) · Vidhya (education)
**Depends on:** M6-1-T1 (analytics service), M6-3-T1 (rate limiting)
**Blocks:** M0-7-T5b (billing UI), M0-7-T5c (logs UI)
**Effort:** 4–5 hours

---

## Vidhya — Educational Context

**Trial extensions are educationally significant decisions.**

A trial extension isn't a billing formality — it's a statement of faith in a school's readiness to onboard. From Vidhya's experience, schools commonly need extensions for legitimate educational reasons:

- **School calendar pressure:** International schools often run their onboarding drive in September/January. If a trial starts in August, key staff are unavailable during curriculum preparation weeks.
- **Teacher PD requirement:** Cambridge and IB-registered schools require professional development sign-off before teachers use new tools in class. This often takes 2–4 weeks.
- **Student enrollment cycles:** Small international schools sometimes have late admissions that delay diagnostic cohort formation.

The mandatory `reason` field in the trial extension modal (min 10 chars) is not bureaucracy — it creates an audit trail that Vibhu can review when evaluating whether a school is genuinely progressing or stalling indefinitely. The reason text should guide Vibhu's decision-making in future conversations with the school. Require it and store it.

The **activity feed** on the platform overview is primarily useful for noticing school-level patterns: "School X invited 5 teachers in 2 days — they're serious" vs. "School Y hasn't had any user activity in 3 weeks — they may need check-in support." Design the activity feed to surface these signals.

---

## Pixel — Operator-Tool Design Principles

These are internal operator APIs consumed by the Kaihle Admin UI. No parent or teacher will ever call them. Design for the expert user case:

**Trial extension response:** The `AdminExtendTrialModal` needs exactly `new_trial_end` and `days_added` to update its UI optimistically after the API call. Include both. Don't make the UI do date arithmetic.

**Activity feed:** The `detail` field is the human-readable line that appears in the activity feed. It is plain text — no HTML, no markdown. It must be short enough to fit on one line at the font size used in the Kaihle Admin overview dashboard (approximately 60 characters). Kramer should enforce this in the service.

**Logs response:** The `LogEntry` schema feeds the dark terminal panel. Level must be an uppercase string matching `DEBUG|INFO|WARNING|ERROR|CRITICAL` exactly — the frontend colour-codes by this string. No variations, no sentence-case.

---

## Kramer — Engineering Spec

### Files

```
backend/app/api/v1/routes/platform.py       ← MODIFY: add 3 new endpoints
backend/app/schemas/platform.py             ← CREATE or MODIFY: new schemas
backend/app/services/platform_service.py   ← MODIFY: trial extension + activity
backend/app/services/log_service.py         ← CREATE: Redis log buffer reader
backend/app/tests/integration/test_platform_ops.py ← CREATE
```

### Schemas

```python
class TrialExtensionRequest(BaseModel):
    days: Literal[7, 14, 30]
    reason: str = Field(..., min_length=10, max_length=500)
    # Vidhya: reason is mandatory — creates audit trail for school relationship decisions

class TrialExtensionResponse(BaseModel):
    school_id: uuid.UUID
    previous_trial_end: datetime
    new_trial_end: datetime       # Pixel: UI needs this to update optimistically
    days_added: int               # Pixel: UI needs this too
    reason: str
    extended_by: uuid.UUID
    extended_at: datetime

class ActivityEvent(BaseModel):
    event_type: str
    school_name: str | None
    actor_email: str | None
    detail: str = Field(..., max_length=80)  # Pixel: must fit one line in the dashboard
    occurred_at: datetime

class LogEntry(BaseModel):
    timestamp: datetime
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    # Pixel: uppercase only — frontend colour-codes by exact string match
    service: str
    message: str
    request_id: str | None = None
    extra: dict = Field(default_factory=dict)
```

### Service Methods

**Trial extension (`platform_service.py`):**
```python
async def extend_trial(self, school_id: uuid.UUID, days: int, reason: str, admin_user_id: uuid.UUID) -> TrialExtensionResponse:
    sub = await self._get_active_subscription(school_id)
    if sub is None:
        raise ValueError("No active subscription found")
    if sub.tier != SubscriptionTier.TRIAL:
        raise ValueError("Trial extension only applies to TRIAL tier schools")
    previous_end = sub.trial_end_date
    sub.trial_end_date = previous_end + timedelta(days=days)
    extension = TrialExtension(
        school_id=school_id, extended_by=admin_user_id,
        days_added=days, reason=reason,
        previous_end=previous_end, new_end=sub.trial_end_date,
    )
    self.db.add(extension)
    await self.db.flush()
    return TrialExtensionResponse(...)
```

**Activity feed (`platform_service.py`):**
```python
async def get_recent_activity(self, limit: int = 10) -> list[ActivityEvent]:
    """
    Merges recent events from: school creations, user invitations,
    assessment publishes. Sorted by time desc, limited to N.
    Pixel: detail field max 80 chars — enforce truncation here, not in UI.
    Vidhya: useful for spotting schools that aren't progressing.
    """
```

**Log service (`log_service.py`):**
```python
class LogService:
    """Reads from Redis log buffer (key: 'kaihle:logs:buffer', max 1000 entries).
    Pixel: level values must be uppercase — DO NOT lowercase or title-case them.
    Degrades gracefully if Redis unavailable (returns warning entry, not 500).
    """
    async def get_logs(self, level: str | None, search: str | None, limit: int, offset: int) -> tuple[list[LogEntry], int]:
        ...
```

### Route Handlers

```python
@router.post("/admin/schools/{school_id}/trial-extension",
             response_model=TrialExtensionResponse, status_code=201)
async def extend_trial(school_id: uuid.UUID, body: TrialExtensionRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)), ...):
    ...

@router.get("/platform/activity", response_model=list[ActivityEvent])
async def get_platform_activity(limit: int = Query(10, ge=1, le=50),
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)), ...):
    ...

@router.get("/platform/logs", response_model=Page[LogEntry])
async def get_platform_logs(
    level: str | None = Query(None), q: str | None = Query(None),
    limit: int = Query(100, ge=1, le=100), offset: int = Query(0, ge=0),
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN))):
    ...
```

### Integration Tests

```python
class TestTrialExtension:
    async def test_extend_trial_school_admin_then_201_new_date(...)
    async def test_extend_trial_writes_audit_record(...)       # Vidhya: reason stored
    async def test_extend_trial_reason_too_short_then_422(...)  # Vidhya: mandatory
    async def test_extend_trial_non_trial_school_then_400(...)
    async def test_extend_trial_school_admin_role_then_403(...)
    async def test_response_includes_new_trial_end(...)        # Pixel: UI needs it
    async def test_response_includes_days_added(...)           # Pixel: UI needs it

class TestPlatformActivity:
    async def test_returns_list_sorted_newest_first(...)
    async def test_detail_field_under_80_chars(...)            # Pixel: fits one line
    async def test_school_admin_then_403(...)

class TestPlatformLogs:
    async def test_level_values_are_uppercase(...)             # Pixel: colour-code match
    async def test_level_filter_applied(...)
    async def test_degrades_gracefully_when_redis_unavailable(...) # Pixel: no 500
    async def test_non_kaihle_admin_then_403(...)
```

---

## Acceptance Criteria

- [ ] `POST /admin/schools/{id}/trial-extension` → 201 with `new_trial_end` + `days_added` (Pixel)
- [ ] Trial extension writes audit record to `trial_extensions` with reason stored (Vidhya)
- [ ] Reason < 10 chars → 422 (Vidhya)
- [ ] Extension on non-TRIAL school → 400 (Kramer)
- [ ] `GET /platform/activity` detail field ≤ 80 chars (Pixel)
- [ ] `GET /platform/logs` level values are uppercase only (Pixel)
- [ ] Logs endpoint degrades gracefully if Redis unavailable — returns warning entry, not 500 (Pixel)
- [ ] All three endpoints return 403 for non-KaihleAdmin roles (Kramer)
- [ ] All integration tests pass (Kramer)
- [ ] `mypy app/` passes with zero errors (Kramer)
