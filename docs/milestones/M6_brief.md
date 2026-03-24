# M6 Brief — Analytics, Billing & Launch Polish
**Milestone:** 6 of 6
**Estimated duration:** 2–3 weeks
**Previous milestone:** M5 — Parent Portal
**Constitution version:** 2.0

> Load this brief alongside CONSTITUTION.md when working on any M6 task.
> Load the specific task file for the task you are implementing.

---

## Goal

The school admin sees a usage analytics dashboard. Billing tier limits are enforced
at the service layer. Rate limiting and structured error handling are production-grade.
The first real pilot school (Bali) is live on Render.com with all features operational.

---

## Exit Criteria

- First real school (Bali pilot) is live in production on Render.com
- School admin sees the analytics dashboard including onboarding completion rate
- Billing tier limits enforced — trial school cannot exceed 30 students
- Rate limiting active on auth and LLM routes
- Full manual end-to-end journey verified in production

---

## What This Milestone Delivers

**Analytics service and API — stub replacement**

M0-10-T6 created `routes/analytics.py` with two stubs: `GET /schools/{id}/analytics`
and `GET /platform/stats`. This milestone replaces both stub bodies with real
aggregation queries. The analytics service aggregates counts from every feature table
into the `SchoolAnalytics` and `PlatformStats` response shapes, both of which are
frozen from M0-10.

The school impersonation endpoint (`POST /platform/schools/{id}/impersonate`) is also
implemented here. It issues a scoped JWT carrying the target school's `school_id` so
a Kaihle Admin can browse a school's data as if they were that school's admin. The
stub in `routes/analytics.py` currently returns 501 — M6 replaces it with the real
token issuance logic.

**Analytics dashboard UI — School Admin app**

Built in `apps/school-admin`. This is a critical app target correction from the
original plan, which incorrectly placed this UI in `apps/teacher`. The analytics
dashboard belongs in `apps/school-admin` because it is a school admin feature — a
teacher should never see it. The `useSchoolAnalytics` hook created in M0-10-T10
is the data layer. The page shows KPI cards, an onboarding completion rate progress
bar, a mastery-by-subject bar chart using Recharts, and a class breakdown table.

**Billing enforcement**

A `billing.py` module with `check_student_limit(school_id)` and `is_trial_expired(school)`
functions. The student limit check is called before every enrollment INSERT — if the
school would exceed its tier's maximum active student count, the service returns HTTP
402 with a structured error body including `upgrade_url`. The trial expiry check is
called on every login for schools on the TRIAL tier.

**Rate limiting**

`slowapi` rate limiting on four route groups: login (10 req/min per IP), magic link
(3 req/min per email), attempt responses (60 req/min per user), and any LLM-backed
route (20 req/min per school).

**Global error handling**

A registered FastAPI exception handler that ensures every unhandled error returns the
`ErrorDetail` schema defined in `schemas/common.py` from M0-10-T1. Stack traces never
reach the client. The `request_id` from structlog context is included in every error
response so operators can correlate errors with server logs.

**Pilot seed script and pre-launch checklist**

A `seed_pilot_school.py` script that creates the Bali pilot school with one school
admin, two teachers, and ten students. The pre-launch checklist is a verification
task that confirms every item in the definition of done is true in the production
environment.

---

## Tasks in This Milestone

| Task ID | File | Description |
|---|---|---|
| M6-1-T1 | `M6/M6-1-T1_analytics_service_routes.md` | Replace analytics stubs + impersonation |
| M6-1-T2 | `M6/M6-1-T2_analytics_ui.md` | School admin analytics dashboard (apps/school-admin) |
| M6-1-T3 | `M6/M6-1-T3_class_gap_map_admin_ui.md` | Class gap map — read-only admin view (apps/school-admin) |
| M6-1-T4 | `M6/M6-1-T4_platform_ops_endpoints.md` | Trial extension + platform activity + platform logs endpoints |
| M6-2-T1 | `M6/M6-2-T1_billing_tier_enforcement.md` | Billing limits + trial expiry |
| M6-2-T2 | `M6/M6-2-T2_billing_ui_school_admin.md` | Billing page UI — plan, usage bars, invoice list, trial banner (apps/school-admin) |
| M6-3-T1 | `M6/M6-3-T1_rate_limiting.md` | slowapi rate limiting |
| M6-3-T2 | `M6/M6-3-T2_error_handling.md` | Global error handler + structured responses |
| M6-3-T3 | `M6/M6-3-T3_data_backup.md` | Render PostgreSQL backups + RUNBOOK |
| M6-3-T4 | `M6/M6-3-T4_pilot_seed_script.md` | Seed script for Bali pilot school |
| M6-3-T5 | `M6/M6-3-T5_prelaunch_checklist.md` | Pre-launch verification checklist |
| M6-3-T6 | `M6/M6-3-T6_runbook.md` | Operations RUNBOOK.md — full operational documentation |
---

