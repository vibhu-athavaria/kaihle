# M1-4-T4 — Student Assessment Taking UI (Student App)
**Milestone:** M1 · **Epic:** M1-4 · **Task:** T4
**Depends on:** M1-4-T1 (attempt routes must return real data), M0-10-T8 (student app hooks updated)
**Blocks:** Nothing — students can complete assessments once this is done
**Estimated effort:** 4–5 hours

---

## Context

This task builds the student-facing assessment taking UI. It is used for both Tier 1
(onboarding diagnostic) and Tier 2 (teacher-created) assessments. The component is
shared — the same UI handles both tiers. The only behavioral difference is what
happens after submission, and that is determined by data from the API, not by separate
components.

All code in this task lives in `frontend/apps/student`. No code goes in any other app.

Read `docs/design/DESIGN_SYSTEM.md` §5.4 (Student) before writing any component. The
student app uses no sidebar. All layouts use `StudentLayout` from `packages/ui`. This
is a mobile-first UI — design for 375px first, then enhance upward.

---

## How the Assessment Flow Works (Read This Before Writing Code)

The student assessment flow is different from what was previously documented. There is
no `/start` endpoint. Here is the exact sequence for each tier.

For Tier 1 diagnostics, the student's attempt already exists in the database, created
by `trigger_onboarding_diagnostics` when they were enrolled. The student retrieves it
via `GET /api/v1/classes/{classId}/diagnostic`. This endpoint returns an `AttemptResponse`
with `status="NOT_STARTED"` and the full list of questions (without correct answers).
The student reads the questions from this response — there is no separate step to fetch
questions.

For Tier 2 assessments, the flow is: the student sees the assessment listed in their
class content page (it appears after the Tier 1 diagnostic is complete). They click it,
which calls `GET /api/v1/attempts/{attemptId}`. If no attempt exists for them yet, the
backend creates one lazily and returns it with questions. The student then proceeds
identically to the Tier 1 flow.

In both cases, once the student has the attempt data, they answer questions by calling
`POST /api/v1/attempts/{attemptId}/responses` for each question, and finally submit
everything with `POST /api/v1/attempts/{attemptId}/submit`.

---

## User Story

As a student, I want a focused, mobile-friendly interface to take any assessment —
whether it is my onboarding diagnostic or a teacher-assigned quiz — and see my score
afterwards.

---

## Files to Create

```
frontend/apps/student/src/pages/assessments/
  TakeAssessmentPage.tsx         ← shared assessment-taking component (Tier 1 + Tier 2)
  AssessmentResultsPage.tsx      ← score summary after submission

frontend/apps/student/src/hooks/
  useAttempt.ts                  ← React Query hooks for all attempt operations

frontend/apps/student/src/tests/
  take-assessment.spec.ts        ← Playwright E2E tests
```

Note: `AssessmentListPage` for Tier 2 assessments is rendered inside the class content
view (a later milestone). This task only builds the taking UI and results page. The
DiagnosticHub in the onboarding flow (M0-6-T4) links directly to `TakeAssessmentPage`
for Tier 1.

---

## Routes

`/student/assessments/:attemptId/take` — `TakeAssessmentPage`. The attempt ID is
passed as a URL parameter. This route is reached from the DiagnosticHub (Tier 1) or
from the class content list (Tier 2). Protected by `PrivateRoute` + `OnboardingRoute`.

`/student/assessments/:attemptId/results` — `AssessmentResultsPage`. Protected by
the same guards.

---

## `useAttempt.ts` — React Query Hooks

