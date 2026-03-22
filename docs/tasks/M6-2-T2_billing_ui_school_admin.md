# M6-2-T2 — Billing UI (School Admin App)
**Milestone:** M6 · **Epic:** M6-2 · **Task:** T2
**Depends on:** M6-2-T1 (billing tier enforcement — subscription routes exist), M0-10-T6 (billing stubs created)
**Blocks:** Nothing — standalone billing page
**Estimated effort:** 3–4 hours

---

## Context

All code in this task lives in `frontend/apps/school-admin`. No code goes in any
other app.

Read `docs/design/DESIGN_SYSTEM.md` §5.2 (School Admin) before writing any component.
Green is the action color. Left green stripe is the sidebar active state.

The billing page is read-only for school admins in v1. School admins can view their
plan, monitor usage against limits, and download invoice PDFs. They cannot change
payment method, cancel subscriptions, or self-serve upgrade — these actions require
Kaihle Admin intervention (V1 constraint — upgrade is a sales-led motion).

The billing tier enforcement service (`M6-2-T1`) has already built the backend logic.
This task builds the frontend that surfaces it.

---

## User Story

As a school admin, I want to see my school's current subscription plan, how many
students I have enrolled versus my limit, and download invoices for our records.

---

## Files to Create

```
frontend/apps/school-admin/src/pages/billing/
  BillingPage.tsx                ← page shell

frontend/apps/school-admin/src/components/billing/
  PlanHeroCard.tsx               ← current plan name, status, key details
  UsageCard.tsx                  ← students/curricula/features usage vs limits
  InvoiceList.tsx                ← downloadable invoice rows
  TrialBanner.tsx                ← amber warning banner for TRIAL tier schools

frontend/apps/school-admin/src/hooks/
  useBilling.ts                  ← React Query hooks for subscription + invoices

frontend/apps/school-admin/src/tests/
  billing.spec.ts                ← Playwright E2E tests
```

---

## Route

`/school-admin/billing` — `BillingPage`.
Protected by `PrivateRoute` + `RoleRoute(['SCHOOL_ADMIN', 'KAIHLE_ADMIN'])`.

Accessible from the sidebar ADMIN section. Also linked from the trial expiry
warning banner shown on any page when `trial_end_date` is within 7 days.

---

## Complete List of API Calls This UI Makes

`GET /api/v1/schools/{schoolId}/subscription` — called on mount. Returns
`SchoolSubscriptionResponse` with plan tier, status, student count, limits,
billing cycle, dates, and features JSONB.

`GET /api/v1/schools/{schoolId}/invoices` — called on mount in parallel with
subscription. Returns `Page[InvoiceResponse]` ordered by period descending.

`GET /api/v1/subscription-plans` — called once (cached globally) to get the full
plan comparison for the upgrade CTA tooltip. Returns all active `SubscriptionPlan`
rows.

Those are the only three API calls. No write operations — billing page is read-only.

---

## Page Layout

```
┌──────────────────────────────────────────────────────────────────┐
│  [Trial banner — amber, shown only for TRIAL tier]              │
│                                                                  │
│  Plan hero card (full width)                                     │
│  Plan name + status · Price · Billing cycle · Renewal date      │
│  [Upgrade to Scale →]                                            │
│                                                                  │
│  Usage                                                           │
│  Active students: 147 of 500 · Teachers: 8 unlimited ...       │
│                                                                  │
│  Invoices                                                        │
│  Annual invoice 2026 · $14,700 · Paid [PDF]                    │
│  Annual invoice 2025 · $12,400 · Paid [PDF]                    │
└──────────────────────────────────────────────────────────────────┘
```

Max content width: `max-w-2xl` — billing is a focused read-only page.

---

## Trial Banner (`TrialBanner.tsx`)

Shown only when `subscription.plan.tier === 'TRIAL'`.

