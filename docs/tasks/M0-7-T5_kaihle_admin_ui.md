# M0-7-T5 — Kaihle Admin UI
**Milestone:** M0 — Foundations
**Epic:** M0-7 — Frontend Foundations
**Task ID:** M0-7-T5
**Depends on:** M0-8-T3 (brand tokens in tailwind), M0-8-T4 (Button, Card, Badge from @kaihle/ui), M0-7-T1 (layout wrappers), M0-4-T1 (school management API), M0-3-T4 (auth)

REASON: Pages use AdminLayout from @kaihle/ui and role-admin-* color tokens from tailwind.
**Blocks:** M6-3-T4 (pilot seed — admin needs to create and manage the pilot school)
**Estimated effort:** 4–5 hours

---

## Context

Kaihle Admin (Vibhu and the internal team) has no frontend at all. All the backend APIs
exist (school management, user management, trial extensions) but there is no UI to use them.
This task implements the Kaihle Admin interface as a **route-guarded section of the teacher
app** (no separate app required at v1 scale).

**Architecture decision — why NOT a separate app:**
At v1 (10 schools, ~400 students), a separate admin app adds Docker services, build
pipeline entries, and maintenance overhead for what is a handful of screens used by 1-2
people. Instead, Kaihle Admin pages live at `/kaihle-admin/*` within the teacher app,
protected by `RoleRoute(KAIHLE_ADMIN)`. A separate app can be split out in v2 if needed.

Read `docs/design/DESIGN_SYSTEM.md` §5.1 (Kaihle Admin) before writing any code.
Use `AdminLayout` from `packages/ui`. All text is Inter — no Fraunces.

---

## User Story

As Vibhu (Kaihle Admin), I want a simple internal dashboard where I can create schools,
manage their subscriptions, extend trials, and monitor overall platform health, without
needing to run SQL queries directly against the database.

---

## Files to Create

```
frontend/apps/teacher/src/pages/kaihle-admin/
  AdminOverview.tsx              ← platform overview / KPI dashboard
  AdminSchools.tsx               ← list + manage all schools
  AdminSchoolDetail.tsx          ← single school — users, classes, trial, billing
  AdminCreateSchoolModal.tsx     ← create new school form
  AdminExtendTrialModal.tsx      ← extend a school's trial

frontend/apps/teacher/src/hooks/
  useKaihleAdmin.ts              ← React Query hooks for admin data

frontend/apps/teacher/src/tests/
  kaihle-admin.spec.ts           ← Playwright E2E
```

---

## Routes

```
/kaihle-admin/overview         → AdminOverview.tsx
/kaihle-admin/schools          → AdminSchools.tsx
/kaihle-admin/schools/:id      → AdminSchoolDetail.tsx
```

All protected by `RoleRoute(KAIHLE_ADMIN)`.
Any other role landing on `/kaihle-admin/*` → 403 page ("You don't have access to this area").

Kaihle Admin login: same `/login` as teacher app. Post-login redirect: `/kaihle-admin/overview`.
The `AdminLayout` sidebar replaces the teacher sidebar automatically via `RoleRoute` logic.

---

## Page 1: Platform Overview (`AdminOverview.tsx`)

```
┌──────────────────────────────────────────────────────────┐
│  TOPNAV (Inter): Platform overview  [+ Add school]       │
├──────────────────┬───────────────────────────────────────┤
│  SIDEBAR         │                                       │
│  (admin, Inter)  │  ── Platform KPIs ─────────────────  │
│                  │  ┌───────┐ ┌───────┐ ┌───────┐       │
│  Overview ●      │  │Schools│ │Stud.  │ │  MRR  │       │
│  Schools         │  │  7    │ │  312  │ │ $2.4k │       │
│  Users           │  └───────┘ └───────┘ └───────┘       │
│  Billing         │                                       │
│  Logs            │  ┌───────────────────────────────┐   │
│  Config          │  │ Uptime: 99.9%   Latency: 142ms│   │
│                  │  └───────────────────────────────┘   │
│                  │                                       │
│                  │  ── School status ─────────────────  │
│                  │  Name          │Status  │Plan │Expiry │
│                  │  Bali Coding   │Active  │Growth│ —    │
│                  │  Green School  │Active  │Strt  │ —    │
│                  │  ISIA Jakarta  │Trial   │Trial │7d    │
│                  │  Naraya School │Trial   │Trial │2d    │
│                  │                                       │
│                  │  ── Recent activity ───────────────  │
│                  │  New school enrolled: ISIA Jakarta    │
│                  │  Trial extended: Naraya +7 days       │
│                  │  Payment received: Bali Coding        │
└──────────────────┴───────────────────────────────────────┘
```

KPI cards: `bg-white border border-role-admin-border` — neutral, no green tint.
MRR card: value in `text-brand-primary` (green = money is good).
Trial expiry badges: `< 3 days` → `bg-brand-red-light text-brand-red`, `< 7 days` → `bg-brand-amber-light text-brand-amber`.

Recent activity: timestamp + message, sorted newest first, limit 10.

---

## Page 2: Schools List (`AdminSchools.tsx`)

```
┌──────────────────────────────────────────────────────────┐
│  TOPNAV: Schools  [+ Add school]                         │
├──────────────────┬───────────────────────────────────────┤
│                  │  [All] [Active] [Trial] [Suspended]   │  ← filter tabs
│                  │                                       │
│                  │  Name         │Plan  │Students│Status │
│                  │  Bali Coding  │Growth│  147   │Active │
│                  │  Green School │Start │   89   │Active │
│                  │  ISIA Jakarta │Trial │   12   │Trial  │
│                  │  Naraya School│Trial │    8   │Trial  │
│                  │                                       │
│                  │  Click row → /kaihle-admin/schools/:id│
└──────────────────┴───────────────────────────────────────┘
```

