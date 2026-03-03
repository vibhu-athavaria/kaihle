# M1-4-T4 — Student Assessment Taking UI
**Milestone:** M1 · **Epic:** M1-4 · **Task:** T4
**Depends on:** M1-4-T1 (attempt API), M0-3-T4 (auth frontend), M0-6-T4 (onboarding UI — shares this component for Tier 1)

---

## User Story
As a student, I want a focused, mobile-friendly interface to take any assessment — whether it's my onboarding diagnostic or a teacher-assigned quiz.

---

## Files to Create

```
frontend/apps/student/src/pages/assessments/AssessmentList.tsx
frontend/apps/student/src/pages/assessments/TakeAssessment.tsx   # shared by Tier 1 + Tier 2
frontend/apps/student/src/pages/assessments/AssessmentResults.tsx
frontend/apps/student/src/hooks/useAttempt.ts
frontend/apps/student/src/tests/take-assessment.spec.ts
```

---

## AssessmentList (`/student/assessments`)

- Lists ACTIVE Tier 2 assessments only (Tier 1 shown in onboarding DiagnosticHub)
- Fetches `GET /api/v1/classes/{class_id}/assessments?status=ACTIVE`
- For each enrolled class, shows assessment cards:
  ```
  [Subject icon]  Mathematics Diagnostic
  Due: 15 March 2026
  Status: Not Started | In Progress | Completed ✓
  [Start / Continue / View Results] button
  ```
- Completed badge with score `85%` when done
- Empty state: "No active assessments right now"

---

## TakeAssessment (`/student/assessments/:assessmentId/take`)

This component is used by BOTH:
- Tier 2 assessments (from `/student/assessments`)
- Tier 1 assessments (from `/student/onboarding/diagnostics` → same route)

On mount:
1. Call `POST /api/v1/assessments/{assessmentId}/start` → get `attempt_id` + `questions[]`
2. Store questions in local state (not persisted)
3. Render first unanswered question

### Question Card Layout
```
┌─────────────────────────────────────────┐
│  Progress: ████████░░  8 / 10           │
│                                         │
│  Q8.  What is the value of x if...      │
│                                         │
│  ○  A.  x = 2                           │
│  ●  B.  x = 4   ← selected             │
│  ○  C.  x = 6                           │
│  ○  D.  x = 8                           │
│                                         │
│  [← Back]              [Next →]         │
└─────────────────────────────────────────┘
```

### MCQ / True-False
- 2×2 grid on mobile, horizontal on desktop
- Single select — tapping another option deselects previous
- Selected state: filled border + check icon

### Short Answer
- Multi-line text area
- Character counter (max 500 chars)
- Placeholder: "Type your answer here..."

### Navigation
- Back/Next moves between questions without submitting (answers buffered locally)
- Answered questions show a dot in progress bar
- Unanswered questions can be left blank (warn at submit, do not block)

### Auto-save
- On each "Next" click: silently call `POST /api/v1/attempts/{attempt_id}/responses` for that question if not already saved
- On network error: show inline "Saving..." then "Saved" indicator — do not block navigation

### Submit Flow
1. Click "Submit Assessment" on last question (or anytime from question list)
2. Confirmation modal: "You have 2 unanswered questions. Submit anyway?"
3. On confirm: call `POST /api/v1/attempts/{attempt_id}/submit`
4. Loading spinner overlay during submit
5. On success: navigate to `/student/assessments/{assessmentId}/results`
6. **Post-submit redirect logic:**
   - If this was a Tier 1 assessment (check `is_system_generated` from assessment data):
     → After results shown for 3 seconds, redirect back to `/student/onboarding/diagnostics`
   - If Tier 2:
     → Stay on results page

---

## AssessmentResults (`/student/assessments/:assessmentId/results`)

```
┌─────────────────────────────────┐
│  ✓  Assessment Complete         │
│                                 │
│       73%                       │
│   7 of 10 correct               │
│                                 │
│  [View Detailed Answers]        │
│  [Back to Dashboard]            │
└─────────────────────────────────┘
```

- Score ring / large percentage display
- "View Detailed Answers" → expands list showing each question, student's answer, correct answer, explanation
- Correct answers shown in green, incorrect in red

---

## Acceptance Criteria

- [ ] E2E: student starts 10-question MCQ, answers all, submits → sees score summary
- [ ] E2E: student refreshes mid-assessment → answers already saved are preserved (auto-save)
- [ ] E2E: student returns to `/student/assessments` → assessment shows "In Progress"
- [ ] E2E: completed assessment shows score badge and "View Results" button (not "Start")
- [ ] E2E: Tier 1 assessment taken from onboarding → after results, redirected to DiagnosticHub
- [ ] Unit: unanswered question warning shown in submit modal
- [ ] Unit: MCQ selecting option B deselects previously selected option A
- [ ] Responsive: correct at 375px mobile and 768px tablet

---

## Tests to Write (Playwright)

```typescript
test('take_assessment_mcq_submit_shows_score')
test('auto_save_preserves_answers_on_refresh')
test('completed_assessment_shows_view_results_button')
test('tier1_assessment_redirects_to_onboarding_after_results')
test('unanswered_questions_show_warning_in_submit_modal')
```
