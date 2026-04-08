# M1 Brief — Core Diagnostics Flow
**Milestone:** 1 of 6
**Estimated duration:** 3–4 weeks
**Previous milestone:** M0 — Foundations + M0-9 + M0-10
**Constitution version:** 2.0
**Last updated:** April 2026 — PDF ingestion retired; mastery formula updated

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
- 7,000+ questions importable via `import_questions.py` script without errors
- Cambridge curriculum data seeded via `seed_curriculum_graph.py`
- All active subtopics have non-null `subtopic_id` in the question bank

> **REMOVED from exit criteria (April 2026):** "Cambridge curriculum PDFs ingested
> with embeddings stored in pgvector." PDF ingestion is abandoned. `M1-2-T2` is
> RETIRED. `subtopics.embedding` is not populated in v1. `curriculum_chunks` table
> exists in the schema but is never written to. See CONSTITUTION.md §8 for rationale.

---

## What This Milestone Delivers

**Data foundation**

The question bank and curriculum graph must be seeded before any assessment logic
can work. These are script-based operations, not API features. The curriculum seeding
script (`seed_curriculum_graph.py`) populates the hierarchical subject→topic→subtopic
graph for Cambridge Lower Secondary and IGCSE. The question import script
(`import_questions.py`) loads the pre-built MCQ question bank, resolving each
question's `subtopic_id` from the seeded graph. Both scripts must be idempotent —
safe to run multiple times without creating duplicates.

The question bank covers Cambridge Lower Secondary and IGCSE across all core subjects
plus History, Geography, and Global Perspectives. Canonical codes (`canonical_code`)
are present on all subtopics and questions.

**Assessment service**

A service layer (`assessment_service.py`) that handles Tier 2 assessment creation —
selecting questions from the `question_bank` by topic, subject, and grade, and
creating the `assessment_selected_questions` bridge rows. Note that Tier 1 diagnostic
creation is already handled by the `create_class_diagnostic_task` Celery task
(M0-6-T2). This service handles Tier 2 only.

**Assessment API — stub replacement**

M0-10-T3 already created `routes/assessments.py` and `routes/attempts.py` with stub
implementations. This milestone replaces the stub function bodies with real service
calls. The route paths, auth requirements, request schemas, and response schemas are
frozen from M0-10 — do not change them.

**Scoring — deterministic MCQ only**

All questions in the question bank are MCQ. Scoring is a single deterministic
operation: `is_correct = (student_selected_key == question.correct_answer_key)`.
There is no separate scoring service, no async LLM scoring, and no scoring Celery
task. Scoring happens inline inside the attempt submit handler before the gap state
calculation task is queued.

**Gap state calculation — weighted mastery formula**

A Celery task (`calculate_gap_states`) fires after every attempt submission. It
reads all `student_responses` for the attempt, maps each question to its `subtopic_id`
via the `question_bank`, and upserts `gap_states` rows using the **recency-weighted
mastery formula** (confirmed product decision):

```
3 attempts: (attempt_n × 0.5) + (attempt_n-1 × 0.3) + (attempt_n-2 × 0.2)
2 attempts: (attempt_n × 0.65) + (attempt_n-1 × 0.35)
1 attempt:  attempt_n × 1.0
Enrollment diagnostic (first attempt only): attempt_score × 0.7  ← seeded at reduced confidence
```

After this task completes, if the assessment was `is_system_generated = TRUE`
(Tier 1), it calls `check_and_update_onboarding_complete(student_id)` from M0-6-T3
to update the per-class `onboarding_diagnostic_status` and unlock class content.

**Frontend — assessment taking UI**

The student assessment UI is built in `apps/student`. The teacher assessment creation
wizard is built in `apps/teacher`. Both apps already have their React Query hooks wired
to the correct stub endpoints from M0-10-T8 and M0-10-T9 — this milestone populates
those hooks with real data.

---

## Important: M1-4-T2 Is Retired

The original M1-4-T2 (`answer_scoring_service.md`) is retired. All questions are MCQ.
No LLM scoring needed. MCQ scoring is a single inline function:

```python
def score_mcq(selected_key: str, correct_answer_key: str) -> bool:
    return selected_key.strip().lower() == correct_answer_key.strip().lower()
```

## Important: M1-2-T2 Is Retired

The original M1-2-T2 (`curriculum_pdf_ingestion.md`) is retired. PDF ingestion is
abandoned. `subtopics.embedding` is not populated. `curriculum_chunks` is not written
to. The `subtopic_content` table (created in M3-0-T1) replaces curriculum chunks as
the content source for quiz generation and lesson planning.

---

## Tasks in This Milestone

