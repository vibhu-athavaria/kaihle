# M3 Brief — Smart Study Plans
**Milestone:** 3 of 6
**Estimated duration:** 3–4 weeks
**Previous milestone:** M2 — Gap Map & Teacher Dashboard

> Load this brief alongside CONSTITUTION.md when working on any M3 task.
> Load the specific task file for the task you are implementing.

---

## Goal

The system automatically generates personalised study plans for identified gaps. Resources are matched to the student's learning modality. Quiz question scenarios are contextualised using the student's personal interests.

## Exit Criteria

- Teacher assigns a study plan from the gap map → student sees curated resources matched to their learning style → student takes a quiz with personally relevant examples → gap state updates

---

## What This Milestone Delivers

- Content curation engine with learning profile weighting (YouTube, Khan Academy, static index)
- Quiz generation service with interest injection
- Study plan service (orchestrates curation + quiz)
- Study plan API routes (assign, fetch, submit quiz)
- Student study plan UI (resource list + quiz)
- Teacher study plan assignment UI (from gap map)

---

## Tasks in This Milestone

| Task ID | File | Description |
|---|---|---|
| M3-1-T1 | `M3/M3-1-T1_content_curator.md` | Resource curation with learning profile weighting |
| M3-1-T2 | `M3/M3-1-T2_quiz_generator.md` | Quiz generation with interest injection |
| M3-2-T1 | `M3/M3-2-T1_study_plan_service.md` | Study plan orchestration service |
| M3-2-T2 | `M3/M3-2-T2_study_plan_routes.md` | Study plan API endpoints |
| M3-2-T3 | `M3/M3-2-T3_student_study_plan_ui.md` | Student study plan UI |
| M3-2-T4 | `M3/M3-2-T4_teacher_assignment_ui.md` | Teacher study plan assignment UI |

---

## Task Execution Order

```
M3-1-T1 (content curator)  ← parallel start
M3-1-T2 (quiz generator)   ← parallel start
  → M3-2-T1 (study plan service) ← needs both curator + quiz generator
    → M3-2-T2 (study plan routes) ← needs service
      → M3-2-T3 (student UI) ← needs routes
      → M3-2-T4 (teacher UI) ← needs routes
```

---

## Definition of Done

- [ ] Teacher can assign study plans from gap map
- [ ] Resources are personalised based on student's learning modality
- [ ] Quiz scenarios use student's personal interests where applicable
- [ ] Student can view resources, take quiz, see score
- [ ] Quiz submission updates gap state for the subtopic
- [ ] All M3 tests pass

---

## Key Tables Used in This Milestone

`study_plans`, `study_plan_resources`, `study_plan_quizzes`, `gap_states`, `subtopics`, `curriculum_chunks`, `student_learning_profiles`, `question_bank`

Full schema: `kaihle_v2_1_schema.sql`

---

## Learning Profile Integration (CRITICAL for M3-1-T1 and M3-1-T2)

### Content Curator (M3-1-T1)
Function signature: `curate_resources(subtopic, student_id, school_id) → list[Resource]`

Modality weighting logic:
- Load `student_learning_profiles` for `student_id`
- Compute weighted score = base_alignment_score × modality_multiplier
- Multipliers (cumulative if student is high on multiple):
  - `modality_scores.visual > 0.6` → VIDEO resources × 1.3
  - `modality_scores.reading_writing > 0.6` → ARTICLE resources × 1.3
  - `modality_scores.kinesthetic > 0.6` → INTERACTIVE resources × 1.3
  - `modality_scores.auditory > 0.6` → VIDEO resources × 1.2
- No profile → use base alignment score only (do not error)
- Redis cache key: `content:{subtopic_id}:{student_id}`, TTL 24 hours

### Quiz Generator (M3-1-T2)
Function signature: `generate_quiz(subtopic, student_mastery, student_id) → Quiz`

Interest injection:
- Load `student_learning_profiles.interests` for `student_id`
- If non-empty: inject top 2 into prompt — see prompt template in `kaihle_product_plan_v2_1.md` Part 4
- If empty or no profile: omit personalisation section from prompt entirely
- Academic accuracy is ALWAYS priority over personalisation — the prompt must state this

---

## Resource Types

| Type | When Used |
|---|---|
| `VIDEO` | YouTube (3–15 min, English, education category) |
| `ARTICLE` | Khan Academy text, OpenStax chapters |
| `INTERACTIVE` | Khan Academy exercises, interactive tools |

Alignment threshold: cosine similarity vs `subtopic.embedding` must be > 0.72 to be included.

---

## What M2 Delivered (Available to Use)

- `/api/v1/classes/{class_id}/gap-map` endpoint operational
- `/api/v1/students/{student_id}/gap-map` endpoint operational
- `student_learning_profiles` readable via `/api/v1/onboarding/learning-profile`
- `gap_states` populated with real data
- `subtopics.embedding` populated in pgvector (needed for cosine similarity in curation)

## What M4 Expects From M3

- Study plans can be assigned by a teacher for a given `subtopic_id`
- `gap_states` update correctly after quiz submission (M4 lesson planner reads gap map to generate lesson context)
- Study plan routes operational (M4 lesson plan may reference assigned study plans)
