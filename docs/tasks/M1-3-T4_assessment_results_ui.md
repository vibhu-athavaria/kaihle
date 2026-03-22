# M1-3-T4 — Assessment Results UI (Teacher App)
**Milestone:** M1 · **Epic:** M1-3 · **Task:** T4
**Depends on:** M1-3-T2 (assessment routes return real data), M1-4-T1 (attempt routes return real data), M0-7-T1 (layout wrappers), M0-8-T4 (shared components)
**Blocks:** Nothing — final UI task of M1-3 epic
**Estimated effort:** 4–5 hours

---

## Context

All code in this task lives in `frontend/apps/teacher`. No code goes in any other app.

Read `docs/design/DESIGN_SYSTEM.md` §5.3 (Teacher) before writing any component.
Action buttons use gold (`brand-gold #c9932a`). Green is reserved for mastery
indicators — never use green buttons in the teacher app.

This task builds two pages: the class-level results overview and the individual
student answer breakdown. Both are reached by clicking "View Results" on the
assessments list page (`M1-3-T3`).

The teacher sees `correct_answer_key` in results — confirmed by `M1-3-T2` which
specifies role-based field filtering in the service layer. The student-facing results
page (`M1-4-T4`) strips this field. This task is teacher-only.

---

## User Story

As a teacher, I want to see how my class performed on an assessment — who submitted,
their scores, and how each student answered each question — so I can identify
misconceptions and decide whether to assign study plans or revisit a topic.

---

## Files to Create

```
frontend/apps/teacher/src/pages/assessments/
  AssessmentResultsPage.tsx        ← class overview (KPIs, distribution, student table)
  StudentAnswerBreakdownPage.tsx   ← individual student's per-question breakdown

frontend/apps/teacher/src/components/assessments/
  ScoreDistributionBar.tsx         ← horizontal distribution bar (Strong/Developing/Needs Work/Not submitted)
  StudentResultsTable.tsx          ← sortable table of all students with scores

frontend/apps/teacher/src/hooks/
  useAssessmentResults.ts          ← React Query hooks for results data

frontend/apps/teacher/src/tests/
  assessment-results.spec.ts       ← Playwright E2E tests
  ScoreDistributionBar.test.tsx    ← Jest unit tests
```

---

## Routes

`/teacher/assessments/:assessmentId/results` — `AssessmentResultsPage`.
Protected by `PrivateRoute` + `RoleRoute(['TEACHER', 'SCHOOL_ADMIN', 'KAIHLE_ADMIN'])`.

`/teacher/assessments/:assessmentId/results/:studentId` — `StudentAnswerBreakdownPage`.
Same guards. Reached by clicking "View answers →" in the student table.

---

## Complete List of API Calls This UI Makes

`GET /api/v1/assessments/{assessmentId}` — called on mount for assessment metadata
(title, type, class name, question count, deadline, status). Cached by React Query.

`GET /api/v1/classes/{classId}/assessments` — not called here; class context comes
from the assessment response.

`GET /api/v1/attempts/{attemptId}/results` — called per student on the breakdown
page to get per-question responses. The `assessmentId` and `studentId` are used to
look up the `attemptId` from the results list.

No endpoint currently returns all student attempt summaries for a single assessment
in one call. The `AssessmentResultsPage` derives this from the assessment response's
`student_results` field (added in M1-3-T2). Do not make N individual attempt calls
on the overview page — the aggregated data comes from the assessment endpoint.

Those are the only API calls. Do not call gap map or study plan endpoints from
these pages.

---

## Page 1: Assessment Results Overview (`AssessmentResultsPage.tsx`)

### Page layout

```
┌─────────────────────────────────────────────────────────────────┐
│  ← Assessments  |  Mid-term algebra check — Results             │
│  Status badge                           [Close assessment]      │
├─────────────────────────────────────────────────────────────────┤
│  KPI row (4 cards)                                              │
│  Score distribution bar                                         │
│  Student results table (searchable, sortable)                   │
└─────────────────────────────────────────────────────────────────┘
```