```typescript
// Fetches the attempt and its questions.
// Used by TakeAssessmentPage on mount.
export const useAttempt = (attemptId: string) =>
  useQuery({
    queryKey: ['student', 'attempt', attemptId],
    queryFn: () => apiClient.get<AttemptResponse>(`/attempts/${attemptId}`),
    enabled: !!attemptId,
    // Do not refetch on window focus — this would disrupt mid-assessment state
    refetchOnWindowFocus: false,
  })

// Mutation for saving a single answer.
export const useSubmitResponse = () =>
  useMutation({
    mutationFn: ({
      attemptId,
      questionId,
      selectedKey,
    }: {
      attemptId: string
      questionId: string
      selectedKey: string
    }) =>
      apiClient.post(`/attempts/${attemptId}/responses`, {
        question_id: questionId,
        selected_key: selectedKey,
      }),
  })

// Mutation for submitting the whole attempt.
export const useSubmitAttempt = () =>
  useMutation({
    mutationFn: ({
      attemptId,
      answers,
    }: {
      attemptId: string
      answers: Array<{ question_id: string; selected_key: string }>
    }) => apiClient.post<AttemptResultResponse>(`/attempts/${attemptId}/submit`, { answers }),
  })
```

---

## `TakeAssessmentPage.tsx`

### On Mount

Call `useAttempt(attemptId)` to load the attempt and questions. While loading, show
a skeleton of three question cards. If the attempt is `COMPLETED`, redirect immediately
to `/student/assessments/{attemptId}/results` — do not allow re-taking a completed
assessment.

Store the questions in local component state (not in a server-synced query) since they
do not change during the attempt. Store the student's answer selections in local state
as well: `answers: Record<questionId, selectedKey>`.

### Layout

```
┌─────────────────────────────────────────┐
│  [←]  Mathematics Diagnostic   Q8 of 10 │  ← top bar
│       ████████████░░  (progress bar)    │
│                                         │
│  When a ray of light hits a flat        │
│  mirror, the angle of reflection...     │  ← question text
│                                         │
│  ┌──────────────┐  ┌──────────────┐    │
│  │ A  Equals the│  │ B  Is less   │    │  ← MCQ options
│  │    angle of  │  │    than the  │    │
│  │    incidence │  │    angle of  │    │
│  └──────────────┘  └──────────────┘    │
│  ┌──────────────┐  ┌──────────────┐    │
│  │ C  Is greater│  │ D  Is 90°    │    │
│  │    than the  │  │    minus     │    │
│  └──────────────┘  └──────────────┘    │
│                                         │
│  [← Back]              [Next →]         │
└─────────────────────────────────────────┘
```

The progress bar shows answered questions as a filled segment. The question counter
shows the current question number and total. The back arrow in the top bar shows a
confirmation dialog before navigating away: "Leave this assessment? Your progress will
be saved."

### MCQ Options

Render as a 2×2 grid on mobile (375px), switching to a horizontal row on screens
wider than 768px. Each option card shows the letter key (A, B, C, D) and the option
text. Tapping selects that option and deselects any previously selected option for
the same question. Selected state: `border-2 border-brand-primary bg-brand-primary/10`.
Unselected state: `border border-role-student-border bg-white`.

### Navigation and Auto-Save

Back and Next buttons navigate between questions without submitting the whole attempt.
When the student selects an option and clicks Next, call `useSubmitResponse` to
save that answer silently in the background. Do not block navigation while the save
is in progress. If the save fails (network error), show a brief inline "Saving..." →
"Saved ✓" indicator under the progress bar. If save still fails after one retry, show
"Save failed — check your connection" but do not block the student from continuing.

When navigating back to a previously answered question, show the previously selected
option in the selected state. The answer is already in local state (`answers` record)
so this requires no API call.

### Submit Flow

On the final question page, the Next button is replaced by a "Submit Assessment"
button. If any questions are unanswered, show a modal: "You have left {n} question(s)
unanswered. Unanswered questions will count as incorrect. Submit anyway?"

On confirm (or if all questions are answered), show a loading overlay ("Submitting...").
Call `useSubmitAttempt` with the full `answers` array. This endpoint handles any
responses that were not already saved individually. On success, navigate to
`/student/assessments/{attemptId}/results`.

---

## `AssessmentResultsPage.tsx`

Load the result data by reading from the mutation result state passed via router
state, or by calling `GET /api/v1/attempts/{attemptId}/results` if the page is
visited directly (e.g. by refreshing after submission).

### Layout

```
┌─────────────────────────────────────────┐
│                                         │
│           ✓  Submitted                  │
│                                         │
│              73%                        │  ← large score circle
│          7 of 10 correct                │
│                                         │
│  ┌──────────────────────────────────┐   │
│  │  [Back to Dashboard]             │   │
│  └──────────────────────────────────┘   │
│                                         │
└─────────────────────────────────────────┘
```

