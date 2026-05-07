# Step 4 Preview — Redesign Spec
**Date:** 2026-04-18
**Status:** Approved
**Scope:** Teacher assessment wizard Step 4 (question pool preview before publish)

---

## Context

Step 4 of the assessment wizard previews the question pool before publishing. The pool is now 3–4× the per-attempt count (up to `MAX_DIAGNOSTIC_POOL = 60`) distributed across difficulty levels. Teachers need visibility into the pool composition and confidence that the questions are appropriate before publishing.

---

## Design: A + C Combined

### Layout (top to bottom inside the wizard card)

**1. Stats bar**
Four stat boxes in a row:
- Questions in pool (green, e.g. 40)
- Per student attempt (gold, e.g. 10)
- Topics covered (grey, count)
- Difficulty range (grey, e.g. "1–5")

**2. Difficulty distribution chart**
Horizontal bar chart, one bar per difficulty integer level within the configured range. Each bar shows the count of questions at that level. Bars use `brand-primary` (green) for lower levels and `brand-gold` for higher levels.

**3. Questions in pool list**
Compact rows — one row per question:
- Number badge (green circle)
- Question text (truncated with ellipsis if too long)
- Tags: difficulty level (stars + number), subtopic name, option count
- "Preview" button (gold, opens single-question modal)
- Remove (×) button

3 questions per page. Pagination controls below the list.

**4. Student view banner**
Green-tinted card with "Open preview →" button. Opens the student view modal.

**5. Footer actions**
← Back | Review & Publish →

---

## Modals

### Single-question preview modal
Opens when teacher clicks "Preview" on any row.
- Header: "Question preview — as student sees it"
- Full question text (not truncated)
- Four answer options (A/B/C/D) as selectable cards — visual only, no submit
- Metadata tags: difficulty level, subtopic
- Close: × button or Escape or click outside

### Student view modal
Opens when teacher clicks "Open preview →".
- Shows the adaptive assessment UI as a student sees it
- Progress bar (e.g. "Question 3 of 10")
- One question + four options
- Note: "Next question adapts based on the student's answer"
- Close: × button or Escape or click outside

---

## Data requirements

The API response for `POST /classes/:classId/assessments` already returns `questions[]` (added in a previous fix). Each question needs:
- `question_id`
- `question_text`
- `options: [{key, text}]`
- `difficulty_level` ← **needs to be added to the API response**
- `subtopic_name` ← **needs to be added to the API response** (join through Subtopic model)

The frontend currently only receives `question_id`, `question_text`, `options`. The backend must also return `difficulty_level` and `subtopic_name` per question.

---

## What changes

### Backend
- `AssessmentQuestion` schema: add `difficulty_level: int` and `subtopic_name: str`
- `create_assessment` route: populate these fields from `QuestionBank.difficulty_level` and `Subtopic.name` when building the questions list

### Frontend — `Step4Preview.tsx`
- Replace current flat list with the new layout
- Local state: `currentPage`, `previewQuestion | null`, `studentViewOpen`
- Stats bar computed from `localQuestions`
- Difficulty chart computed from `localQuestions` grouped by `difficulty_level`
- Paginated question rows (3 per page)
- Single-question preview modal (uses `Modal` from `@kaihle/ui`)
- Student view modal (uses `Modal` from `@kaihle/ui`)

### Types
- Extend `PreviewQuestion` in `useAssessmentWizard.ts` to include `difficulty_level` and `subtopic_name`

---

## Constraints
- All modals must use `Modal` from `@kaihle/ui` (Constitution Rule 21 — focus trap required)
- Loading state: skeleton while draft is being created (already implemented)
- Design tokens from `docs/design/DESIGN_SYSTEM.md` §5.3 (Teacher role)
- Gold is the teacher action color — Preview button uses gold tint