### KPI cards (4, in a row)

```typescript
interface ResultKPIProps {
  label: string
  value: string | number
  sub?: string
  valueColor?: string  // mastery color if applicable
}
```

Four KPIs in order:
1. **Submitted** — `{submitted} of {total} students` · sub: `{pct}% submitted`
2. **Class average** — `{avg}%` · colored by `getMasteryStyle(avg/100)` · sub: band label
3. **Highest score** — `{pct}%` · sub: `{student_first_name} {student_last_name}`
4. **Needs attention** — count of students with score < 0.4 · sub: "below 40%" · value in `text-red-600`

Card style: `bg-white border border-role-teacher-border rounded-xl p-4`.
Do not use green card borders — that is school-admin. Teacher border is `#e5e7eb`.

### Score distribution (`ScoreDistributionBar.tsx`)

Horizontal bar chart showing count per band:
- Strong (>70%) — `#16a34a`
- Developing (40–70%) — `#f59e0b`
- Needs work (<40%) — `#ef4444`
- Not submitted — `#e5e7eb`

```typescript
interface ScoreDistributionBarProps {
  strong: number
  developing: number
  needsWork: number
  notSubmitted: number
  total: number
}
```

Each band renders as a horizontal bar row:
```
label (90px fixed)   [██████████░░░░░░] (flex bar)   count (30px)
```

Bar fill width = `(count / total) * 100%`.

### Student results table (`StudentResultsTable.tsx`)

Columns: Student · Score · Band · Submitted date · Action

Sorting: click column headers to sort. Default sort: Score ascending (lowest first —
teacher attention goes to students needing help). Secondary sort: Name alphabetically.

Submitted students show:
- Score as coloured pill badge using `getMasteryStyle` band colors
- Band label as text (Strong / Developing / Needs work)
- Submitted date formatted as "18 Mar 2026"
- Action: "View answers →" link → navigates to `StudentAnswerBreakdownPage`

Not-submitted students show:
- Score: "—" (muted)
- Band: "Not submitted" (muted)
- Date: "—"
- Action: "Pending" (muted text, no link)

Search input (top right of table): filters by student name client-side.

"Close assessment" button (topbar right, outline style, only for ACTIVE assessments):
calls `POST /api/v1/assessments/{assessmentId}/close`. On success, show success toast
and update status badge from Active to Closed.

---

## Page 2: Student Answer Breakdown (`StudentAnswerBreakdownPage.tsx`)

### Route
`/teacher/assessments/:assessmentId/results/:studentId`

Back navigation: breadcrumb "← Results" → returns to `AssessmentResultsPage`.

### Page layout

```
┌──────────────────────────────────────────────────────────────┐
│  ← Results  |  [Student name] — Answer breakdown            │
├──────────────────────────────────────────────────────────────┤
│  Student header card                                         │
│  Question-by-question breakdown (scrollable)                 │
│  [ ← Prev student ]   1 of 19 submitted   [ Next student → ] │
└──────────────────────────────────────────────────────────────┘
```

### Student header card

Left side: avatar initials circle (`bg-brand-primary text-white`) + student name
(Fraunces) + "Mathematics 9B · Mid-term algebra check" meta.

Right side: SVG score ring (56px) — stroke from `getMasteryStyle(score)`.
Below ring: band label · "N of M correct" · "Class avg: X%".

### Question breakdown list

One row per question. Ordered by `order_index` from the assessment.

Each row:
```
[icon]  Q{n}
        {question_text}
        Given: {student_answer}   Correct: {correct_answer}
```

Icon: green filled circle ✓ if correct, red filled circle ✕ if wrong.
No icon if question was not answered (show "Not answered" in muted text).

