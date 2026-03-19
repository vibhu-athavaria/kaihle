# M0-9-T2 — School Admin App Migration
**Milestone:** M0 — Foundations
**Epic:** M0-9 — Architecture Corrections and Spec Alignment
**Task ID:** M0-9-T2
**Depends on:** M0-9-T1 (apps/school-admin scaffold must exist), M0-7-T4 (source pages to migrate)
**Blocks:** Nothing — but M1 must not begin until this task is complete
**Estimated effort:** 3–4 hours

---

## Context

Task M0-7-T4 built School Admin pages (SchoolOverview, UserManagement, ClassManagement,
InviteUserModal, CreateClassModal) but placed them incorrectly inside `apps/teacher/src/pages/school-admin/`.
This task migrates all of that work into its correct home at `apps/school-admin/src/pages/`,
wires up the routing in the new app's `App.tsx`, and deletes the source directory from
`apps/teacher` so no cross-role code remains.

Read `CONSTITUTION.md` §3 (App Isolation Rule) and `docs/design/DESIGN_SYSTEM.md`
§5.2 (School Admin design spec) before writing any code. School Admin uses
`DashboardLayout variant="school-admin"`, Fraunces headings, and green-tinted borders.
None of these are the same as the teacher app's design tokens.

---

## User Story

As a school admin, I want my own dedicated portal at port 3004 — separate from the
teacher interface — so that my pages use the correct design, my session is isolated
from teacher sessions, and my app can be deployed and scaled independently.

---

## Files to Move (source → destination)

```
FROM: frontend/apps/teacher/src/pages/school-admin/SchoolOverview.tsx
TO:   frontend/apps/school-admin/src/pages/SchoolOverview.tsx

FROM: frontend/apps/teacher/src/pages/school-admin/UserManagement.tsx
TO:   frontend/apps/school-admin/src/pages/UserManagement.tsx

FROM: frontend/apps/teacher/src/pages/school-admin/ClassManagement.tsx
TO:   frontend/apps/school-admin/src/pages/ClassManagement.tsx

FROM: frontend/apps/teacher/src/pages/school-admin/InviteUserModal.tsx
TO:   frontend/apps/school-admin/src/pages/InviteUserModal.tsx

FROM: frontend/apps/teacher/src/pages/school-admin/CreateClassModal.tsx
TO:   frontend/apps/school-admin/src/pages/CreateClassModal.tsx
```

Also move any hooks created by M0-7-T4 for school admin data:

```
FROM: frontend/apps/teacher/src/hooks/useSchoolAdmin.ts
TO:   frontend/apps/school-admin/src/hooks/useSchoolAdmin.ts
```

And move the Playwright E2E spec:

```
FROM: frontend/apps/teacher/src/tests/school-admin.spec.ts
TO:   frontend/apps/school-admin/src/tests/school-admin.spec.ts
```

---

## Files to Delete After Migration

```
frontend/apps/teacher/src/pages/school-admin/   ← entire directory, recursively
```

Verify with `ls frontend/apps/teacher/src/pages/` after deletion — the
`school-admin/` subdirectory must not appear.

---

## Files to Modify

### `frontend/apps/school-admin/src/App.tsx`

Replace the scaffold placeholder from M0-9-T1 with real routes:

```tsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { PrivateRoute, RoleRoute, PasswordSetupRoute } from '@kaihle/auth'
import { LoginPage } from './pages/LoginPage'
import { SchoolOverview } from './pages/SchoolOverview'
import { UserManagement } from './pages/UserManagement'
import { ClassManagement } from './pages/ClassManagement'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />

        {/* Password setup — required before any other school-admin route */}
        <Route
          path="/school-admin/setup-password"
          element={
            <PrivateRoute>
              {/* PasswordSetupPage wired in M0-9-T4 */}
              <div className="p-8 text-gray-500">Password setup — wired in M0-9-T4</div>
            </PrivateRoute>
          }
        />

        {/* All school admin pages — require auth + password setup + correct role */}
        <Route
          path="/school-admin/*"
          element={
            <PrivateRoute>
              <PasswordSetupRoute>
                <RoleRoute roles={['SCHOOL_ADMIN', 'KAIHLE_ADMIN']}>
                  <Routes>
                    <Route path="dashboard" element={<SchoolOverview />} />
                    <Route path="users" element={<UserManagement />} />
                    <Route path="classes" element={<ClassManagement />} />
                    <Route index element={<Navigate to="dashboard" replace />} />
                  </Routes>
                </RoleRoute>
              </PasswordSetupRoute>
            </PrivateRoute>
          }
        />

        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
```

