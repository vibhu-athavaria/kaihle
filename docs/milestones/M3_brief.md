# M3 Brief — Smart Study Plans
**Milestone:** 3 of 6
**Estimated duration:** 4–5 weeks (extended from 3–4 to accommodate M3-0 content infrastructure)
**Previous milestone:** M2 — Gap Map & Teacher Dashboard
**Constitution version:** 2.0
**Last updated:** April 2026 — content architecture revised; M3-0 epic added

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

- `subtopic_content` table seeded with LLM explanations and YouTube video candidates for all active subtopics
- KaihleAdmin has reviewed and approved at least one video per subtopic before student-facing features are enabled
- Teacher has reviewed and approved explanations for subtopics in their classes
- Teacher assigns a study plan from a red or amber gap map cell → student sees curated video matched to their learning style → student takes a quiz with personally relevant examples → gap state updates after quiz submission
- Nightly stale link Celery job operational and scheduled

---

## Architecture Change from Original Design (April 2026)

**What changed and why:**

The original M3 design used pgvector cosine similarity against `curriculum_chunks`
(PDF-sourced text) to retrieve and score resources. This design was abandoned when
PDF ingestion was dropped from the product.

**New architecture:**

Resources come from the `subtopic_content` table — a structured relational table with
one row per subtopic, storing:
- LLM-generated explanation text (reviewed and approved by teachers)
- YouTube video candidates as a JSONB array (reviewed and approved by KaihleAdmin)

Retrieval is a filtered SQL query, not semantic search. No pgvector. No embeddings.
No `curriculum_chunks`. No `embedder.py` or `retriever.py`.

**Implications for coding agents:**

- Do NOT create `backend/app/ai/rag/` directory or any files within it
- Do NOT import or call `cosine_similarity`, `embed()`, or pgvector functions
- Do NOT reference `curriculum_chunks` table in any query
- Do NOT add `subtopics.embedding` population to any script
- Resource retrieval = `SELECT FROM subtopic_content WHERE subtopic_id = X AND video status = 'approved'`
- Quiz context = `subtopic_content.approved_explanation` (falls back to `subtopic.learning_objective`)

---

## What This Milestone Delivers

### EPIC M3-0 — Content Infrastructure (NEW — runs before all other M3 tasks)

A `subtopic_content` table and associated workflows that create a quality-controlled
content library for all subtopics. This is the foundation every subsequent M3 feature
depends on.

**Subtopic content table and migration**

A `subtopic_content` table with one row per subtopic. Stores LLM-generated explanation
text (pending teacher review) and an array of YouTube video candidates (pending
KaihleAdmin review). Also creates the `student_lesson_packs` table used by M4-2-T1.
Created via Alembic migration. Includes deprecation comment on `curriculum_chunks`.

**YouTube seed pipeline**

A `seed_subtopic_content.py` script that iterates all active subtopics, generates
an LLM explanation via Gemini 2.5 Pro, searches YouTube Data API v3 for video
candidates, scores them by view count, and stores the top 3 as `status = 'pending'`.
Idempotent — safe to re-run. Supports `--subject`, `--limit`, `--dry-run` flags.

**KaihleAdmin video review UI**

A new Content section in `apps/kaihle-admin` where Vibhu and the Kaihle team can
review YouTube video candidates per subtopic. Each video shows an embedded YouTube
preview (with correct `sandbox` and `title` attributes), channel, view count, and
confidence. KaihleAdmin approves or rejects each video. Approved videos become
available for student packs. Stale videos are flagged by the nightly Celery job.

**Teacher explanation review UI**

A new Content section in `apps/teacher` scoped to the teacher's own classes. Teachers
review LLM-generated text explanations for subtopics they teach, edit if needed, and
approve. Interest-injected examples are flagged separately for independent approval.
The approved explanation becomes the canonical text used in student packs and quiz
generation. Also surfaced inline within the Gap Map side panel.

**Stale link Celery job**

A nightly Celery beat task (`check_stale_video_links`) running at 02:00 that performs
HEAD requests on every approved and pending video URL not checked in 7 days. Broken
URLs (404, 403) are marked `status = 'stale'`. KaihleAdmin is surfaced stale counts
in the review queue badge. Uses `new_event_loop()` pattern, not `asyncio.run()`.
Capped at 500 URL checks per run with 0.5s rate-limit delay between requests.

---

### EPIC M3-1 — Content Curation & Quiz Generation (updated)

**Content curation engine**

A `ContentCurator` service that retrieves approved YouTube videos for a given subtopic
from the `subtopic_content` table. Videos are ordered by view-count-normalised score
weighted by student modality (visual and auditory learners receive a 1.3× and 1.2×
multiplier respectively). Results are cached per `(subtopic_id, student_id)` for 24
hours in Redis. Returns empty list gracefully when no approved videos exist yet.
Does NOT call YouTube API at runtime — the seed pipeline handles that.

**Quiz generation service**

A `QuizGenerator` service that builds a 5-question MCQ quiz for a subtopic. Uses
`subtopic_content.approved_explanation` (or falls back to `subtopic.learning_objective`)
as the curriculum context — replacing the previous pgvector chunk retrieval. Uses
`get_compatible_interests()` from `questionnaire_config.py` to inject only subject-
appropriate student interests into the prompt. All 5 questions are MCQ — no
`SHORT_ANSWER` type. Called via `get_provider(task="question_generation")`.

**Quiz quality validation**

