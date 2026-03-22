# M0-7-T4b — School Admin Settings UI (School Admin App)
**Milestone:** M0 · **Epic:** M0-7 · **Task:** T4b
**Depends on:** M0-7-T4 (school admin shell pages), M0-3-T4 (auth frontend)
**Blocks:** Nothing — standalone settings page
**Estimated effort:** 2–3 hours

---

## Context

All code in this task lives in `frontend/apps/school-admin`. No code goes in any
other app.

Read `docs/design/DESIGN_SYSTEM.md` §5.2 (School Admin) before writing any component.
Green is the action color. Left green stripe is the sidebar active state.

Two distinct concerns on this page: the school admin's own account details (editable)
and the school profile (read-only — managed by Kaihle Admin). Keeping them visually
separated avoids confusion about what the admin can and cannot change.

---

## User Story

As a school admin, I want to update my display name and change my password from within
the app, and view my school's profile details so I understand what Kaihle Admin has
configured for my school.

---

## Files to Create

```
frontend/apps/school-admin/src/pages/settings/
  SchoolAdminSettingsPage.tsx    ← page shell

frontend/apps/school-admin/src/tests/
  school-admin-settings.spec.ts  ← Playwright E2E tests
```

---

## Route

`/school-admin/settings` — `SchoolAdminSettingsPage`.
Protected by `PrivateRoute` + `RoleRoute(['SCHOOL_ADMIN'])`.

Reached via avatar dropdown in topbar. Not in the sidebar nav.

---

## Complete List of API Calls This UI Makes

`GET /api/v1/schools/{schoolId}` — called on mount to display school profile.
Returns school name, country, city, timezone, slug.

`PATCH /api/v1/users/me` — called when admin saves name change.
Body: `{ first_name, last_name }`. Returns updated `UserResponse`.

`POST /api/v1/auth/change-password` — called on password change.
Body: `{ current_password, new_password }`. Returns 200, 400, or 422.

`POST /api/v1/auth/logout` — called on sign out. Clears tokens, redirects `/login`.

---

## Page Layout

```
Settings
Ms. Sari Kim · School Admin · Green Valley International

MY ACCOUNT
┌──────────────────────────────────────────────────────────────┐
│  Name        Ms. Sari Kim                        [Edit]      │
│  ──────────────────────────────────────────────────────────  │
│  Email       sari.kim@greenvalley.edu   [Managed by school]  │
│  ──────────────────────────────────────────────────────────  │
│  Password    Last changed 2 months ago             [Change]  │
└──────────────────────────────────────────────────────────────┘

SCHOOL PROFILE
┌──────────────────────────────────────────────────────────────┐
│  School name    Green Valley International School            │
│  Country        Indonesia                                    │
│  City           Kuta, Bali                                   │
│  Timezone       Asia/Makassar (WITA, UTC+8)                  │
│  School slug    green-valley                                 │
│  ─────────────────────────────────────────────────────────── │
│  ℹ️  School profile is managed by Kaihle. Contact            │
│     support@kaihle.com to request changes.                   │
└──────────────────────────────────────────────────────────────┘

ACCOUNT ACTIONS
┌──────────────────────────────────────────────────────────────┐
│  Sign out   You will need to sign in again.    [Sign out]    │
└──────────────────────────────────────────────────────────────┘
```

Max content width: `max-w-lg` — settings pages use narrow reading column.

---

## My Account section

Card: `bg-white border border-role-school-border rounded-2xl`.

**Name row:**
- Label + current display name (muted)
- "Edit" link (green text, `text-brand-primary`)
- Click → inline form expands below row
- Form: First name input + Last name input (side by side on desktop)
- Validation: both required
- Buttons: "Save" (`bg-brand-primary text-white rounded-full`) · "Cancel" (ghost outline)
- On success: toast "Name updated", collapse form, refresh displayed name
- On API error: inline error below inputs

**Email row:**
- Label + email address (muted)
- Right: "Managed by school" (small muted — no edit link)

**Password row:**
- Label + "Last changed {relative time}" (muted)
- "Change" link (green text)
- Click → inline form expands
- Three fields stacked: Current password · New password · Confirm new password
- Client-side validation: new and confirm must match before submit
- On 400 from API: "Current password is incorrect" inline error
- On success: toast "Password updated", collapse and clear form
- Buttons: "Update password" (green) · "Cancel" (ghost)

Only one inline form open at a time — opening one auto-closes the other.

---

## School Profile section

Card: `bg-white border border-role-school-border rounded-2xl p-5`.

Rows (all read-only, no edit controls):
- School name
- Country
- City
- Timezone (display name + abbreviation + UTC offset)
- School slug (monospace font, `font-mono text-sm text-gray-600`)

Below rows: info note in `bg-blue-50 border border-blue-100 rounded-lg p-3`:
"School profile is managed by Kaihle. Contact support@kaihle.com to request changes."

---

## Account actions section

Card: `bg-white border border-red-200 rounded-2xl`.

**Sign out row:**
- Label + sub text
- Button: `border border-red-200 text-red-600 rounded-full` outline — never filled red
- On click: `POST /auth/logout` → clear tokens → `/login`

---

## Acceptance Criteria

**Playwright E2E tests in `school-admin-settings.spec.ts`**

`test_settings_when_loaded_then_three_sections_visible` — Navigate to
`/school-admin/settings`. Assert account, school profile, and account actions
sections are visible.

`test_settings_when_edit_name_clicked_then_two_inputs_visible` — Click "Edit" on
name row. Assert first name and last name inputs appear.

`test_settings_when_name_saved_then_row_updates` — Fill new name, click Save. Mock
`PATCH /users/me` → 200. Assert row shows new name.

`test_settings_when_school_profile_then_no_edit_links` — Assert no "Edit" link or
input field is present in the School Profile section.

`test_settings_when_password_mismatch_then_error_before_api` — Fill different
new/confirm password values. Click "Update password". Assert a validation error
is shown and no API call is made.

`test_settings_when_wrong_current_password_then_error_shown` — Mock
`POST /auth/change-password` → 400. Assert "Current password is incorrect" message.

`test_settings_when_sign_out_then_redirects_to_login` — Click sign out. Mock
`POST /auth/logout` → 200. Assert URL becomes `/login`.

**Jest unit tests**

`test_password_form_when_confirm_differs_then_submit_disabled` — Assert submit
button is disabled when new and confirm passwords differ.

---

## Do NOT Touch

`frontend/apps/teacher/` — no code goes here.
`frontend/apps/student/` — no code goes here.
Any backend file — all endpoints already exist.
