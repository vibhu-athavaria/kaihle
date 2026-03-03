# M2 Brief — Gap Map & Teacher Dashboard
**Milestone:** 2 of 6
**Estimated duration:** 2–3 weeks
**Previous milestone:** M1 — Core Diagnostics Flow

> Load this brief alongside CONSTITUTION.md when working on any M2 task.
> Load the specific task file for the task you are implementing.

---

## Goal

Teachers see a real-time colour-coded heatmap of class performance by curriculum subtopic. Students see their own gap profile. The teacher's gap map also shows each student's learning style to inform differentiated teaching.

## Exit Criteria

- Teacher views class gap map for a completed assessment and can identify which subtopics to address
- Clicking a student cell shows their full gap profile and learning style summary
- Student views their own progress profile with traffic-light colour coding

---

## What This Milestone Delivers

- Gap map aggregation service (class-level and student-level)
- Gap map API endpoints
- Teacher gap map heatmap UI with learning profile side panel
- Student gap profile UI with expandable topics

---

## Tasks in This Milestone

| Task ID | File | Description |
|---|---|---|
| M2-1-T1 | `M2/M2-1-T1_gap_map_service.md` | Gap map aggregation service (class + student) |
| M2-1-T2 | `M2/M2-1-T2_gap_map_routes.md` | Gap map API endpoints |
| M2-1-T3 | `M2/M2-1-T3_gap_map_heatmap_ui.md` | Teacher heatmap UI with learning profile panel |
| M2-1-T4 | `M2/M2-1-T4_student_gap_profile_ui.md` | Student progress profile UI |

---

## Task Execution Order

```
M2-1-T1 (service)
  → M2-1-T2 (routes) ← needs service
    → M2-1-T3 (teacher UI) ← needs routes
    → M2-1-T4 (student UI) ← needs routes (different endpoint)
```

M2-1-T3 and M2-1-T4 can be built in parallel once routes exist.

---

## Definition of Done

- [ ] Teacher sees colour-coded gap map for their class
- [ ] Student sees their personal gap profile
- [ ] Teacher gap map side panel shows student learning style (dominant modality icon + interests)
- [ ] Gap map reflects latest assessment results in real-time
- [ ] All M2 tests pass

---

## Key Tables Used in This Milestone

`gap_states`, `subtopics`, `curriculum_topics`, `topics`, `users`, `student_profiles`, `student_learning_profiles`, `classes`, `class_enrollments`

Full schema: `kaihle_v2_1_schema.sql`

---

## Mastery Colour Bands (Use Exactly These)

| Score | Label | Colour Hex |
|---|---|---|
| < 0.4 | Needs Work | `#EF4444` (red) |
| 0.4 – 0.7 | Developing | `#F59E0B` (amber) |
| > 0.7 | Strong | `#10B981` (green) |
| No data | — | `#9CA3AF` (grey) |

---

## Learning Profile Display in Gap Map (NEW v2.1)

When a teacher clicks a cell in the heatmap, the side panel must include:
- **Dominant modality icon:** compute `argmax(modality_scores)` — show matching icon (eye=visual, ear=auditory, book=reading_writing, hand=kinesthetic)
- **Top interests:** show up to 3 interest tags from `student_learning_profiles.interests`
- This is **read-only** — teacher cannot edit the student's profile from here

If student has no learning profile yet (edge case: they skipped onboarding somehow), show "Learning profile not yet completed" message — do not crash.

---

## What M1 Delivered (Available to Use)

- `gap_states` table populated with real mastery scores
- `student_learning_profiles` rows exist for students who completed onboarding
- `subtopics.embedding` populated in pgvector
- Auth + school_id filtering middleware fully operational

## What M3 Expects From M2

- `gap_states` API working so M3 teacher UI can read mastery scores when assigning study plans
- `/api/v1/students/{student_id}/gap-map` endpoint exists (M3 teacher UI links from gap map to "Assign Study Plan")
- `student_learning_profiles` readable via API (M3 content curator will also use this data)