### `AdminCreateSchoolModal.tsx`

```
Fields:
  - School name        (required)
  - Slug               (auto-derived from name, editable)
  - Country            (text, optional)
  - City               (text, optional)
  - Timezone           (dropdown, default: Asia/Makassar)
  - Plan tier          (dropdown: TRIAL / STARTER / GROWTH / SCALE)
  - Admin email        (required — will receive magic link)
  - Admin first name   (required)
  - Admin last name    (required)

Actions: [Cancel]  [Create school →]

On submit:
  1. POST /api/v1/admin/schools  → creates school
  2. POST /api/v1/schools/{id}/users  → creates SCHOOL_ADMIN user
  On success: modal closes, toast "School created · Magic link sent to {email}"
```

---

## Page 3: School Detail (`AdminSchoolDetail.tsx`)

Route: `/kaihle-admin/schools/:schoolId`

Single school deep-dive. Three sections:

**Section 1 — Info + Status**
```
School name, slug, country, timezone (editable inline)
Status badge: Active / Trial / Suspended  + [Change status] action
Plan: Current tier + [Change plan] action
```

**Section 2 — Trial management**
Shown only when `subscription_status = TRIAL`:
```
bg-brand-amber-light rounded-xl border border-brand-gold-mid p-4
Trial expires: {date}  ({N} days remaining)
[+ Extend trial] button → AdminExtendTrialModal
```

### `AdminExtendTrialModal.tsx`
```
"Extend trial for {school name}"
Extension: [7 days] [14 days] [30 days] — pill selector
Reason: textarea (required — stored in trial_extensions.reason)
[Cancel]  [Extend trial →]
On success: trial end date updates on screen, toast "Trial extended by N days"
```

**Section 3 — Summary stats**
```
Teachers: N  |  Students: N  |  Assessments completed: N  |  Avg mastery: N%
(read-only, derived from analytics endpoint)
```

---

## Data (`useKaihleAdmin.ts`)

```typescript
// Queries:
// GET /api/v1/admin/schools?page=1&page_size=50   (admin list)
// GET /api/v1/admin/schools/:id                   (school detail)
// GET /api/v1/schools/:id/analytics               (school stats)

// Mutations:
// POST /api/v1/admin/schools                    (create school)
// PATCH /api/v1/admin/schools/:id               (update status/plan)
// POST /api/v1/schools/:id/users               (create school admin)
// POST /api/v1/admin/schools/:id/trial-extension  (extend trial)
//   Note: trial extension endpoint may not exist yet — implement in M0-4-T1 if missing
```

---

## Acceptance Criteria

- [ ] E2E: Kaihle Admin logs in → lands on `/kaihle-admin/overview`
- [ ] E2E: overview shows correct school count, student count, MRR KPI cards
- [ ] E2E: schools list shows all schools with correct status badges
- [ ] E2E: clicking school row → navigates to school detail page
- [ ] E2E: `[+ Add school]` → modal opens → form fills → school appears in list
- [ ] E2E: school detail shows trial section for trial schools
- [ ] E2E: `[+ Extend trial]` → modal → select 14 days → extend → trial date updates
- [ ] E2E: Teacher role trying to access `/kaihle-admin/*` → sees 403 page
- [ ] E2E: School Admin trying `/kaihle-admin/*` → sees 403 page
- [ ] Unit: trial badge shows red when < 3 days remaining
- [ ] Unit: trial badge shows amber when 3–7 days remaining
- [ ] Unit: `AdminCreateSchoolModal` slug auto-derives from name ("Bali School" → "bali-school")
- [ ] Unit: slug field is editable and validated (lowercase, hyphens only, no spaces)
- [ ] Responsive: usable at 1024px (desktop minimum, no mobile requirement for admin)
- [ ] Design: ALL text uses Inter font — no Fraunces anywhere in admin pages
- [ ] Design: uses `AdminLayout` — cool `#f8f9fb` background, gray borders
- [ ] Design: primary button = green `bg-brand-primary` (admin uses green, not gold)

---

## M0 Brief Update Note

The M0 brief does NOT currently list M0-7 as an epic. Before this task can be picked up,
add the following to `docs/milestones/M0_brief.md` task table:

```
| M0-7-T1 | `M0/M0-7-T1_layout_wrappers.md`      | Shared layout wrappers (all roles)     |
| M0-7-T2 | `M0/M0-7-T2_teacher_dashboard.md`     | Teacher home dashboard                 |
| M0-7-T3 | `M0/M0-7-T3_student_dashboard.md`     | Student home dashboard                 |
| M0-7-T4 | `M0/M0-7-T4_school_admin_ui.md`       | School Admin overview, users, classes  |
| M0-7-T5 | `M0/M0-7-T5_kaihle_admin_ui.md`       | Kaihle Admin platform dashboard        |
```

And add to M0 execution order:
```
M0-3-T5 (login UI)
  → M0-7-T1 (layout wrappers)  ← must complete before any page tasks
    → M0-7-T2 (teacher dashboard)    ← parallel
    → M0-7-T3 (student dashboard)    ← parallel, after M0-6-T3
    → M0-7-T4 (school admin UI)      ← parallel
    → M0-7-T5 (kaihle admin UI)      ← parallel
```
