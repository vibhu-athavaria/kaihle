# M1 Brief — Core Diagnostics Flow
**Milestone:** 1 of 6
**Estimated duration:** 3–4 weeks
**Previous milestone:** M0 — Foundations + M0-9 + M0-10
**Constitution version:** 2.0

> Load this brief alongside CONSTITUTION.md when working on any M1 task.
> Load the specific task file for the task you are implementing.

---

## Goal

The full diagnostic pipeline is operational end to end. Students complete Tier 1
onboarding diagnostics and unlock their class content. Teachers can create and
publish Tier 2 assessments. All submitted answers are scored and gap states are
populated. The curriculum and question bank are seeded with real data.

---

## Exit Criteria

- Student completes all Tier 1 diagnostics → `gap_states` populated → class content unlocked per class
- Teacher creates a Tier 2 assessment → publishes → student takes it → `gap_states` updated
- 7,000 questions importable via `import_questions.py` script without errors
- Cambridge curriculum data seeded via `seed_curriculum_graph.py`
- Cambridge curriculum PDFs ingested with embeddings stored in pgvector

---

## What This Milestone Delivers

**Data foundation**

The question bank and curriculum graph must be seeded before any assessment logic
can work. These are script-based operations, not API features. The curriculum seeding
script (`seed_curriculum_graph.py`) populates the hierarchical subject→topic→subtopic
graph for Cambridge Lower Secondary and IGCSE. The question import script
(`import_questions.py`) loads 7,000 pre-built MCQ questions, resolving each question's
`subtopic_id` from the seeded graph. Both scripts must be idempotent — safe to run
multiple times without creating duplicates.

**Assessment service**

A service layer (`assessment_service.py`) that handles Tier 2 assessment creation —
selecting questions from the `question_bank` by topic, subject, and grade, and creating
the `assessment_selected_questions` bridge rows. Note that Tier 1 diagnostic creation
is already handled by the `create_class_diagnostic_task` Celery task (M0-6-T2). This
service handles Tier 2 only.

**Assessment API — stub replacement**

M0-10-T3 already created `routes/assessments.py` and `routes/attempts.py` with stub
implementations. This milestone replaces the stub function bodies with real service
calls. The route paths, auth requirements, request schemas, and response schemas are
frozen from M0-10 — do not change them. The specific stubs to replace are documented
in each task file.

**Scoring — deterministic MCQ only**

All questions in the question bank are MCQ. Scoring is a single deterministic operation:
`is_correct = (student_selected_key == question.correct_answer_key)`. There is no
separate scoring service, no async LLM scoring, and no scoring Celery task. Scoring
happens inline inside the attempt submit handler before the gap state calculation task
is queued. The old `M1-4-T2_answer_scoring_service.md` task is retired — see note below.

**Gap state calculation**

A Celery task (`calculate_gap_states`) fires after every attempt submission. It reads
all `student_responses` for the attempt, maps each question to its `subtopic_id` via
the `question_bank`, and upserts `gap_states` rows with rolling mastery scores. After
this task completes, if the assessment was `is_system_generated = TRUE` (Tier 1), it
calls `check_and_update_onboarding_complete(student_id)` from M0-6-T3 to update the
per-class `onboarding_diagnostic_status` and potentially unlock class content.

**Frontend — assessment taking UI**

The student assessment UI is built in `apps/student`. The teacher assessment creation
wizard is built in `apps/teacher`. Both apps already have their React Query hooks wired
to the correct stub endpoints from M0-10-T8 and M0-10-T9 — this milestone populates
those hooks with real data.

---

## Important: M1-4-T2 Is Retired

The original M1-4-T2 (`answer_scoring_service.md`) specified building a scoring service
that handled both rule-based MCQ and async LLM scoring for short-answer questions. Since
the confirmed question bank contains exclusively MCQ questions, this task is retired.
There is no short-answer question type and no LLM scoring needed.

MCQ scoring is implemented as a single inline function in the attempt service:

```python
def score_mcq(selected_key: str, correct_answer_key: str) -> bool:
    """Deterministic MCQ scoring. No LLM. No async. No separate service."""
    return selected_key.strip().lower() == correct_answer_key.strip().lower()
```

This replaces the entire `scoring_service.py` module, `scoring_tasks.py`, and
`answer_scoring.jinja2` prompt template that M1-4-T2 would have created.

---

## Tasks in This Milestone

| Task ID | File | Description |
|---|---|---|
| M1-1-T1 | `M1/M1-1-T1_question_bank_import.md` | Import 7,000 MCQ questions into `question_bank` |
| M1-2-T3 | `M1/M1-2-T3_curriculum_content_review.md` | **MUST RUN FIRST** — Vidhya reviews cambridge_v1.json for accuracy |
| M1-2-T1 | `M1/M1-2-T1_curriculum_graph_seeding.md` | Seed curriculum hierarchy JSON → DB |
| M1-2-T2 | `M1/M1-2-T2_curriculum_pdf_ingestion.md` | PDF → chunks → embeddings → pgvector |
| M1-3-T1 | `M1/M1-3-T1_assessment_generation_service.md` | Tier 2 assessment creation service |
| M1-3-T2 | `M1/M1-3-T2_assessment_api_routes.md` | Replace assessment stubs with real logic |
| M1-3-T3 | `M1/M1-3-T3_assessment_creation_ui.md` | Teacher assessment wizard (apps/teacher) |
| M1-3-T4 | `M1/M1-3-T4_assessment_results_ui.md` | Teacher assessment results UI — class overview + per-student answer breakdown (apps/teacher) |
| M1-4-T1 | `M1/M1-4-T1_student_attempt_api.md` | Replace attempt stubs with real logic |
| ~~M1-4-T2~~ | ~~`M1/M1-4-T2_answer_scoring_service.md`~~ | **RETIRED** — MCQ scoring is inline, no LLM |
| M1-4-T3 | `M1/M1-4-T3_gap_state_calculation.md` | Celery task: calculate_gap_states |
| M1-4-T4 | `M1/M1-4-T4_student_assessment_ui.md` | Student assessment taking UI (apps/student) |

