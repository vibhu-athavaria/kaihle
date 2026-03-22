# M6-1-T3 — Class Gap Map Admin UI (School Admin App)
**Milestone:** M6 · **Epic:** M6-1 · **Task:** T3
**Depends on:** M6-1-T1 (analytics service — gap map route returns real data), M2-1-T2 (gap map routes)
**Parallel with:** M6-1-T2 (analytics dashboard UI — different component, same page shell)
**Blocks:** Nothing — final UI task of M6-1 epic
**Estimated effort:** 2–3 hours

---

## Context

All code in this task lives in `frontend/apps/school-admin`. No code goes in any
other app. The teacher gap map (`M2-1-T3`) lives in `apps/teacher` — do not import
from it. Build a separate read-only version here.

Read `docs/design/DESIGN_SYSTEM.md` §5.2 (School Admin) before writing any component.
Green is the action color. Left green stripe is the sidebar active state.

The school admin gap map is a read-only oversight tool. It differs from the teacher
gap map in three critical ways:
1. No "Assign study plan" action — that is a teacher function only
2. No student side panel — cell click shows a lightweight tooltip, not a drawer
3. Available from two entry points: the Classes side panel and the Analytics page

---

## User Story

As a school admin, I want to view a colour-coded heatmap of any class's performance
so I can monitor which classes and subjects need attention without interfering in the
teacher's workflow.

---

## Files to Create

```
frontend/apps/school-admin/src/pages/analytics/
  ClassGapMapPage.tsx            ← standalone page (entry from Classes side panel)

frontend/apps/school-admin/src/components/analytics/
  ReadOnlyGapMap.tsx             ← heatmap grid with tooltip — reused in both locations
  ClassSelector.tsx              ← dropdown to switch between school's classes

frontend/apps/school-admin/src/hooks/
  useAdminGapMap.ts              ← React Query hook wrapping the gap map endpoint

frontend/apps/school-admin/src/tests/
  class-gap-map.spec.ts          ← Playwright E2E tests
```

---

## Routes

`/school-admin/classes/:classId/gap-map` — `ClassGapMapPage`.
Protected by `PrivateRoute` + `RoleRoute(['SCHOOL_ADMIN', 'KAIHLE_ADMIN'])`.

This page is also embedded as a tab on the Analytics page (`M6-1-T2`) — the
`ReadOnlyGapMap` component is shared between both locations via props. The
`ClassGapMapPage` is the standalone version reached from the Classes side panel.

---

## Complete List of API Calls This UI Makes

`GET /api/v1/classes/{classId}/gap-map?subject_id={subjectId}` — called via
`useAdminGapMap(classId, subjectId)`. Same endpoint as the teacher gap map. The
school admin role has access per `routes/gap_map.py` role checks — no new endpoint
needed.

`GET /api/v1/schools/{schoolId}/classes` — called once to populate the class
selector dropdown. Reuses `useSchoolClasses` hook from `useSchoolAdmin.ts`.

Those are the only two API calls.

---

## `ReadOnlyGapMap` Component

```typescript
interface ReadOnlyGapMapProps {
  classId: string
  subjectId: string
  onSubjectChange?: (subjectId: string) => void
  showClassSelector?: boolean   // false when embedded in Analytics tab
  onClassChange?: (classId: string) => void
}
```

### Grid structure (same as teacher heatmap)

- HTML `<table>` with sticky first column (subtopic name)
- Rows: curriculum subtopics, grouped by topic with `<tr colSpan>` section headers
- Columns: one per enrolled student (first name + last initial)
- Final column: "Class avg" — bold, colored, sticky right

### Cell rendering

Each cell: a `32px × 32px` colored square.

Color mapping (same thresholds as all roles):
- `score > 0.7` → `#dcfce7` (Strong)
- `0.4 ≤ score ≤ 0.7` → `#fef3c7` (Developing)
- `score < 0.4` → `#fee2e2` (Needs Work)
- `score = null` → `#f3f4f6` (Not assessed)

### Cell interaction — tooltip only (no side panel)

On hover: show a small tooltip above the cell:
```
Aisha Rahman
Algebraic fractions
32% — Needs Work
Last assessed 18 Mar 2026
```

Tooltip style: `bg-white border border-gray-200 rounded-lg shadow-md p-3 text-xs`.
Dismiss on mouse leave. No click action — no side panel, no navigation from cell click.

This is the key difference from the teacher gap map. The admin sees data, does not
take action from the cell.

### Subject tabs

One pill tab per subject the class is enrolled in. Default: first subject
alphabetically. Switching tab fires a new `useAdminGapMap` call with the new
`subject_id`.

### Legend

Below the grid, inline:
```
● Strong >70%   ● Developing 40–70%   ● Needs work <40%   ○ Not assessed
```

### Class average row

Pinned as final row (below all student rows). Cells show class average per subtopic.
Row label: "Class average" in bold green `text-brand-primary`.
Average cells colored by band — same color rules as individual cells.

### Class selector dropdown (`ClassSelector.tsx`)

Shown only when `showClassSelector=true` (standalone page, not embedded in Analytics).
Dropdown above the subject tabs: "Mathematics 9B ▼"
Selecting a different class navigates to `/school-admin/classes/{newClassId}/gap-map`
(standalone page) or fires `onClassChange` callback (Analytics embed).

---

## Standalone Page Layout (`ClassGapMapPage.tsx`)

```
← Back to Classes  |  Mathematics 9B — Gap Map
[Class selector ▼]  [Subject tabs: Mathematics | Science]

[ReadOnlyGapMap grid]

[Legend row]
```

Back navigation: "← Classes" → `/school-admin/classes`.

Breadcrumb: `School admin / Classes / Mathematics 9B / Gap Map`

---

## Acceptance Criteria

**Playwright E2E tests in `class-gap-map.spec.ts`**

`test_gap_map_when_loaded_then_grid_renders` — Navigate to
`/school-admin/classes/{classId}/gap-map`. Assert the heatmap table is visible with
at least one subtopic row.

`test_gap_map_when_score_below_0_4_then_red_cell` — Mock a subtopic with
`mastery_score=0.3` for a student. Assert that cell has the red background color.

`test_gap_map_when_score_null_then_gray_cell` — Mock a null score. Assert gray cell.

`test_gap_map_when_cell_hovered_then_tooltip_shown` — Hover over a cell. Assert a
tooltip element is visible containing the student's name and a mastery percentage.

`test_gap_map_when_cell_clicked_then_no_side_panel` — Click a cell. Assert no
side panel drawer is added to the DOM. Assert URL does not change.

`test_gap_map_when_subject_tab_changed_then_new_request_fired` — Click a different
subject tab. Assert a new API call is made with the new subject ID.

`test_gap_map_when_class_changed_then_url_updates` — Select a different class from
the class selector. Assert URL changes to the new class ID.

`test_gap_map_class_avg_row_pinned_at_bottom` — Assert the "Class average" row is
the last row in the table body.

**Jest unit tests**

`test_read_only_gap_map_when_score_0_7_exactly_then_strong_cell` — Score boundary:
assert green cell (Strong side of boundary).

`test_read_only_gap_map_when_score_0_4_exactly_then_developing_cell` — Score
boundary: assert amber cell (Developing side of boundary).

`test_read_only_gap_map_when_no_assign_button_rendered` — Render the component.
Assert no element with text "Assign" or "Study plan" is present anywhere in the DOM.

---

## Do NOT Touch

`frontend/apps/teacher/` — the teacher gap map component is separate.
`frontend/apps/student/` — no code goes here.
Any backend file — the endpoint already exists and supports SCHOOL_ADMIN role.
