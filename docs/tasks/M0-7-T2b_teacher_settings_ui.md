# M0-7-T2b — Teacher Settings UI (Teacher App)
**Milestone:** M0 · **Epic:** M0-7 · **Task:** T2b
**Depends on:** M0-7-T1 (layout wrappers), M0-8-T4 (shared components), M0-3-T4 (auth frontend)
**Blocks:** Nothing — standalone account management page
**Estimated effort:** 2–3 hours

---

## Context

All code in this task lives in `frontend/apps/teacher`. No code goes in any other app.

Read `docs/design/DESIGN_SYSTEM.md` §5.3 (Teacher) before writing any component.
Gold is the action color for this role.

This is a basic account settings page. Scope is deliberately narrow in v1 — name
and password only. Notification preferences, class-level preferences, and email
changes (which may require school admin approval) are deferred.

---

## User Story

As a teacher, I want to update my display name and change my password from within
the app so I do not need to contact the school admin for basic account changes.

---

## Files to Create

```
frontend/apps/teacher/src/pages/settings/
  TeacherSettingsPage.tsx        ← page shell

frontend/apps/teacher/src/tests/
  teacher-settings.spec.ts       ← Playwright E2E tests
```

---

## Route

`/teacher/settings` — `TeacherSettingsPage`.
Protected by `PrivateRoute` + `RoleRoute(['TEACHER'])`.

Accessible from the sidebar footer area (avatar + name → settings link) or via a
Settings nav item if added to the sidebar TOOLS section. Do not add it to the main
MY CLASSES section — it is a profile concern, not a classroom concern.

---

## Complete List of API Calls This UI Makes

`PATCH /api/v1/users/me` — called when teacher saves a name change. Body:
`{ first_name: string, last_name: string }`. Returns updated `UserResponse`.

`POST /api/v1/auth/change-password` — called when teacher submits password change.
Body: `{ current_password: string, new_password: string }`. Returns 200 on success,
400 if current password is wrong, 422 if new password fails validation.

Those are the only two API calls.

---

## Page Layout

```
┌──────────────────────────────────────────────────────────────┐
│  Dashboard layout — variant="teacher"                        │
│  Sidebar active: Settings (TOOLS section)                    │
├──────────────────────────────────────────────────────────────┤
│  Page title: Settings                                        │
│  Sub: Ms. Ravi Tan · Mathematics · Science                   │
│                                                              │
│  ACCOUNT                                                     │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Name        Ms. Ravi Tan                  [Edit]    │   │
│  │  ─────────────────────────────────────────────────   │   │
│  │  Email       ravi.tan@school.edu   [Managed by school]│  │
│  │  ─────────────────────────────────────────────────   │   │
│  │  Password    Last changed 3 months ago      [Change] │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ACCOUNT ACTIONS                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Sign out                              [Sign out]    │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

Max content width: `max-w-lg` — settings pages are narrow by convention.

---

## Account section

Settings card: `bg-white border border-role-teacher-border rounded-2xl`.

**Name row:**
- Label: "Name" (font-semibold, small)
- Value: current display name (muted)
- "Edit" link (gold text, `text-brand-gold hover:text-amber-600`)
- Click Edit → expand inline edit form below the row

**Inline name edit form:**
- Two inputs: First name + Last name (side by side on desktop, stacked on mobile)
- Validation: both required, min 1 character
- Buttons: "Save" (gold, `bg-brand-gold`) · "Cancel" (ghost outline)
- On save: call `PATCH /api/v1/users/me`, show success toast "Name updated",
  collapse form, refresh displayed name
- On cancel: collapse form, no API call

**Email row:**
- Label: "Email"
- Value: email address (muted)
- Right: "Managed by school" (small, muted text — no edit link)
- Note: email changes require school admin action; not self-service in v1

**Password row:**
- Label: "Password"
- Value: "Last changed {relative time}" (muted) — derive from user's `updated_at`
  if available, otherwise "—"
- "Change" link (gold text)
- Click Change → expand inline password change form

**Inline password change form:**
- Three inputs stacked: Current password · New password · Confirm new password
- All type="password"
- Validation:
  - Current password: required
  - New password: required, min 8 characters
  - Confirm: must match new password — validate client-side before submit
- Buttons: "Update password" (gold) · "Cancel" (ghost)
- On submit: call `POST /api/v1/auth/change-password`
  - 200: success toast "Password updated", collapse form
  - 400: inline error "Current password is incorrect"
  - 422: inline error listing validation failures
- On cancel: collapse form, clear all fields

Only one inline form can be open at a time. Opening the password form collapses
the name form if it is open, and vice versa.

---

## Account actions section

Single card: `bg-white border border-red-200 rounded-2xl`.

**Sign out row:**
- Label: "Sign out" (font-semibold)
- Sub: "You will need to sign in again on this device" (muted)
- "Sign out" button: `bg-white border border-red-200 text-red-600 rounded-full` —
  NOT a filled red button. Outline only.
- On click: confirmation browser dialog is NOT needed — call `POST /api/v1/auth/logout`,
  clear tokens, redirect to `/login`.

No account deletion in v1.

---

## Acceptance Criteria

**Playwright E2E tests in `teacher-settings.spec.ts`**

`test_settings_page_when_loaded_then_name_email_password_rows_visible` — Navigate to
`/teacher/settings`. Assert three rows are visible: Name, Email, Password.

`test_settings_page_when_edit_name_clicked_then_form_expands` — Click the "Edit" link
on the Name row. Assert two input fields (first name, last name) become visible.

`test_settings_page_when_name_saved_then_form_collapses` — Fill in new name, click
Save. Mock `PATCH /users/me` to return 200. Assert the form collapses and the new
name appears in the row.

`test_settings_page_when_change_password_clicked_then_form_expands` — Click "Change"
on Password row. Assert three password input fields are visible.

`test_settings_page_when_new_passwords_dont_match_then_error_shown` — Fill mismatched
new/confirm passwords, click "Update password". Assert client-side validation error
is visible before any API call.

`test_settings_page_when_wrong_current_password_then_api_error_shown` — Mock
`POST /auth/change-password` to return 400. Click "Update password". Assert inline
error "Current password is incorrect" is visible.

`test_settings_page_when_sign_out_clicked_then_redirects_to_login` — Click sign out.
Mock `POST /auth/logout` to return 200. Assert URL changes to `/login`.

`test_settings_page_when_name_form_open_and_password_clicked_then_name_form_closes` —
Open the name edit form. Click "Change" on password row. Assert name form is no
longer visible.

**Jest unit tests**

`test_password_form_when_new_and_confirm_differ_then_submit_disabled` — Render the
password form with different values in new/confirm. Assert the submit button is
disabled or shows an error.

---

## Do NOT Touch

`frontend/apps/student/` — no code goes here.
`frontend/apps/school-admin/` — no code goes here.
`frontend/packages/ui/` — do not add settings-specific components here.
Any backend file — all endpoints already exist.
