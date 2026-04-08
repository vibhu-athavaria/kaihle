# M4 Brief — Teacher Copilot (Lesson Planning)
**Milestone:** 4 of 6
**Estimated duration:** 3–4 weeks (extended from 2–3 to accommodate M4-2 student pack epic)
**Previous milestone:** M3 — Smart Study Plans
**Constitution version:** 2.0
**Last updated:** April 2026 — student pack epic added; RAG context replaced

> Load this brief alongside CONSTITUTION.md when working on any M4 task.
> Load the specific task file for the task you are implementing.

---

## Goal

Every Monday at 06:00, each teacher automatically receives an AI-generated weekly
lesson plan based on their class's current gap map. The plan groups students by
mastery level into three differentiated activity streams. Teachers view, edit, and
mark plans as used from their dashboard.

On first access by a student, a personalised student pack is generated on-demand
from the same lesson plan — adapted to the student's learning style and interests —
and cached for subsequent access.

---

## Exit Criteria

- Weekly lesson plans auto-generated every Monday for all active classes that have assessment data
- Teacher receives an email notification with a link to the plan
- Teacher views the plan in their dashboard, edits a section, and marks it as used
- Regeneration on demand works
- Student opens a lesson plan → receives personalised pack (text + video + pre/post quiz)
- Student pack generated within 30s on first access; instant on subsequent access

---

## Architecture Change from Original Design (April 2026)

**What changed and why:**

The original M4 design retrieved lesson plan context via pgvector cosine similarity
against `curriculum_chunks`. This was abandoned when PDF ingestion was dropped.

**New context source:**

`subtopic_content.approved_explanation` replaces pgvector retrieval. The
`_get_rag_context()` method is renamed to `_get_subtopic_context()` and reads
from the `subtopic_content` table directly. Falls back to `subtopic.learning_objective`
if no approved explanation exists yet.

**Student pack is a new separate output:**

The original design produced one teacher-facing lesson plan. This milestone now
produces two distinct artefacts from the same lesson plan:

| | Teacher Plan | Student Pack |
|---|---|---|
| Generation | Celery beat, Monday 06:00 | On-demand, first student access |
| Storage | `lesson_plans` table | `student_lesson_packs` table |
| Audience | Teacher only | Student only |
| Language | Cambridge LO codes, formal | Plain language, interest-adapted |
| Resources | YouTube preview links for teacher | Embedded video from subtopic_content |
| Quiz | Class gap summary, activity streams | 3 pre + 3 post MCQ from question_bank |

**Implications for coding agents:**

- `_get_rag_context()` does NOT exist — use `_get_subtopic_context()` instead
- Do NOT reference `curriculum_chunks` in any lesson plan generation query
- Do NOT add pgvector calls or embedding lookups
- Teacher plan generation: unchanged schedule, unchanged output schema
- Student pack generation: new on-demand endpoint, new service, new table

---

## What This Milestone Delivers

### EPIC M4-1 — Teacher Lesson Plan (updated)

**Lesson plan JSON schema and storage**

A validated Pydantic schema (`LessonPlanLLMOutput`) that represents the exact JSON
structure the LLM must return. Rich format with per-activity `timeline` array,
`diagnostic_gaps` with WHERE and HOW fields, Cambridge objective codes, and VARK
learning style embedding. Storage via `_store_plan()` in `lesson_plan_service.py`.
This task runs first — all other M4 tasks depend on the schema being locked.

**Celery beat generation task**

A `generate_weekly_lesson_plans()` function registered as a Celery beat task running
every Monday at 06:00. For each active class with at least one completed assessment,
it loads the gap map, identifies the two subtopics with the lowest class average mastery,
clusters students into Group A (mastery < 0.4), Group B (0.4–0.7), and Group C (> 0.7),
loads subtopic context from `subtopic_content.approved_explanation` via
`_get_subtopic_context()`, builds a structured prompt including VARK learning style
profile for the dominant class style, and calls LiteLLM with the configured lesson
plan model (default: Claude Sonnet 4.6 via OpenRouter, 90s timeout). On success it
stores the plan and sends an email notification via Resend. On timeout or failure it
logs at ERROR level and does not store a partial plan.

