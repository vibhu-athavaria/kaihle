# M0-7-T4 — School Admin UI Pages
**Milestone:** M0 — Foundations
**Epic:** M0-7 — Frontend Foundations
**Task ID:** M0-7-T4
**Depends on:** M0-8-T3 (brand tokens in tailwind), M0-8-T4 (Button, Card, Badge, Input from @kaihle/ui), M0-7-T1 (layout wrappers), M0-4-T1/T2/T3 (school/user/class APIs), M0-3-T4 (auth)

REASON: Pages use DashboardLayout from @kaihle/ui (created by M0-7-T1, which requires M0-8-T4),
and reference brand-* color tokens (available after M0-8-T3 extends tailwind config).
**Blocks:** M6-1-T2 (analytics UI — School Admin views it from this shell)
**Estimated effort:** 5–6 hours

---

## Context

School Admin lives in the teacher app (`/apps/teacher`) but sees a different set of
sidebar links and pages. Three pages are completely undefined: the overview/home page,
the user management page, and the class management page. The analytics page already
exists as M6-1-T2. This task builds the missing three.

Read `docs/design/DESIGN_SYSTEM.md` §5.2 (School Admin) before writing any code.
Use `DashboardLayout variant="school-admin"` from `packages/ui`.

---

## User Story

As a school admin, I want a home overview, a user management interface, and a class
management interface so I can set up and manage my school on the platform.

---

## Files to Create

```
frontend/apps/teacher/src/pages/school-admin/
  SchoolOverview.tsx             ← home page / landing after School Admin login
  UserManagement.tsx             ← invite + manage teachers, students, parents
  ClassManagement.tsx            ← create classes, assign teachers, enroll students
  InviteUserModal.tsx            ← modal for inviting a new user
  CreateClassModal.tsx           ← modal for creating a new class

frontend/apps/teacher/src/hooks/
  useSchoolAdmin.ts              ← React Query hooks for all school admin data

frontend/apps/teacher/src/tests/
  school-admin.spec.ts           ← Playwright E2E
```

---

## Routes

```
/school/overview       → SchoolOverview.tsx    (School Admin landing after login)
/school/users          → UserManagement.tsx
/school/classes        → ClassManagement.tsx
```

All routes protected by `RoleRoute` requiring `SCHOOL_ADMIN | KAIHLE_ADMIN`.

Teacher role → redirect to `/teacher/dashboard` if they land on `/school/*`.

---

## Page 1: School Overview (`SchoolOverview.tsx`)

Landing page for School Admin after login.

```
┌──────────────────────────────────────────────────────────┐
│  TOPNAV: School overview  [Invite teacher] [avatar]      │
├───────────────┬──────────────────────────────────────────┤
│  SIDEBAR      │                                          │
│  (school-     │  ── Quick stats ─────────────────────── │
│   admin)      │  ┌────────┐ ┌────────┐ ┌────────┐       │
│               │  │Teachers│ │Students│ │Onboard.│       │
│  Overview ●   │  │   8    │ │  147   │ │  73%   │       │
│  Teachers     │  └────────┘ └────────┘ └────────┘       │
│  Students     │                                          │
│  Classes      │  ── Classes ──────────────────────────  │
│  Analytics    │  ┌──────────────────────────────────┐   │
│  Billing      │  │ Class      │ Teacher   │ Students │   │
│               │  │ Maths 9B   │ Ms. Ravi  │    28    │   │
│               │  │ Science 8A │ Mr. Tan   │    24    │   │
│               │  │ English 10 │ Ms. Wu    │    31    │   │
│               │  └──────────────────────────────────┘   │
│               │  [+ Create class]                        │
│               │                                          │
│               │  ── Onboarding progress ──────────────  │
│               │  73% students fully onboarded            │
│               │  [████████████████░░░░░░] 107 / 147      │
│               │  [View analytics →]                      │
└───────────────┴──────────────────────────────────────────┘
```

KPI cards: same pattern as DESIGN_SYSTEM KPI card, `bg-white border-role-school-border`.
Classes table: compact, no pagination (max 10 rows visible, scroll if more).
Onboarding progress: `bg-brand-light` card with progress bar using `brand-primary`.

---

## Page 2: User Management (`UserManagement.tsx`)

```
┌──────────────────────────────────────────────────────────┐
│  TOPNAV: Users  [+ Invite user] [avatar]                 │
├───────────────┬──────────────────────────────────────────┤
│  SIDEBAR      │  [Teachers]  [Students]  [Parents]        │  ← role tabs
│               │                                          │
│               │  ┌──────────────────────────────────┐   │
│               │  │ Name        │ Email    │ Status   │   │
│               │  │ Ms. Ravi    │ ravi@..  │ ● Active │   │
│               │  │ Mr. Tan     │ tan@...  │ ● Active │   │
│               │  │ Ms. Wu      │ wu@....  │ ○ Invited│   │
│               │  └──────────────────────────────────┘   │
│               │                                          │
│               │  [Showing 3 of 8 teachers]               │
│               │  [Load more]                             │
└───────────────┴──────────────────────────────────────────┘
```

