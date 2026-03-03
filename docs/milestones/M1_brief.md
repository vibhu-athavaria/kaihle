# M1 Brief — Core Diagnostics Flow
**Milestone:** 1 of 6
**Estimated duration:** 3–4 weeks
**Previous milestone:** M0 — Foundations

> Load this brief alongside CONSTITUTION.md when working on any M1 task.
> Load the specific task file for the task you are implementing.

---

## Goal

The full diagnostic pipeline is operational. Students complete Tier 1 onboarding diagnostics and unlock their dashboard. Teachers can create and publish Tier 2 assessments. All submitted answers are scored and gap states are populated.

## Exit Criteria

- Student completes all Tier 1 diagnostics → `gap_states` populated → dashboard accessible
- Teacher creates a Tier 2 assessment → publishes it → student takes it → `gap_states` updated
- 7,000 question bank importable via script
- Cambridge curriculum PDFs ingestable with embeddings stored in pgvector

---

## What This Milestone Delivers

- Question bank import script (7,000 existing questions → `question_bank` table)
- Curriculum graph seeding script (`seed_curriculum_graph.py`)
- Curriculum PDF ingestion script with pgvector embeddings (`ingest_curriculum.py`)
- Assessment generation service (Tier 2 — teacher-created)
- Assessment API routes (create, publish, list)
- Student attempt API (start, answer, submit, results)
- Answer scoring service (rule-based MCQ + async LLM for short answer)
- Gap state calculation Celery task (`calculate_gap_states`)
- Onboarding completion check triggered on Tier 1 submit
- Student assessment UI (shared by both Tier 1 and Tier 2)
- Teacher assessment creation UI (5-step wizard)

---

## Tasks in This Milestone

| Task ID | File | Description |
|---|---|---|
| M1-1-T1 | `M1/M1-1-T1_question_bank_import.md` | Import script for 7,000 existing questions |
| M1-2-T1 | `M1/M1-2-T1_curriculum_graph_seeding.md` | Seed curriculum hierarchy JSON → DB |
| M1-2-T2 | `M1/M1-2-T2_curriculum_pdf_ingestion.md` | PDF → chunks → embeddings → pgvector |
| M1-3-T1 | `M1/M1-3-T1_assessment_generation_service.md` | Tier 2 assessment creation service |
| M1-3-T2 | `M1/M1-3-T2_assessment_api_routes.md` | Assessment CRUD API endpoints |
| M1-3-T3 | `M1/M1-3-T3_assessment_creation_ui.md` | Teacher 5-step assessment wizard UI |
| M1-4-T1 | `M1/M1-4-T1_student_attempt_api.md` | Start/answer/submit/results endpoints |
| M1-4-T2 | `M1/M1-4-T2_answer_scoring_service.md` | Rule-based + LLM scoring service |
| M1-4-T3 | `M1/M1-4-T3_gap_state_calculation.md` | Celery task: calculate_gap_states |
| M1-4-T4 | `M1/M1-4-T4_student_assessment_ui.md` | Student assessment taking UI |

---

## Task Execution Order

```
M1-2-T1 (curriculum seeding) ← MUST run before everything else
  → M1-1-T1 (question import) ← resolves subtopic_id from seeded data
  → M1-2-T2 (PDF ingestion) ← resolves subtopic_id from seeded data
    → M1-3-T1 (assessment service) ← needs question_bank populated
      → M1-3-T2 (assessment routes) ← needs service
        → M1-3-T3 (teacher UI) ← needs routes
      → M1-4-T2 (scoring service) ← parallel with assessment routes
        → M1-4-T1 (attempt API) ← needs scoring service
          → M1-4-T3 (gap states Celery) ← triggered by submit
          → M1-4-T4 (student UI) ← needs attempt API
```

---

## Critical: Tier 1 vs Tier 2 in This Milestone

- **Tier 1 assessment creation** was done in M0-6-T2 (Celery task). Do NOT re-implement here.
- **Tier 1 taking** uses the identical API (M1-4-T1) and UI (M1-4-T4) as Tier 2.
- The only Tier 1 specific behaviour: after `POST /api/v1/attempts/{attempt_id}/submit`, if `assessment.is_system_generated = TRUE`, call `check_and_update_onboarding_complete(student_id)` — implemented in M0-6-T3, called from M1-4-T1.
- The `is_system_generated` flag is only checked in the submit endpoint. All other assessment logic is identical.

---

## Definition of Done

- [ ] 7,000 questions importable via `import_questions.py` without errors
- [ ] Cambridge curriculum PDFs ingestable with embeddings in pgvector
- [ ] Teacher can create and publish a Tier 2 diagnostic assessment
- [ ] Student can take and submit any assessment (Tier 1 or Tier 2)
- [ ] MCQ answers scored immediately; short answers queued for LLM scoring
- [ ] `gap_states` calculated and stored after every submission
- [ ] Tier 1 submission triggers onboarding completion check
- [ ] Student dashboard unlocked after all Tier 1 diagnostics complete
- [ ] All M1 tests pass

---

## Key Tables Used in This Milestone

`question_bank`, `curricula`, `subjects`, `grades`, `topics`, `curriculum_topics`, `subtopics`, `curriculum_chunks`, `assessments`, `assessment_selected_questions`, `student_attempts`, `student_responses`, `gap_states`, `student_profiles`

Full schema: `kaihle_v2_1_schema.sql`

---

## What M0 Delivered (Available to Use)

- All 35 tables migrated and ORM models exist
- Auth system fully functional — JWT issued, middleware guards active
- `require_onboarding_complete` dependency implemented
- Student enrollment fires `trigger_onboarding_diagnostics` Celery task
- Tier 1 `assessments` rows exist in DB with `is_system_generated=TRUE` after enrollment
- `check_and_update_onboarding_complete(student_id)` service method implemented

## What M2 Expects From M1

- `gap_states` table populated with real mastery scores for enrolled students
- At least one student has completed all Tier 1 diagnostics (onboarding done)
- `subtopics.embedding` populated in pgvector (required by M2 gap map service)
- `question_bank` has questions across multiple `curriculum_topics` so gap map has data to show
