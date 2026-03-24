# M0-10-T13 — Billing Read + Update Endpoints
**Milestone:** M0 · **Epic:** M0-10 — API Contract Finalization · **Task:** T13
**Depends on:** M0-10-T1 (schemas/common.py, CORS fix)
**Parallel with:** M0-10-T2 through T6 (Group B)
**Real implementation:** M6-2-T1 (billing enforcement), M6 (billing update)
**Estimated effort:** 2 hours

---

## Context

Two billing endpoints were identified as gaps in the API audit:
`GET /schools/{school_id}/billing` and `PATCH /schools/{school_id}/billing`.

The `GET` endpoint is needed by the school admin app to show the school's current
subscription tier, trial expiry, and student usage against their limit. This data
drives the upgrade CTA shown when a school is approaching their limit. It is also
shown on the school admin settings page so the admin knows what plan they are on.

The `PATCH` endpoint is for KaihleAdmin to update a school's subscription tier
(e.g. moving a school from TRIAL to STARTER after payment is confirmed). In v1
there is no self-serve payment flow — plan upgrades happen manually via a KaihleAdmin
action. School admins cannot change their own subscription tier.

Both endpoints are stubbed in this task. The real implementation of `GET` lands in
M6-2-T1 (alongside the billing enforcement logic). The `PATCH` implementation is
a M6 task with no separate task file yet — it will be a simple field update on the
`school_subscriptions` table.

---

## User Story

As a school admin, I want to see my current subscription tier, how many active
students I have against my limit, and when my trial expires, so I know when I need
to upgrade. As KaihleAdmin, I want to update a school's subscription tier without
needing direct database access.

---

## Files to Modify

```
backend/app/api/v1/routes/schools.py           ← MODIFY: add two new route handlers
backend/app/schemas/school.py                  ← MODIFY: add BillingResponse + BillingUpdateRequest
backend/app/tests/integration/test_billing_routes.py  ← CREATE
```

---

## New Schemas — Add to `schemas/school.py`

```python
class BillingResponse(BaseModel):
    """Billing and subscription details for a school.

    Shown on the school admin settings page and used to drive upgrade CTAs.
    All fields are read-only from the school admin's perspective.
    """
    school_id: uuid.UUID
    plan_tier: str           # "TRIAL" | "STARTER" | "GROWTH" | "SCALE"
    plan_name: str           # Human-readable: "Free Trial", "Starter Plan", etc.
    is_trial: bool
    trial_start: datetime | None    # None for non-trial plans
    trial_end: datetime | None      # None for non-trial plans
    trial_days_remaining: int | None # None for non-trial; 0 if expired
    is_trial_expired: bool
    max_students: int | None         # None = unlimited (SCALE tier)
    current_active_students: int     # current count — updated in real-time
    student_slots_remaining: int | None  # None = unlimited; 0 = at limit
    upgrade_url: str                 # always "https://kaihle.com/pricing"


class BillingUpdateRequest(BaseModel):
    """Update a school's subscription tier. KaihleAdmin only.

    In v1, plan changes are manual — KaihleAdmin confirms payment and updates
    the tier here. No self-serve payment flow exists yet.
    """
    plan_tier: str   # "TRIAL" | "STARTER" | "GROWTH" | "SCALE"
    # Optional: extend trial by N days (for trial schools only)
    extend_trial_days: int | None = None
```

---

## Tier Constants

These must match exactly the constants in `billing_service.py` (M6-2-T1). Define
them once in a shared location — `app/core/billing_constants.py` — and import from
there in both this task and M6-2-T1:

```python
# backend/app/core/billing_constants.py

TIER_LIMITS: dict[str, int | None] = {
    "TRIAL": 30,
    "STARTER": 100,
    "GROWTH": 500,
    "SCALE": None,   # None = unlimited
}

TIER_NAMES: dict[str, str] = {
    "TRIAL": "Free Trial",
    "STARTER": "Starter Plan",
    "GROWTH": "Growth Plan",
    "SCALE": "Scale Plan",
}

TRIAL_DURATION_DAYS: int = 15
UPGRADE_URL: str = "https://kaihle.com/pricing"
```

---

## New Route Handlers — Add to `routes/schools.py`

Add both handlers after the existing `update_school` handler.

### `GET /schools/{school_id}/billing`

