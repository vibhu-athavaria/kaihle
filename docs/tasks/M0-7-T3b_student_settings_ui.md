# M0-7-T3b — Student Settings UI (Student App)
**Milestone:** M0 · **Epic:** M0-7 · **Task:** T3b
**Depends on:** M0-7-T3 (student dashboard), M0-6-T4 (onboarding questionnaire UI), M0-3-T4 (auth frontend)
**Blocks:** Nothing — standalone settings page
**Estimated effort:** 2–3 hours

---

## Context

All code in this task lives in `frontend/apps/student`. No code goes in any other app.

Read `docs/design/DESIGN_SYSTEM.md` §5.4 (Student) before writing any component.
Green `#1a5c38` is the action color. Page background `#f9fafb`. No sidebar —
`StudentLayout` only.

This page is reached via the avatar/profile icon in the top-right of the student
topbar — it is NOT in the bottom nav. The URL is accessible directly.

Two main concerns: account details (name, password) and learning profile (view current
profile, retake questionnaire). Email is managed by the school — not self-service.

---

## User Story

As a student, I want to update my name, change my password, and retake my learning
profile questionnaire if my preferences have changed, so that Kaihle can better
personalise my study experience.

---

## Files to Create

```
frontend/apps/student/src/pages/settings/
  StudentSettingsPage.tsx        ← page shell

frontend/apps/student/src/tests/
  student-settings.spec.ts       ← Playwright E2E tests
```

---

## Route

`/student/settings` — `StudentSettingsPage`.
Protected by `PrivateRoute` + `OnboardingRoute` (student must have completed
learning profile to access settings).

The settings page is not part of the bottom nav tab set. It is reached by tapping
the avatar in the topnav. On desktop, clicking the avatar could show a small dropdown:
"Settings" and "Sign out". On mobile, both options can be in the settings page itself.

---

## Complete List of API Calls This UI Makes

`GET /api/v1/onboarding/learning-profile` — called on mount (no `student_id` param —
student reads their own profile). Returns `StudentLearningProfileResponse`.

`PATCH /api/v1/users/me` — called when student saves a name change. Body:
`{ first_name: string, last_name: string }`. Returns updated `UserResponse`.

`POST /api/v1/auth/change-password` — called on password change submission. Body:
`{ current_password: string, new_password: string }`. Returns 200 or 400/422.

`POST /api/v1/auth/logout` — called on sign out. Returns 200. Then clear tokens,
redirect to `/login`.

Note: Retake questionnaire does NOT call an endpoint from this page — it navigates
to `/student/onboarding/profile` which handles the questionnaire flow. The existing
`POST /api/v1/onboarding/questionnaire/submit` endpoint is idempotent — re-submitting
updates the existing `student_learning_profiles` row.

---

## Page Layout

Uses `StudentLayout` — top nav tabs visible on desktop, bottom nav on mobile.
No active tab highlighted (settings is not one of the 4 nav items).

Content max-width: `max-w-lg mx-auto` — narrow reading column suits settings pages.

```
Settings
Aisha Rahman · Grade 7 · Green Valley International School

ACCOUNT
┌─────────────────────────────────────────────────────────────┐
│  Name          Aisha Rahman                        [Edit]   │
│  ─────────────────────────────────────────────────────────  │
│  Email         aisha@greenvalley.edu   [Managed by school]  │
│  ─────────────────────────────────────────────────────────  │
│  Password      Last changed 3 months ago          [Change]  │
└─────────────────────────────────────────────────────────────┘

LEARNING PROFILE
┌─────────────────────────────────────────────────────────────┐
│  Your learning profile             Completed 12 Jan 2026    │
│                                                             │
│  Learning style:                                            │
│  Kinesthetic  [████████░░]  80%                             │
│  Visual       [█████░░░░░]  55%                             │
│  Reading      [███░░░░░░░]  30%                             │
│  Auditory     [██░░░░░░░░]  20%                             │
│                                                             │
│  Interests: ⚽ Football  🎮 Gaming  🎨 Art                   │
│                                                             │
│  [↺ Retake questionnaire]                                   │
│  Updating your profile improves future personalisation.     │
│  Takes about 5 minutes.                                     │
└─────────────────────────────────────────────────────────────┘

ACCOUNT ACTIONS
┌─────────────────────────────────────────────────────────────┐
│  Sign out                                      [Sign out]   │
└─────────────────────────────────────────────────────────────┘
```

---

## Account section

Card: `bg-white border border-role-student-border rounded-2xl`.
`role-student-border` = student app border token.

**Name row:**
- Label + current name (muted)
- "Edit" link → inline form expands below row
- Form: First name + Last name inputs, "Save" (green button, `bg-brand-primary`) +
  "Cancel" (ghost)
- Validation: both required
- On success: toast "Name updated", collapse form

