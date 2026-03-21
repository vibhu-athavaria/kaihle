# M6-2-T1 — Billing Tier Enforcement
**Milestone:** M6 · **Epic:** M6-2 · **Task:** T1
**Depends on:** M0-2-T2 (ORM models — school_subscriptions, subscription_plans)
**Parallel with:** M6-1-T1, M6-3-T1, M6-3-T2
**Estimated effort:** 3–4 hours

---

## Context

Billing enforcement is a lightweight service layer that intercepts two operations and
rejects them if the school has exceeded its tier limits. It does not handle payment
processing — that is out of scope for v1. It enforces limits so the platform stays
within the operational commitments made during the pilot.

Two enforcement points exist. First, student enrollment: before a student is added to
any class, the system checks whether the school has reached its maximum active student
count for its tier. Second, login: before issuing a JWT to any user at a TRIAL school,
the system checks whether the trial period has expired.

Both checks return HTTP 402 Payment Required with a structured `ErrorDetail` body. The
`error_code` is machine-readable so frontend code can detect it and show an upgrade
prompt.

Read CONSTITUTION.md Rule 2 (school_id on every table) before writing any code.
Read `schemas/common.py` for the `ErrorDetail` shape — use it exactly.

---

## User Story

As the system, I want to prevent a school from exceeding its billing tier limits so
that the platform stays within its operational commitments during the pilot.

---

## Files to Create / Modify

```
backend/app/services/billing_service.py         ← CREATE
backend/app/api/v1/routes/classes.py            ← MODIFY: add student limit check
backend/app/api/v1/routes/auth.py               ← MODIFY: add trial expiry check
backend/app/tests/unit/test_billing_service.py
backend/app/tests/integration/test_billing_enforcement.py
```

---

## Billing Tier Reference

| Tier | Max active students | Trial days |
|---|---|---|
| TRIAL | 30 | 15 |
| STARTER | 100 | — |
| GROWTH | 500 | — |
| SCALE | Unlimited | — |

These constants must live in `billing_service.py` as a dict, not hardcoded in the
route handlers:

```python
TIER_LIMITS: dict[str, int | None] = {
    "TRIAL": 30,
    "STARTER": 100,
    "GROWTH": 500,
    "SCALE": None,   # None = unlimited
}
TRIAL_DURATION_DAYS = 15
```

---

## `BillingService` — Full Method Signatures

### `check_student_limit`

```python
async def check_student_limit(
    self,
    school_id: uuid.UUID,
) -> None:
    """Raise HTTP 402 if the school has reached its active student limit.

    Called before every class enrollment INSERT. If the school's tier allows
    unlimited students (SCALE), this method returns immediately without querying.

    Raises:
        HTTPException(402): if the school has reached its student limit.
    """
```

Step 1 — Load the school's subscription:

```python
subscription = await self.db.scalar(
    select(SchoolSubscription).where(
        SchoolSubscription.school_id == school_id,
        SchoolSubscription.is_active.is_(True),
    )
)
if not subscription:
    # No subscription row means the school was created without one — treat as TRIAL
    tier = "TRIAL"
else:
    tier = subscription.plan.tier
```

Step 2 — Look up the limit. If `TIER_LIMITS[tier] is None`, return immediately.

Step 3 — Count current active students:

```python
current_count = await self.db.scalar(
    select(func.count())
    .select_from(User)
    .where(
        User.school_id == school_id,
        User.role == "STUDENT",
        User.is_active.is_(True),
    )
)
```

Step 4 — If `current_count >= limit`, raise:

```python
raise HTTPException(
    status_code=status.HTTP_402_PAYMENT_REQUIRED,
    detail={
        "error_code": "STUDENT_LIMIT_REACHED",
        "message": (
            f"Your school has reached its {tier} plan limit of "
            f"{limit} active students. Upgrade to enroll more students."
        ),
        "upgrade_url": "https://kaihle.com/pricing",
    },
)
```

### `check_trial_expired`

