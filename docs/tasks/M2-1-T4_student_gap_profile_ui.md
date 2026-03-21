# M2-1-T4 — Student Gap Profile UI (Student App)
**Milestone:** M2 · **Epic:** M2-1 · **Task:** T4
**Depends on:** M2-1-T2 (gap map routes return real data)
**Parallel with:** M2-1-T3 (teacher heatmap UI — independent, different app)
**Blocks:** M3-2-T3 (study plan UI links from this page)
**Estimated effort:** 4–5 hours

---

## Context

All code in this task lives in `frontend/apps/student`. No code goes in any other app.

Read `docs/design/DESIGN_SYSTEM.md` §5.4 (Student) before writing any component. The
student app uses a cool, airy palette with no sidebar. All layouts use `StudentLayout`
from `packages/ui`. This is mobile-first — design for 375px and then enhance up.

The `useMyGapMap` hook already exists from M0-10-T8. It calls
`GET /api/v1/students/me/gap-map?subject_id={subjectId}`. This is the `/me` shortcut
— not `GET /students/{current_user_id}/gap-map` with a hardcoded user ID. Never
construct the student's ID manually in a URL in the frontend; the `/me` shortcut
exists precisely to avoid that pattern.

---

## User Story

As a student, I want to see my personal mastery profile grouped by subject and topic
so I can understand which areas I am strong in and which need more work.

---

## Files to Create

```
frontend/apps/student/src/pages/progress/
  MyProgressPage.tsx           ← page shell with subject tabs
  TopicProgressRow.tsx         ← expandable topic row with subtopic breakdown
  SubtopicProgressRow.tsx      ← individual subtopic with mastery circle

frontend/apps/student/src/tests/
  my-progress.spec.ts          ← Playwright E2E and Jest unit tests
```

---

## Route

`/student/my-progress` — `MyProgressPage`. Protected by `PrivateRoute` +
`OnboardingRoute` (student must have completed the learning profile to access this
page, since that is the first onboarding gate — but the diagnostic may not yet be
complete, so this page may show "Not yet assessed" states for many subtopics early on).

---

## Complete List of API Calls This UI Makes

`GET /api/v1/students/me/gap-map?subject_id={subjectId}` — called via the
`useMyGapMap(subjectId)` hook. Called once on page load with the first subject tab
selected and again whenever the student switches subject tabs. Returns a `StudentGapMap`
with `scores: StudentSubtopicScore[]`.

That is all. There are no additional API calls from this page.

---

## Page Layout (`MyProgressPage.tsx`)

The page has two regions: a subject tab bar at the top and a scrollable list of
topic groups below.

```
┌───────────────────────────────────────────────────────────┐
│  My Progress                                              │
│  ─────────────────────────────────────────────────────    │
│  [Mathematics]  [Science]  [English]  ← subject tabs     │
│                                                           │
│  ▶ Algebra                           (class avg shown)    │
│     ● Algebraic Fractions   🟡 65%                        │
│     ● Quadratic Equations   🔴 28%                        │
│  ▶ Geometry                                               │
│     ● Pythagoras Theorem    ⬜ Not assessed               │
│     ● Circle Theorems       🟢 82%                        │
│                                                           │
│  ────────────────────────────────────                     │
│  Suggested next steps                                     │
│  [Go to Study Plans →]  (placeholder for M3)             │
└───────────────────────────────────────────────────────────┘
```

The subject tab bar reads its tab list from the current user's enrolled classes.
For simplicity in v1, derive the subject list from the `gap_map.scores` data —
group by `topic_id` → `subject` from the score data. The tab labeled "Mathematics"
is simply the first subject alphabetically unless the student has recent activity in
another subject (use `last_assessed_at` to determine most-recent, show that first).

While data is loading, show skeleton rows inside the topic groups — not a full-page
spinner.

---

## Topic Progress Row (`TopicProgressRow.tsx`)

Each topic group is a collapsible row. It starts expanded by default. The topic row
header shows the topic name and a small aggregate indicator — the average of all
subtopic mastery scores in that topic group, displayed as a compact pill badge with
the appropriate color from `getMasteryStyle`.

Clicking the topic row header toggles the expansion state. The expanded state shows
the subtopic rows. The collapsed state shows only the topic header. Use a smooth CSS
height transition, not an abrupt show/hide.

Props interface:

```typescript
interface TopicProgressRowProps {
  topicName: string
  subtopics: StudentSubtopicScore[]
  defaultExpanded?: boolean   // default: true
}
```

---

## Subtopic Progress Row (`SubtopicProgressRow.tsx`)

Each subtopic shows a mastery indicator circle, the subtopic name, and the last
assessed date (or "Not yet assessed" if `last_assessed_at` is null).

The mastery indicator is an SVG circle with a colored stroke arc. Use
`getMasteryStyle(score)` from `@kaihle/types` to get the color. The circle must
carry an `aria-label` — color alone is not sufficient as an accessibility indicator.
The `aria-label` should read exactly as the plain-text label returned by
`getMasteryStyle` — for example, "Strong", "Developing", "Needs Work", or
"Not assessed".

