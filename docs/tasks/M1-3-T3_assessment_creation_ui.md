# M1-3-T3 — Assessment Creation UI (Teacher App)
**Milestone:** M1 · **Epic:** M1-3 · **Task:** T3
**Depends on:** M1-3-T2 (assessment routes must return real data), M0-10-T9 (teacher app hooks updated to new API paths)
**Blocks:** Nothing — teacher can use the app once this is done
**Estimated effort:** 4–5 hours

---

## Context

This task builds the teacher-facing assessment management UI. All routes, hooks,
and API calls in this task use the API contracts frozen in M0-10. Do not invent new
endpoints — use only what exists.

All code in this task lives in `frontend/apps/teacher`. No code goes in any other app.

Read `docs/design/DESIGN_SYSTEM.md` §5.3 (Teacher) before writing any component.
Teacher action buttons use gold (`brand-gold #c9932a`), not green. Green in the
teacher app signals mastery data only.

---

## User Story

As a teacher, I want a step-by-step wizard to create and publish an assessment for
my class so I can set up a diagnostic or topic check without manually searching a
question bank.

---

## Files to Create

```
frontend/apps/teacher/src/pages/assessments/
  NewAssessmentPage.tsx           ← 5-step wizard container
  AssessmentListPage.tsx          ← list of assessments for a class
  steps/
    Step1ClassAndType.tsx         ← select class and assessment type
    Step2Topics.tsx               ← select topics (conditional)
    Step3Configure.tsx            ← question count, difficulty
    Step4Preview.tsx              ← preview generated questions
    Step5Publish.tsx              ← review and publish

frontend/apps/teacher/src/hooks/
  useAssessmentWizard.ts          ← wizard state management via Zustand
  useClassAssessments.ts          ← React Query hook for class assessment list

frontend/apps/teacher/src/tests/
  assessment-creation.spec.ts     ← Playwright E2E tests
```

---

## Routes

`/teacher/classes/:classId/assessments` — `AssessmentListPage` — lists all assessments
for a class. Protected by `PrivateRoute` + `RoleRoute(['TEACHER'])`.

`/teacher/assessments/new` — `NewAssessmentPage` — the wizard. Protected by
`PrivateRoute` + `RoleRoute(['TEACHER'])`.

---

## API Calls This UI Makes

The following is the complete list of API calls made by these components. Use only
these — do not call any other endpoint.

`GET /api/v1/schools/{school_id}/classes` — called in Step 1 to populate the class
dropdown. Use the `useSchoolClasses` hook if available, or create a new
`useMyClasses` hook that calls this endpoint with `teacher_id=me` query param.

`GET /api/v1/classes/{class_id}/assessments` — called by `AssessmentListPage` via the
`useClassAssessments` hook.

`POST /api/v1/classes/{class_id}/assessments` — called in Step 4 to create the draft
assessment and receive the preview questions. The response includes an `id` (the draft
assessment ID) which is stored in wizard state for Step 5.

`POST /api/v1/assessments/{assessment_id}/publish` — called in Step 5 when the teacher
clicks "Publish Now".

That is the complete set of API calls. There is no separate `/start` endpoint, no
question generation endpoint, and no endpoint to "preview" questions separately — the
draft assessment created in Step 4 IS the preview.

---

## Wizard State (`useAssessmentWizard.ts`)

The wizard state is managed by a Zustand store, not React local state, so that
navigating back and forward between steps does not lose entered data.

```typescript
interface AssessmentWizardState {
  // Navigation
  currentStep: 1 | 2 | 3 | 4 | 5

  // Step 1
  classId: string | null
  className: string | null       // display only, not sent to API
  assessmentType: 'DIAGNOSTIC' | 'TOPIC_SPECIFIC' | 'PROGRESS_CHECK' | null

  // Step 2 (only for TOPIC_SPECIFIC and PROGRESS_CHECK)
  topicIds: string[]

  // Step 3
  questionCount: number          // 5–30, default 10
  difficultyMin: number          // 1.0–5.0, default 1.0
  difficultyMax: number          // 1.0–5.0, default 5.0
  deadline: string | null        // ISO date string or null

  // Step 4 (populated after POST /classes/{id}/assessments)
  draftAssessmentId: string | null
  previewQuestions: PreviewQuestion[]

  // Actions
  setStep: (step: number) => void
  setClassId: (id: string, name: string) => void
  setAssessmentType: (type: string) => void
  setTopicIds: (ids: string[]) => void
  setQuestionCount: (n: number) => void
  setDifficulty: (min: number, max: number) => void
  setDeadline: (date: string | null) => void
  setDraftAssessment: (id: string, questions: PreviewQuestion[]) => void
  reset: () => void              // called after successful publish or cancel
}
```

