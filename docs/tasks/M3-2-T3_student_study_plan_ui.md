# M3-2-T3 — Student Study Plan UI (Student App)
**Milestone:** M3 · **Epic:** M3-2 · **Task:** T3
**Depends on:** M3-2-T2 (study plan routes return real data), M2-1-T4 (my-progress page — study plans section wires up here)
**Parallel with:** M3-2-T4 (teacher assignment UI — different app)
**Blocks:** Nothing — last student-facing task in M3
**Estimated effort:** 5–6 hours

---

## Context

All code in this task lives in `frontend/apps/student`. No code goes in any other app.

Read `docs/design/DESIGN_SYSTEM.md` §5.4 (Student) before writing anything. The student
app is mobile-first and uses the airy, cool palette. No sidebar. All layouts use
`StudentLayout` from `packages/ui`.

The `useMyStudyPlans` hook already exists from M0-10-T8. It now returns real data
after M3-2-T2 completes. This task also wires the "Go to Study Plans" link that was
rendered as a passive placeholder in M2-1-T4.

Study plan quizzes are LLM-generated and contain both MCQ and SHORT_ANSWER questions.
This is different from the question bank (MCQ only). The quiz component must render
both question types.

---

## User Story

As a student, I want to see the study plans my teacher has assigned for my gaps, work
through curated resources at my own pace, and take a practice quiz to confirm my
understanding.

---

## Files to Create

```
frontend/apps/student/src/pages/study-plans/
  StudyPlanListPage.tsx        ← list of all plans grouped by subject
  StudyPlanDetailPage.tsx      ← single plan with resources + quiz
  components/
    ResourceCard.tsx            ← individual resource with watch/read button
    StudyPlanQuiz.tsx           ← quiz component (MCQ + short answer)
    PlanStatusBadge.tsx         ← GENERATING / ACTIVE / COMPLETED badge

frontend/apps/student/src/hooks/
  useStudyPlanDetail.ts         ← React Query for single plan
  useStudyPlanActions.ts        ← mutations for watched + quiz submit

frontend/apps/student/src/tests/
  study-plans.spec.ts           ← Playwright E2E tests
  StudyPlanQuiz.test.tsx        ← Jest unit tests
```

---

## Routes

`/student/study-plans` — `StudyPlanListPage`. Protected by `PrivateRoute` +
`OnboardingRoute`.

`/student/study-plans/:planId` — `StudyPlanDetailPage`. Same guards.

Add "Study Plans" to the student navigation. Also update the "Suggested Next Steps"
section on `/student/my-progress` (built in M2-1-T4) to link to `/student/study-plans`
now that real plans can exist. The conditional check is already there from M2-1-T4 —
this task simply ensures the link destination is correct.

---

## Complete List of API Calls This UI Makes

`GET /api/v1/students/me/study-plans` — called by `useMyStudyPlans` on the list page,
with optional `?status=` and `?subject_id=` filters.

`GET /api/v1/study-plans/{planId}` — called by `useStudyPlanDetail(planId)` on the
detail page.

`PATCH /api/v1/study-plans/{planId}/resources/{resourceId}/watched` — called when a
student clicks "Mark as done" on a resource card.

`POST /api/v1/study-plans/{planId}/quiz/submit` — called when the student submits
the quiz.

That is the complete set. No other endpoints are called.

---

## Study Plan List Page (`StudyPlanListPage.tsx`)

Group plans by subject. Within each subject group, sort by status: ACTIVE first,
then GENERATING, then COMPLETED last. Each plan card shows the subtopic name, a
`PlanStatusBadge`, the resource count (e.g. "3 resources"), and the quiz score if
the plan is COMPLETED ("Quiz: 80%").

For plans in GENERATING status, show an animated pulse indicator and the text
"Your personalised plan is being prepared...". Do not show a resource count or quiz
link for generating plans — the data does not exist yet.

Empty state when no plans exist: "No study plans yet. Your teacher will assign
them based on your assessment results." This replaces the passive message from
M2-1-T4's suggested next steps section once a student has at least one plan.

---

## Study Plan Detail Page (`StudyPlanDetailPage.tsx`)

The page has two sections: Resources and Practice Quiz. Both are always rendered, but
the quiz section is visually locked until at least one resource is marked watched (a
soft UX gate — not enforced by the backend).

**Resources section header:** "Learning Resources" with a small "✨ Matched to your
style" badge. This badge is always shown — it signals personalization even if the
student does not consciously notice the modality weighting. Do not add a tooltip
explaining the algorithm; just the badge.

**Quiz lock state:** When no resources are watched yet, the quiz section header shows
a lock icon and the text "Complete at least one resource to unlock the quiz." The quiz
questions are still rendered in the DOM but are visually dimmed (`opacity-40
pointer-events-none`). This is a UX hint, not a security boundary — the backend
accepts quiz submissions regardless.

---

## ResourceCard (`ResourceCard.tsx`)

```typescript
interface ResourceCardProps {
  resource: StudyPlanResource  // from schemas/study_plans.ts
  planId: string
  onWatched: (resourceId: string) => void
}
```