The score is displayed as a large percentage inside a circular progress ring. The ring
color uses `getMasteryStyle(score)` from `packages/types` — red for under 0.4, amber
for 0.4–0.7, green for over 0.7.

"Back to Dashboard" navigates to `/student/dashboard`.

There is no "View Detailed Answers" feature in v1. Do not add it — it requires the
backend to return `correct_answer` in the results response, which raises security
concerns about caching the answers client-side. This is a v2 feature.

### Post-Submit Redirect for Tier 1

After a Tier 1 submission, the onboarding gate may now open for this class. The
student should be aware of this without an awkward redirect. Show a brief banner below
the score ring: "Diagnostic complete! Head back to see what's now unlocked." The
"Back to Dashboard" button navigates to `/student/dashboard` as normal — the
`OnboardingRoute` guard will handle any redirect logic automatically based on the
updated `onboarding_diagnostic_status`.

Do not detect whether this was Tier 1 by checking `is_system_generated` on the
frontend. The `AttemptResultResponse` does not include this field. Instead, show the
banner unconditionally after every submission — it is informative and harmless for
Tier 2 assessments as well.

---

## Acceptance Criteria

**Playwright E2E tests in `take-assessment.spec.ts`**

`test_take_assessment_when_attempt_loaded_then_first_question_shown` — Navigate to
`/student/assessments/{attemptId}/take`. Assert that a question card is visible with
four MCQ option cards.

`test_take_assessment_when_option_selected_then_selected_state_applied` — Click option
B. Assert it has the selected border and background. Click option C. Assert C is now
selected and B is deselected.

`test_take_assessment_when_next_clicked_then_response_saved_and_next_question_shown` —
Select an option and click Next. Assert the progress bar shows one answered question
and the second question is now displayed.

`test_take_assessment_when_back_clicked_then_previous_answer_still_selected` — Answer
Q1, advance to Q2, click Back. Assert Q1's previously selected option is still shown
in selected state.

`test_take_assessment_when_all_answered_then_submit_button_shown_on_last_question` —
Answer all questions up to the last one. Assert the "Submit Assessment" button is
visible (not a "Next" button).

`test_take_assessment_when_some_unanswered_then_confirmation_modal_shown` — Answer
only 5 of 10 questions and click Submit. Assert the confirmation modal is shown
mentioning the number of unanswered questions.

`test_take_assessment_when_completed_attempt_loaded_then_redirects_to_results` —
Load the page with an `attemptId` whose status is already `COMPLETED`. Assert the
URL changes to `/student/assessments/{attemptId}/results` without showing the question
UI.

`test_results_page_when_score_above_0_7_then_green_ring` — Render the results page
with a score of 0.8. Assert the score ring has the green color token.

`test_results_page_when_score_below_0_4_then_red_ring` — Score of 0.3. Assert red
color token.

`test_results_page_shows_diagnostic_complete_banner` — After any submission, assert
the "Diagnostic complete! Head back to see what's now unlocked." banner is visible.

**Jest unit tests**

`test_mcq_options_when_option_selected_then_others_deselected` — Render four MCQ
option buttons. Click B. Assert B has `selected` className. Click C. Assert C has
`selected` and B does not.

`test_progress_bar_when_3_of_10_answered_then_30_percent_filled` — Render progress
bar with `answered=3` and `total=10`. Assert the filled segment is 30% width.

`test_score_ring_when_mastery_0_6_then_uses_amber_color` — Render score ring with
`score=0.6`. Assert the ring uses the amber color from `getMasteryStyle`.

---

## Do NOT Touch

`frontend/apps/teacher/` — no code goes here.
`frontend/apps/school-admin/` — no code goes here.
`frontend/apps/kaihle-admin/` — no code goes here.
`frontend/apps/parent/` — no code goes here.
`frontend/packages/ui/src/components/` — do not add assessment-specific components
  here; they are student-specific and belong in `apps/student`.
Any backend file.
