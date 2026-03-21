# M2-1-T3 — Teacher Gap Map Heatmap UI
**Milestone:** M2 · **Epic:** M2-1 · **Task:** T3
**Depends on:** M2-1-T2 (gap map routes return real data)
**Parallel with:** M2-1-T4 (student UI — independent, different app)
**Blocks:** M3-2-T4 (study plan assignment UI extends this component)
**Estimated effort:** 5–6 hours

---

## Context

All code in this task lives in `frontend/apps/teacher`. No code goes in any other app.

Read `docs/design/DESIGN_SYSTEM.md` §5.3 (Teacher) before writing any component. The
teacher app uses a gold action color (`brand-gold #c9932a`) for interactive elements.
Green in the teacher app is reserved exclusively for mastery indicators — never use
green for buttons, tab highlights, or navigation in this app.

The `useClassGapMap` and `useClassSummary` hooks already exist from M0-10-T9 and now
return real data after M2-1-T2 completes. These are the data layer — this task builds
the presentation layer on top of them.

---

## User Story

As a teacher, I want a colour-coded heatmap showing every student's mastery per
curriculum subtopic so I can instantly see who needs help with what and act on it
from the same screen.

---

## Files to Create

```
frontend/apps/teacher/src/pages/gap-map/
  GapMapPage.tsx             ← page shell: subject tabs, grid, export
  GapMapGrid.tsx             ← pure presentational grid component
  StudentSidePanel.tsx       ← drawer showing student detail + learning style
  GapMapCell.tsx             ← individual cell with tooltip

frontend/apps/teacher/src/tests/
  gap-map.spec.ts            ← Playwright E2E tests

frontend/apps/teacher/src/utils/
  gapMapExport.ts            ← CSV export logic
```

---

## Route

`/teacher/classes/:classId/gap-map` — `GapMapPage`. Protected by `PrivateRoute` +
`RoleRoute(['TEACHER'])`. The `classId` param is read from the URL, not from global
state.

---

## Complete List of API Calls This UI Makes

The following is the complete and exhaustive list of API calls these components make.
Do not call any other endpoint.

`GET /api/v1/classes/{classId}/gap-map?subject_id={subjectId}` — called by the
`useClassGapMap(classId, subjectId)` hook on page load and whenever the subject tab
changes. This is the primary data source for the heatmap grid.

`GET /api/v1/onboarding/learning-profile?student_id={studentId}` — called by
`StudentSidePanel` when a cell is clicked, using a React Query query keyed by
`['teacher', 'learning-profile', studentId]`. This populates the learning style
section of the side panel. This call is deferred until a cell is actually clicked —
do not prefetch it.

That is all. The class summary (`GET /classes/{classId}/summary`) is called by the
dashboard card (a separate component, already built in M0), not by this page.
There is no API call to list students separately — the gap map response already
contains all student data.

---

## Page Layout (`GapMapPage.tsx`)