---

## Step 1 — Class and Assessment Type (`Step1ClassAndType.tsx`)

Display a dropdown of classes fetched from `GET /api/v1/schools/{school_id}/classes`.
Only show the teacher's own classes (the API already filters by `teacher_id` for the
Teacher role). Show a loading skeleton while classes are fetching.

Below the class dropdown, show four assessment type cards in a 2×2 grid. Each card
shows an icon, a title, and a one-sentence description:

DIAGNOSTIC: "A broad sweep across all topics to establish a baseline." No topics to
select in Step 2 — skip directly to Step 3.

TOPIC_SPECIFIC: "Focused on one or more specific topics you have taught."

PROGRESS_CHECK: "A quick check on recent topics to measure retention."

FINAL: "A comprehensive end-of-term assessment covering all topics."

The "Next" button is disabled until both a class and a type are selected. On click,
advance to Step 2 (or Step 3 if DIAGNOSTIC or FINAL).

---

## Step 2 — Topics (`Step2Topics.tsx`)

Only rendered for TOPIC_SPECIFIC and PROGRESS_CHECK. Skipped entirely for DIAGNOSTIC
and FINAL.

Show a checklist of curriculum topics for the selected class's subject and grade. The
topics come from the curriculum data — use `GET /api/v1/subjects/{subject_id}/topics`
if that endpoint exists, otherwise show a placeholder and note the dependency on
curriculum data being seeded (M1-2-T1).

At least one topic must be selected to proceed. Show a validation message if the
teacher tries to proceed with no topics selected.

---

## Step 3 — Configure Questions (`Step3Configure.tsx`)

Show three controls:

A slider for question count, range 5 to 30, default 10. Show the current value as
a large number next to the slider label ("10 questions").

Two number inputs for difficulty min and max, both in range 1.0 to 5.0 with 0.5
increments, defaults 1.0 and 5.0. Show a helper text: "1.0 = easiest, 5.0 = hardest.
A wider range gives more variety."

A date picker for deadline (optional). Label: "Deadline (optional)". If not set, the
assessment has no deadline.

The "Next" button is always enabled in this step — all fields have valid defaults.

---

## Step 4 — Preview Questions (`Step4Preview.tsx`)

On mount, call `POST /api/v1/classes/{class_id}/assessments` with the wizard state:

```typescript
const body = {
  assessment_type: wizardState.assessmentType,
  topic_ids: wizardState.topicIds,       // empty array for DIAGNOSTIC
  question_count: wizardState.questionCount,
  difficulty_min: wizardState.difficultyMin,
  difficulty_max: wizardState.difficultyMax,
  deadline: wizardState.deadline,
}
```

While the API call is in progress, show a loading skeleton with the message "Selecting
questions from the bank...". Do not show a spinner only — show a skeleton that
approximates the question list layout.

On success, store `response.id` as `draftAssessmentId` in wizard state and render
the question list. Each question card shows: the question text, the question type
badge (MCQ), and a remove button (✕ icon). The question count badge at the top
updates as questions are removed.

When the teacher removes a question, remove it from the local `previewQuestions` array
in wizard state. Do not call the API on each removal — the removal is applied when
the teacher publishes. On publish, send only the kept questions to the server. However,
in v1 the assessment was already created with all questions — the teacher's removals
in Step 4 are a UX affordance but the API call in Step 5 simply publishes the draft
as-is. Add a note in the code: "TODO M1+: implement per-question removal via DELETE
/assessments/{id}/questions/{question_id}".

