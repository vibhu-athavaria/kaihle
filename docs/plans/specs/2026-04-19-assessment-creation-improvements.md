# Assessment Creation — Three Improvements
**Date:** 2026-04-19
**Branch:** fix/teacher-assessment-creation
**Status:** Approved

---

## Context

The Teacher assessment creation wizard is a 5-step flow (`NewAssessmentPage` → Step1–5). Three improvements were identified:

1. Topic selection was skipped for Diagnostic and Final assessment types.
2. A bug caused "No topics found" to appear when the topics API errored silently.
3. The Step 4 preview modal showed only one question and had no attempt/try-out mode.

---

## Improvement 1 — Topic Selection for All Assessment Types

### Current behaviour
`Step1ClassAndType.handleNext()` skips Step 2 for `DIAGNOSTIC` and `FINAL` types, jumping directly to Step 3.

### Target behaviour
All four assessment types go through Step 2 (topic selection). Topic selection is **required** for all types — at least one topic must be selected to proceed. "Select all" button already exists and is kept.

### Changes

**`Step1ClassAndType.tsx`**
- Remove the `skipsTopics` check. `handleNext` always calls `setStep(2)`.
- Update the description text on the `DIAGNOSTIC` card from "Assess baseline knowledge across all topics" → "Assess baseline knowledge across selected topics".
- Update the description on the `FINAL` card from "End-of-term comprehensive assessment" → "End-of-term assessment across selected topics".

**`Step2Topics.tsx`**
- No logic change needed — `canProceed = topicIds.length > 0` already enforces at least one selection.
- "Next" button `disabled` condition already prevents proceeding with zero topics when topics exist.
- Back button already returns to Step 1.

**`NewAssessmentPage.tsx` step indicator**
- Ensure Step 2 label is not greyed-out/inactive for Diagnostic and Final types (if the indicator has any type-based conditional styling, remove it).

### Backend impact
None. The backend `AssessmentCreateRequest` already accepts `topic_ids: list[UUID]` for all assessment types. The question pool selection in `assessment_service._select_questions_for_diagnostic()` already filters by topic IDs when provided.

---

## Improvement 2 — Bug: "No Topics Found" Shown on API Error

### Root cause
`fetchTopicsForClass` in `Step2Topics.tsx` catches all errors and returns `[]`. This makes a network/server failure indistinguishable from a class that genuinely has no topics defined.

Additionally, if `subjectId`, `gradeId`, or `curriculumId` are `null` in wizard state when Step 2 renders, the React Query `enabled` guard prevents the query from running, leaving `topics = []` with no indication of why.

### Target behaviour
Three distinct states, each with its own UI:

| State | Condition | UI |
|---|---|---|
| Loading | `isLoading = true` | Existing skeleton |
| Error | Query threw (network/server error) | Red bordered box: "Failed to load topics" + "Try again" button |
| Empty | Query succeeded, returned `[]` | Neutral box: "No topics defined for this subject yet." (no skip affordance — teacher cannot proceed without topics) |
| Has topics | `topics.length > 0` | Existing checkbox list |

### Changes

**`Step2Topics.tsx`**
- Add `isError` from `useQuery` (already returned by React Query, just not destructured).
- Remove the try/catch inside `fetchTopicsForClass` — let errors propagate so React Query captures them in `isError`.
- Add an error state render branch above the empty-state branch:
  ```tsx
  } else if (isError) {
    // red error box with refetch button
  } else if (topics.length === 0) {
    // neutral "no topics defined" box — no skip link
  }
  ```
- Use `refetch` from `useQuery` for the "Try again" button.
- Remove the "Skip to configuration →" link from the empty state — with Improvement 1 making topics required, skipping is no longer valid.

---

## Improvement 3 — Preview Modal: Larger + Attempt Mode

### Current behaviour
Step 4 has a "Student view" modal that shows a static student experience at 30% progress. Questions are paginated 3-per-page in the main list, and a "Preview" modal shows one question and its options statically.

### Target behaviour
Replace the static single-question preview modal with a full **attempt mode** that lets the teacher try the assessment question-by-question, with immediate feedback, without storing anything to the database.

### Attempt Mode UX

- **Entry:** "Try it" button on each question row (replaces current "Preview" button on individual questions). Also a "Try assessment" button in the stats bar.
- **Dialog size:** `max-w-3xl` (≈768px) instead of current `max-w-lg`. Centred, with overflow-y-scroll for long questions.
- **Question flow:**
  - One question displayed at a time.
  - Progress header: "Question N of M" + difficulty dots.
  - Linear progress bar (fills as teacher advances).
  - Four answer option buttons (A/B/C/D), styled as outlined pills.
  - Selecting an option locks the question and shows immediate feedback:
    - Selected wrong answer: red border + `✗ Your answer` label.
    - Correct answer: green border + `✓ Correct` label.
    - Unselected options: greyed out.
  - "Next →" button appears after an answer is selected. On last question, shows "See results".
- **Results screen (final screen in modal):**
  - Score: "You got X / M correct"
  - "Close" button only — no retry.
- **State:** All attempt state is local React state (`useState`). Zero API calls. No writes to DB.
- **Footer note:** Italic caption "Preview only — no answers stored" shown during attempt.

### Changes

**`Step4Preview.tsx`**
- Add local state: `attemptOpen: boolean`, `attemptStartIndex: number` (which question to start from, defaults to 0 for "Try assessment", or question's index for per-question entry).
- Add `currentQuestionIndex: number`, `answers: Record<string, string>` (question_id → selected option key) to attempt state.
- Replace the existing single-question preview modal with the new attempt modal.
- Remove the static "Student view" modal (superseded by this).
- "Try assessment" CTA: added to stats bar row (gold outlined button).
- Per-question "Try" button: replaces the existing "Preview" eye-icon button on each row.
- Dialog uses `Modal` from `@kaihle/ui` (Radix Dialog) to comply with CONSTITUTION Rule 21 (focus trap).
- Dialog `maxWidth` prop or inline `className`: `max-w-3xl`.

### What is NOT changed
- The paginated question list (3-per-page) in the main Step 4 body remains.
- The stats bar (question count, subtopic count, difficulty range, chart) remains.
- The "Remove" button per question remains.
- No backend changes.

---

## Files Touched

| File | Change type |
|---|---|
| `frontend/apps/teacher/src/pages/assessments/steps/Step1ClassAndType.tsx` | Remove skip logic, update card descriptions |
| `frontend/apps/teacher/src/pages/assessments/steps/Step2Topics.tsx` | Add error state, remove silent catch, remove skip link |
| `frontend/apps/teacher/src/pages/assessments/steps/Step4Preview.tsx` | Replace static preview modal with attempt mode |

No backend changes. No new dependencies. No schema changes.

---

## Constraints & Rules Applied

- **CONSTITUTION Rule 21:** Modal uses `Modal` from `@kaihle/ui` (Radix Dialog) — focus trap guaranteed.
- **CONSTITUTION Rule 22:** Loading state remains skeleton; button spinners not needed (no async in attempt mode).
- **DESIGN_SYSTEM §5.3:** Teacher primary action buttons use `brand-gold`. "Try assessment" CTA uses gold outlined style. Feedback colors (green/red) are mastery data colors, not action colors — acceptable per spec.
- No additional UI kits introduced.