**Email row:**
- Label + email address (muted)
- Right: "Managed by school" (muted, no edit action)

**Password row:**
- Label + "Last changed {relative time}" (muted)
- "Change" link → inline form expands
- Form: Current password · New password · Confirm new password (all type="password")
- Validation: new/confirm must match client-side; min 8 chars
- On 400: inline error "Current password is incorrect"
- On success: toast "Password updated", collapse form, clear fields

Only one inline form open at a time — opening one collapses the other.

---

## Learning profile section

Card: `bg-white border border-role-student-border rounded-2xl p-5`.

Shows current profile data — read only display:

**Modality bars** (4 bars, one per modality):
```
Kinesthetic  [████████░░]  80%
Visual       [█████░░░░░]  55%
Reading      [███░░░░░░░]  30%
Auditory     [██░░░░░░░░]  20%
```
Dominant modality bar uses gold `#c9932a` (matching lesson plan rationale shown to
teacher — consistency signal if student and teacher compare notes).
Others use `#9ca3af`.

Bar: `h-6px bg-gray-100 rounded-full` bg, fill colored.
Score = `modality_scores[key] * 100` rounded to nearest integer.

**Work style** (from `work_style` JSONB):
Show as compact true-value badges: "Solo study" / "Short sessions" / "Task-based" /
"Group learning" / "Concept first". Only show TRUE values.

**Interests:**
Pill badges from `interests[]`. Use `bg-gray-100 text-gray-700 rounded-full`.

**Completed date:**
"Completed {date formatted as '12 Jan 2026'}" — small muted text top-right of card.

**If profile not yet complete** (`completed_at = null`):
Do not show bars, work style, or interests. Show: "Your learning profile is not yet
complete. Complete the questionnaire to personalise your experience." with a primary
"Complete profile →" green button linking to `/student/onboarding/profile`.
(This state should be rare since the student must complete the profile before reaching
the dashboard, but handle it gracefully.)

**Retake questionnaire button:**
```tsx
<button
  onClick={() => navigate('/student/onboarding/profile')}
  className="flex items-center gap-2 border border-brand-mid text-brand-primary rounded-full px-4 py-2 text-sm font-bold hover:bg-brand-light"
>
  ↺ Retake questionnaire
</button>
```
Below button: "Updating your profile improves future study plan and quiz
personalisation. Takes about 5 minutes." (muted, 11px).

---

## Account actions section

Card: `bg-white border border-red-200 rounded-2xl`.

**Sign out row:**
- Label: "Sign out" (font-semibold)
- Sub: "You will need to sign in again" (muted, 11px)
- Button: outline red `border border-red-200 text-red-600 rounded-full` — NOT filled
- On click: `POST /api/v1/auth/logout` → clear tokens → redirect `/login`

No account deletion in v1.

---

## Acceptance Criteria

**Playwright E2E tests in `student-settings.spec.ts`**

`test_settings_page_when_loaded_then_three_sections_visible` — Navigate to
`/student/settings`. Assert Account, Learning profile, and Account actions sections
are all visible.

`test_settings_page_when_profile_complete_then_modality_bars_shown` — Mock a
completed learning profile. Assert four bar rows are visible.

`test_settings_page_when_profile_incomplete_then_complete_profile_cta_shown` — Mock
`completed_at=null`. Assert "Complete profile →" button is visible. Assert no bars
are shown.

`test_settings_page_when_edit_name_opened_then_two_inputs_visible` — Click "Edit"
on Name row. Assert first name and last name inputs are present.

`test_settings_page_when_name_saved_then_row_updates` — Fill in new name, click Save.
Mock `PATCH /users/me` → 200. Assert the row now shows the new name.

`test_settings_page_when_retake_clicked_then_navigates_to_questionnaire` — Click
"Retake questionnaire". Assert URL changes to `/student/onboarding/profile`.

`test_settings_page_when_sign_out_clicked_then_redirects_to_login` — Click sign out.
Mock `POST /auth/logout` → 200. Assert URL becomes `/login`.

`test_settings_page_when_password_form_open_and_name_edit_clicked_then_password_form_closes` —
Open password form. Click "Edit" on name row. Assert password form is no longer visible.

**Jest unit tests**

`test_modality_bars_when_kinesthetic_dominant_then_gold_fill` — Render bars with
`kinesthetic: 0.8, visual: 0.5`. Assert kinesthetic bar has gold color.

`test_modality_bars_when_all_zero_then_all_bars_empty` — All `modality_scores=0`.
Assert all bars show 0% fill.

---

## Do NOT Touch

`frontend/apps/teacher/` — no code goes here.
`frontend/apps/school-admin/` — no code goes here.
`frontend/packages/ui/` — do not add settings-specific components here.
Any backend file — all endpoints already exist.
