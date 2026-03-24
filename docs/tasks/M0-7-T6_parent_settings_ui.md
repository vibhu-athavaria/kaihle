# M0-7-T6 — Parent Settings UI
**Milestone:** M0 — Foundations
**Epic:** M0-7 — Frontend Foundations
**Task ID:** M0-7-T6
**Depends on:** M0-8-T4 (shared components), M0-7-T1 (ParentLayout wrapper), M0-10-T14 (PATCH /users/me + POST /auth/change-password)
**Blocks:** Nothing — settings is a leaf feature
**Estimated effort:** 2–3 hours
**Design sprint:** Vidhya (information hierarchy) · Pixel (UI/UX) · Kramer (implementation)

---

## Context

The parent settings page provides account management (name, password) and a read-only
view of linked children. It is reached via the avatar icon in the `ParentLayout` top
nav — the parent app has no sidebar and no bottom nav tabs.

All code lives in `frontend/apps/parent`. Read `docs/design/DESIGN_SYSTEM.md` §5.5
(Parent palette) and `docs/design/screens/PARENT_SCREENS.md` §5 before starting.

**Important — no PasswordSetupRoute for parents.** Per CONSTITUTION.md §5 Role→App→Route
mapping: parents are NOT invited via magic link in v1. They log in directly (school admin
creates their account and shares credentials). There is no `PasswordSetupRoute` guard for
the parent app. The settings route only needs `PrivateRoute` + `RoleRoute(['PARENT'])`.

---

## Vidhya — Information Hierarchy

Parent settings is the simplest of the five settings pages. Parents have no curriculum
preferences, no learning profile, no assessment configuration. Three sections only:

**Priority 1 — Account** (name, email, password)
All parents need this. Name may be wrong on first login if the school admin entered
it incorrectly. Password change is the most common settings action.

**Priority 2 — Children** (read-only list)
Parents in international schools often have multiple children across different year
groups. A read-only list confirms which children's data they can see — important for
trust ("I can see my daughter Emma but not my son's account — is that right?"). This
is reassurance, not an action.

**Priority 3 — Sign out** (separate card)
Last, because it is destructive. Separate visually from account management.

