# M0-7-T4 — School Admin UI Pages
**Milestone:** M0 — Foundations
**Epic:** M0-7 — Frontend Foundations
**Task ID:** M0-7-T4
**Depends on:** M0-8-T3 (brand tokens in tailwind), M0-8-T4 (Button, Card, Badge, Input from @kaihle/ui), M0-7-T1 (layout wrappers), M0-4-T1/T2/T3 (school/user/class APIs), M0-3-T4 (auth)
**Blocks:** M6-1-T2 (analytics UI), M6-1-T3 (class gap map admin), M6-2-T2 (billing UI school admin)
**Estimated effort:** 5–6 hours

> ⚠️ **SUPERSESSION NOTE — READ BEFORE STARTING**
>
> This task was originally written to place files in `frontend/apps/teacher/`.
> That was wrong. CONSTITUTION.md §3 (App Isolation Rule, added in ADR-001) and
> M0-9-T2 corrected this. **All files in this task MUST go in `apps/school-admin/`.**
>
> If M0-9-T2 has already run, its migration is the canonical version of these pages.
> Do not re-create them — instead verify they exist at the correct path and proceed to
> the new tasks listed at the bottom of this file (T4b and T4c).
>
> If M0-9-T2 has NOT yet run, build the pages directly in `apps/school-admin/` and
> skip M0-9-T2 entirely (its migration work is unnecessary if you build in the right
> place to begin with).

---

## Context

School Admin lives in `apps/school-admin` (port 3004). Three pages need building:
the overview/home page, the user management page, and the class management page.
Analytics (M6-1-T2), billing (M6-2-T2), and class gap map (M6-1-T3) are separate
tasks in their respective milestones.

Read `docs/design/DESIGN_SYSTEM.md` §5.2 (School Admin) before writing any code.
Read `docs/design/screens/SCHOOL_ADMIN_SCREENS.md` for full page specifications.
Use `DashboardLayout variant="school-admin"` from `packages/ui`.

---

## User Story

As a school admin, I want a home overview, a user management interface, and a class
management interface so I can set up and manage my school on the platform.

---

## Files to Create

```
frontend/apps/school-admin/src/pages/
  SchoolOverview.tsx             ← home page / landing after School Admin login
  UserManagement.tsx             ← invite + manage teachers, students, parents
  ClassManagement.tsx            ← create classes, assign teachers, enroll students

frontend/apps/school-admin/src/components/
  InviteUserModal.tsx            ← modal for inviting a new user
  CreateClassModal.tsx           ← modal for creating a new class

frontend/apps/school-admin/src/hooks/
  useSchoolAdmin.ts              ← React Query hooks for all school admin data

frontend/apps/school-admin/src/tests/
  school-admin.spec.ts           ← Playwright E2E
```

**NEVER place files in `frontend/apps/teacher/`. Violation of CONSTITUTION §3.**

---

## Routes

```
/school-admin/overview    → SchoolOverview.tsx
/school-admin/users       → UserManagement.tsx
/school-admin/classes     → ClassManagement.tsx
```

All routes protected by `RoleRoute` requiring `SCHOOL_ADMIN | KAIHLE_ADMIN`.
Teacher role attempting to access `/school-admin/*` → redirect to `/teacher/dashboard`.

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
│  Users        │  └────────┘ └────────┘ └────────┘       │
│  Classes      │                                          │
│  Analytics    │  ── Classes ──────────────────────────  │
│  Billing      │  ┌──────────────────────────────────┐   │
│               │  │ Class      │ Teacher   │ Mastery  │   │
│               │  │ Maths 9B   │ Ms. Ravi  │  61%     │   │
│               │  │ Science 8A │ Mr. Tan   │  74%     │   │
│               │  └──────────────────────────────────┘   │
│               │  [+ Create class]                        │
│               │                                          │
│               │  ── Onboarding progress ──────────────  │
│               │  73% students fully onboarded            │
│               │  [██████████████░░░░░░] 107 / 147        │
│               │  [View analytics →]                      │
└───────────────┴──────────────────────────────────────────┘
```

KPI cards: `bg-white border-role-school-border`. Green-tinted borders, not gray.
Classes table: compact, no pagination initially (max 10 rows, scroll if more).
Onboarding progress: `bg-brand-light` card with `bg-brand-primary` progress bar.

---

## Page 2: User Management (`UserManagement.tsx`)

Role tabs: `[Teachers] [Students] [Parents]` — horizontal pill toggle.
Active tab: `bg-white shadow-sm`. Inactive: `bg-gray-100`.

Table rows: avatar initials + name + email + status badge + action menu (⋮)
Action menu: Resend invite | Deactivate (for active) | Reactivate (for inactive)
Status badges: `● Active` (brand-green) / `○ Invited` (brand-gold) / `✕ Inactive` (muted)

`[+ Invite user]` topnav button → opens `InviteUserModal`.

### `InviteUserModal.tsx`

```
Modal (centered, bg-white rounded-2xl p-6 max-w-md)
Title: "Invite a teacher" (or student/parent based on active tab)
Fields:
  - First name (required)
  - Last name (required)
  - Email address (required, validated)
  - Role: pre-filled from active tab, editable dropdown
