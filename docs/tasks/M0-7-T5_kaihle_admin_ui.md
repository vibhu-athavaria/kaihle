# M0-7-T5 — Kaihle Admin UI
**Milestone:** M0 — Foundations
**Epic:** M0-7 — Frontend Foundations
**Task ID:** M0-7-T5
**Depends on:** M0-8-T3 (brand tokens in tailwind), M0-8-T4 (Button, Card, Badge from @kaihle/ui), M0-7-T1 (layout wrappers), M0-4-T1 (school management API), M0-3-T4 (auth)
**Blocks:** M6-3-T4 (pilot seed)
**Estimated effort:** 4–5 hours

> ⚠️ **SUPERSESSION NOTE — READ BEFORE STARTING**
>
> This task was originally written to place files inside `frontend/apps/teacher/`
> as a v1 expedient. That decision was superseded by CONSTITUTION.md §3 (App Isolation
> Rule, added in ADR-001) and M0-9-T3. **All files in this task MUST go in
> `apps/kaihle-admin/`.**
>
> If M0-9-T3 has already run, its migration is the canonical version of these pages.
> Do not re-create them — verify they exist at the correct path and proceed to the
> new tasks at the bottom of this file.
>
> If M0-9-T3 has NOT yet run, build directly in `apps/kaihle-admin/` and skip M0-9-T3
> (its migration is unnecessary if you build in the right place to begin with).

---

## Context

Kaihle Admin (Vibhu and the internal team) needs a platform dashboard to create schools,
manage subscriptions, extend trials, and monitor platform health without running SQL queries.

All code lives in `apps/kaihle-admin` (port 3005). Use `AdminLayout` from `packages/ui`.
All text is Inter — no Fraunces anywhere in this app.

Read `docs/design/DESIGN_SYSTEM.md` §5.1 (Kaihle Admin) before writing any code.
Read `docs/design/screens/KAIHLE_ADMIN_SCREENS.md` for full page specifications.

---

## User Story

As Vibhu (Kaihle Admin), I want a simple internal dashboard where I can create schools,
manage their subscriptions, extend trials, and monitor overall platform health, without
needing to run SQL queries directly against the database.

---

## Files to Create

```
frontend/apps/kaihle-admin/src/pages/
  AdminOverview.tsx              ← platform overview / KPI dashboard
  AdminSchools.tsx               ← list + manage all schools
  AdminSchoolDetail.tsx          ← single school — users, classes, trial, billing
  AdminBilling.tsx               ← platform-wide billing + MRR overview
  AdminLogs.tsx                  ← structured system logs viewer
  AdminConfig.tsx                ← read-only platform config display
  AdminUsers.tsx                 ← cross-platform user search

frontend/apps/kaihle-admin/src/components/
  AdminCreateSchoolModal.tsx     ← create new school form
  AdminExtendTrialModal.tsx      ← extend a school's trial

frontend/apps/kaihle-admin/src/hooks/
  useKaihleAdmin.ts              ← React Query hooks for admin data

frontend/apps/kaihle-admin/src/tests/
  kaihle-admin.spec.ts           ← Playwright E2E
```

**NEVER place files in `frontend/apps/teacher/`. Violation of CONSTITUTION §3.**

---

## Routes

```
/kaihle-admin/overview         → AdminOverview.tsx
/kaihle-admin/schools          → AdminSchools.tsx
/kaihle-admin/schools/:id      → AdminSchoolDetail.tsx
/kaihle-admin/billing          → AdminBilling.tsx
/kaihle-admin/logs             → AdminLogs.tsx
/kaihle-admin/config           → AdminConfig.tsx
/kaihle-admin/users            → AdminUsers.tsx
```

All protected by `RoleRoute(KAIHLE_ADMIN)`.
Any other role landing on `/kaihle-admin/*` → 403 page.
Kaihle Admin login: same `/login` as other apps. Post-login redirect: `/kaihle-admin/overview`.

---

## Page 1: Platform Overview (`AdminOverview.tsx`)

```
┌──────────────────────────────────────────────────────────┐
│  TOPNAV (Inter): Platform overview  [+ Add school]       │
├──────────────────┬───────────────────────────────────────┤
│  SIDEBAR         │  KPIs: Schools · Students · MRR       │
│  Overview ●      │  Health bar: uptime · latency · Redis │
│  Schools         │  School status table                  │
│  Users           │  Recent activity feed                 │
│  Billing         │                                       │
│  ──────          │                                       │
│  Logs            │                                       │
│  Config          │                                       │
└──────────────────┴───────────────────────────────────────┘
```