```
┌──────────────────────────────────────────────────────────────────────┐
│  [← Classes]  Grade 9 Mathematics — Gap Map        [Export CSV ↓]   │
│                                                                      │
│  Subject: [Mathematics ▼]  [Science]  [English]  ← tabs             │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │                      GapMapGrid                                │  │
│  │  Subtopic              Aisha   Ben   Citra  (...)  Class Avg   │  │
│  │  ─ Algebra ─────────────────────────────────────────────────   │  │
│  │    Algebraic Fractions  [🔴]   [🟡]  [🟢]          54%        │  │
│  │    Quadratic Equations  [🟡]   [🟢]  [🟢]          71%        │  │
│  │  ─ Geometry ────────────────────────────────────────────────   │  │
│  │    Pythagoras Theorem   [⬜]   [🔴]  [🟡]          45%        │  │
│  └────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

While gap map data is loading, show a skeleton grid of the same dimensions — do not
show a spinner in the centre of the page. A skeleton that mirrors the grid layout
gives the teacher a sense of what is coming.

If the gap map returns `nodes` with all `student_scores` empty (no assessments
taken yet), show an empty state inside the grid area: "No assessment data yet for
this class. Students will appear here after completing their first diagnostic."

---

## GapMapGrid Component (`GapMapGrid.tsx`)

This component is a pure presentational component — it receives data as props and
emits events. It has no data fetching of its own.

Props interface:

```typescript
interface GapMapGridProps {
  nodes: GapMapNode[]           // sorted by topic then subtopic — use as-is from API
  students: StudentInfo[]       // unique students extracted from nodes, preserving order
  onCellClick: (studentId: string, subtopicId: string) => void
}
```

Extract the unique student list from the nodes on the parent (`GapMapPage`) before
passing it to the grid. The column order matches the order students first appear in
`nodes[0].student_scores`. Use this consistently across all rows.

The grid is rendered as an HTML `<table>` for accessibility and for the correct
column-alignment behaviour when scrolling horizontally. The subtopic column is
sticky (`position: sticky; left: 0`) so it stays visible when scrolling right on
a class with many students.

Topic group headers span the full width of the table as a distinct row — they are
not a separate table. Use `<tr className="bg-gray-50"><td colSpan={...}>` with the
topic name in uppercase with letter-spacing.

---

## GapMapCell Component (`GapMapCell.tsx`)

```typescript
interface GapMapCellProps {
  score: number | null   // null = not yet assessed
  studentName: string
  subtopicName: string
  lastAssessedAt: string | null
  onClick: () => void
}
```

Use `getMasteryStyle(score)` from `@kaihle/types` to derive the cell's background
class. Do not hardcode color strings — the function returns the correct Tailwind class
and the plain-text label.

Cells are `w-10 h-10` squares. No text inside the cell — color only. The cell must
have an `aria-label` combining the student name, subtopic name, and label (e.g.
"Aisha Rahman — Algebraic Fractions: Developing") so screen readers can navigate the
grid. The tooltip content appears on hover:

```
Aisha Rahman
Algebraic Fractions
Mastery: 65%   Developing
Last assessed: 2 Mar 2026
```

For `score=null`, the tooltip shows "Not yet assessed" instead of a percentage.

---

## Student Side Panel (`StudentSidePanel.tsx`)

The side panel is a right-side drawer that slides in when a cell is clicked. It is
380px wide and slides over the grid without pushing it. It can be dismissed by
clicking ✕, pressing Escape, or clicking the overlay.

The panel shows three sections:

**Header section:** Student name, grade name, and a close button.

**Gap section:** The specific subtopic that was clicked, its mastery percentage, its
plain-text label (Developing/Needs Work/Strong), and the last assessed date. If no
data exists, show "Not yet assessed."

**Learning style section:** This section loads asynchronously after the panel opens
using `GET /api/v1/onboarding/learning-profile?student_id={studentId}`. While loading,
show a small skeleton of two rows. On success, display:

The dominant modality is computed as `argmax(modality_scores)` — find the key with
the highest value. Show the corresponding icon and label:
- `visual` → 👁 Visual learner
- `auditory` → 👂 Auditory learner
- `reading_writing` → 📖 Reading/Writing learner
- `kinesthetic` → 🤲 Hands-on learner

Below the modality, show up to three interest tags from the `interests` array,
rendered as small pill badges with `bg-gray-100 text-gray-700 rounded-full px-2 py-0.5
text-xs`.

If the API returns a 404 or the profile is null, show a single muted line:
"Learning profile not yet completed." Do not crash, do not show a skeleton forever.

**Action button:** "Assign Study Plan" at the bottom of the panel. In M2, this button
logs a click to the console and shows a toast: "Study plan assignment coming in the
next update." Do not wire it to any API call in this task. M3-2-T4 replaces this
stub with the real modal. The button renders with `opacity-60 cursor-not-allowed` to
communicate it is not yet active.

---

## Export CSV (`gapMapExport.ts`)

```typescript
export function exportGapMapCsv(
  nodes: GapMapNode[],
  className: string,
  subjectName: string,
): void {
  // Build CSV with columns: Student, Topic, Subtopic, Mastery %, Last Assessed
  // Use encodeURIComponent to handle special characters in student or topic names
  // Trigger download by creating a temporary anchor element
}
```

The CSV filename format is `gap-map-{className}-{subjectName}-{YYYY-MM-DD}.csv`.
Replace spaces with hyphens in the filename.

---

## Acceptance Criteria

**Playwright E2E tests in `gap-map.spec.ts`**

Each test description below specifies the setup, the action, and the assertion.

`test_gap_map_page_when_loaded_then_cells_render_with_correct_colours` — Navigate to
`/teacher/classes/{classId}/gap-map`. Mock the gap map API to return one subtopic
with three students: scores 0.35, 0.55, 0.85. Assert the page contains cells with
the red background class, amber background class, and green background class
respectively.

`test_gap_map_page_when_loading_then_skeleton_shown_not_spinner` — While the API
response is pending, assert a skeleton element is visible. Assert no `role="progressbar"`
spinner is present.

`test_gap_map_page_when_no_assessment_data_then_empty_state_shown` — Mock the API to
return an empty `nodes` array. Assert the empty state message is visible.

`test_gap_map_cell_when_hovered_then_tooltip_shows_student_and_score` — Hover over
the cell for student "Aisha Rahman" with mastery 0.65. Assert a tooltip element is
visible containing "Aisha Rahman", "65%", and "Developing".

`test_gap_map_cell_when_unassessed_then_tooltip_shows_not_yet_assessed` — Hover over
a cell where `score=null`. Assert tooltip contains "Not yet assessed".

`test_side_panel_when_cell_clicked_then_opens_with_correct_student` — Click the cell
for student "Aisha Rahman." Assert a panel element becomes visible containing "Aisha
Rahman."

`test_side_panel_when_learning_profile_loaded_then_shows_modality_icon` — Mock the
learning profile API to return `modality_scores: { visual: 0.8, auditory: 0.2, ... }`.
Click a cell. Assert the panel shows "👁 Visual learner."

`test_side_panel_when_learning_profile_missing_then_shows_fallback_message` — Mock
the profile API to return 404. Click a cell. Assert the panel shows "Learning profile
not yet completed" and does not throw an error.

`test_side_panel_when_escape_pressed_then_closes` — Open the side panel. Press Escape.
Assert the panel is no longer visible.

`test_assign_study_plan_button_when_clicked_then_shows_coming_soon_toast` — Open the
side panel. Click "Assign Study Plan." Assert a toast message appears mentioning the
next update. Assert no API call to `/study-plans` is made.

`test_export_csv_when_button_clicked_then_download_triggered` — Click "Export CSV."
Assert a download is initiated (detect via `window.URL.createObjectURL` being called
in the test mock or by asserting the temporary anchor element exists with a `download`
attribute).

`test_subject_tab_when_changed_then_new_gap_map_request_fires` — Load the page on
Mathematics. Click the Science tab. Assert a new API request is made for Science's
`subject_id`.

**Jest unit tests**

`test_gap_map_cell_when_score_0_35_then_red_class_applied` — Render `GapMapCell` with
`score=0.35`. Assert it has the red background Tailwind class from `getMasteryStyle`.

`test_gap_map_cell_when_score_0_7_boundary_then_strong_class_applied` — `score=0.7`
is the boundary — it is Strong (green), not Developing. Assert green class applied.

`test_gap_map_cell_when_score_null_then_muted_class_applied` — `score=null`. Assert
the muted/grey class is applied.

`test_export_csv_produces_correct_column_headers` — Call `exportGapMapCsv` with one
node, one student. Assert the returned CSV string starts with
"Student,Topic,Subtopic,Mastery %,Last Assessed".

`test_side_panel_argmax_when_visual_highest_then_visual_icon_rendered` — Render
`StudentSidePanel` with a mocked profile where `visual=0.9` is the highest score.
Assert the visual learner icon text is present.

---

## Do NOT Touch

`frontend/apps/student/` — no code goes here. `frontend/apps/school-admin/` — no
code goes here. Any backend file. The `getMasteryStyle` function in `packages/types`
— use it as-is; do not copy its logic into this component.