Unchanged from original design. Validates generated quiz questions for curriculum
alignment before they reach students.

---

### EPIC M3-2 — Study Plan Service & UI (unchanged)

Study plan service, routes, student UI, and teacher assignment UI are unchanged in
design intent. The content curator and quiz generator they depend on have changed
their internal implementation, but their external interfaces (function signatures,
return types) are identical.

---

## Tasks in This Milestone

| Task ID | File | Description | Status |
|---|---|---|---|
| M3-0-T1 | `M3-0-T1_subtopic_content_migration_and_seed.md` | `subtopic_content` table + YouTube seed pipeline | **NEW** |
| M3-0-T2a | `M3-0-T2a_kaihle_admin_video_review_ui.md` | KaihleAdmin video review queue UI | **NEW** |
| M3-0-T2b | `M3-0-T2b_teacher_explanation_review_ui.md` | Teacher explanation review UI | **NEW** |
| M3-0-T3 | `M3-0-T3_stale_link_celery_job.md` | Nightly stale video link Celery job | **NEW** |
| M3-1-T1 | `M3-1-T1_content_curator.md` | Resource curation from subtopic_content | **UPDATED** |
| M3-1-T2 | `M3-1-T2_quiz_generator.md` | Quiz generation with subtopic context | **UPDATED** |
| M3-1-T3 | `M3-1-T3_quiz_quality_validation.md` | Quiz quality gate | Unchanged |
| M3-2-T1 | `M3-2-T1_study_plan_service.md` | Study plan orchestration service | Unchanged |
| M3-2-T2 | `M3-2-T2_study_plan_routes.md` | Replace study plan stubs | Unchanged |
| M3-2-T3 | `M3-2-T3_student_study_plan_ui.md` | Student study plan UI | Unchanged |
| M3-2-T4 | `M3-2-T4_teacher_assignment_ui.md` | Teacher assignment UI | Unchanged |

---

## Task Execution Order

```
M3-0-T1 (subtopic_content table + seed pipeline) ← MUST run first
  → M3-0-T2a (KaihleAdmin video review UI)  ← parallel once T1 complete
  → M3-0-T2b (teacher explanation review UI) ← parallel once T1 complete
  → M3-0-T3  (stale link Celery job)         ← parallel once T1 complete

All M3-0 tasks must be complete before M3-1 begins.

M3-1-T1 (content curator) ← parallel start after M3-0 complete
M3-1-T2 (quiz generator)  ← parallel start after M3-0 complete
  → M3-1-T3 (quiz quality validation) ← add validator to generator
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

`M3-1-T2` (quiz generation) calls via `get_provider(task="question_generation")`.
`M3-0-T1` seed script calls Gemini 2.5 Pro directly via `litellm.acompletion()` —
this is a CLI script, not a request-path service, so direct litellm is acceptable.
All other M3 tasks that need LLM access must go through `app.ai.providers.router.complete()`.
Never import provider SDKs directly in service or route files.

---

## Do NOT Build in This Milestone

- pgvector indexes or cosine similarity queries — not used in v1
- `embedder.py` or `retriever.py` — do not create these files
- Khan Academy API integration — removed from MVP
- Audio generation — deferred
- Slides generation — deferred

---

## Frontend App Targets

The student study plan view (`/student/study-plans` and `/student/study-plans/:id`)
builds in `apps/student`. The teacher assignment modal and button on the gap map cell
side panel build in `apps/teacher` as an addition to M2-1-T3's heatmap component.
The KaihleAdmin video review builds in `apps/kaihle-admin`. The teacher explanation
review builds in `apps/teacher`. No app touches another's directory.

---

## Definition of Done

- `subtopic_content` table exists and is seeded for all active subtopics
- At least one video per subtopic has been approved by KaihleAdmin
- Teacher explanation review UI operational
- Nightly stale link job registered and confirmed running in staging
- Teacher can assign study plans from the gap map with one click
- Resources are personalised based on student's learning modality
- Quiz scenarios use student's personal interests where applicable
- Student can view resources, mark them watched, take the quiz, and see their score
- Quiz submission updates `gap_states` for the subtopic
- All M3 tests pass

---

## Key Tables Used in This Milestone

`subtopic_content`, `student_lesson_packs` (created here, used in M4),
`study_plans`, `study_plan_resources`, `study_plan_quizzes`, `gap_states`,
`subtopics`, `student_learning_profiles`, `question_bank`

Full schema: `kaihle_v2_1_schema.sql`

---

## What M2 Delivered (Available to Use)

`GET /classes/{id}/gap-map` returns real data. The teacher heatmap renders and the
cell side panel is clickable. `GET /students/{id}/gap-map` returns real subtopic
scores. `student_learning_profiles` is populated for onboarded students.

---

## What M4 Expects From M3

Study plans are assignable and `gap_states` update after quiz submission. The lesson
plan generator in M4 reads the current gap map to identify which subtopics to focus
on. `subtopic_content.approved_explanation` is populated for focus subtopics — M4
lesson plan generation uses this as curriculum context. `student_lesson_packs` table
exists (created in M3-0-T1) for M4-2-T1 to write into.

---

*M3 Brief v2.0 · April 2026*
*Key changes from v1.0: M3-0 epic added (content infrastructure), content curation*
*architecture changed from pgvector/curriculum_chunks to subtopic_content table,*
*quiz generator updated to use approved_explanation instead of RAG context,*
*SHORT_ANSWER question type removed from quiz generator.*