```tsx
<div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-center justify-between">
  <div className="flex items-center gap-3">
    <span className="text-amber-600 text-lg">⚠️</span>
    <div>
      <div className="font-bold text-amber-800 text-sm">
        Your free trial expires in {daysRemaining} days
      </div>
      <div className="text-amber-700 text-xs mt-0.5">
        {maxStudents} student limit · Full feature access
      </div>
    </div>
  </div>
  <a href="mailto:hello@kaihle.com?subject=Upgrade enquiry" className="...">
    Talk to us about upgrading →
  </a>
</div>
```

`daysRemaining` = `Math.ceil((trial_end_date - now) / 86400000)`.
If trial has already expired (negative days): "Your trial has ended" with stronger
red styling — `bg-red-50 border-red-200 text-red-800`.

Dismiss is NOT available — the banner persists until the school upgrades.

---

## Plan Hero Card (`PlanHeroCard.tsx`)

```typescript
interface PlanHeroCardProps {
  tier: 'TRIAL' | 'STARTER' | 'GROWTH' | 'SCALE'
  status: 'ACTIVE' | 'PAST_DUE' | 'CANCELLED' | 'EXPIRED'
  pricePerStudent: number
  billingCycle: 'annual' | 'monthly'
  studentCount: number
  totalAmount: number
  startDate: string
  endDate: string
  trialEndDate: string | null
}
```

**Plan name** (Fraunces, 16px, bold) + **Status badge** next to it:
- ACTIVE: `bg-green-100 text-green-700`
- PAST_DUE: `bg-red-100 text-red-700`
- CANCELLED / EXPIRED: `bg-gray-100 text-gray-500`

**Details row** (below name):
```
Students: 147 / 500   Price: $100/student/yr   Billing: Annual   Renews: 1 Jan 2027
```

**Upgrade CTA** (right side):
- TRIAL / STARTER / GROWTH: "Talk to us about upgrading →" — `mailto:hello@kaihle.com`
  styled as a green outline button
- SCALE: No upgrade CTA — show "You're on our highest plan" in muted text
- PAST_DUE: "Resolve payment issue →" — link to Kaihle contact

---

## Usage Card (`UsageCard.tsx`)

```typescript
interface UsageCardProps {
  activeStudents: number
  studentLimit: number | null     // null = unlimited
  teacherCount: number
  curriculaActive: number
  curriculaLimit: number | null   // null = unlimited
  features: {
    parent_portal: boolean
    teacher_copilot: boolean
    api_access: boolean
    sla_guarantee: boolean
    dedicated_support: boolean
  }
}
```

**Usage rows** (one per resource):

```
Active students   147   of 500 limit
                  [██████████░░░░░░░░░░]    ← usage bar, green fill

Teachers          8     unlimited
Curricula         2     of 2 included
```

Usage bar only shown for students and curricula (countable resources with limits).
Bar fill: green if under 80%, amber if 80–95%, red if >95%.
`null` limit: show "unlimited" — no bar.

**Feature pills** (below usage rows):
Grid of feature pills, 3 per row:
- Included: `bg-green-50 border border-green-200 text-green-700` + ✓ icon
- Not included: `bg-gray-50 border border-gray-200 text-gray-400` + – icon (not ✕ — avoid negative framing)

Features to show: Parent portal · AI lesson plans · API access · SLA guarantee · Dedicated support

---

## Invoice List (`InvoiceList.tsx`)

```typescript
interface InvoiceRowProps {
  invoiceNumber: string
  periodStart: string
  periodEnd: string
  studentCount: number
  amount: number
  currency: string
  status: 'PENDING' | 'PAID' | 'FAILED' | 'REFUNDED'
  pdfUrl: string | null
}
```

One row per invoice, ordered newest first:

```
Annual invoice · 2026     Jan 1 – Dec 31 2026 · 147 students     $14,700   [Paid]  [PDF ↓]
Annual invoice · 2025     Jan 1 – Dec 31 2025 · 124 students     $12,400   [Paid]  [PDF ↓]
```

