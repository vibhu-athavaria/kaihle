# M0-6-T4 — Student Onboarding UI
**Milestone:** M0 · **Epic:** M0-6 (Student Onboarding) · **Task:** T4
**Depends on:** M0-6-T1 (questionnaire API), M0-6-T2 (Tier 1 trigger), M0-6-T3 (completion tracking), M0-3-T4 (auth frontend)

---

## User Story
As a student logging in for the first time, I want a guided onboarding experience that walks me through my learning style questionnaire and my subject diagnostics before I reach my dashboard.

---

## Files to Create / Modify

```
frontend/apps/student/src/pages/onboarding/OnboardingRouter.tsx
frontend/apps/student/src/pages/onboarding/ProfileQuestionnaire.tsx
frontend/apps/student/src/pages/onboarding/DiagnosticHub.tsx
frontend/apps/student/src/hooks/useOnboardingStatus.ts
frontend/apps/student/src/store/questionnaireStore.ts
frontend/apps/student/src/routes.tsx        # add /onboarding/* routes outside OnboardingRoute guard
frontend/apps/student/src/tests/onboarding.spec.ts   # Playwright E2E
```

---

## Route Structure

```
/student/onboarding              → OnboardingRouter (checks status, redirects to correct step)
/student/onboarding/profile      → ProfileQuestionnaire (Step 1)
/student/onboarding/diagnostics  → DiagnosticHub (Step 2)
```

These routes must NOT be wrapped in `OnboardingRoute` guard — that would cause infinite redirect loop.

---

## OnboardingRouter Component

Fetches `GET /api/v1/onboarding/status` on mount. Redirects:
- `learning_profile_complete = false` → `/student/onboarding/profile`
- `learning_profile_complete = true` AND `diagnostics_complete = false` → `/student/onboarding/diagnostics`
- Both complete → `/student/dashboard`

---

## ProfileQuestionnaire (Step 1)

### Layout
- Full-screen, centred card layout. Kaihle logo top-left.
- Progress indicator: `"Question 3 of 6"` (treat multi-select interest block as 1 question)
- "Back" and "Next" buttons. "Submit" on final step.

### Q1–Q5 (Single Select)
- Render as 4 large clickable cards in a 2×2 grid
- Each card: icon + label text
- Selected state: highlighted border + fill
- Icons: use Lucide React icons (Video, BookOpen, Wrench, MessageCircle for Q1 etc.)

### Q6 (Multi-Select Interests)
- Grid of 10 emoji tiles (2×5 on mobile, 5×2 on desktop)
- Toggle on/off with checkmark overlay
- No minimum selection required — student can skip interests

### Local State
- Store answers in `questionnaireStore.ts` (Zustand)
- Persists across Back/Next navigation
- Does NOT persist to localStorage (memory only — fresh on page reload is acceptable)

### Submit
```
POST /api/v1/onboarding/questionnaire/submit
  → Loading spinner overlay
  → On success: navigate to /student/onboarding/diagnostics
  → On error: toast "Something went wrong, please try again"
```

---

## DiagnosticHub (Step 2)

### Layout
- Header: "Complete your subject diagnostics" with subtitle explaining purpose
- Progress summary: `"2 of 3 subjects completed"`
- One card per Tier 1 assessment (fetched from student's active assessments where `is_system_generated=true`)

### Assessment Card
```
[Subject Icon]  Mathematics — Grade 9
Status badge:   ● Not Started  |  ⏳ In Progress  |  ✓ Completed
Estimated time: ~15 minutes
[Start / Continue / View Results] button
```

### Navigation to Assessment
- "Start" / "Continue" button → navigates to `/student/assessments/{assessment_id}/take`
- The assessment taking UI (M1-4-T4) is SHARED — same component used for Tier 1 and Tier 2
- After submitting a Tier 1 assessment, the student is returned to `/student/onboarding/diagnostics`
- DiagnosticHub polls `GET /api/v1/onboarding/status` every 3 seconds OR refetches on focus to detect completion

### Completion
- When all assessments completed → show "🎉 You're all set!" full-screen card for 3 seconds → redirect to `/student/dashboard`

---

## useOnboardingStatus Hook

```typescript
const { status, isLoading, refetch } = useOnboardingStatus()
// Calls GET /api/v1/onboarding/status
// Auto-refetch on window focus
```

---

## Acceptance Criteria

- [ ] E2E: student logs in for first time → redirected to `/student/onboarding/profile`
- [ ] E2E: student answers all questions → submits → redirected to `/student/onboarding/diagnostics`
- [ ] E2E: student completes all Tier 1 diagnostics → redirected to `/student/dashboard`
- [ ] E2E: student who has already completed onboarding is NOT redirected to onboarding
- [ ] E2E: navigating Back preserves previously selected answers
- [ ] Unit: interest tile toggles correctly — selecting and deselecting
- [ ] Unit: progress indicator shows correct step number
- [ ] Unit: DiagnosticHub shows correct status badge per assessment
- [ ] Responsive: all screens render correctly at 375px (mobile) viewport
- [ ] Accessibility: all interactive elements keyboard-navigable, have aria-labels

---

## Tests to Write (Playwright E2E)

```typescript
test('first_login_redirects_to_onboarding_profile')
test('questionnaire_submit_navigates_to_diagnostic_hub')
test('back_navigation_preserves_answers')
test('interest_tile_multi_select_toggles')
test('diagnostic_hub_shows_not_started_badges')
test('completing_all_diagnostics_redirects_to_dashboard')
test('completed_student_not_redirected_to_onboarding')
```