Actions: [Cancel] [Send invite →]
On success: modal closes, toast "Invite sent to {email}", table row appears with "Invited" badge
```

---

## Page 3: Class Management (`ClassManagement.tsx`)

```
Table: Class | Subject | Grade | Teacher | Students | Avg mastery
Click row → right-side slide-in panel (320px, overlay behind)
```

**Class side panel:**
- Class name + subject + grade (header)
- Teacher section: initials + name + "Reassign" button
- Enrolled students: count + name pills (first 4 + "+ N more") + "+ Enroll students" button
- Performance: avg mastery badge + "View class gap map →" link → `/school-admin/classes/{id}/gap-map`
- Footer: "Deactivate class" red outline button

### `CreateClassModal.tsx`

```
Fields:
  - Class name (e.g. "Maths 9B") — required
  - Subject: dropdown (MATH / SCI / ENG / BIO / CHEM / PHY / ENGL)
  - Grade: dropdown (Grade 6 → Grade 12)
  - Curriculum: auto-suggested from grade (6–8 → Cambridge Lower, 9–10 → IGCSE), overridable
    Uses UUID lookup from GET /api/v1/curricula — never hardcoded IDs
  - Teacher: dropdown of active teachers in this school
Actions: [Cancel] [Create class →]
On success: toast "Class created", table row added
```

---

## New tasks added in design sprint — March 2026

The following tasks extend this epic. They were not in the original task file.

### M0-7-T4b — School Admin Settings UI
See `docs/tasks/M0/M0-7-T4b_school_admin_settings_ui.md`
- Route: `/school-admin/settings`
- Account section (name, email read-only, password change)
- School profile section (read-only — managed by Kaihle Admin)
- Sign out

---

## Data (`useSchoolAdmin.ts`)

```typescript
// Queries:
// GET /api/v1/schools/{schoolId}/classes
// GET /api/v1/schools/{schoolId}/users?role=teacher|student|parent
// GET /api/v1/schools/{schoolId}/analytics  (overview KPIs)
// GET /api/v1/curricula
// GET /api/v1/grades

// Mutations:
// POST /api/v1/schools/{schoolId}/users       (invite user)
// POST /api/v1/schools/{schoolId}/classes     (create class)
// POST /api/v1/classes/{classId}/enroll       (enroll students)
// PATCH /api/v1/schools/{schoolId}/users/:id  (deactivate)
```

---

## Acceptance Criteria

- [ ] E2E: School Admin logs in → lands on `/school-admin/overview`
- [ ] E2E: overview shows correct teacher count, student count, onboarding %
- [ ] E2E: clicking `[+ Invite user]` → modal opens
- [ ] E2E: invite modal submits → toast "Invite sent" → new row with "Invited" badge
- [ ] E2E: role tabs switch between Teachers / Students / Parents lists
- [ ] E2E: `[+ Create class]` → modal → class appears in table
- [ ] E2E: clicking class row → side panel slides in
- [ ] E2E: side panel allows reassigning teacher → save → row updates
- [ ] E2E: Teacher role accessing `/school-admin/*` → redirected to `/teacher/dashboard`
- [ ] Unit: `InviteUserModal` with empty email → validation error "Enter a valid email address"
- [ ] Unit: `CreateClassModal` Grade 9 → curriculum auto-suggests "Cambridge IGCSE"
- [ ] Unit: `CreateClassModal` Grade 7 → curriculum auto-suggests "Cambridge Lower Secondary"
- [ ] Design: `DashboardLayout variant="school-admin"` — green left stripe active nav
- [ ] Design: KPI cards use `border-role-school-border` not generic gray

---

## Do NOT Touch

`frontend/apps/teacher/` — School Admin code must never live here (CONSTITUTION §3).
`frontend/apps/student/` — no code goes here.
Any backend file.
