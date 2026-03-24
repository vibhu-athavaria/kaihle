# M0-7-T3b — Student Settings UI
**Milestone:** M0 · **Epic:** M0-7
**Authors:** Kramer (engineering) · Pixel (design) · Vidhya (education)
**Depends on:** M0-8-T3, M0-8-T4, M0-7-T3, M0-10-T14
**Effort:** 3–4 hours

---

## Vidhya — Educational Context

**The learning profile retake is educationally significant.** Students' learning preferences evolve — a 12-year-old who identified as a hands-on learner in September may discover a genuine love of reading by March. Restricting retakes would mean the personalisation system gradually becomes less accurate. The retake must be frictionless: one button, clear explanation, no warning dialogs.

**The explanation copy matters.** "Updating your profile improves future personalisation" is technically accurate but educationally inert. Students aged 11–18 respond to concrete relevance. The copy should say something like: *"Retaking the questionnaire updates how your study plans and lesson activities are personalised for you. Takes about 5 minutes."*

**What students should NOT be able to change:** Email (managed by school — confused students sometimes try to change this and then lose access to their account). Role, grade, and class assignments are all managed by the school admin. Make the boundary clear with a short, non-technical explanation: "Managed by school."

**The settings page is an honesty moment.** Students land here when something is wrong — forgot password, name is misspelled, wants to update interests. The UX should feel calm, competent, and safe. No alarm-bell colours, no threatening warnings, no confirmation dialogs for non-destructive actions.

---

## Pixel — Design Spec

### Layout

Max-width `max-w-xl mx-auto px-4 py-8`. Three stacked section cards with `gap-4`. No sidebar or bottom nav active state — settings is a detached destination.

```
Page title: "Settings" — font-fraunces text-2xl text-ink mb-6
Sections:   bg-white rounded-2xl border border-gray-100 shadow-sm
            Divide sections with h-px bg-gray-100 inside the card
```

### Component: AccountSection

```
Section heading: font-fraunces text-base text-ink px-6 pt-5 pb-3
                 border-b border-gray-50

Row base:   flex items-center justify-between px-6 py-4
Label:      font-nunito text-sm font-medium text-ink
Value:      font-nunito text-sm text-gray-400

Name row:
  Value: "{firstName} {lastName}"
  Action: "Edit" — text-brand-primary text-sm font-medium cursor-pointer
  Inline expansion: slides down with max-height transition 200ms ease-out
  Do NOT replace the row — expand below it

Email row:
  Value: email string (muted)
  Badge: "Managed by school"
         bg-gray-100 text-gray-400 text-xs rounded-full px-2 py-0.5

Password row:
  Value: "Last changed {date}" or "—"
  Action: "Change" — text-brand-primary text-sm
```

### Component: InlineEditName

```
Component: InlineEditName
──────────────────────────────────────────────────────────
Container:  px-6 pb-4 pt-1 bg-gray-50/50
            border-b border-gray-100
Inputs:     grid-cols-2 gap-3 (stacked on mobile: grid-cols-1)
            rounded-lg border border-gray-200 px-3 py-2 text-sm
            focus: border-brand-primary ring-1 ring-brand-primary/20
            transition: border-color 100ms, box-shadow 100ms
Validation: error text text-red-500 text-xs mt-1
Buttons:    flex gap-2 mt-3
  Save:     bg-brand-primary text-white rounded-lg px-4 py-2 text-sm
            Loading: spinner inside, disabled + opacity-60
  Cancel:   border border-gray-200 text-gray-600 rounded-lg px-4 py-2 text-sm
Rule:       Only one inline form open at a time. Opening password
            collapses name and vice versa.
──────────────────────────────────────────────────────────
Success:    Toast notification (bottom-right) — "Name updated"
            bg-gray-900 text-white text-sm px-4 py-2 rounded-xl
            auto-dismiss after 3 seconds
```

### Component: InlineChangePassword

```
Component: InlineChangePassword
──────────────────────────────────────────────────────────
Same container style as InlineEditName
Inputs stacked (always, never grid):
  Current password · New password · Confirm new password
  type="password" — show/hide toggle (👁 icon, right-inside)
Validation (client-side before submit):
  New ≥ 8 chars: error below field as user types
  Confirm must match: error on blur
  Never show errors before interaction (Pixel: don't blame the user early)
API call on submit: POST /auth/change-password
  204: toast "Password updated", collapse form, clear all fields
  400: inline error below Current password field — "Incorrect password"
  422: inline errors per field
──────────────────────────────────────────────────────────
Note (Pixel): Password show/hide on each field is a UX must.
Students on shared devices (school computers) need to be able to
type passwords confidently without shoulder-surfing risk.
```

### Component: LearningProfileSection