## Task Execution Order

```
M6-1-T1 (analytics service) ← start here
  → M6-1-T2 (analytics UI)  ← apps/school-admin, needs real routes
  → M6-1-T3 (class gap map admin UI) ← parallel with T2, read-only component, same endpoint
M6-2-T1 (billing)           ← parallel with analytics
  → M6-2-T2 (billing UI)    ← apps/school-admin, depends on subscription endpoint from T1
M6-3-T1 (rate limiting)     ← parallel
M6-3-T2 (error handling)    ← parallel — note: uses ErrorDetail from schemas/common.py
M6-3-T3 (backup)            ← parallel
M6-3-T4 (pilot seed)
  → M6-3-T6 (runbook) ← write before final checklist
    → M6-3-T5 (pre-launch checklist) ← RUNBOOK must exist before checklist is verified
```

---

## Critical: Stub Replacement Protocol

M6-1-T1 replaces stubs in `backend/app/api/v1/routes/analytics.py` (created by
M0-10-T6). Open the file, find every function marked `# STUB — M0-10-T6`, and replace
only the function body. The impersonation endpoint stub returns 501 — M6 replaces it
with real JWT issuance. The frozen paths, auth, and schemas must not change.

---

## App Target Correction for M6-1-T2

The original analytics UI task specification (`M6/M6-1-T2_analytics_ui.md`) placed
the page at `apps/teacher/src/pages/admin/AnalyticsDashboard.tsx`. This was incorrect.
The analytics dashboard is a school admin feature and belongs in `apps/school-admin`.
When implementing M6-1-T2, the coding agent must build at:

```
frontend/apps/school-admin/src/pages/analytics/AnalyticsDashboard.tsx
```

The route is `/school-admin/analytics`, protected by `RoleRoute(['SCHOOL_ADMIN', 'KAIHLE_ADMIN'])`.
The `useSchoolAnalytics` hook from `apps/school-admin/src/hooks/useSchoolAdmin.ts`
(created in M0-10-T10) is the data layer.

---

## Billing Tier Reference

| Tier | Max active students | Trial days |
|---|---|---|
| TRIAL | 30 | 15 |
| STARTER | 100 | — |
| GROWTH | 500 | — |
| SCALE | Unlimited | — |

Billing checks return HTTP 402 Payment Required with body:
`{ "error_code": "BILLING_LIMIT_EXCEEDED", "message": "...", "upgrade_url": "..." }`

---

## Rate Limits Reference

| Route | Limit |
|---|---|
| `POST /api/v1/auth/login` | 10 req/min per IP |
| `POST /api/v1/auth/magic-link` | 3 req/min per email |
| `POST /api/v1/attempts/*/responses` | 60 req/min per user |
| Any LLM-backed route | 20 req/min per school |

---

## Error Handling Note

M6-3-T2 implements the global exception handler that uses `ErrorDetail` from
`schemas/common.py`. This schema was created in M0-10-T1 precisely so that the shape
could be referenced in stub responses throughout the platform. M6-3-T2 ensures that
every unhandled error now returns this shape — completing the error response consistency
that was designed from the beginning.

---

## Definition of Done

- School admin analytics dashboard shows correct counts and onboarding completion rate (in `apps/school-admin`)
- Billing tier limits enforced at service layer — 402 on breach
- Trial expiry enforced — 402 on login after 15 days for TRIAL schools
- Rate limiting active on all auth and LLM routes
- Global error handler returns `ErrorDetail` JSON — never stack traces to client
- Render PostgreSQL daily backups enabled and restore procedure documented in `RUNBOOK.md`
- Pilot seed script runs cleanly and creates all expected records
- Pre-launch checklist fully verified in production
- All M6 tests pass
- Full manual journey verified: school admin → teacher → student (onboarding + diagnostic + study plan) → parent

---

## Key Tables Used in This Milestone

`schools`, `school_subscriptions`, `subscription_plans`, `subscription_invoices`,
`trial_extensions`, `users`, `student_profiles`, `gap_states`, `assessments`,
`student_attempts`, `study_plans`, `lesson_plans`, `parent_report_snapshots`,
`student_learning_profiles`

Full schema: `kaihle_v2_1_schema.sql`

---

## What M5 Delivered (Available to Use)

All product features are complete and tested. `parent_report_snapshots` is populated.
Celery beat is operational for lesson plan generation (Monday) and parent narrative
generation (Sunday). The full stack is running in the staging environment on Render.

---

## This Is The Final Milestone

There is no M7. After M6-3-T5 is complete and the pre-launch checklist is fully
verified in production, the Bali pilot school is live and the project has achieved
its v1 exit criteria.
