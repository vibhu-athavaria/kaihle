# M6-2-T1 — Billing Tier Enforcement

**Milestone:** M6 — Analytics, Billing & Launch Polish
**Epic:** M6-2 — Billing Tier Enforcement
**Task ID:** M6-2-T1
**Depends on:** M0-2-T1 (subscription tables migrated), M0-4-T3 (enrollment endpoint — billing check hooks in here)
**Blocks:** M6-3-T4 (pilot seed script must set up correct subscription tier)

---

## User Story

As Kaihle (the business), I want billing limits enforced automatically so that trial schools cannot exceed 30 students and expired trials are blocked from logging in, without requiring manual intervention.

---

## What To Build

A billing service with two core checks: student count limit enforcement (called before every enrollment) and trial expiry enforcement (called on every login for trial schools). Both return HTTP 402 on breach.

---

## Files To Create / Modify

```
/backend/app/core/
  billing.py                    ← NEW — billing enforcement functions

/backend/app/services/
  enrollment_service.py         ← MODIFY — call billing check before INSERT
  auth_service.py               ← MODIFY — call trial expiry check on login

/backend/app/schemas/
  billing.py                    ← NEW — 402 error response schema
```

---

## `billing.py`

```python
from datetime import datetime, timezone
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models import SchoolSubscription, SubscriptionPlan, ClassEnrollment, User

class BillingEnforcement:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def check_student_limit(self, school_id: UUID) -> None:
        """
        Called before every new class enrollment.
        Raises HTTP 402 if school has reached its subscription student limit.
        """
        subscription = await self._get_active_subscription(school_id)
        if subscription is None:
            raise HTTPException(
                status_code=402,
                detail={
                    "error_code": "NO_ACTIVE_SUBSCRIPTION",
                    "message": "This school does not have an active subscription.",
                    "upgrade_url": "https://kaihle.ai/pricing",
                }
            )

        plan = await self._get_plan(subscription.plan_id)

        if plan.max_students is None:
            return  # SCALE tier — unlimited

        # Count current active students (enrolled, not soft-deleted)
        current_count = await self._count_active_students(school_id)

        if current_count >= plan.max_students:
            raise HTTPException(
                status_code=402,
                detail={
                    "error_code": "STUDENT_LIMIT_REACHED",
                    "message": (
                        f"Your {plan.tier} plan allows up to {plan.max_students} students. "
                        f"You currently have {current_count}. "
                        f"Upgrade your plan to add more students."
                    ),
                    "current_count": current_count,
                    "limit": plan.max_students,
                    "upgrade_url": "https://kaihle.ai/pricing",
                }
            )

    async def check_trial_not_expired(self, school_id: UUID) -> None:
        """
        Called on every login attempt for TRIAL tier schools.
        Raises HTTP 402 if trial has expired.
        NOT called for paid tier schools.
        """
        subscription = await self._get_active_subscription(school_id)
        if subscription is None:
            return  # handled by check_student_limit on enrollment

        plan = await self._get_plan(subscription.plan_id)
        if plan.tier != "TRIAL":
            return  # only check trials

        if self.is_trial_expired(subscription):
            raise HTTPException(
                status_code=402,
                detail={
                    "error_code": "TRIAL_EXPIRED",
                    "message": (
                        f"Your free trial ended on {subscription.trial_end_date.strftime('%d %b %Y')}. "
                        f"Upgrade to continue using Kaihle."
                    ),
                    "trial_end_date": subscription.trial_end_date.isoformat(),
                    "upgrade_url": "https://kaihle.ai/pricing",
                }
            )

    @staticmethod
    def is_trial_expired(subscription) -> bool:
        if subscription.trial_end_date is None:
            return False
        return datetime.now(timezone.utc) > subscription.trial_end_date

    async def _get_active_subscription(self, school_id: UUID):
        result = await self.session.execute(
            select(SchoolSubscription)
            .where(SchoolSubscription.school_id == school_id)
            .where(SchoolSubscription.status == "ACTIVE")
        )
        return result.scalar_one_or_none()

    async def _count_active_students(self, school_id: UUID) -> int:
        result = await self.session.execute(
            select(func.count(User.id))
            .where(User.school_id == school_id)
            .where(User.role == "STUDENT")
            .where(User.is_active == True)
        )
        return result.scalar_one()
```

---

## Integration Points

### In `enrollment_service.py` — before INSERT into `class_enrollments`
```python
async def enroll_student(self, student_id, class_id, school_id, enrolled_by):
    # Billing check FIRST — before any DB write
    billing = BillingEnforcement(self.session)
    await billing.check_student_limit(school_id)

    # Proceed with enrollment
    ...
```

### In `auth_service.py` — in the `login()` method, after verifying password
```python
async def login(self, email: str, password: str) -> TokenPair:
    user = await self._verify_credentials(email, password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Trial expiry check (only for non-KaihleAdmin users with a school)
    if user.school_id and user.role != "KAIHLE_ADMIN":
        billing = BillingEnforcement(self.session)
        await billing.check_trial_not_expired(user.school_id)

    return await self._create_token_pair(user)
```

---

## Tier Limits Reference

| Tier | `max_students` | Trial days | `subscription_plans.trial_days` |
|---|---|---|---|
| TRIAL | 30 | 15 | 15 |
| STARTER | 100 | — | NULL |
| GROWTH | 500 | — | NULL |
| SCALE | NULL (unlimited) | — | NULL |

---

## 402 Error Response Schema (`schemas/billing.py`)

```python
class BillingErrorDetail(BaseModel):
    error_code: str     # STUDENT_LIMIT_REACHED | TRIAL_EXPIRED | NO_ACTIVE_SUBSCRIPTION
    message: str        # Human-readable, suitable for showing to school admin
    upgrade_url: str    # https://kaihle.ai/pricing
    current_count: int | None = None
    limit: int | None = None
    trial_end_date: str | None = None
```

Frontend must handle 402 responses by showing a clear upgrade prompt to SchoolAdmin.

---

## Acceptance Criteria

- [ ] Integration test: TRIAL school at 30 students → enrolling 31st returns 402 with `STUDENT_LIMIT_REACHED`
- [ ] Integration test: STARTER school at 100 → enrolling 101st returns 402
- [ ] Integration test: SCALE school → no limit, can enroll any number
- [ ] Integration test: TRIAL school with `trial_end_date` 16 days ago → login returns 402 with `TRIAL_EXPIRED`
- [ ] Integration test: TRIAL school with `trial_end_date` 5 days in future → login succeeds
- [ ] Integration test: STARTER school (paid) → no trial expiry check on login
- [ ] Integration test: KaihleAdmin login on expired trial school → NOT blocked (admin always passes)
- [ ] Unit test: `is_trial_expired` with `trial_end_date` yesterday → True
- [ ] Unit test: `is_trial_expired` with `trial_end_date` None → False
- [ ] Unit test: `check_student_limit` with no active subscription → 402 `NO_ACTIVE_SUBSCRIPTION`
- [ ] Unit test: SCALE tier (max_students=None) → `check_student_limit` returns without raising

---

## Output (what M6-3-T4 needs)

- `BillingEnforcement` class importable and tested
- `is_trial_expired` usable in pilot seed script to verify trial dates are set correctly
- Enrollment endpoint correctly gated — pilot school can enroll up to tier limit