Status badges:
- PAID: `bg-green-100 text-green-700`
- PENDING: `bg-amber-100 text-amber-700`
- FAILED: `bg-red-100 text-red-700`
- REFUNDED: `bg-gray-100 text-gray-500`

PDF button: outline button, opens `pdfUrl` in new tab.
If `pdfUrl = null`: show "Generating..." muted — PDF not yet available.

Empty state (no invoices yet): "No invoices yet. Your first invoice will appear
here after your trial ends and you subscribe."

---

## `useBilling.ts`

```typescript
export const useSubscription = (schoolId: string) =>
  useQuery({
    queryKey: ['school-admin', 'subscription', schoolId],
    queryFn: () => apiClient.get<SchoolSubscriptionResponse>(
      `/schools/${schoolId}/subscription`
    ),
    staleTime: 5 * 60 * 1000,  // 5 minutes — subscription data changes rarely
  })

export const useInvoices = (schoolId: string) =>
  useQuery({
    queryKey: ['school-admin', 'invoices', schoolId],
    queryFn: () => apiClient.get<Page<InvoiceResponse>>(
      `/schools/${schoolId}/invoices`
    ),
    staleTime: 5 * 60 * 1000,
  })
```

Both queries fire on mount in parallel — do not wait for subscription before
fetching invoices.

---

## Acceptance Criteria

**Playwright E2E tests in `billing.spec.ts`**

`test_billing_page_when_active_plan_then_plan_name_shown` — Navigate to
`/school-admin/billing`. Mock subscription as GROWTH/ACTIVE. Assert "Growth Plan"
text is visible.

`test_billing_page_when_trial_then_trial_banner_shown` — Mock subscription as
TRIAL. Assert the trial banner is visible with "Your free trial expires in" text.

`test_billing_page_when_trial_expired_then_red_banner_shown` — Mock
`trial_end_date` in the past. Assert the banner uses red styling.

`test_billing_page_when_students_over_80_pct_then_amber_usage_bar` — Mock 450
students of 500 limit (90%). Assert the usage bar has the amber color class.

`test_billing_page_when_unlimited_limit_then_no_bar_shown` — Mock teacher count
with no limit. Assert no bar element is rendered for the teacher row.

`test_billing_page_when_feature_included_then_green_pill_shown` — Mock
`parent_portal: true`. Assert a green pill with "Parent portal" and ✓ is visible.

`test_billing_page_when_feature_not_included_then_muted_pill_shown` — Mock
`api_access: false`. Assert the pill for "API access" uses the gray/muted styling.

`test_billing_page_when_invoice_paid_then_green_badge_shown` — Mock a PAID invoice.
Assert the badge has green styling.

`test_billing_page_when_pdf_url_null_then_generating_shown` — Mock `pdf_url: null`.
Assert "Generating..." text appears in place of the PDF button.

`test_billing_page_when_scale_plan_then_no_upgrade_cta` — Mock SCALE tier. Assert
no "Upgrade" or "Talk to us" link is visible.

**Jest unit tests**

`test_trial_banner_when_5_days_remaining_then_shows_5_days` — Render `TrialBanner`
with `trial_end_date` 5 days from now. Assert "5 days" text is present.

`test_usage_bar_when_over_95_pct_then_red_fill` — Render `UsageCard` with 96 of
100 students. Assert the bar fill has the red color class.

`test_usage_card_when_null_limit_then_unlimited_text` — Render with
`studentLimit=null`. Assert "unlimited" text is present and no bar is rendered.

---

## Do NOT Touch

`frontend/apps/teacher/` — no code goes here.
`frontend/apps/student/` — no code goes here.
`frontend/apps/kaihle-admin/` — Kaihle Admin has its own billing management UI.
Any backend file — billing endpoints exist from M6-2-T1.