If correct: show only "Answer: {answer} ✓" in green. No "Correct:" line needed.
If wrong: "Given: {answer} ✕" in red + "Correct: {correct_answer}" in green.

Show first 6 questions, then "+ N more questions" expandable link.
Clicking reveals remaining questions without page navigation.

### Student navigation

Previous / Next buttons cycle through submitted students only (exclude not-submitted).
Show "N of M submitted" centred between buttons.

Navigation is client-side — the full submitted student list is in component state from
the parent page. No additional API call on prev/next.

---

## `useAssessmentResults.ts`

```typescript
// Assessment metadata + aggregated results
export const useAssessmentResults = (assessmentId: string) =>
  useQuery({
    queryKey: ['teacher', 'assessment-results', assessmentId],
    queryFn: () => apiClient.get<AssessmentWithResults>(`/assessments/${assessmentId}`),
    enabled: !!assessmentId,
  })

// Individual student attempt breakdown
// attemptId is looked up from the student's result entry in useAssessmentResults
export const useStudentAttemptResults = (attemptId: string | null) =>
  useQuery({
    queryKey: ['teacher', 'attempt-results', attemptId],
    queryFn: () => apiClient.get<AttemptResultResponse>(`/attempts/${attemptId}/results`),
    enabled: !!attemptId,
  })
```

---

## Acceptance Criteria

**Playwright E2E tests in `assessment-results.spec.ts`**

`test_results_page_when_loaded_then_four_kpi_cards_visible` — Navigate to the
results page for an assessment with 10 submitted students. Assert four KPI card
elements are visible.

`test_results_page_when_all_submitted_then_submitted_kpi_shows_100_percent` — Mock
all students as submitted. Assert the Submitted KPI shows "100% submitted".

`test_results_page_when_student_not_submitted_then_row_shows_pending` — Mock one
student with no attempt. Assert their row shows "—" score and "Pending" action text
with no link.

`test_results_page_when_sort_by_score_then_lowest_first` — Assert default sort places
lowest-scoring student at top.

`test_results_page_when_search_by_name_then_table_filters` — Type "Aisha" in the
search input. Assert only rows containing "Aisha" are visible.

`test_results_page_when_view_answers_clicked_then_navigates_to_breakdown` — Click
"View answers →" for a submitted student. Assert the URL changes to
`/teacher/assessments/{id}/results/{studentId}`.

`test_breakdown_page_when_loaded_then_score_ring_visible` — Navigate to the breakdown
page. Assert an SVG circle element is visible with a non-zero stroke-dashoffset.

`test_breakdown_page_when_score_above_0_7_then_green_ring` — Mock score of 0.8.
Assert the ring stroke uses the green mastery color.

`test_breakdown_page_when_answer_wrong_then_correct_answer_shown` — Mock a question
where student answered incorrectly. Assert both "Given:" and "Correct:" labels are
visible in the question row.

`test_breakdown_page_when_answer_correct_then_only_answer_shown` — Mock a correct
answer. Assert "Correct:" label is NOT present (only "Answer: ✓" shown).

`test_breakdown_page_when_next_student_clicked_then_url_changes` — Click "Next
student →". Assert the URL changes to the next student's ID.

**Jest unit tests**

`test_score_distribution_when_10_strong_5_developing_5_needs_then_bars_proportional` —
Render `ScoreDistributionBar` with those values. Assert the Strong bar width is 50%,
Developing 25%, Needs Work 25%.

`test_student_results_table_when_score_0_38_then_needs_work_badge_shown` — Assert
the badge label reads "Needs work".

`test_student_results_table_when_not_submitted_then_no_link_in_action_column` —
Assert that a not-submitted student row has no `<a>` element in the action cell.

---

## Do NOT Touch

`frontend/apps/student/` — no code goes here.
`frontend/apps/school-admin/` — no code goes here.
`frontend/packages/ui/` — do not add assessment-results-specific components here.
Any backend file.