Inside the circle, show the mastery percentage as a number (e.g. "65%"). For `null`
scores, show "–" inside the circle (an en-dash, not a hyphen).

```typescript
interface SubtopicProgressRowProps {
  subtopicName: string
  score: number | null           // 0.0–1.0, null = not yet assessed
  lastAssessedAt: string | null  // ISO datetime string or null
}
```

---

## Suggested Next Steps Section

At the bottom of the page, below all topic groups, show a "Suggested next steps"
section. In M2, this section shows one of two states depending on whether the student
has any active study plans. However, since the study plans API (`GET /students/me/study-plans`)
is a stub returning an empty list in M2, always show the passive state: "Your teacher
will assign study plans for areas that need more work."

Wire the section to check `useMyStudyPlans()` defensively:

```typescript
const { data: studyPlans } = useMyStudyPlans()
const hasActivePlans = (studyPlans?.data?.length ?? 0) > 0
```

If `hasActivePlans` is true (which will not happen in M2 but will in M3): show "You
have active study plans waiting. [Go to Study Plans →]" with a link to
`/student/study-plans`. If false: show the passive message. This means the section
will automatically activate in M3 with no code change required.

---

## Mastery Colour Reference

These values are defined in `getMasteryStyle` from `@kaihle/types`. Do not duplicate
or override them in this component.

Score above 0.7 → Strong → green (`#16a34a`). Score 0.4–0.7 → Developing → amber
(`#F59E0B`). Score below 0.4 → Needs Work → red (`#EF4444`). Score null → Not
assessed → grey (`#9CA3AF`).

The boundary at 0.4 is inclusive on the Developing side: a score of exactly 0.4
is Developing, not Needs Work.

---

## Acceptance Criteria

**Playwright E2E tests in `my-progress.spec.ts`**

`test_progress_page_when_loaded_then_topic_groups_expanded_by_default` — Navigate to
`/student/my-progress`. Mock the gap map API to return two topics each with two
subtopics. Assert that all four subtopic rows are visible without any user interaction.

`test_progress_page_when_topic_header_clicked_then_subtopics_collapse` — Click the
topic header of the first topic group. Assert the subtopic rows for that topic are
no longer visible. Click the header again. Assert they reappear.

`test_progress_page_when_subject_tab_changed_then_new_request_fired` — Click the
Science subject tab. Assert that a new API request is made for the Science subject ID.

`test_progress_page_when_loading_then_skeleton_rows_visible` — While the API response
is pending, assert skeleton row elements are visible and no actual subtopic names are
displayed yet.

`test_progress_page_when_score_0_65_then_amber_circle_and_65_percent` — Mock a
subtopic with `mastery_score=0.65`. Assert the circle for that subtopic has the amber
stroke color and shows "65%" inside it.

`test_progress_page_when_score_null_then_grey_circle_and_not_assessed_label` — Mock
a subtopic with `score=null`. Assert the circle has the grey color and displays "–"
inside it. Assert the row shows "Not yet assessed" as the date text.

`test_progress_page_when_no_study_plans_then_passive_suggestion_shown` — Mock
`GET /students/me/study-plans` to return `{ data: [], total: 0 }`. Assert the
suggested next steps section shows the passive message about teacher assignment.

`test_progress_page_when_active_study_plans_exist_then_go_to_plans_link_shown` —
Mock `GET /students/me/study-plans` to return one plan in `data`. Assert the
"Go to Study Plans →" link is visible.

**Jest unit tests**

`test_subtopic_row_when_score_null_shows_dash_not_zero` — Render `SubtopicProgressRow`
with `score=null`. Assert the text "–" is present and the text "0%" is not present.

`test_subtopic_row_when_score_0_35_shows_needs_work` — `score=0.35`. Assert the
`aria-label` on the mastery circle is "Needs Work".

`test_subtopic_row_when_score_0_4_exactly_shows_developing_not_needs_work` — `score=0.4`
is the boundary. Assert `aria-label` is "Developing", not "Needs Work".

`test_subtopic_row_when_score_0_7_exactly_shows_strong` — `score=0.7` is the boundary.
Assert `aria-label` is "Strong".

`test_subtopic_row_color_circles_have_aria_labels` — Render any `SubtopicProgressRow`
with a non-null score. Assert the SVG circle element has an `aria-label` attribute
that is not empty.

`test_topic_row_aggregate_when_scores_0_4_and_0_8_then_average_0_6` — Render
`TopicProgressRow` with two subtopics of scores 0.4 and 0.8. Assert the aggregate
pill shows "60%".

`test_topic_row_aggregate_when_all_null_then_shows_no_data` — Render with all
`score=null`. Assert the aggregate pill shows "No data" or an equivalent muted
indicator rather than "0%".

---

## Do NOT Touch

`frontend/apps/teacher/` — no code goes here. `frontend/apps/school-admin/` — no
code goes here. The `getMasteryStyle` utility in `packages/types` — use it as-is.
Any backend file.
