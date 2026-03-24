# M6-2-T1b — Billing API Routes
**Milestone:** M6 · **Epic:** M6-2 · **Task:** T1b
**Depends on:** M6-2-T1 (BillingService with limit checks), M0-10-T7 addendum (billing stubs created)
**Blocks:** M6-2-T2 (billing UI calls these three endpoints)
**Estimated effort:** 3–4 hours

---

## Context

The billing enforcement logic (`M6-2-T1`) already exists — `check_student_limit` and
`check_trial_expired` are called on enrollment and login respectively. This task adds
the read-only API surface that lets the school admin UI display the school's
subscription details, usage against limits, and invoice history.

The `billing.py` ORM models (`SubscriptionPlan`, `SchoolSubscription`,
`SubscriptionInvoice`) are already built and migrated. The three routes in this task
read from those tables — they do not write.

The billing stubs (`GET /schools/{id}/billing` and `PATCH /schools/{id}/billing`)
from the API endpoint map are replaced here. The `PATCH` endpoint is **not**
implemented in v1 — billing changes require Kaihle Admin intervention, not a
self-serve API call. The stub returns 501 and is intentionally left that way.

---

## User Story

As a school admin, I want to see my current subscription plan, usage against my
student limit, and invoice history so I can manage my school's billing relationship
with Kaihle.

---

## Files to Create / Modify

```
backend/app/api/v1/routes/schools.py         ← MODIFY: add three billing routes
backend/app/schemas/billing.py               ← CREATE: response schemas
backend/app/services/billing_service.py      ← MODIFY: add three read methods
backend/app/tests/integration/test_billing_routes.py  ← CREATE
```

---

## New Schemas (`schemas/billing.py`)

```python
"""Billing response schemas — read-only views of subscription data."""

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


class SubscriptionPlanResponse(BaseModel):
    id: UUID
    tier: str           # "TRIAL" | "STARTER" | "GROWTH" | "SCALE"
    name: str           # e.g. "Growth Plan"
    price_per_student_annual: float
    max_students: int | None        # None = unlimited
    max_curricula: int | None       # None = unlimited
    trial_days: int | None          # None for paid tiers
    features: dict                  # {"parent_portal": true, "api_access": false, ...}


class SchoolSubscriptionResponse(BaseModel):
    id: UUID
    school_id: UUID
    plan: SubscriptionPlanResponse
    status: str         # "ACTIVE" | "PAST_DUE" | "CANCELLED" | "EXPIRED"
    billing_cycle: str  # "annual" | "monthly"
    student_count: int  # agreed headcount at subscription time
    active_student_count: int       # current count — computed, not stored
    total_amount: float
    currency: str
    start_date: datetime
    end_date: datetime
    trial_end_date: datetime | None
    payment_status: str  # "PENDING" | "PAID" | "FAILED" | "REFUNDED"


class InvoiceResponse(BaseModel):
    id: UUID
    school_id: UUID
    invoice_number: str
    period_start: datetime
    period_end: datetime
    student_count: int
    amount: float
    currency: str
    status: str         # "PENDING" | "PAID" | "FAILED" | "REFUNDED"
    pdf_url: str | None  # None until PDF is generated (async)
    issued_at: datetime
```

---

## New Service Methods (add to `BillingService`)

### `get_school_subscription`

