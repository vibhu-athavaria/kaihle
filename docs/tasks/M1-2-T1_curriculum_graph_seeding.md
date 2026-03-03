# M1-2-T1 — Curriculum Graph Seeding
**Milestone:** M1 — Core Diagnostics Flow
**Epic:** M1-2 — Curriculum Graph & RAG Ingestion
**Task:** T1 of 2 in this epic

---

## Context

This script seeds the entire curriculum hierarchy into the database. It must run before anything else in M1 — question import (M1-1-T1) and PDF ingestion (M1-2-T2) both depend on `subtopics` rows existing.

The hierarchy is: `curricula → curriculum_subjects → subjects → grades → topics → curriculum_topics → subtopics → subtopic_prerequisites`

**Depends on:** M0-2-T1 (migrations — all curriculum tables exist)
**Must run before:** M1-1-T1, M1-2-T2

---

## Files to Create

```
CREATE  backend/scripts/seed_curriculum_graph.py
CREATE  backend/data/curriculum/cambridge_v1.json    ← the seed data
CREATE  backend/tests/unit/test_seed_curriculum_graph.py
```

---

## Database Tables Written

```sql
curricula            -- curriculum boards
subjects             -- academic disciplines
grades               -- grade levels 6–12
curriculum_subjects  -- junction: curriculum ↔ subject
topics               -- named topic units (curriculum-agnostic)
curriculum_topics    -- PIVOT: curriculum + subject + grade + topic
subtopics            -- atomic learning units (embedding populated later in M1-2-T2)
subtopic_prerequisites  -- prerequisite graph
topic_prerequisites     -- prerequisite graph at topic level
```

---

## Seed Data Format (`cambridge_v1.json`)

Structure the JSON as follows. This file must be manually authored — it is the canonical curriculum definition for v1.

```json
{
  "curricula": [
    {
      "code": "cambridge_lower",
      "name": "Cambridge Lower Secondary",
      "description": "Cambridge Lower Secondary curriculum for Grades 6–9",
      "country": null,
      "is_active": true
    },
    {
      "code": "igcse",
      "name": "Cambridge IGCSE",
      "description": "Cambridge IGCSE for Grades 10–12",
      "country": null,
      "is_active": true
    }
  ],
  "subjects": [
    {"code": "MATH", "name": "Mathematics", "icon": "calculator", "color": "#0D9488"},
    {"code": "SCI",  "name": "Science",     "icon": "flask",      "color": "#7C3AED"},
    {"code": "ENG",  "name": "English Language", "icon": "book", "color": "#DC2626"}
  ],
  "grades": [
    {"level": 6,  "name": "Grade 6"},
    {"level": 7,  "name": "Grade 7"},
    {"level": 8,  "name": "Grade 8"},
    {"level": 9,  "name": "Grade 9"},
    {"level": 10, "name": "Grade 10"},
    {"level": 11, "name": "Grade 11"},
    {"level": 12, "name": "Grade 12"}
  ],
  "curriculum_tree": [
    {
      "curriculum_code": "cambridge_lower",
      "subject_code": "MATH",
      "grade_levels": [6, 7, 8, 9],
      "topics": [
        {
          "name": "Number",
          "subtopics": [
            {
              "name": "Integers and Place Value",
              "learning_objectives": "Understand place value for integers up to 10 digits. Order and compare integers.",
              "prerequisites": []
            },
            {
              "name": "Fractions",
              "learning_objectives": "Simplify fractions. Add, subtract, multiply and divide fractions.",
              "prerequisites": ["Integers and Place Value"]
            }
          ]
        },
        {
          "name": "Algebra",
          "subtopics": [
            {
              "name": "Linear Equations",
              "learning_objectives": "Solve linear equations with one unknown. Form equations from word problems.",
              "prerequisites": ["Fractions"]
            },
            {
              "name": "Algebraic Fractions",
              "learning_objectives": "Simplify algebraic fractions. Add and subtract algebraic fractions.",
              "prerequisites": ["Linear Equations", "Fractions"]
            }
          ]
        }
      ]
    }
    // ... repeat for all curriculum/subject/grade combinations
  ]
}
```

**Important:** The `cambridge_v1.json` file must cover all combinations:
- `cambridge_lower` × `MATH`, `SCI`, `ENG` × Grades 6–9
- `igcse` × `MATH`, `SCI`, `ENG` × Grades 10–12

Each topic should have 3–8 subtopics. Each subtopic must have `learning_objectives` (used in LLM prompts later).

---

## Script Logic (`seed_curriculum_graph.py`)

```
Usage: python seed_curriculum_graph.py [--data-file cambridge_v1.json]
```

Insert order (respect FK dependencies):

1. Upsert `curricula` (ON CONFLICT `code` DO NOTHING)
2. Upsert `subjects` (ON CONFLICT `code` DO NOTHING)
3. Upsert `grades` (ON CONFLICT `level` DO NOTHING)
4. For each `curriculum_tree` entry:
   a. Resolve `curriculum_id`, `subject_id`, `grade_id`
   b. Upsert `curriculum_subjects` junction
   c. For each topic:
      - Upsert `topics` (ON CONFLICT `name` DO NOTHING)
      - Upsert `curriculum_topics` (ON CONFLICT `curriculum_id, subject_id, grade_id, topic_id` DO NOTHING)
      - For each subtopic:
        - Upsert `subtopics` with `curriculum_topic_id` FK, `learning_objectives`
        - `embedding` left NULL (populated by M1-2-T2)
5. After all subtopics inserted, process `prerequisites`:
   - For each subtopic with non-empty prerequisites list:
     - Look up prerequisite subtopic_id by name within same curriculum_topic
     - Upsert `subtopic_prerequisites (subtopic_id, prerequisite_id)`

Log stats at end: curricula, subjects, grades, topics, subtopics, prerequisites inserted/skipped.

**Idempotent:** Every insert uses ON CONFLICT DO NOTHING. Re-running is safe.

---

## Acceptance Criteria

### Unit Tests (`test_seed_curriculum_graph.py`)

- [ ] `test_seed_when_valid_json_then_all_tables_populated`
  - Use a minimal JSON with 1 curriculum, 1 subject, 2 grades, 2 topics, 3 subtopics
  - After seed: all rows exist in correct tables

- [ ] `test_seed_when_run_twice_then_no_duplicates`
  - Run seed twice → row counts identical after second run

- [ ] `test_prerequisites_when_subtopic_b_requires_a_then_subtopic_prerequisites_row_exists`

- [ ] `test_prerequisites_when_unknown_prerequisite_name_then_warning_logged_not_crash`

- [ ] `test_subtopic_has_learning_objectives_field`
  - After seed: `subtopics.learning_objectives` is non-null for all rows

### Manual Verification

- [ ] Full `cambridge_v1.json` seeds without errors
- [ ] `SELECT COUNT(*) FROM subtopics` returns expected count (manually verify ~200+ subtopics across all curricula)
- [ ] Every `subtopic` has non-null `curriculum_topic_id` and `learning_objectives`
- [ ] `SELECT COUNT(*) FROM subtopic_prerequisites` > 0

---

## Output of This Task

- `seed_curriculum_graph.py` script
- `cambridge_v1.json` (complete curriculum definition — this is significant manual work, but must be done before any other M1 task)
- All unit tests passing

**Unlocks:** M1-1-T1 (question import), M1-2-T2 (PDF ingestion with embeddings)