```python
async def check_trial_expired(
    self,
    school_id: uuid.UUID,
) -> None:
    """Raise HTTP 402 if the school's trial period has expired.

    Only checks TRIAL tier schools. Called during the login flow, before
    issuing a JWT. Does nothing for non-TRIAL schools.

    Raises:
        HTTPException(402): if the trial has expired.
    """
```

Step 1 — Load subscription. If tier is not TRIAL, return immediately.

Step 2 — Check the trial start date:

```python
trial_start = subscription.created_at  # or school.created_at if no separate field
trial_end = trial_start + timedelta(days=TRIAL_DURATION_DAYS)
if datetime.now(timezone.utc) > trial_end:
    raise HTTPException(
        status_code=status.HTTP_402_PAYMENT_REQUIRED,
        detail={
            "error_code": "TRIAL_EXPIRED",
            "message": (
                "Your free trial has ended. Upgrade to continue using Kaihle."
            ),
            "upgrade_url": "https://kaihle.com/pricing",
            "trial_ended_at": trial_end.isoformat(),
        },
    )
```

---

## Integration Points

### In `routes/classes.py` — `create_enrollments` endpoint

Add the billing check immediately after verifying the class exists and before
inserting the enrollment rows. The check is called once per enrollment request, not
per individual student in the batch:

```python
# In create_enrollments(), after the class ownership check:
billing = BillingService(db)
await billing.check_student_limit(school_id=class_.school_id)
# Then proceed with enrollment
```

### In `routes/auth.py` — `login` endpoint

Add the trial expiry check after successful credential verification but before
returning the JWT:

```python
# In login(), after service.login() succeeds:
billing = BillingService(db)
await billing.check_trial_expired(school_id=result.user.school_id)
return result
```

Do not add the trial check to the magic link flow — if a user has a magic link, they
should be able to reach the password setup page even if the trial has expired. The
trial check fires on credential-based login only.

---

## Acceptance Criteria

**Unit tests — `test_billing_service.py`**

`test_check_student_limit_when_trial_at_30_then_raises_402` — Seed a TRIAL school
with 30 active students. Call `check_student_limit`. Assert HTTP 402 is raised with
`error_code: "STUDENT_LIMIT_REACHED"`.

`test_check_student_limit_when_trial_at_29_then_no_error` — 29 active students on a
TRIAL school. Assert the method returns without raising.

`test_check_student_limit_when_scale_tier_then_never_raises` — 10,000 students on a
SCALE school. Assert the method returns without raising (no query even needed).

`test_check_student_limit_when_no_subscription_then_treated_as_trial` — A school with
no `school_subscriptions` row. Assert the TRIAL limit (30) is applied.

`test_check_trial_expired_when_trial_over_15_days_then_raises_402` — Seed a TRIAL
subscription created 16 days ago. Call `check_trial_expired`. Assert HTTP 402 with
`error_code: "TRIAL_EXPIRED"`.

`test_check_trial_expired_when_trial_14_days_then_no_error` — 14 days since creation.
Assert no exception raised.

`test_check_trial_expired_when_starter_tier_then_no_error` — A STARTER school with no
trial. Assert the method returns without raising regardless of subscription age.

**Integration tests — `test_billing_enforcement.py`**

`test_enrollment_when_trial_at_limit_then_enrollment_returns_402` — Seed a TRIAL
school at exactly 30 active students. POST to `POST /classes/{id}/enrollments`.
Assert HTTP 402 in the response.

`test_enrollment_when_below_limit_then_enrollment_succeeds` — 29 active students.
POST enrollment. Assert HTTP 200.

`test_login_when_trial_expired_then_returns_402` — Seed a TRIAL school created 20
days ago with valid credentials. POST to `POST /auth/login`. Assert HTTP 402.

`test_login_when_trial_active_then_returns_jwt` — Trial school created 5 days ago.
POST valid credentials. Assert HTTP 200 with access token returned.

---

## Do NOT Touch

`backend/app/api/v1/routes/assessments.py`. `backend/app/api/v1/routes/attempts.py`.
`backend/app/schemas/common.py` — the `ErrorDetail` shape is frozen from M0-10-T1.
Any existing migration file — add a new one if `school_subscriptions` table is missing.