```python
@router.get("/{school_id}/billing", response_model=BillingResponse)
async def get_school_billing(
    school_id: uuid.UUID,
    current_user: CurrentUser = Depends(
        require_role(UserRole.SCHOOL_ADMIN, UserRole.KAIHLE_ADMIN)
    ),
    db: AsyncSession = Depends(get_db),
) -> BillingResponse:
    """Get billing and subscription details for a school.

    SchoolAdmin: can only view their own school's billing.
    KaihleAdmin: can view any school's billing.
    """
    # CONSTITUTION Rule 12: KaihleAdmin bypass explicit
    if current_user.role != UserRole.KAIHLE_ADMIN:
        if current_user.school_id != school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot access billing for a different school",
            )

    # STUB — M0-10-T13 | Real implementation: M6-2-T1
    # M6 adds: load from school_subscriptions table, compute real student count,
    # compute trial_days_remaining from subscription.created_at.
    # Returns a stub response with TRIAL tier and zero counts until M6 ships.
    from app.core.billing_constants import TIER_LIMITS, TIER_NAMES, UPGRADE_URL
    from datetime import datetime, timezone, timedelta

    return BillingResponse(
        school_id=school_id,
        plan_tier="TRIAL",
        plan_name=TIER_NAMES["TRIAL"],
        is_trial=True,
        trial_start=None,       # M6 populates from school_subscriptions.created_at
        trial_end=None,         # M6 computes as trial_start + 15 days
        trial_days_remaining=15,
        is_trial_expired=False,
        max_students=TIER_LIMITS["TRIAL"],
        current_active_students=0,   # M6 queries users table
        student_slots_remaining=TIER_LIMITS["TRIAL"],
        upgrade_url=UPGRADE_URL,
    )
```

### `PATCH /schools/{school_id}/billing`

```python
@router.patch("/{school_id}/billing", response_model=BillingResponse)
async def update_school_billing(
    school_id: uuid.UUID,
    body: BillingUpdateRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> BillingResponse:
    """Update a school's subscription tier. KaihleAdmin only.

    Used when a school upgrades their plan after payment is confirmed.
    In v1, there is no self-serve payment flow — KaihleAdmin performs this
    action manually.
    """
    # STUB — M0-10-T13 | Real implementation: M6 (no separate task file yet)
    # M6 adds: update school_subscriptions.plan_tier, handle trial extension,
    # then return the updated BillingResponse.
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Billing tier updates are available from M6.",
    )
```

---

## Acceptance Criteria

**Stub behaviour (before M6-2-T1):**

`test_get_billing_when_school_admin_own_school_then_200_with_trial_stub` — Call
`GET /schools/{id}/billing` as school admin for their own school. Assert HTTP 200.
Assert the response has `plan_tier: "TRIAL"`, `is_trial: true`, `max_students: 30`,
and `upgrade_url: "https://kaihle.com/pricing"`.

`test_get_billing_when_school_admin_other_school_then_403` — Call as school admin for
a different school. Assert HTTP 403.

`test_get_billing_when_kaihle_admin_any_school_then_200` — Call as KaihleAdmin for
any school. Assert HTTP 200 (bypass applies).

`test_get_billing_when_teacher_then_403` — Call as teacher. Assert HTTP 403.

`test_get_billing_when_student_then_403` — Call as student. Assert HTTP 403.

`test_patch_billing_when_kaihle_admin_then_501` — Call `PATCH /schools/{id}/billing`
as KaihleAdmin with `{"plan_tier": "STARTER"}`. Assert HTTP 501 (stub until M6).

`test_patch_billing_when_school_admin_then_403` — Call as school admin. Assert HTTP 403.

**Real behaviour after M6-2-T1 replaces the stub:**

`test_get_billing_reflects_real_student_count` — Create 5 active students for the
school. Call `GET /schools/{id}/billing`. Assert `current_active_students: 5` and
`student_slots_remaining: 25` (30 - 5 for TRIAL tier).

`test_get_billing_trial_expired_when_over_15_days` — Create a school subscription
with `created_at` 16 days ago. Assert `is_trial_expired: true` and
`trial_days_remaining: 0`.

`test_patch_billing_upgrades_tier_when_kaihle_admin` — Call `PATCH` with
`{"plan_tier": "STARTER"}`. Assert HTTP 200 and the response shows
`plan_tier: "STARTER"`, `max_students: 100`.

---

## Frontend Usage

The school admin settings page uses this endpoint to render the billing section.
The student count bar and upgrade CTA are driven by this data. Add this hook to
`apps/school-admin/src/hooks/useSchoolAdmin.ts` (alongside the existing hooks from
M0-10-T10):

```typescript
export const useSchoolBilling = (schoolId: string) =>
  useQuery({
    queryKey: ['school-admin', 'billing', schoolId],
    queryFn: () => apiClient.get(`/schools/${schoolId}/billing`),
    enabled: !!schoolId,
    // Billing data changes rarely — 5 minute stale time is appropriate
    staleTime: 5 * 60 * 1000,
  })
```

The `student_slots_remaining` field drives a warning banner in the school admin
dashboard: show a yellow warning when `student_slots_remaining <= 5`, and a red
warning when `student_slots_remaining === 0`. These are pure frontend conditions
— no additional API calls needed.

---

## Do NOT Touch

`billing_service.py` — that file does not exist yet and is owned by M6-2-T1.
`schemas/common.py` — do not modify.
Any existing route handler in `schools.py`.