Show a resource type icon (📹 for VIDEO, 📄 for ARTICLE, 🎮 for INTERACTIVE), the
title (truncated to two lines), the source name and duration (e.g. "YouTube · 8 min"),
and a primary action button. The button text adapts to type: "Watch" for VIDEO,
"Read" for ARTICLE, "Try" for INTERACTIVE. Clicking opens the URL in a new tab.

Below the action button, show a "Mark as done ✓" checkbox. When ticked, call the
`PATCH .../watched` mutation and immediately show a filled checkmark. If the API call
fails, revert the checkbox state and show a brief error toast. Do not disable the
checkbox while the request is in-flight — optimistic update, then reconcile.

Cards for already-watched resources (`is_watched: true`) render with a green tint
background (`bg-green-50`) and a filled checkmark. The "Mark as done" checkbox is
replaced by "Done ✓" in green text.

---

## StudyPlanQuiz (`StudyPlanQuiz.tsx`)

The quiz renders all questions on a single scrollable page (not paginated). Questions
are numbered Q1–Q5. Each question shows the question text and its input:

MCQ questions show four option cards in a 2×2 grid on mobile. Single select — tapping
one deselects the others. Same visual pattern as the assessment taking UI from M1-4-T4.

SHORT_ANSWER questions show a multi-line textarea with a 300-character limit and a
character counter. Placeholder: "Write your answer here...".

"Submit Quiz" button at the bottom is disabled until all questions have a non-empty
response. On click, show a loading state ("Checking...") while the API responds.

After successful submission, transition the quiz section to a results state. Show the
overall score prominently, then reveal each question with: the student's answer, a
correct/incorrect icon, the correct answer, and the explanation. For SHORT_ANSWER
questions, show the model answer below the student's answer (the backend scores these
via LLM and returns the explanation in `QuizSubmitResponse`).

Score display: if `score >= 0.8`, show "Great work! 🎉" in green. If `score >= 0.6`,
show "Good effort! Keep it up." in amber. If below 0.6, show "Keep practising — you'll
get there!" in the student app's muted text colour. Never show a discouraging message.

---

## Acceptance Criteria

**Playwright E2E tests in `study-plans.spec.ts`**

`test_list_page_when_plans_exist_then_grouped_by_subject` — Seed two plans for
Mathematics and one for Science. Navigate to `/student/study-plans`. Assert two subject
group headers are visible and the Mathematics group shows two plan cards.

`test_list_page_when_no_plans_then_empty_state_shown` — Mock the API to return empty
data. Assert the empty state message is visible.

`test_list_page_when_plan_generating_then_pulse_indicator_shown` — Mock one plan with
`status: "GENERATING"`. Assert the animated pulse element is visible and no resource
count is shown for that card.

`test_detail_page_when_loaded_then_resources_and_locked_quiz_shown` — Navigate to a
plan detail page. Assert resource cards are visible and the quiz section shows a lock
indicator.

`test_detail_page_when_resource_marked_done_then_quiz_unlocks` — Click "Mark as done"
on a resource card. Assert the lock state is removed from the quiz section.

`test_detail_page_when_mark_done_api_fails_then_checkbox_reverts` — Mock the PATCH
endpoint to return 500. Click "Mark as done". Assert the checkbox returns to unchecked
state and an error toast appears.

`test_quiz_when_all_questions_answered_then_submit_enabled` — Fill in all five quiz
responses. Assert the "Submit Quiz" button is no longer disabled.

`test_quiz_when_submitted_then_results_shown_with_score` — Mock the submit endpoint to
return `score: 0.8, correct_count: 4, total_questions: 5`. Submit the quiz. Assert
"Great work! 🎉" is visible and the score is shown.

`test_quiz_results_show_correct_answer_and_explanation_per_question` — After submit,
assert that each question row shows the correct answer text and the explanation string
from the API response.

**Jest unit tests in `StudyPlanQuiz.test.tsx`**

`test_submit_button_disabled_when_any_question_unanswered` — Render `StudyPlanQuiz`
with five questions, answer only four. Assert the submit button has the `disabled`
attribute.

`test_submit_button_enabled_when_all_questions_answered` — Answer all five questions.
Assert the button is not disabled.

`test_score_display_when_0_8_then_great_work_message` — Render the post-submit result
state with `score: 0.8`. Assert "Great work!" text is present.

`test_score_display_when_0_4_then_keep_practising_message` — `score: 0.4`. Assert
the keep-practising message appears and neither "Great work" nor "Good effort" is shown.

`test_mcq_question_when_option_selected_then_others_deselected` — Render an MCQ
question, click option A, then click option B. Assert only option B has the selected
visual state.

`test_short_answer_when_over_300_chars_then_counter_shows_warning` — Type 301
characters into a SHORT_ANSWER textarea. Assert the character counter shows a warning
colour and the text is capped at 300 characters.

---

## Do NOT Touch

`frontend/apps/teacher/` — no code goes here. `frontend/apps/school-admin/` — no
code goes here. The `useMyStudyPlans` hook from M0-10-T8 — use as-is. Any backend file.