```python
async def get_school_subscription(
    self,
    school_id: uuid.UUID,
) -> SchoolSubscriptionResponse:
    """Return the active subscription for a school.

    Joins school_subscriptions → subscription_plans to build the full response.
    Also counts current active students so the UI can show usage vs limit.

    Raises:
        ValueError: if no active subscription found (returns 404 in the route).
    """
    subscription = await self.db.scalar(
        select(SchoolSubscription)
        .options(selectinload(SchoolSubscription.plan))
        .where(
            SchoolSubscription.school_id == school_id,
            SchoolSubscription.status.in_(["ACTIVE", "PAST_DUE"]),
        )
        .order_by(SchoolSubscription.created_at.desc())
        .limit(1)
    )
    if not subscription:
        raise ValueError(f"No active subscription found for school {school_id}")

    # Count current active students for the usage display
    active_student_count = await self.db.scalar(
        select(func.count())
        .select_from(User)
        .where(
            User.school_id == school_id,
            User.role == "STUDENT",
            User.is_active.is_(True),
        )
    ) or 0

    plan = subscription.plan
    return SchoolSubscriptionResponse(
        id=subscription.id,
        school_id=school_id,
        plan=SubscriptionPlanResponse(
            id=plan.id,
            tier=plan.tier,
            name=plan.name,
            price_per_student_annual=float(plan.price_per_student_annual),
            max_students=plan.max_students,
            max_curricula=plan.max_curricula,
            trial_days=plan.trial_days,
            features=plan.features,
        ),
        status=subscription.status,
        billing_cycle=subscription.billing_cycle,
        student_count=subscription.student_count,
        active_student_count=active_student_count,
        total_amount=float(subscription.total_amount),
        currency=subscription.currency,
        start_date=subscription.start_date,
        end_date=subscription.end_date,
        trial_end_date=subscription.trial_end_date,
        payment_status=subscription.payment_status,
    )
```

### `get_school_invoices`

```python
async def get_school_invoices(
    self,
    school_id: uuid.UUID,
    page: int,
    page_size: int,
) -> tuple[list[InvoiceResponse], int]:
    """Return paginated invoices for a school, newest first.

    Returns (invoices_list, total_count).
    """
    total = await self.db.scalar(
        select(func.count())
        .select_from(SubscriptionInvoice)
        .where(SubscriptionInvoice.school_id == school_id)
    ) or 0

    rows = await self.db.scalars(
        select(SubscriptionInvoice)
        .where(SubscriptionInvoice.school_id == school_id)
        .order_by(SubscriptionInvoice.period_start.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    return [
        InvoiceResponse(
            id=inv.id,
            school_id=inv.school_id,
            invoice_number=inv.invoice_number,
            period_start=inv.period_start,
            period_end=inv.period_end,
            student_count=inv.student_count,
            amount=float(inv.amount),
            currency=inv.currency,
            status=inv.status,
            pdf_url=inv.pdf_url,
            issued_at=inv.issued_at,
        )
        for inv in rows
    ], total
```

### `get_subscription_plans`

```python
async def get_subscription_plans(self) -> list[SubscriptionPlanResponse]:
    """Return all active subscription plans, ordered for plan comparison display."""
    rows = await self.db.scalars(
        select(SubscriptionPlan)
        .where(SubscriptionPlan.is_active.is_(True))
        .order_by(SubscriptionPlan.sort_order)
    )
    return [
        SubscriptionPlanResponse(
            id=p.id,
            tier=p.tier,
            name=p.name,
            price_per_student_annual=float(p.price_per_student_annual),
            max_students=p.max_students,
            max_curricula=p.max_curricula,
            trial_days=p.trial_days,
            features=p.features,
        )
        for p in rows
    ]
```

---

## Routes to Add to `routes/schools.py`

Add the following three routes to the existing `schools.py` router. They use
the `/schools/{school_id}` prefix that was established by M0-10-T7.

