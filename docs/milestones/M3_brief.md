# M3 Brief — Smart Study Plans
**Milestone:** 3 of 6
**Estimated duration:** 3–4 weeks
**Previous milestone:** M2 — Gap Map & Teacher Dashboard
**Constitution version:** 2.0

> Load this brief alongside CONSTITUTION.md when working on any M3 task.
> Load the specific task file for the task you are implementing.

---

## Goal

The system generates personalised study plans for identified knowledge gaps. Resources
are matched to each student's learning modality from their profile. Quiz question
scenarios are contextualised using the student's personal interests. A teacher assigns
a study plan from the gap map with one action, and the student sees curated content
within seconds.

---

## Exit Criteria

- Teacher assigns a study plan from a red or amber gap map cell → student sees curated resources matched to their learning style → student takes a quiz with personally relevant examples → gap state updates after quiz submission

---

## What This Milestone Delivers

**Content curation engine**

A `ContentCurator` service that retrieves the best 2–3 resources for a given subtopic
and student. It uses pgvector cosine similarity against `subtopic.embedding` to find
aligned curriculum chunks, weights results by the student's `modality_scores` from
their learning profile (visual learners get more videos, reading/writing learners get
more articles), and returns a ranked list. Resources are sourced from YouTube (via
YouTube Data API), Khan Academy, and the internal `curriculum_chunks` table.

**Quiz generation service**

A `QuizGenerator` service that builds a 5-question MCQ quiz for a subtopic. It uses
the student's `interests` array from their learning profile to inject personalised
context into the quiz question prompts — a student interested in football gets physics
problems framed around ball trajectory rather than abstract equations. Questions are
generated via LiteLLM (`task="study_plan"` routes to GPT-4.1 mini). Academic accuracy
always takes priority over personalisation — the prompt explicitly instructs the model
to ensure the question is curriculum-correct before adding interest context.

**Study plan service**

A `StudyPlanService` that orchestrates curation and quiz generation, writes the
results to the `study_plans`, `study_plan_resources`, and `study_plan_quizzes` tables,
and updates `gap_states` after the student submits their quiz answers.

**Study plan API — stub replacement**

M0-10-T4 created `routes/study_plans.py` with stubs. This milestone replaces all stub
bodies with real service calls. The frozen contracts from M0-10 must not be changed.

**Frontend UI**

The student study plan view builds in `apps/student`. The teacher assignment UI
builds in `apps/teacher` as an extension of the gap map heatmap from M2-1-T3.

---

## Tasks in This Milestone

| Task ID | File | Description |
|---|---|---|
| M3-1-T1 | `M3/M3-1-T1_content_curator.md` | Resource curation with learning profile weighting |
| M3-1-T2 | `M3/M3-1-T2_quiz_generator.md` | Quiz generation with interest injection via LiteLLM |
| M3-2-T1 | `M3/M3-2-T1_study_plan_service.md` | Study plan orchestration service |
| M3-2-T2 | `M3/M3-2-T2_study_plan_routes.md` | Replace study plan stubs with real logic |
| M3-2-T3 | `M3/M3-2-T3_student_study_plan_ui.md` | Student study plan UI (apps/student) |
| M3-2-T4 | `M3/M3-2-T4_teacher_assignment_ui.md` | Teacher assignment UI (apps/teacher) |

---

## Task Execution Order

```
M3-1-T1 (content curator) ← parallel start
M3-1-T2 (quiz generator)  ← parallel start
  → M3-2-T1 (study plan service) ← needs both curator and generator
    → M3-2-T2 (study plan routes) ← replace stubs, calls service
      → M3-2-T3 (student UI)   ← apps/student, needs real routes
      → M3-2-T4 (teacher UI)   ← apps/teacher, needs real routes
```

M3-2-T3 and M3-2-T4 can be built in parallel once M3-2-T2 is live.

---

## Critical: Stub Replacement Protocol

M3-2-T2 replaces stubs in `backend/app/api/v1/routes/study_plans.py` (created by
M0-10-T4). Open the file, find every function marked `# STUB — M0-10-T4`, replace
only the function body. The `POST /classes/{id}/study-plans` stub currently returns
501 — M3 replaces this with real async plan generation. The read endpoints return
real data from the database. The `PATCH .../watched` and quiz submit endpoints write
real records.

---

## LiteLLM Usage in This Milestone

Both `M3-1-T2` (quiz generation) and `M3-2-T1` (study plan orchestration) make LLM
calls. All calls must go through `app.ai.providers.router.complete()` — never import
provider SDKs directly. The task string for study plan generation is `"study_plan"`,
which routes to GPT-4.1 mini with a 10-second timeout per CONSTITUTION §8.

If the LLM call fails or times out, the study plan should be created in a degraded
state with resources but no quiz (resources come from deterministic cosine similarity
retrieval, not LLM). A structured warning log must be emitted. The student should
see the resources section and a "Quiz unavailable — try again later" message.

---

## Frontend App Targets

The student study plan view (`/student/study-plans` and `/student/study-plans/:id`)
builds in `apps/student`. The teacher assignment modal and button on the gap map cell
side panel build in `apps/teacher` as an addition to M2-1-T3's heatmap component.
Neither app touches the other's directory.

---

## Definition of Done

- Teacher can assign study plans from the gap map with one click
- Resources are personalised based on student's learning modality
- Quiz scenarios use student's personal interests where applicable
- Student can view resources, mark them watched, take the quiz, and see their score
- Quiz submission updates `gap_states` for the subtopic
- All M3 tests pass

---

## Key Tables Used in This Milestone

`study_plans`, `study_plan_resources`, `study_plan_quizzes`, `gap_states`, `subtopics`,
`curriculum_chunks`, `student_learning_profiles`, `question_bank`

Full schema: `kaihle_v2_1_schema.sql`

---

## What M2 Delivered (Available to Use)

`GET /classes/{id}/gap-map` returns real data. The teacher heatmap renders and the
cell side panel is clickable. `GET /students/{id}/gap-map` returns real subtopic
scores. `student_learning_profiles` is populated for onboarded students.
`subtopics.embedding` is in pgvector for cosine similarity retrieval.

---

## What M4 Expects From M3

Study plans are assignable and `gap_states` update after quiz submission. The lesson
plan generator in M4 reads the current gap map to identify which subtopics to focus
on — it benefits from accurate `gap_states` that reflect both Tier 1 and any quiz
submissions from M3 study plans.
