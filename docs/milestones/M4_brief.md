# M4 Brief — Teacher Copilot (Lesson Planning)
**Milestone:** 4 of 6
**Estimated duration:** 2–3 weeks
**Previous milestone:** M3 — Smart Study Plans
**Constitution version:** 2.0

> Load this brief alongside CONSTITUTION.md when working on any M4 task.
> Load the specific task file for the task you are implementing.

---

## Goal

Every Monday at 06:00, each teacher automatically receives an AI-generated weekly
lesson plan based on their class's current gap map. The plan groups students by
mastery level into three differentiated activity streams. Teachers view, edit, and
mark plans as used from their dashboard.

---

## Exit Criteria

- Weekly lesson plans auto-generated every Monday for all active classes that have assessment data
- Teacher receives an email notification with a link to the plan
- Teacher views the plan in their dashboard, edits a section, and marks it as used
- Regeneration on demand works

---

## What This Milestone Delivers

**Lesson plan JSON schema and storage**

A validated Pydantic schema (`LessonPlanLLMOutput`) that represents the exact JSON
structure the LLM must return. Storage via `_store_plan()` in `lesson_plan_service.py`.
This task runs first — all other M4 tasks depend on the schema being locked.

**Celery beat generation task**

A `generate_weekly_lesson_plans()` function registered as a Celery beat task running
every Monday at 06:00. For each active class with at least one completed assessment,
it loads the gap map, identifies the two subtopics with the lowest class average mastery,
clusters students into Group A (mastery < 0.4), Group B (0.4–0.7), and Group C (> 0.7),
retrieves the three most relevant `curriculum_chunks` via pgvector cosine similarity,
builds a structured prompt, and calls LiteLLM with `task="lesson_plan"` (GPT-4.1,
15-second timeout). On success it stores the plan and sends an email notification via
Resend. On timeout or failure it logs at ERROR level and does not store a partial plan.

**Lesson plan API — stub replacement**

M0-10-T5 created `routes/lesson_plans.py` with stubs for all five lesson plan
endpoints. This milestone replaces every stub body with real service calls. The frozen
contracts from M0-10 must not be changed. The PATCH endpoint accumulates teacher edits
in the `teacher_edits` JSONB column as a sparse delta — it never overwrites
`generated_plan`.

**Teacher lesson plan UI**

Built in `apps/teacher`. The dashboard "This Week" card now shows real lesson plan
data when a plan exists (previously showing a placeholder). A full plan view page lets
the teacher see the lesson structure, edit any section, regenerate, and mark as used.

---

## Tasks in This Milestone

| Task ID | File | Description |
|---|---|---|
| M4-1-T2 | `M4/M4-1-T2_lesson_plan_schema_storage.md` | Lesson plan JSON schema + storage service |
| M4-1-T1 | `M4/M4-1-T1_lesson_plan_celery_task.md` | Celery beat: weekly lesson plan generation |
| M4-1-T3 | `M4/M4-1-T3_lesson_plan_routes.md` | Replace lesson plan stubs with real logic |
| M4-1-T4 | `M4/M4-1-T4_lesson_plan_ui.md` | Teacher lesson plan UI (apps/teacher) |
| M4-1-T5 | `M4/M4-1-T5_student_lesson_plan_preview_ui.md` | Per-student personalised lesson plan preview — read-only teacher view (apps/teacher) |

---

## Task Execution Order

```
M4-1-T2 (schema + storage) ← MUST run first — all other tasks import from it
  → M4-1-T1 (Celery task)  ← needs schema to validate and store LLM output
  → M4-1-T3 (routes)       ← replace stubs, needs schema for response types
    → M4-1-T4 (UI)         ← apps/teacher, needs real routes returning data
      → M4-1-T5 (student lesson plan preview) ← depends on T4 Students tab existing
```

---

## Critical: Stub Replacement Protocol

M4-1-T3 replaces stubs in `backend/app/api/v1/routes/lesson_plans.py` (created by
M0-10-T5). Open the file, find every function marked `# STUB — M0-10-T5`, and replace
only the function body. The `GET /classes/{id}/lesson-plans` and individual plan
endpoints currently return 404 — M4 replaces these with real DB queries. The `PATCH`
endpoint implements the sparse delta edit pattern. The frozen paths, auth, and schemas
must not change.

---

## LiteLLM Usage in This Milestone

The lesson plan generation task calls `app.ai.providers.router.complete()` with
`task="lesson_plan"`. Per CONSTITUTION §8, this routes to GPT-4.1 with a 15-second
hard timeout. The prompt is a Jinja2 template at `backend/app/ai/prompts/lesson_plan.jinja2`.

The LLM response must be validated against `LessonPlanLLMOutput` before being stored.
If validation fails, log at ERROR level with the raw response included, and do not
store the plan. Do not email the teacher for a failed generation.

---

## Frontend App Target

All lesson plan UI builds in `apps/teacher`. The `useClassLessonPlans` hook created
in M0-10-T9 is the data layer — M4-1-T4 builds the presentation components that
consume it. No code goes into `apps/school-admin` or any other app.

---

## Definition of Done

- Weekly lesson plans auto-generated every Monday for active classes
- Teacher receives email with link to the plan
- Teacher can view, edit (delta stored separately), and mark as used
- Regeneration queues a new Celery task and clears previous plan and edits
- `GET /classes/{id}/lesson-plans` returns real data
- All M4 tests pass

---

## Key Tables Used in This Milestone

`lesson_plans`, `gap_states`, `subtopics`, `curriculum_topics`, `classes`,
`class_enrollments`, `users`, `curriculum_chunks`

Full schema: `kaihle_v2_1_schema.sql`

---

## What M3 Delivered (Available to Use)

Gap states reflect both Tier 1 diagnostic results and M3 study plan quiz submissions.
The gap map service is operational. Study plan assignment works. The content curation
and quiz generation patterns established in M3 inform the lesson plan prompt design
in M4.

---

## What M5 Expects From M4

Lesson plans are being generated on the Monday schedule. Celery beat is confirmed
operational with at least one successful lesson plan generation in the staging
environment. The parent narrative in M5 may reference whether the student has active
study plans, which indirectly depends on M4's gap map data being fresh.