```python
# ── Billing routes ────────────────────────────────────────────────────────────

@router.get("/{school_id}/subscription", response_model=SchoolSubscriptionResponse)
async def get_school_subscription(
    school_id: uuid.UUID,
    current_user: CurrentUser = Depends(
        require_role(UserRole.SCHOOL_ADMIN, UserRole.KAIHLE_ADMIN)
    ),
    db: AsyncSession = Depends(get_db),
) -> SchoolSubscriptionResponse:
    """Get the current subscription for a school.

    School Admin sees own school only. KaihleAdmin sees any school (Rule 12 bypass).
    """
    # KaihleAdmin bypass per CONSTITUTION Rule 12
    if current_user.role != UserRole.KAIHLE_ADMIN:
        if current_user.school_id != school_id:
            raise HTTPException(status_code=403, detail="Access denied")

    service = BillingService(db)
    try:
        return await service.get_school_subscription(school_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="No active subscription found")


@router.get("/{school_id}/invoices", response_model=Page[InvoiceResponse])
async def list_school_invoices(
    school_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    current_user: CurrentUser = Depends(
        require_role(UserRole.SCHOOL_ADMIN, UserRole.KAIHLE_ADMIN)
    ),
    db: AsyncSession = Depends(get_db),
) -> Page[InvoiceResponse]:
    """List invoices for a school, newest first."""
    if current_user.role != UserRole.KAIHLE_ADMIN:
        if current_user.school_id != school_id:
            raise HTTPException(status_code=403, detail="Access denied")

    service = BillingService(db)
    invoices, total = await service.get_school_invoices(school_id, page, page_size)
    return Page(data=invoices, total=total, page=page, page_size=page_size)


@router.patch("/{school_id}/billing", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def update_school_billing(
    school_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Update billing subscription. KaihleAdmin only.

    Not implemented in v1 — subscription changes are handled offline.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "Self-serve subscription changes are not available in v1. "
            "Contact hello@kaihle.com to modify your subscription."
        ),
    )
```

---

## Global Subscription Plans Route

This route does not belong in `schools.py` — it is not school-scoped. Add it to a
new `routes/billing.py` file registered at the top level:

```python
# backend/app/api/v1/routes/billing.py

"""Billing API routes — global plan catalogue."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, get_current_user
from app.schemas.billing import SubscriptionPlanResponse
from app.services.billing_service import BillingService

router = APIRouter(tags=["billing"])


@router.get("/subscription-plans", response_model=list[SubscriptionPlanResponse])
async def list_subscription_plans(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SubscriptionPlanResponse]:
    """List all active subscription plans.

    Any authenticated user can read plan information — used by the billing
    page to populate the upgrade comparison tooltip.
    """
    service = BillingService(db)
    return await service.get_subscription_plans()
```

Register in `main.py`:
```python
from app.api.v1.routes import billing
app.include_router(billing.router, prefix="/api/v1")
```

---

## Acceptance Criteria

**Integration tests — `test_billing_routes.py`**

`test_get_subscription_when_school_admin_own_school_then_200_with_plan` — Seed a
`SchoolSubscription` with a GROWTH plan. Call `GET /schools/{id}/subscription` as
school admin. Assert HTTP 200 and `plan.tier == "GROWTH"` in the response.

`test_get_subscription_when_school_admin_other_school_then_403` — Call for another
school's subscription as school admin. Assert HTTP 403.

`test_get_subscription_when_kaihle_admin_any_school_then_200` — Call as KaihleAdmin
for any school. Assert HTTP 200 (Rule 12 bypass).

`test_get_subscription_includes_active_student_count` — Seed 5 active students for
the school. Assert `active_student_count == 5` in the response.

`test_get_subscription_when_no_subscription_then_404` — Call for a school with no
`school_subscriptions` row. Assert HTTP 404.

`test_get_subscription_trial_includes_trial_end_date` — Seed a TRIAL subscription.
Assert `trial_end_date` is non-null in the response.

`test_list_invoices_when_three_invoices_then_ordered_newest_first` — Seed three
invoices for different periods. Assert the first item in `data` has the most recent
`period_start`.

`test_list_invoices_when_no_invoices_then_empty_page` — No invoices seeded. Assert
HTTP 200 with `data: []` and `total: 0`.

`test_list_invoices_when_other_school_admin_then_403` — Call as a school admin for
a different school's invoices. Assert HTTP 403.

`test_update_billing_returns_501` — Call `PATCH /schools/{id}/billing` with any
role. Assert HTTP 501 with a message about contacting support.

`test_list_subscription_plans_when_authenticated_then_200_with_plans` — Seed two
active plans. Assert HTTP 200 and both plans appear in the response.

`test_list_subscription_plans_when_unauthenticated_then_401` — Call without a JWT.
Assert HTTP 401.

---

## Do NOT Touch

`backend/app/api/v1/routes/auth.py`. `backend/app/schemas/common.py`.
The `check_student_limit` and `check_trial_expired` methods in `billing_service.py` —
add only the three new read methods, do not modify the enforcement methods.