Note that `KAIHLE_ADMIN` is included in the `RoleRoute` — this allows a Kaihle Admin
who is viewing a specific school's admin interface to access these pages.

### Imports in migrated page files

After moving the files, update any relative imports that previously navigated up into
`apps/teacher/src/` to use the correct paths within `apps/school-admin/src/`. For
example, if a page previously imported a hook via `../../hooks/useSchoolAdmin`, the
new relative path from `pages/` to `hooks/` within the same app is simply
`../hooks/useSchoolAdmin`.

Also update any imports that used teacher-specific layout components. If any migrated
page references `DashboardLayout` without a `variant` prop, add `variant="school-admin"`.
If any page uses `brand-gold` action colors (a teacher-specific token), replace with
`brand-primary` (green) which is the School Admin action color.

### `frontend/apps/teacher/src/App.tsx`

Remove the school admin routes that were previously defined here:

```tsx
// DELETE these routes — they no longer belong in the teacher app:
// <Route path="/school/overview" element={...} />
// <Route path="/school/users" element={...} />
// <Route path="/school/classes" element={...} />
// Any RoleRoute wrapping SCHOOL_ADMIN in this file
```

After deletion, verify that `SCHOOL_ADMIN` does not appear anywhere in
`apps/teacher/src/` via `grep -r "SCHOOL_ADMIN" apps/teacher/src/`.

---

## Design Corrections to Apply During Migration

Because the pages were built inside the teacher app, they may have inherited
teacher-specific design decisions. During migration, audit each page for the following
and correct as needed.

Action buttons should use `bg-brand-primary` (green), not `bg-brand-gold` or any gold
variant. Gold is the teacher action color and must never appear in School Admin pages.

Headings should use `font-fraunces` (Fraunces serif), not `font-nunito`. School Admin
uses Fraunces for display headings per the design system.

The sidebar active state should use a left green stripe (`border-l-4 border-brand-primary
bg-brand-primary/5`), not the gold tint fill used in the teacher layout.

Layout wrapper should be `DashboardLayout variant="school-admin"`. If any page uses
`DashboardLayout` without a variant, or `DashboardLayout variant="teacher"`, correct it.

---

## Playwright E2E Update

Update `apps/school-admin/src/tests/school-admin.spec.ts` to point at the correct
base URL for the school admin app (`http://localhost:3004`) instead of the teacher
app URL (`http://localhost:3001`).

---

## Acceptance Criteria

- `http://localhost:3004/school-admin/dashboard` renders SchoolOverview with the
  school admin design (Fraunces headings, green action buttons, no gold)
- `http://localhost:3004/school-admin/users` renders UserManagement correctly
- `http://localhost:3004/school-admin/classes` renders ClassManagement correctly
- `grep -r "school-admin" apps/teacher/src/` returns zero results
- `grep -r "SCHOOL_ADMIN" apps/teacher/src/` returns zero results
- `tsc --noEmit` passes in `apps/school-admin`
- Playwright E2E spec runs against `http://localhost:3004` and passes
- No gold/teacher-specific color tokens remain in any school admin page

---

## Do NOT Touch

- Any file in `apps/teacher/src/pages/` other than the `school-admin/` subdirectory
- Any backend route or service
- Any file in `packages/ui` or `packages/auth`
