# M0-9-T3 — Kaihle Admin App Migration
**Milestone:** M0 — Foundations
**Epic:** M0-9 — Architecture Corrections and Spec Alignment
**Task ID:** M0-9-T3
**Depends on:** M0-9-T1 (apps/kaihle-admin scaffold must exist), M0-7-T5 (source pages to migrate)
**Blocks:** Nothing — but M1 must not begin until this task is complete
**Estimated effort:** 3–4 hours

---

## Context

Task M0-7-T5 built Kaihle Admin pages (AdminOverview, AdminSchools, AdminSchoolDetail,
AdminCreateSchoolModal, AdminExtendTrialModal) but placed them incorrectly inside
`apps/teacher/src/pages/kaihle-admin/`. This task migrates all of that work into its
correct home at `apps/kaihle-admin/src/pages/`, wires up routing in the new app's
`App.tsx`, and deletes the source directory from `apps/teacher`.

Read `CONSTITUTION.md` §3 (App Isolation Rule) and `docs/design/DESIGN_SYSTEM.md`
§5.1 (Kaihle Admin design spec) before writing any code. Kaihle Admin uses
`AdminLayout`, Inter font throughout — no Fraunces, no Lora — and a neutral gray
admin aesthetic distinct from both teacher and school admin styling.

---

## User Story

As Vibhu (Kaihle Admin), I want a dedicated admin portal at port 3005 — entirely
separate from the teacher and school admin interfaces — so that platform-level
administration is isolated, clearly scoped to internal use, and independently deployable.

---

## Files to Move (source → destination)

```
FROM: frontend/apps/teacher/src/pages/kaihle-admin/AdminOverview.tsx
TO:   frontend/apps/kaihle-admin/src/pages/AdminOverview.tsx

FROM: frontend/apps/teacher/src/pages/kaihle-admin/AdminSchools.tsx
TO:   frontend/apps/kaihle-admin/src/pages/AdminSchools.tsx

FROM: frontend/apps/teacher/src/pages/kaihle-admin/AdminSchoolDetail.tsx
TO:   frontend/apps/kaihle-admin/src/pages/AdminSchoolDetail.tsx

FROM: frontend/apps/teacher/src/pages/kaihle-admin/AdminCreateSchoolModal.tsx
TO:   frontend/apps/kaihle-admin/src/pages/AdminCreateSchoolModal.tsx

FROM: frontend/apps/teacher/src/pages/kaihle-admin/AdminExtendTrialModal.tsx
TO:   frontend/apps/kaihle-admin/src/pages/AdminExtendTrialModal.tsx
```

Also move hooks and tests:

```
FROM: frontend/apps/teacher/src/hooks/useKaihleAdmin.ts
TO:   frontend/apps/kaihle-admin/src/hooks/useKaihleAdmin.ts

FROM: frontend/apps/teacher/src/tests/kaihle-admin.spec.ts
TO:   frontend/apps/kaihle-admin/src/tests/kaihle-admin.spec.ts
```

---

## Files to Delete After Migration

```
frontend/apps/teacher/src/pages/kaihle-admin/   ← entire directory, recursively
```

---

## Files to Modify

### `frontend/apps/kaihle-admin/src/App.tsx`

Replace the scaffold placeholder from M0-9-T1 with real routes:

```tsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { PrivateRoute, RoleRoute } from '@kaihle/auth'
import { LoginPage } from './pages/LoginPage'
import { AdminOverview } from './pages/AdminOverview'
import { AdminSchools } from './pages/AdminSchools'
import { AdminSchoolDetail } from './pages/AdminSchoolDetail'

// Kaihle Admin does NOT use PasswordSetupRoute — Kaihle Admin accounts
// are created directly, not via magic link invitation in v1.
// If this changes in future, add PasswordSetupRoute here.
export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/kaihle-admin/*"
          element={
            <PrivateRoute>
              <RoleRoute roles={['KAIHLE_ADMIN']}>
                <Routes>
                  <Route path="dashboard" element={<AdminOverview />} />
                  <Route path="schools" element={<AdminSchools />} />
                  <Route path="schools/:schoolId" element={<AdminSchoolDetail />} />
                  <Route index element={<Navigate to="dashboard" replace />} />
                </Routes>
              </RoleRoute>
            </PrivateRoute>
          }
        />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
```

### `frontend/apps/teacher/src/App.tsx`

Remove all Kaihle Admin routes from the teacher app:

```tsx
// DELETE these routes — they no longer belong in the teacher app:
// <Route path="/kaihle-admin/*" element={...} />
// Any RoleRoute wrapping KAIHLE_ADMIN in this file
```

After deletion, verify with `grep -r "KAIHLE_ADMIN" apps/teacher/src/` — it must
return zero results.

---

## Design Corrections to Apply During Migration

Kaihle Admin has a strictly different design spec from Teacher and School Admin. The
pages were built inside the teacher app and may have picked up incorrect tokens. Apply
these corrections during migration.

All fonts in Kaihle Admin must be Inter. If any heading uses `font-fraunces` or
`font-lora`, replace with `font-inter` or remove the font class entirely (Inter is the
base font in the AdminLayout). Search each file for `fraunces` and `lora` and remove.

The layout wrapper must be `AdminLayout` from `packages/ui`, not `DashboardLayout`.
`DashboardLayout` is for Teacher and School Admin only. If any page wraps itself in
`DashboardLayout`, replace it with `AdminLayout`.

Action buttons use green (`bg-brand-primary`). If any button uses gold
(`bg-brand-gold`), replace it. Gold is the Teacher action color only.

The page background in Kaihle Admin is `#f8f9fb` (neutral gray-white), not the green
tint `#f5f7f1` used in School Admin. If any page sets a background color explicitly
using the school-admin token, correct it to the admin token.

---

## Playwright E2E Update

Update `apps/kaihle-admin/src/tests/kaihle-admin.spec.ts` to point at
`http://localhost:3005` instead of `http://localhost:3001`. Also update the test
that verifies the post-login redirect — it should land on
`/kaihle-admin/dashboard`, not `/teacher/dashboard`.

---

## Acceptance Criteria

- `http://localhost:3005/kaihle-admin/dashboard` renders AdminOverview with
  Inter font throughout and no Fraunces headings
- `http://localhost:3005/kaihle-admin/schools` renders AdminSchools correctly
- A teacher JWT (role: TEACHER) accessing `http://localhost:3005/kaihle-admin/*`
  is redirected by `RoleRoute` — not shown admin content
- `grep -r "kaihle-admin" apps/teacher/src/` returns zero results
- `grep -r "KAIHLE_ADMIN" apps/teacher/src/` returns zero results
- `grep -r "font-fraunces" apps/kaihle-admin/src/` returns zero results
- `grep -r "DashboardLayout" apps/kaihle-admin/src/` returns zero results
- `tsc --noEmit` passes in `apps/kaihle-admin`
- Playwright E2E spec runs against `http://localhost:3005` and passes

---

## Do NOT Touch

- Any file in `apps/teacher/src/` other than the `kaihle-admin/` subdirectory and
  the App.tsx route cleanup
- Any backend route or service
- Any file in `packages/ui` or `packages/auth`