**Lesson plan API — stub replacement**

M0-10-T5 created `routes/lesson_plans.py` with stubs for all five lesson plan
endpoints. This milestone replaces every stub body with real service calls. The frozen
contracts from M0-10 must not be changed. The PATCH endpoint accumulates teacher edits
in the `teacher_edits` JSONB column as a sparse delta — it never overwrites
`generated_plan`. Two new student-pack endpoints are added to the same route file.

**Teacher lesson plan UI**

Built in `apps/teacher`. The dashboard "This Week" card now shows real lesson plan
data when a plan exists. A full plan view page lets the teacher see the lesson
structure, edit any section, regenerate, and mark as used.

---

### EPIC M4-2 — Student Pack (NEW)

**Student pack on-demand generation**

A `StudentPackService` that generates a personalised lesson pack for a student on
first access and caches it in `student_lesson_packs`. The pack contains:
- `what_you_will_learn` — one motivating plain-language sentence
- `real_life_intro` — max 100 words, interest-matched real-world connection
- `explanation` — max 200 words, learning-style adapted, curriculum-accurate
- `content_sequence` — `video_first` (visual/auditory/kinesthetic) or `text_first` (reading_writing)
- `video_url` / `video_title` — first approved video from `subtopic_content`
- `pre_quiz` — 3 easier MCQ questions from question_bank (difficulty ≤ 2.0)
- `post_quiz` — 3 mastery-calibrated MCQ questions (difficulty matched to student's current gap_state)

Cache key: `(student_id, lesson_plan_id, learning_style, interest_category)`.
Two students sharing learning style and interest category receive the same cached pack.
Interest category derived from student profile via `get_interest_category()` in
`questionnaire_config.py` — not hardcoded in the service.

Post-quiz submission scores answers deterministically (MCQ string match), updates
`gap_states` for the subtopic via `update_mastery_from_pack_quiz()`, and is idempotent
on re-submission.

LLM generation degrades gracefully on timeout — a fallback pack using the base
explanation text is stored rather than failing entirely.

---

## Tasks in This Milestone

| Task ID | File | Description | Status |
|---|---|---|---|
| M4-1-T2 | `M4-1-T2_lesson_plan_schema_storage.md` | Lesson plan JSON schema + storage | Updated (addendum) |
| M4-1-T1 | `M4-1-T1_lesson_plan_celery_task.md` | Celery beat: weekly lesson plan generation | Updated (`_get_subtopic_context`) |
| M4-1-T3 | `M4-1-T3_lesson_plan_routes.md` | Replace lesson plan stubs + add student pack endpoints | Stub replacement unchanged; new endpoints added |
| M4-1-T4 | `M4-1-T4_lesson_plan_ui.md` | Teacher lesson plan UI | Unchanged |
| M4-1-T5 | `M4-1-T5_student_lesson_plan_preview_ui.md` | Per-student lesson plan preview — teacher read-only view | Unchanged |
| M4-2-T1 | `M4-2-T1_student_pack_generation.md` | Student pack on-demand generation service + API | **NEW** |
| M4-2-T2 | `M4-2-T2_student_pack_ui.md` | Student pack UI in apps/student | **NEW — task file not yet written** |

---

## Task Execution Order

```
M4-1-T2 (schema + storage) ← MUST run first — all other tasks import from it
  → M4-1-T1 (Celery task)  ← needs schema to validate and store LLM output
  → M4-1-T3 (routes)       ← replace stubs, adds student pack endpoints
    → M4-1-T4 (teacher UI) ← apps/teacher, needs real routes returning data
      → M4-1-T5 (student lesson plan preview) ← depends on T4 Students tab

M4-2-T1 (student pack service) ← can start parallel with M4-1-T1 once M4-1-T2 done
  → M4-2-T2 (student pack UI)  ← apps/student, needs M4-2-T1 endpoint live
```

M4-1-T4 and M4-2-T1 can be worked in parallel once M4-1-T2 is done.

---

## Outstanding Task File

`M4-2-T2_student_pack_ui.md` has not yet been written. It builds the student-facing
lesson pack view in `apps/student`. Required before student pack is usable. Write
this task file before scheduling M4-2-T2 implementation.

Screen spec reference: See `docs/design/screens/STUDENT_SCREENS.md` for the student
lesson pack page design when available.

---

## Critical: Stub Replacement Protocol

M4-1-T3 replaces stubs in `backend/app/api/v1/routes/lesson_plans.py` (created by
M0-10-T5). Open the file, find every function marked `# STUB — M0-10-T5`, and replace
only the function body. The frozen paths, auth, and schemas must not change.

Two new endpoints are ADDED (not replacements) in M4-1-T3:
- `GET /lesson-plans/{plan_id}/student-pack` — student pack retrieval or generation
- `POST /lesson-plans/{plan_id}/student-pack/quiz/submit` — post-quiz submission

These endpoints are STUDENT role only. They do not replace any existing stub.

---

## LiteLLM Usage in This Milestone

M4-1-T1 calls `litellm.acompletion()` directly with OpenRouter API key injection —
this is the established pattern for OpenRouter-routed models. See M4-1-T1 task file
for the exact pattern. M4-2-T1 follows the same pattern for Gemini 2.5 Pro student
pack generation. Both set timeouts via `asyncio.wait_for()`.

M4-1-T1 uses `new_event_loop()` pattern for the Celery beat task wrapper.
M4-2-T1 does NOT use Celery — it is a synchronous request-time service.

---

## Environment Variables

Add to `.env.example` alongside existing lesson plan vars:

```bash
# Student pack generation (new in M4)
LLM_STUDENT_PACK_MODEL=gemini/gemini-2.5-pro
LLM_STUDENT_PACK_TIMEOUT_S=30
LLM_STUDENT_PACK_MAX_TOKENS=1000
```

---

## Definition of Done

- Weekly lesson plans auto-generated every Monday for active classes
- Teacher receives email with link to the plan
- Teacher can view, edit (delta stored separately), and mark as used
- Regeneration queues a new Celery task and clears previous plan and edits
- `GET /classes/{id}/lesson-plans` returns real data
- Student opens lesson plan → receives personalised pack within 30s (first access)
- Student pack cached → returns instantly on second access
- Post-quiz submission scores MCQ deterministically and updates gap_states
- All M4 tests pass

---

## Key Tables Used in This Milestone

`lesson_plans`, `student_lesson_packs`, `gap_states`, `subtopics`,
`subtopic_content`, `curriculum_topics`, `classes`, `class_enrollments`,
`users`, `student_learning_profiles`, `question_bank`

**Removed from key tables (compared to original brief):**
`curriculum_chunks` — deprecated, not used in v1

Full schema: `kaihle_v2_1_schema.sql`

---

## What M3 Delivered (Available to Use)

Gap states reflect both Tier 1 diagnostic results and M3 study plan quiz submissions.
The gap map service is operational. Study plan assignment works. `subtopic_content`
table is seeded and has approved explanations and videos. `student_lesson_packs` table
exists (created in M3-0-T1 migration).

---

## What M5 Expects From M4

Lesson plans are being generated on the Monday schedule. Celery beat is confirmed
operational with at least one successful lesson plan generation in the staging
environment. The parent narrative in M5 may reference whether the student has active
study plans, which indirectly depends on M4's gap map data being fresh.

---

*M4 Brief v2.0 · April 2026*
*Key changes from v1.0: M4-2 student pack epic added; `_get_rag_context()` replaced*
*with `_get_subtopic_context()`; `curriculum_chunks` removed from key tables;*
*LLM model updated to Claude Sonnet 4.6 via OpenRouter (lesson plan) and*
*Gemini 2.5 Pro (student pack); 90s timeout for lesson plan generation.*
