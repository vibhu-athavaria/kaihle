# M2-2-T1 — My Students List UI (Teacher App)
**Milestone:** M2 · **Epic:** M2-2 · **Task:** T1
**Depends on:** M2-1-T2 (gap map routes return real data), M0-7-T1 (layout wrappers), M0-8-T4 (shared components)
**Blocks:** M2-2-T2 (student profile page — list links to it)
**Estimated effort:** 3–4 hours

---

## Context

All code in this task lives in `frontend/apps/teacher`. No code goes in any other app.

Read `docs/design/DESIGN_SYSTEM.md` §5.3 (Teacher) before writing any component.
Gold is the action color. Green is mastery data only.

This page is the class roster — a teacher's view of every student in a selected class.
It is the entry point to the Student Profile page (`M2-2-T2`). It also surfaces at
a glance each student's overall mastery, learning style, and whether they have any
active study plans, so a teacher can prioritise who needs attention.

The sidebar link "My Students" routes here with the last active `classId` pre-selected.

---

## User Story

As a teacher, I want to see my full class roster with each student's mastery overview
and learning style so I can quickly identify who needs attention and navigate to a
student's full profile.

---

## Files to Create

```
frontend/apps/teacher/src/pages/students/
  MyStudentsPage.tsx             ← page shell with class selector and student table

frontend/apps/teacher/src/components/students/
  StudentRosterTable.tsx         ← sortable table of students
  LearningStyleTag.tsx           ← modality icon + label pill

frontend/apps/teacher/src/hooks/
  useClassStudents.ts            ← React Query hooks for student list

frontend/apps/teacher/src/tests/
  my-students.spec.ts            ← Playwright E2E tests
```

---

## Route

`/teacher/classes/:classId/students` — `MyStudentsPage`.
Protected by `PrivateRoute` + `RoleRoute(['TEACHER'])`.

`classId` is read from the URL param. If the teacher navigates via the sidebar,
the last active classId is used.

---

## Complete List of API Calls This UI Makes

`GET /api/v1/schools/{schoolId}/classes?teacher_id=me` — called on mount to populate
the class selector dropdown. Reuses the same hook as the dashboard.

`GET /api/v1/classes/{classId}/gap-map?subject_id={subjectId}` — called to derive
per-student mastery aggregates. Use the first enrolled subject by default.
Reuses `useClassGapMap` from M0-10-T9.

`GET /api/v1/onboarding/learning-profile?student_id={id}` — called per student
to get modality data. Batch these in parallel using `Promise.all` — do not make
sequential requests. Cache with React Query so switching subjects does not re-fetch.

Those are the only API calls. Do not call study plan or assessment endpoints here —
the table shows only mastery and learning style data.

---

## Page Layout

```
┌──────────────────────────────────────────────────────────────────┐
│  ← Classes  |  Mathematics 9B — My students         [classId ▼] │
│  28 students                                                     │
├──────────────────────────────────────────────────────────────────┤
│  Subject tabs: [Mathematics] [Science] [English]                 │
├──────────────────────────────────────────────────────────────────┤
│  Search: [____________]          Sort: [Name ▼]                  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │  Student    │ Mastery │ Band       │ Learning style │ →  │    │
│  │  Aisha R.   │   57%   │ Developing │ ✋ Kinesthetic  │ →  │    │
│  │  Ben K.     │   74%   │ Strong     │ 👁 Visual      │ →  │    │
│  │  Citra D.   │   89%   │ Strong     │ 📖 Reading     │ →  │    │
│  │  Dani P.    │   32%   │ Needs work │ ✋ Kinesthetic  │ →  │    │
│  └──────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────┘
```

### Class selector dropdown

Teacher may teach multiple classes. Show the current class name in the topbar with a
dropdown chevron. Selecting a different class navigates to
`/teacher/classes/{newClassId}/students`.

### Subject tabs

One tab per subject the class is enrolled in. Switching subject tab changes which
gap map data is used for the Mastery column. Default: first subject alphabetically
unless there is recent activity in another.

---

## Student Roster Table (`StudentRosterTable.tsx`)

### Columns

| Column | Width | Content | Sortable |
|---|---|---|---|
| Student | 28% | Full name (Fraunces, font-semibold) + grade badge | Yes (alpha) |
| Mastery | 12% | Percentage, colored by `getMasteryStyle` | Yes (numeric) |
| Band | 14% | Band label pill badge (Strong/Developing/Needs work/Not assessed) | Yes |
| Learning style | 20% | `LearningStyleTag` — modality icon + label | No |
| Last active | 14% | ISO date formatted "18 Mar 2026", or "—" | Yes |
| → | 12% | "View profile →" link → `/teacher/students/{studentId}` | No |

Default sort: Mastery ascending (lowest first — teacher attention to struggling students).

Students with `mastery=null` (no assessments yet): show "—" and band "Not assessed".
Sort these to the bottom regardless of sort direction.

### `LearningStyleTag.tsx`

```typescript
interface LearningStyleTagProps {
  dominantModality: 'visual' | 'auditory' | 'reading_writing' | 'kinesthetic' | null
}
```

Render as pill: `bg-gray-100 text-gray-700 rounded-full px-2 py-1 text-xs`.

Modality → icon + label:
- `visual` → 👁 Visual
- `auditory` → 👂 Auditory
- `reading_writing` → 📖 Reading
- `kinesthetic` → ✋ Hands-on
- `null` → "—" (profile not yet complete)

Dominant modality = `argmax(modality_scores)`. If profile not yet completed
(`completed_at = null`), show "—".

### Loading state

Show skeleton rows (same column widths, animated pulse) while data is loading.
Never show a full-page spinner — skeleton rows give the teacher a sense of layout.

### Empty state

If class has no enrolled students: "No students enrolled in this class yet. Students
are enrolled by the school admin."

---

## Acceptance Criteria

**Playwright E2E tests in `my-students.spec.ts`**

`test_students_page_when_loaded_then_roster_table_visible` — Navigate to
`/teacher/classes/{classId}/students`. Assert a table with at least one student row
is visible.

`test_students_page_when_sort_by_mastery_then_lowest_first` — Assert default sort
places lowest-mastery student at top row.

`test_students_page_when_search_by_name_then_table_filters` — Type a student name
in the search input. Assert only matching rows remain visible.

`test_students_page_when_subject_tab_changed_then_mastery_updates` — Click the
Science tab. Assert the Mastery column values change (different subject gap map data).

`test_students_page_when_view_profile_clicked_then_navigates` — Click "View profile →"
for a student. Assert the URL changes to `/teacher/students/{studentId}`.

`test_students_page_when_no_profile_then_learning_style_shows_dash` — Mock a student
with no completed learning profile (`completed_at=null`). Assert "—" appears in the
Learning style column for that row.

`test_students_page_when_null_mastery_then_sorted_to_bottom` — Mock one student with
null mastery and one with 0.3. With mastery ascending sort, assert the null student
appears below the 0.3 student.

**Jest unit tests**

`test_learning_style_tag_when_kinesthetic_then_shows_hands_on` — Render
`LearningStyleTag` with `dominantModality="kinesthetic"`. Assert "Hands-on" text
is present.

`test_learning_style_tag_when_null_then_shows_dash` — `dominantModality=null`.
Assert "—" is rendered.

---

## Do NOT Touch

`frontend/apps/student/` — no code goes here.
`frontend/apps/school-admin/` — no code goes here.
Any backend file.