If the API call returns 422 (insufficient questions), show an inline error message:
"Not enough questions in the bank for this configuration. Try broadening your topic
selection or difficulty range." Show a "Back" button to return to Step 3. Do not show
a retry button — the teacher must change the configuration.

---

## Step 5 — Review and Publish (`Step5Publish.tsx`)

Show a summary card:
- Class name and subject
- Assessment type with human-readable label
- Topic names (if applicable)
- Question count
- Deadline (or "No deadline set")

Show two buttons:

"Save as Draft" — does nothing to the API (the draft already exists from Step 4).
Navigate to `/teacher/classes/{classId}/assessments`. Show a success toast: "Assessment
saved as draft."

"Publish Now" — calls `POST /api/v1/assessments/{draftAssessmentId}/publish` with
`{ deadline: wizardState.deadline }`. On success, navigate to
`/teacher/classes/{classId}/assessments`. Show a success toast: "Assessment published
and visible to students." On error, show an inline error and stay on Step 5 — do not
navigate away.

---

## Assessment List Page (`AssessmentListPage.tsx`)

Route: `/teacher/classes/:classId/assessments`

Fetch `GET /api/v1/classes/{classId}/assessments` via the `useClassAssessments` hook.
Show skeleton cards while loading. Show empty state if the list is empty: "No
assessments yet. Create your first assessment to see student progress."

Each row in the list table shows: title, assessment type badge, status badge (DRAFT
in grey, ACTIVE in green, CLOSED in slate), question count, deadline, and an actions
column. Actions: "View Results" (only for ACTIVE and CLOSED), "Close" (only for
ACTIVE), "Delete" (only for DRAFT).

The "Create New Assessment" button in the top right is gold (`bg-brand-gold`), links
to `/teacher/assessments/new`, and pre-selects the current class in the wizard.

---

## Acceptance Criteria

**Playwright E2E tests in `assessment-creation.spec.ts`**

`test_wizard_step1_when_class_selected_and_type_chosen_then_next_enabled` — Navigate
to `/teacher/assessments/new`. Select a class from the dropdown. Select TOPIC_SPECIFIC.
Assert the "Next" button becomes enabled.

`test_wizard_step1_when_diagnostic_selected_then_step2_skipped` — Select DIAGNOSTIC.
Click Next. Assert the wizard advances directly to Step 3, not Step 2.

`test_wizard_step2_when_no_topics_selected_then_next_disabled` — Navigate to Step 2.
Assert the "Next" button is disabled. Select one topic. Assert button becomes enabled.

`test_wizard_step4_when_api_returns_questions_then_question_list_rendered` — Complete
Steps 1–3, reach Step 4. Mock the `POST /classes/{id}/assessments` API to return 10
questions. Assert 10 question cards are rendered.

`test_wizard_step4_when_insufficient_questions_then_error_message_shown` — Mock the
API to return 422. Assert the error message "Not enough questions" is visible and no
question cards are rendered.

`test_wizard_step5_publish_when_success_then_navigates_to_list` — Complete all steps.
Mock `POST /assessments/{id}/publish` to return 200. Click "Publish Now". Assert the
URL changes to `/teacher/classes/{classId}/assessments`.

`test_wizard_step5_publish_when_api_error_then_stays_on_step5` — Mock the publish
endpoint to return 500. Click "Publish Now". Assert the URL does not change and an
error message is visible.

`test_assessment_list_when_empty_then_shows_empty_state` — Fetch returns empty list.
Assert "No assessments yet" empty state is visible.

`test_assessment_list_when_draft_assessment_then_no_view_results_action` — Fetch returns
one DRAFT assessment. Assert the "View Results" action is not present in its row.

`test_assessment_list_when_active_assessment_then_close_action_present` — Fetch returns
one ACTIVE assessment. Assert the "Close" action is present in its row.

---

## Do NOT Touch

`frontend/apps/student/` — no code goes here.
`frontend/apps/school-admin/` — no code goes here.
`frontend/packages/ui/` — do not add wizard-specific components here; they are
  teacher-specific and belong in `apps/teacher`.
Any backend file.
