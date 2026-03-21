# M2 Brief — Gap Map & Teacher Dashboard
**Milestone:** 2 of 6
**Estimated duration:** 2–3 weeks
**Previous milestone:** M1 — Core Diagnostics Flow
**Constitution version:** 2.0

> Load this brief alongside CONSTITUTION.md when working on any M2 task.
> Load the specific task file for the task you are implementing.

---

## Goal

Teachers see a real-time colour-coded heatmap of class performance by curriculum
subtopic, with each student's learning style visible alongside their gaps. Students
see their own progress profile. The class summary card on the teacher dashboard
shows real mastery data for the first time.

---

## Exit Criteria

- Teacher views class gap map for a completed assessment and identifies which subtopics need work
- Clicking a student cell shows their full gap profile and learning style summary (modality + interests)
- Student views their own progress profile with traffic-light colour coding per subtopic
- Teacher dashboard class cards show real `avg_mastery` values (not null)

---

## What This Milestone Delivers

**Gap map aggregation service**

A `GapMapService` in `services/gap_map_service.py` that aggregates `gap_states` rows
into the structured response shapes defined in `schemas/gap_map.py`. Two aggregation
methods are needed: class-level (all students × all subtopics for a subject) and
student-level (one student × all subtopics for a subject). The class-level method
also reads `student_learning_profiles` to include each student's dominant modality
and top interests alongside their gap scores.

**Gap map and class summary API — stub replacement**

M0-10-T2 created `routes/gap_map.py` with four stubs: `GET /classes/{id}/gap-map`,
`GET /classes/{id}/summary`, `GET /students/me/gap-map`, and
`GET /students/{id}/gap-map`. This milestone replaces all four stub function bodies
with real service calls. The frozen contracts from M0-10 must not be changed.

**Teacher heatmap UI**

Built in `apps/teacher`. A grid visualization showing rows as curriculum subtopics
and columns as students, with cells coloured by mastery level using `getMasteryStyle()`
from `packages/types`. Clicking a cell opens a side panel showing the selected
student's full gap profile and their learning style summary (dominant modality icon
and top interests from their `StudentLearningProfile`). The class average row is
pinned at the bottom.

**Student gap profile UI**

Built in `apps/student`. A subject-tabbed view showing the student's own subtopic
mastery scores as a list with colour-coded traffic-light indicators. Each topic row
is expandable to show its subtopics. A "Suggested next steps" placeholder section is
shown (wired to study plans in M3).

---

## Tasks in This Milestone

| Task ID | File | Description |
|---|---|---|
| M2-1-T1 | `M2/M2-1-T1_gap_map_service.md` | Gap map aggregation service |
| M2-1-T2 | `M2/M2-1-T2_gap_map_routes.md` | Replace gap map stubs with real logic |
| M2-1-T3 | `M2/M2-1-T3_gap_map_heatmap_ui.md` | Teacher heatmap UI (apps/teacher) |
| M2-1-T4 | `M2/M2-1-T4_student_gap_profile_ui.md` | Student progress profile UI (apps/student) |

---

## Task Execution Order

```
M2-1-T1 (service) ← start here — defines the aggregation logic
  → M2-1-T2 (routes) ← replace stubs, calls service
    → M2-1-T3 (teacher UI) ← apps/teacher, needs routes returning real data
    → M2-1-T4 (student UI) ← apps/student, needs routes returning real data
```

M2-1-T3 and M2-1-T4 can be built in parallel once M2-1-T2 is live.

---

## Critical: Stub Replacement Protocol

M2-1-T2 replaces stubs in `backend/app/api/v1/routes/gap_map.py` (created by M0-10-T2).
The implementing agent must: open the existing file, find every function body marked
`# STUB — M0-10-T2`, replace only the function body, and verify that the frozen
path, auth, request parameters, and response schema are unchanged.

The `ClassSummary` endpoint (`GET /classes/{id}/summary`) is specifically important
for the teacher dashboard class cards, which have been showing `avg_mastery: null`
since M0. Once M2-1-T2 is live, those cards will display real mastery percentages.

---

## Frontend App Targets

All teacher-facing UI in this milestone builds in `apps/teacher`. All student-facing
UI builds in `apps/student`. Neither app builds in the other's directory.

The teacher heatmap route is `/teacher/classes/:classId/gap-map`. The student
progress route is `/student/my-progress`. The `useClassGapMap` and `useClassSummary`
hooks created in M0-10-T9 are the data layer — M2-1-T3 and M2-1-T4 build the
presentation components that consume those hooks.

---

## Learning Profile Side Panel (M2-1-T3 — Critical Detail)

When a teacher clicks a student cell in the heatmap, the side panel must show not
just gap data but also the student's learning style summary. This requires a second
API call inside the side panel: `GET /onboarding/learning-profile?student_id={id}`.
This endpoint already exists from M0-6-T1 and returns the full `StudentLearningProfile`.
The side panel uses `modality_scores` to determine the dominant modality (highest
of the four scores) and displays a corresponding icon (Video icon for visual, Book
for reading/writing, etc.), plus the top two entries from `interests` as tags.

This is a read-only display — teachers cannot edit a student's learning profile from
the gap map.

---

## Definition of Done

- Teacher sees colour-coded gap map for their class with real mastery data
- Student sees their personal gap profile with correct traffic-light colours
- Teacher gap map side panel shows student learning profile (modality icon + interests)
- Teacher dashboard class cards show real `avg_mastery` (no longer null)
- Gap map reflects latest assessment results — re-fetching after a new submission
  shows updated colours within the React Query stale time window
- All M2 tests pass

---

## Key Tables Used in This Milestone

`gap_states`, `subtopics`, `curriculum_topics`, `topics`, `subjects`,
`student_learning_profiles`, `class_enrollments`, `users`

Full schema: `kaihle_v2_1_schema.sql`

---

## What M1 Delivered (Available to Use)

`gap_states` is populated with real mastery scores. `subtopics.embedding` is
populated in pgvector. Assessment taking UI works end to end. MCQ answers are
scored deterministically on submit. `calculate_gap_states` Celery task is operational.

---

## What M3 Expects From M2

Gap map routes return real data — `/classes/{id}/gap-map` returns populated `nodes[]`
with `class_average` and per-student scores. `/students/{id}/gap-map` returns
populated `scores[]`. The teacher assignment UI in M3 triggers from clicking a red
cell in the M2 heatmap, so the heatmap component structure must support an
"Assign Study Plan" action on cells.