Role tabs: `[Teachers] [Students] [Parents]` — horizontal tab row below topnav.
Active tab: `text-brand-primary border-b-2 border-brand-primary`.

Table rows:
- Avatar initials circle + name + email + status badge + action menu (⋮)
- Action menu: Resend invite | Deactivate (for active) | Reactivate (for inactive)
- Status badges: `● Active` (brand-green) / `○ Invited` (brand-gold) / `✕ Inactive` (brand-muted)

`[+ Invite user]` top nav button → opens `InviteUserModal`.

### `InviteUserModal.tsx`

```
Modal (300ms fade, centered, bg-white rounded-2xl border p-6 max-w-md)
Title: "Invite a teacher" (or student/parent based on active tab)
Fields:
  - First name (required)
  - Last name (required)
  - Email address (required, validated)
  - Role: pre-filled from active tab, editable dropdown
Actions: [Cancel] [Send invite →]
On success: modal closes, success toast "Invite sent to {email}", table refreshes
```

---

## Page 3: Class Management (`ClassManagement.tsx`)

```
┌──────────────────────────────────────────────────────────┐
│  TOPNAV: Classes  [+ Create class] [avatar]              │
├───────────────┬──────────────────────────────────────────┤
│  SIDEBAR      │                                          │
│               │  ┌────────────────────────────────────┐ │
│               │  │ Class       │Subject│Grade│Teacher  │ │
│               │  │ Maths 9B    │ MATH  │  9  │Ms. Ravi │ │
│               │  │ Science 8A  │ SCI   │  8  │Mr. Tan  │ │
│               │  │ English 10B │ ENG   │  10 │Ms. Wu   │ │
│               │  └────────────────────────────────────┘ │
│               │                                          │
│               │  Click any row → class detail side panel │
└───────────────┴──────────────────────────────────────────┘
```

Clicking a row opens a right-side panel (not a new page — inline slide-in panel):

```
Side panel (fixed right, w-80, slides in from right):
  Class name (editable inline)
  Subject + Grade (read only)
  Teacher assigned: [dropdown to reassign]

  "Enrolled students" section:
    List of student names + status badges (Onboarding/Active)
    [+ Enroll students] button → select from existing student list

  [Deactivate class] button (danger, bottom of panel)
```

### `CreateClassModal.tsx`

```
Fields:
  - Class name (e.g. "Maths 9B")  required
  - Subject: dropdown (MATH / SCI / ENG / BIO / CHEM / PHY / ENGL)
  - Grade: dropdown (Grade 6 → Grade 12)
  - Curriculum: dropdown (Cambridge Lower / IGCSE — driven by grade selection)
    Auto-suggested based on grade: Grades 6-8 → cambridge_lower, 9-10 → igcse
  - Teacher: dropdown of active teachers in this school
Actions: [Cancel]  [Create class →]
On success: modal closes, toast "Class created", table row added
```

Note: curriculum is auto-suggested by grade but overridable.
The `curriculum_id` fed to the POST /classes endpoint must be a valid UUID from the
`curricula` table — use a lookup, not a hardcoded value.

---

## Data (`useSchoolAdmin.ts`)

```typescript
// Queries needed:
// GET /api/v1/schools/{school_id}/classes
// GET /api/v1/schools/{school_id}/users?role=teacher|student|parent
// GET /api/v1/schools/{school_id}/analytics  (for overview KPIs)
// GET /api/v1/curricula  (for class creation dropdown)
// GET /api/v1/grades     (for class creation dropdown)

// Mutations:
// POST /api/v1/schools/{school_id}/users       (invite user)
// POST /api/v1/schools/{school_id}/classes     (create class)
// POST /api/v1/classes/{classId}/enroll        (enroll students)
// PATCH /api/v1/schools/{school_id}/users/:id  (deactivate)
```

---

## Acceptance Criteria

- [ ] E2E: School Admin logs in → lands on `/school/overview`
- [ ] E2E: overview shows correct teacher count, student count, onboarding %
- [ ] E2E: clicking `[+ Invite user]` on users page → modal opens
- [ ] E2E: invite modal submits → toast "Invite sent" → new row appears with "Invited" badge
- [ ] E2E: role tabs switch between Teachers / Students / Parents lists
- [ ] E2E: `[+ Create class]` → modal opens → form fills → class appears in table
- [ ] E2E: clicking a class row → side panel slides in with class details
- [ ] E2E: side panel allows reassigning teacher → save → row updates
- [ ] E2E: Teacher role trying to access `/school/overview` → redirected to `/teacher/dashboard`
- [ ] Unit: `InviteUserModal` with empty email → shows validation error "Enter a valid email address"
- [ ] Unit: `CreateClassModal` selecting Grade 9 → curriculum auto-suggests "Cambridge IGCSE"
- [ ] Unit: `CreateClassModal` selecting Grade 7 → curriculum auto-suggests "Cambridge Lower Secondary"
- [ ] Responsive: all three pages usable at 768px (school admin on tablet is common)
- [ ] Design: uses `DashboardLayout variant="school-admin"` — green left stripe active nav
- [ ] Design: KPI cards use `border-role-school-border` not generic gray