```
Section:    bg-white rounded-2xl border border-gray-100 shadow-sm
Heading:    "Learning profile" — font-fraunces text-base

Modality bars (4 rows, matching student progress page):
  Row:      flex items-center gap-3 py-2 px-6
  Label:    text-sm text-gray-700 w-36 font-nunito
  Bar:      h-2 rounded-full flex-1 bg-gray-100
  Fill:     h-full rounded-full bg-brand-primary for dominant,
            bg-gray-300 for others
            Width = score * 100%
            Transition: width 600ms ease on mount
  Pct:      text-sm text-gray-500 w-10 text-right

  Note (Pixel): Student app uses green (brand-primary), not gold.
  Green = action/mastery in student app. Gold is teacher-only.
  Note (Vidhya): Show ALL four modality bars, not just dominant.
  Students should see a complete picture of themselves.

Interests:  flex flex-wrap gap-2 px-6 pb-4
  Pill:     bg-green-50 text-brand-primary border border-green-200
            text-xs rounded-full px-3 py-1

Completed:  "Completed {date}" — text-xs text-gray-400 px-6 pb-4

Retake btn: mx-6 mb-6
  Style:    border border-brand-primary text-brand-primary
            rounded-xl px-4 py-2 text-sm font-medium w-full
            hover: bg-green-50 transition-colors
  Label:    "Retake questionnaire"
  Note below (Vidhya's copy):
    "Retaking updates how your study plans and lesson activities
     are personalised for you. Takes about 5 minutes."
    text-xs text-gray-400 mt-2 text-center
```

### Component: AccountActionsSection

```
Section:    bg-white rounded-2xl border border-red-100 shadow-sm
  (Light red border signals this section has irreversible actions)

Sign out:
  Description: "You'll need to sign in again on this device"
               font-nunito text-sm text-gray-400
  Button:   border border-red-200 text-red-600 rounded-xl px-4 py-2 text-sm
            bg-white hover:bg-red-50 transition-colors
            NOT filled red — outlined only (Pixel: filled red = danger zone)
```

---

## Kramer — Engineering Spec

### Files

```
frontend/apps/student/src/pages/settings/
  StudentSettings.tsx

frontend/apps/student/src/components/settings/
  AccountSection.tsx
  InlineEditName.tsx
  InlineChangePassword.tsx
  LearningProfileSection.tsx
  AccountActionsSection.tsx

frontend/apps/student/src/tests/
  student-settings.spec.ts
  inline-change-password.test.tsx
  learning-profile-section.test.tsx
```

### Route

`/student/settings` — via avatar dropdown in `StudentLayout`.
Add to `App.tsx` inside `PrivateRoute > PasswordSetupRoute > OnboardingRoute > RoleRoute(['STUDENT'])`.

### API Calls

| Action | Endpoint |
|---|---|
| Load current user | `GET /api/v1/users/me` |
| Load learning profile | `GET /api/v1/students/me/learning-profile` |
| Update name | `PATCH /api/v1/users/me` |
| Change password | `POST /api/v1/auth/change-password` |
| Sign out | `POST /api/v1/auth/logout` |

---

## Playwright E2E

```typescript
test('settings_three_sections_visible', ...)
test('settings_name_edit_expands_with_two_inputs', ...)
test('settings_name_save_calls_patch_and_updates_display', ...)
test('settings_password_change_show_hide_toggle_works', ...)     // Pixel
test('settings_password_confirm_mismatch_error_on_blur', ...)    // Pixel
test('settings_wrong_current_password_inline_error', ...)
test('settings_modality_bars_all_four_shown', ...)               // Vidhya
test('settings_dominant_bar_uses_brand_primary_not_gold', ...)   // Pixel (student=green)
test('settings_retake_navigates_to_onboarding', ...)             // Vidhya
test('settings_retake_copy_mentions_personalisation', ...)       // Vidhya
test('settings_sign_out_clears_tokens_redirects', ...)
test('settings_email_row_shows_managed_by_school', ...)          // Vidhya
```

---

## Jest Unit Tests

```typescript
describe('InlineChangePassword', () => {
  it('shows password-toggle button on each field', ...)           // Pixel
  it('does not show error before user interacts with field', ...) // Pixel
  it('confirm field error appears on blur not on type', ...)      // Pixel
  it('disables submit when new password under 8 chars', ...)
  it('disables submit when confirm does not match', ...)
})

describe('LearningProfileSection', () => {
  it('renders all four modality bars', ...)                       // Vidhya
  it('dominant bar uses bg-brand-primary (green)', ...)           // Pixel
  it('non-dominant bars use bg-gray-300', ...)                    // Pixel
  it('shows all interests not just top 2', ...)                   // Vidhya
  it('retake copy mentions personalisation and time', ...)        // Vidhya
})
```

---

## Acceptance Criteria

- [ ] All four modality bars shown — student sees full picture (Vidhya)
- [ ] Dominant bar green (`bg-brand-primary`), others muted — student palette (Pixel)
- [ ] Retake copy mentions personalisation and ~5 minutes (Vidhya)
- [ ] Email row shows "Managed by school" with gentle explanation (Vidhya)
- [ ] Password fields have show/hide toggles (Pixel)
- [ ] No errors shown before user has interacted with a field (Pixel)
- [ ] Confirm mismatch error appears on blur, not on every keypress (Pixel)
- [ ] Sign out button is outlined red, NOT filled red (Pixel)
- [ ] One inline form open at a time (name collapses password and vice versa) (Pixel)
- [ ] Success toast auto-dismisses after 3 seconds (Pixel)
- [ ] All inputs keyboard navigable with visible focus ring (Pixel)