**What is NOT in parent settings:**
- No notification preferences (v1 — parents receive emails only)
- No language preferences (English only in v1)
- No curriculum or school preferences (school admin manages these)
- No learning profile (parents don't have one — that belongs to students)

**Label language:**
- "My account" — not "Profile" or "Personal information"
- "My children" — not "Linked students" or "Student accounts"
- "Sign out" — not "Log out" or "Disconnect"
- Email row: "Managed by school" — explains why it's read-only without being technical

---

## Pixel — Component Specs & UX Design

### Design approach

Parent settings is the warmest, calmest settings page in the platform. Cream background,
Lora headings, narrow reading column. No dense tables, no technical terminology.
The "My children" section should feel like a warm confirmation — not a database record.

### Page Layout

```
Route: /parent/settings
Background: bg-role-parent-bg (#fdf8f0) — cream, same as rest of parent app
Max width:  max-w-lg mx-auto (540px — narrower than dashboard, reading column)
Padding:    px-4 py-8
Font:       Lora for headings, Nunito for body

Page heading (above cards):
  "Settings"
  font-lora text-2xl font-semibold text-gray-900 mb-6

Three stacked section cards, gap: mb-4
```

### Section 1 — My Account

```
Card: bg-white border border-gray-200 rounded-2xl overflow-hidden

Section heading row:
  px-6 py-4 border-b border-gray-100
  "My account" — font-lora text-base font-semibold text-gray-900

Row pattern (repeating):
  Layout: flex items-start justify-between px-6 py-4 border-b border-gray-100 last:border-0
  Left:   label (text-sm font-medium text-gray-700) stacked above value (text-sm text-gray-500)
  Right:  action link or badge
```

**Name row:**
```
Label:  "Name"
Value:  "{firstName} {lastName}" text-sm text-gray-500
Right:  "Edit" — text-sm text-gray-700 font-medium hover:text-gray-900 underline cursor-pointer

Expanded (InlineEditName):
  Slides open below row — max-h transition 200ms ease
  Two inputs: First name (flex-1) + Last name (flex-1) side-by-side on md, stacked on mobile
  Input style: bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm
               focus:ring-2 focus:ring-gray-400 focus:border-gray-400
  Note: Parent app uses NEUTRAL focus rings (not brand-primary green) — green is mastery data
  Buttons (mt-3 gap-2):
    Save:   bg-gray-900 text-white rounded-full px-4 py-2 text-sm   ← neutral dark, not green
    Cancel: bg-white border border-gray-200 text-gray-600 rounded-full px-4 py-2 text-sm
  On save: PATCH /users/me → toast.success("Name updated") → collapse
  On error: inline "Something went wrong. Please try again." text-sm text-red-500
```

**Email row:**
```
Label:  "Email"
Value:  email address — text-sm text-gray-500
Right:  "Managed by school" badge
        bg-gray-100 text-gray-500 text-xs rounded-full px-2.5 py-1
        No click action — purely informational
```

**Password row:**
```
Label:  "Password"
Value:  "Last changed {relative date}" or "—" if unknown — text-sm text-gray-500
Right:  "Change" — text-sm text-gray-700 font-medium hover:text-gray-900 underline cursor-pointer

Expanded (InlineChangePassword):
  Three stacked inputs: Current password · New password · Confirm new password
  All type="password"
  Each with visible <label> above (not placeholder only)
  New password: hint "Minimum 8 characters" — text-xs text-gray-400 below input
  Client-side validation before submit: confirm must match new
  Buttons same pattern as name edit
  On 204: toast.success("Password updated") → collapse → clear all fields
  On 400: inline "Current password is incorrect" text-sm text-red-500
  On 422: show first validation failure inline
```

**Only one inline form open at a time.** Opening one auto-collapses the other.

### Section 2 — My Children

```
Card: bg-white border border-gray-200 rounded-2xl overflow-hidden

Section heading row:
  px-6 py-4 border-b border-gray-100
  "My children" — font-lora text-base font-semibold text-gray-900

Child row (one per linked child):
  Layout: flex items-center gap-4 px-6 py-4 border-b border-gray-100 last:border-0
  Avatar circle: w-9 h-9 rounded-full bg-amber-50 text-amber-700 font-semibold text-sm
                 flex items-center justify-center flex-shrink-0
                 Initials: first letter of child's first + last name
  Text stack:
    Child name: text-sm font-medium text-gray-900
    Grade + school: text-xs text-gray-400  (e.g. "Grade 8 · Bali International School")
  Right: no action — this is display only

Info note (below all child rows):
  px-6 py-3 bg-gray-50 border-t border-gray-100
  "To add or remove linked children, contact your school admin."
  text-xs text-gray-400

Data: GET /users/me returns school/role info only.
      Child list: GET /parent/children returns ChildSummary[] (already used on dashboard)
      Reuse useMyChildren() hook — no additional API call.

Empty state (no children linked — should never happen in practice but handle it):
  px-6 py-6 text-center
  "No children linked to your account."
  text-sm text-gray-400
  "Contact your school admin to link your child's account." text-xs text-gray-400 mt-1
```

### Section 3 — Account Actions

```
Card: bg-white border border-red-100 rounded-2xl overflow-hidden

Sign out row: px-6 py-4
  Left stack:
    "Sign out" — text-sm font-medium text-gray-700
    "You'll need to sign in again to access Kaihle." — text-xs text-gray-400 mt-0.5
  Right:
    Button: bg-white border border-red-200 text-red-600 rounded-full px-4 py-2 text-sm
            hover:bg-red-50 transition-colors
    On click: POST /auth/logout → clear tokens → navigate to /login
    No confirmation dialog (recoverable action)
```

### Responsive Behaviour

```
<md (mobile):
  InlineEditName inputs: stacked full-width (flex-col gap-2)
  Child rows: avatar slightly smaller (w-8 h-8)

≥md:
  InlineEditName: two inputs side-by-side (grid grid-cols-2 gap-3)
```

### Accessibility

- All form inputs have `<label>` elements (not placeholder-only)
- Error messages linked via `aria-describedby`
- Focus rings: `focus-visible:ring-2 focus-visible:ring-gray-400 focus-visible:ring-offset-1`
  (neutral gray — not green, which is mastery data only even in the parent app)
- Avatar circles are `aria-hidden="true"` — child name text is the accessible label
- Toast notifications use `role="status"` `aria-live="polite"` (handled by sonner)

---

## Kramer — Files, Hooks & Tests

### Files to Create

```
frontend/apps/parent/src/pages/settings/
  ParentSettings.tsx

frontend/apps/parent/src/components/settings/
  AccountSection.tsx
  InlineEditName.tsx
  InlineChangePassword.tsx
  ChildrenSection.tsx
  AccountActionsSection.tsx

frontend/apps/parent/src/tests/
  parent-settings.spec.ts         ← Playwright E2E
  parent-settings.test.tsx        ← Jest unit tests
```

### Route

Add to `frontend/apps/parent/src/App.tsx`:

```tsx
<Route path="/parent/settings" element={
  <PrivateRoute>
    <RoleRoute roles={['PARENT']}>
      <ParentSettings />
    </RoleRoute>
  </PrivateRoute>
} />
```

Note: **No `PasswordSetupRoute`** — parents don't go through magic link setup per CONSTITUTION §5.

### API Calls

| Action | Endpoint | From task |
|---|---|---|
| Load user (name, email) | `GET /api/v1/users/me` | M0-10-T14 |
| Load children list | `GET /api/v1/parent/children` | M0-10-T6 (reuse useMyChildren) |
| Update name | `PATCH /api/v1/users/me` | M0-10-T14 |
| Change password | `POST /api/v1/auth/change-password` | M0-10-T14 |
| Sign out | `POST /api/v1/auth/logout` | M0-3-T2 |

### Navigation hook (add to ParentLayout top nav)

The avatar/profile icon in `ParentLayout` must link to `/parent/settings`. Add:

```tsx
// In ParentLayout top nav — avatar icon already exists but likely links nowhere
<button onClick={() => navigate('/parent/settings')} aria-label="Account settings">
  <span className="w-8 h-8 rounded-full bg-amber-50 text-amber-700 text-sm font-semibold
                   flex items-center justify-center">
    {initials}
  </span>
</button>
```

### Jest Unit Tests

```typescript
// parent-settings.test.tsx

describe('InlineEditName (parent variant)', () => {
  it('test_save_disabled_when_first_name_empty', () => {
    render(<InlineEditName currentFirstName="Emma" currentLastName="Chen"
                           onSave={jest.fn()} onCancel={jest.fn()} />)
    fireEvent.change(screen.getByLabelText(/first name/i), { target: { value: '' } })
    expect(screen.getByRole('button', { name: /save/i })).toBeDisabled()
  })

  it('test_cancel_does_not_call_onSave', () => {
    const onSave = jest.fn()
    render(<InlineEditName currentFirstName="Emma" currentLastName="Chen"
                           onSave={onSave} onCancel={jest.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: /cancel/i }))
    expect(onSave).not.toHaveBeenCalled()
  })
})

describe('ChildrenSection', () => {
  it('test_renders_child_name_and_grade', () => {
    const children = [{ id: '1', first_name: 'Emma', last_name: 'Chen',
                        grade: 'Grade 8', school_name: 'Bali IS' }]
    render(<ChildrenSection children={children} />)
    expect(screen.getByText('Emma Chen')).toBeInTheDocument()
    expect(screen.getByText(/Grade 8/)).toBeInTheDocument()
  })

  it('test_empty_state_when_no_children', () => {
    render(<ChildrenSection children={[]} />)
    expect(screen.getByText(/no children linked/i)).toBeInTheDocument()
  })

  it('test_avatar_initials_are_correct', () => {
    const children = [{ id: '1', first_name: 'Emma', last_name: 'Chen',
                        grade: 'Grade 8', school_name: 'Bali IS' }]
    const { container } = render(<ChildrenSection children={children} />)
    // Avatar shows "EC" for Emma Chen
    expect(container.querySelector('[aria-hidden="true"]')?.textContent).toBe('EC')
  })
})
```

### Playwright E2E Tests

```typescript
// parent-settings.spec.ts

test('test_settings_when_loaded_then_three_sections_visible', async ({ page }) => {
  await page.goto('/parent/settings')
  await expect(page.locator('text=My account')).toBeVisible()
  await expect(page.locator('text=My children')).toBeVisible()
  await expect(page.locator('button:has-text("Sign out")')).toBeVisible()
})

test('test_settings_heading_uses_lora_font', async ({ page }) => {
  await page.goto('/parent/settings')
  const heading = page.locator('h1, h2').first()
  const font = await heading.evaluate(el => window.getComputedStyle(el).fontFamily)
  expect(font).toContain('Lora')
})

test('test_settings_edit_name_expands_inline_form', async ({ page }) => {
  await page.goto('/parent/settings')
  await page.click('text=Edit')
  await expect(page.locator('label:has-text("First name") + input, input[name="firstName"]')).toBeVisible()
})

test('test_settings_name_saved_then_form_collapses', async ({ page }) => {
  await page.goto('/parent/settings')
  await page.click('text=Edit')
  await page.fill('input[name="firstName"]', 'Sarah')
  await page.click('button:has-text("Save")')
  await expect(page.locator('input[name="firstName"]')).not.toBeVisible()
  await expect(page.locator('text=Sarah')).toBeVisible()
})

test('test_settings_wrong_password_shows_inline_error', async ({ page }) => {
  await page.goto('/parent/settings')
  await page.click('text=Change')
  await page.fill('[name="currentPassword"]', 'WrongPass')
  await page.fill('[name="newPassword"]', 'NewPass12345')
  await page.fill('[name="confirmPassword"]', 'NewPass12345')
  await page.click('button:has-text("Save")')
  await expect(page.locator('text=Current password is incorrect')).toBeVisible()
})

test('test_settings_email_row_has_managed_by_school_badge', async ({ page }) => {
  await page.goto('/parent/settings')
  await expect(page.locator('text=Managed by school')).toBeVisible()
  // No edit link should be near email
  const emailSection = page.locator('[data-testid="email-row"]')
  await expect(emailSection.locator('text=Edit')).not.toBeVisible()
})

test('test_settings_children_section_shows_child_name', async ({ page }) => {
  // Mock returns one child: Emma Chen, Grade 8
  await page.goto('/parent/settings')
  await expect(page.locator('text=Emma Chen')).toBeVisible()
  await expect(page.locator('text=Grade 8')).toBeVisible()
})

test('test_settings_sign_out_redirects_to_login', async ({ page }) => {
  await page.goto('/parent/settings')
  await page.click('button:has-text("Sign out")')
  await expect(page).toHaveURL('/login')
})

test('test_settings_opening_password_form_closes_name_form', async ({ page }) => {
  await page.goto('/parent/settings')
  await page.click('text=Edit')  // open name form
  await expect(page.locator('input[name="firstName"]')).toBeVisible()
  await page.click('text=Change')  // open password form
  await expect(page.locator('input[name="firstName"]')).not.toBeVisible()
  await expect(page.locator('input[name="currentPassword"]')).toBeVisible()
})
```

---

## Acceptance Criteria

- [ ] Settings page at `/parent/settings` — no `PasswordSetupRoute` guard
- [ ] Page heading uses Lora font, cream background (`bg-role-parent-bg`)
- [ ] My account section: Name (editable), Email (read-only badge), Password (changeable)
- [ ] Name edit: inline form, Save calls `PATCH /users/me`, toast on success
- [ ] Password change: 3 fields, client-side match validation, inline error on 400
- [ ] Only one inline form open at a time
- [ ] Focus rings use neutral gray (not green — green is mastery data in parent app)
- [ ] My children section: child name, grade, school for each linked child
- [ ] "Managed by school" badge on email row — no edit link
- [ ] "Contact your school admin" note in children section
- [ ] Sign out clears tokens, redirects to `/login`
- [ ] Avatar initials in `ParentLayout` top nav link to `/parent/settings`
- [ ] All Jest unit tests pass
- [ ] All Playwright E2E tests pass (both desktop and `parent-mobile` Playwright project)
- [ ] `tsc --noEmit` passes in `apps/parent`

---

## Do NOT Touch

- `frontend/apps/teacher/` or `frontend/apps/student/` — no code goes here
- Any backend files — all endpoints exist from M0-10-T14
- `useMyChildren` hook from M0-10-T12 — reuse as-is