| Task ID | File | Description |
|---|---|---|
| M1-2-T3a | `M1/M1-2-T3a_generate_curriculum_review_csv.md` | Generate CSV for Vidhya review — **DONE** |
| M1-2-T3b | `M1/M1-2-T3b_curriculum_review_and_corrections.md` | Vidhya reviews cambridge_v1.json — **DONE** |
| M1-2-T1 | `M1/M1-2-T1_curriculum_graph_seeding.md` | Seed curriculum hierarchy JSON → DB — **DONE** |
| M1-1-T1 | `M1/M1-1-T1_question_bank_import.md` | Import MCQ questions into `question_bank` — **DONE** |
| ~~M1-2-T2~~ | ~~`M1/M1-2-T2_curriculum_pdf_ingestion.md`~~ | **RETIRED** — PDF ingestion abandoned |
| M1-3-T1 | `M1/M1-3-T1_assessment_generation_service.md` | Tier 2 assessment creation service |
| M1-3-T2 | `M1/M1-3-T2_assessment_api_routes.md` | Replace assessment stubs with real logic |
| M1-3-T3 | `M1/M1-3-T3_assessment_creation_ui.md` | Teacher assessment wizard (apps/teacher) |
| M1-3-T4 | `M1/M1-3-T4_assessment_results_ui.md` | Teacher assessment results UI (apps/teacher) |
| M1-4-T1 | `M1/M1-4-T1_student_attempt_api.md` | Replace attempt stubs with real logic |
| ~~M1-4-T2~~ | ~~`M1/M1-4-T2_answer_scoring_service.md`~~ | **RETIRED** — MCQ scoring is inline, no LLM |
| M1-4-T3 | `M1/M1-4-T3_gap_state_calculation.md` | Celery task: calculate_gap_states (weighted formula) |
| M1-4-T4 | `M1/M1-4-T4_student_assessment_ui.md` | Student assessment taking UI (apps/student) |
| M1-5-T1 | `M1/M1-5-T1_question_review_page.md` | KaihleAdmin question bank review page |

---

## Completed Tasks (do not re-run)

- M1-2-T3a — Curriculum review CSV generated
- M1-2-T3b — Vidhya's review complete; `cambridge_v1.json` approved and committed
- M1-2-T1 — Curriculum graph seeded to DB; canonical codes on all subtopics
- M1-1-T1 — Question bank imported (7,000+ MCQs across all subjects incl. History, Geography, Global Perspectives)

---

## Task Execution Order

```
All data foundation tasks complete (see Completed Tasks above)

M1-3-T1 (assessment service) ← needs question_bank populated ✓
  → M1-3-T2 (assessment routes) ← replace stubs, needs service
    → M1-3-T3 (teacher UI) ← needs real routes returning data
      → M1-3-T4 (teacher results UI) ← depends on M1-3-T3 + M1-4-T1
  → M1-4-T1 (attempt routes) ← replace stubs, needs assessment service
    → M1-4-T3 (gap states Celery) ← triggered by attempt submit
    → M1-4-T4 (student UI) ← needs real attempt routes

M1-5-T1 (question review page) ← parallel, no dependencies on M1-3/M1-4
```

---

## Critical: Stub Replacement Protocol

Tasks M1-3-T2 and M1-4-T1 are replacing stubs, not creating new files.
Before writing any code in these tasks, the implementing agent must:

1. Open the existing route file (created by M0-10-T3)
2. Find every function body marked `# STUB — M0-10-T3`
3. Replace only the function body — never the route decorator, path, auth dependency,
   request schema, or response model
4. Verify the replacement passes the same acceptance criteria the stub verified

---

## Critical: Tier 1 vs Tier 2 in This Milestone

Tier 1 diagnostic creation was done in M0-6-T2 (Celery task `create_class_diagnostic_task`).
The student retrieves their Tier 1 attempt via `GET /classes/{class_id}/diagnostic`.
There is no separate "start" endpoint — the attempt already exists when the student
arrives.

Tier 2 assessments are teacher-created via `POST /classes/{class_id}/assessments`.

After a Tier 1 attempt is submitted, `calculate_gap_states` fires, then
`check_and_update_onboarding_complete(student_id)` is called. If all enrolled classes
now have `onboarding_diagnostic_status = COMPLETED`, the student's class content
gates open automatically.

---

## Definition of Done

- 7,000+ questions are in the question bank without errors
- Teacher can create and publish a Tier 2 assessment via `POST /classes/{id}/assessments`
- Student can start and submit any assessment via the attempt endpoints
- MCQ answers scored deterministically on submit (no LLM, no async scoring)
- `gap_states` calculated and stored after every submission using the weighted formula
- Enrollment diagnostic seeds mastery at 70% of face value
- Tier 1 submission triggers `check_and_update_onboarding_complete`
- Per-class content gate unlocks when a class's Tier 1 diagnostic is complete
- All M1 tests pass
- `mypy app/` passes with zero errors

---

## Key Tables Used in This Milestone

`question_bank`, `curricula`, `subjects`, `grades`, `topics`, `curriculum_topics`,
`subtopics`, `assessments`, `assessment_selected_questions`, `student_attempts`,
`student_responses`, `gap_states`, `student_profiles`, `class_enrollments`

**Not used in this milestone:** `curriculum_chunks` (deprecated), `subtopics.embedding`
(not populated in v1), `subtopic_content` (created in M3-0-T1)

Full schema: `kaihle_v2_1_schema.sql`

---

## What M0 + M0-9 + M0-10 Delivered (Available to Use)

Auth, RBAC, school/user/class management, two-layer student onboarding gate,
password setup flow, all API contracts frozen, Celery diagnostic creation tasks
operational, question bank guard implemented.

---

## What M2 Expects From M1

`gap_states` table is populated with real mastery scores for at least one enrolled
student. At least one student has completed all Tier 1 diagnostics so the gap map
has real data to aggregate and display.

*Note from original brief removed: "subtopics.embedding is populated in pgvector,
which M2's RAG retrieval depends on." This dependency no longer exists. M2 does not
use pgvector.*

---

*M1 Brief v2.0 · April 2026*
*Key changes from v1.0: M1-2-T2 (PDF ingestion) retired; mastery formula updated to*
*recency-weighted (0.5/0.3/0.2) with enrollment seeding at 70%; completed tasks noted.*