---

## Task Execution Order

```
M1-2-T3 (curriculum content review) ← MUST complete before M1-2-T1
  → M1-2-T1 (curriculum graph seeding) ← now approved by Vidhya
    → M1-1-T1 (question import) ← needs subtopic_id from seeded curriculum
    → M1-2-T2 (PDF ingestion)  ← needs subtopic_id from seeded curriculum
      → M1-3-T1 (assessment service) ← needs question_bank populated
        → M1-3-T2 (assessment routes) ← replace stubs, needs service
          → M1-3-T3 (teacher UI) ← needs real routes returning data
            → M1-3-T4 (teacher results UI) ← depends on M1-3-T3 (assessments list) + M1-4-T1 (attempt results endpoint)
        → M1-4-T1 (attempt routes) ← replace stubs, needs assessment service
          → M1-4-T3 (gap states Celery) ← triggered by attempt submit
          → M1-4-T4 (student UI) ← needs real attempt routes
```

---

## Critical: Stub Replacement Protocol

Tasks M1-3-T2 and M1-4-T1 are replacing stubs, not creating new files.
Before writing any code in these tasks, the implementing agent must:

1. Open `backend/app/api/v1/routes/assessments.py` (created by M0-10-T3)
2. Find every function body marked `# STUB — M0-10-T3`
3. Replace only the function body — never the route decorator, path, auth dependency,
   request schema, or response model
4. Verify the replacement passes the same acceptance criteria the stub verified

The same protocol applies to `routes/attempts.py` in M1-4-T1.

---

## Critical: Tier 1 vs Tier 2 in This Milestone

Tier 1 diagnostic creation was done in M0-6-T2 (Celery task `create_class_diagnostic_task`).
The student retrieves their Tier 1 attempt via `GET /classes/{class_id}/diagnostic`
(stub exists in `routes/attempts.py` from M0-10-T3). There is no separate "start"
endpoint — the attempt already exists in the database when the student arrives.

Tier 2 assessments are teacher-created via `POST /classes/{class_id}/assessments`.
The student takes both Tier 1 and Tier 2 assessments through the same UI component
and the same attempt lifecycle endpoints.

After a Tier 1 attempt is submitted, `calculate_gap_states` fires, then
`check_and_update_onboarding_complete(student_id)` is called synchronously. If all
enrolled classes now have `onboarding_diagnostic_status = COMPLETED`, the student's
class content gates open automatically.

---

## Definition of Done

- 7,000 questions are importable via `import_questions.py` without errors
- Cambridge curriculum PDFs ingestable with embeddings stored in pgvector
- Teacher can create and publish a Tier 2 assessment via `POST /classes/{id}/assessments`
- Student can start and submit any assessment via the attempt endpoints
- MCQ answers scored deterministically on submit (no LLM, no async scoring)
- `gap_states` calculated and stored after every submission
- Tier 1 submission triggers `check_and_update_onboarding_complete`
- Per-class content gate unlocks when a class's Tier 1 diagnostic is complete
- All M1 tests pass
- `mypy app/` passes with zero errors

---

## Key Tables Used in This Milestone

`question_bank`, `curricula`, `subjects`, `grades`, `topics`, `curriculum_topics`,
`subtopics`, `curriculum_chunks`, `assessments`, `assessment_selected_questions`,
`student_attempts`, `student_responses`, `gap_states`, `student_profiles`,
`class_enrollments`

Full schema: `kaihle_v2_1_schema.sql`

---

## What M0 + M0-9 + M0-10 Delivered (Available to Use)

The following are confirmed built and available without re-implementation.

Auth, RBAC, and school/user/class management are fully operational. The two-layer
student onboarding gate is active — `OnboardingRoute` blocks dashboard access until
the learning profile is complete, and `require_diagnostic_complete` blocks class
content per enrollment until the Tier 1 diagnostic is submitted. The password setup
flow (magic link → scoped JWT → `POST /auth/set-password` → full JWT) is implemented
for all three invited roles.

All API contracts are frozen in `routes/assessments.py` and `routes/attempts.py`.
Stub routes return correct empty shapes. The `schemas/assessments.py` and
`schemas/attempts.py` Pydantic schemas are defined and importable. React Query hooks
in `apps/student` and `apps/teacher` call the correct stub endpoints.

The `create_class_diagnostic_task` Celery task fires when a class is created and
builds the Tier 1 assessment pool. The `trigger_onboarding_diagnostics` Celery task
fires when a student is enrolled and creates their `StudentAttempt` row. Both are
production-ready with empty question bank guard and dead-letter logging.

---

## What M2 Expects From M1

`gap_states` table is populated with real mastery scores for at least one enrolled
student. At least one student has completed all Tier 1 diagnostics so the gap map
has real data to aggregate and display. `subtopics.embedding` is populated in
pgvector, which M2's RAG retrieval depends on for gap map context.