KPI cards: `bg-white border border-gray-200` — neutral, no green tint.
MRR value: `text-brand-primary` (green = revenue positive).
Trial expiry badges: < 3 days → red, 3–7 days → amber.
Recent activity: timestamp + message, newest first, limit 10.

---

## Page 2: Schools (`AdminSchools.tsx`)

- Search input + status filter (All / Active / Trial)
- Table: School name · Status · Plan · Students · Created date · Trial ends · Open link
- `[+ Add school]` → `AdminCreateSchoolModal`

### `AdminCreateSchoolModal.tsx`
```
Fields: School name · Slug (auto-derived, editable, lowercase+hyphens only)
        Country · City · Timezone dropdown
        Admin first name · Admin last name · Admin email
Flow:   POST /api/v1/schools → POST /api/v1/schools/{id}/users
Toast:  "School created · Magic link sent to {email}"
```

---

## Page 3: School Detail (`AdminSchoolDetail.tsx`)

Route: `/kaihle-admin/schools/:schoolId`

**Topbar actions:**
- Breadcrumb: Schools / {name}
- "Impersonate school admin" button → `POST /platform/schools/{id}/impersonate`
  (scoped JWT, M6 implementation — stub returns 501 until M6)

**Trial banner** (TRIAL tier only, amber):
```
"⚠ Trial expires in N days — {date}"
[+ Extend trial] → AdminExtendTrialModal
```

### `AdminExtendTrialModal.tsx`
```
Title: "Extend trial — {school name}"
Extension: pill selector — 7 days | 14 days | 30 days
Reason: textarea (required — stored in trial_extensions.reason audit table)
Actions: Cancel · "Extend trial →" green
On success: trial date updates, toast "Trial extended by N days"
```

**Stats row:** Students · Teachers · Assessments · Avg mastery

**Two-column layout:**
- Left: school info (name, slug, country, city, timezone, created — all editable inline)
- Right: subscription info (plan, dates, limits, trial extension history, "Upgrade" CTA)

---

## Pages 4–7: Billing, Logs, Config, Users

See `docs/design/screens/KAIHLE_ADMIN_SCREENS.md` for full specifications.
Task files for these pages:
- `docs/tasks/M0/M0-7-T5b_kaihle_admin_billing_ui.md` (to be created)
- `docs/tasks/M0/M0-7-T5c_kaihle_admin_logs_ui.md` (to be created)
- `docs/tasks/M0/M0-7-T5d_kaihle_admin_config_ui.md` (to be created)
- `docs/tasks/M0/M0-7-T5e_kaihle_admin_users_ui.md` (to be created)

---

## Data (`useKaihleAdmin.ts`)

```typescript
// Queries:
// GET /api/v1/platform/stats          (overview KPIs + health)
// GET /api/v1/schools                 (all schools list)
// GET /api/v1/schools/{id}            (school detail)
// GET /api/v1/schools/{id}/analytics  (school stats)

// Mutations:
// POST /api/v1/schools                         (create school)
// POST /api/v1/schools/{id}/users             (create school admin)
// PATCH /api/v1/admin/schools/{id}            (update status/plan)
// POST /api/v1/admin/schools/{id}/trial-extension  (extend trial)
// POST /api/v1/platform/schools/{id}/impersonate   (M6 — scoped JWT)
```

---

## Acceptance Criteria

- [ ] E2E: Kaihle Admin logs in → lands on `/kaihle-admin/overview`
- [ ] E2E: overview shows school count, student count, MRR KPI cards
- [ ] E2E: schools list shows all schools with correct status badges
- [ ] E2E: clicking school row → navigates to school detail page
- [ ] E2E: `[+ Add school]` → modal → school appears in list
- [ ] E2E: school detail shows trial section for trial schools
- [ ] E2E: `[+ Extend trial]` → modal → 14 days → extend → date updates
- [ ] E2E: Teacher or School Admin accessing `/kaihle-admin/*` → 403 page
- [ ] Unit: trial badge < 3 days → red styling
- [ ] Unit: trial badge 3–7 days → amber styling
- [ ] Unit: `AdminCreateSchoolModal` slug auto-derives from name ("Bali School" → "bali-school")
- [ ] Unit: slug validated — lowercase + hyphens only, no spaces
- [ ] Design: ALL text uses Inter font — no Fraunces anywhere
- [ ] Design: `AdminLayout` with cool `#f8f9fb` background
- [ ] Design: primary button = green `bg-brand-primary` (not gold)
- [ ] Design: active sidebar state = gray fill + green dot (not tint, not stripe)

---

## Do NOT Touch

`frontend/apps/teacher/` — Kaihle Admin code must never live here (CONSTITUTION §3).
`frontend/apps/school-admin/` — no code goes here.
`frontend/apps/student/` — no code goes here.
Any backend file.
