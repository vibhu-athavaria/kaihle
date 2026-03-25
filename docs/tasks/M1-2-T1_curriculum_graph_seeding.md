# M1-2-T1 — Curriculum Graph Seeding
**Milestone:** M1 — Core Diagnostics Flow
**Epic:** M1-2 — Curriculum Graph & RAG Ingestion
**Task:** T1 of 2 in this epic

> **⚠️ AMENDMENT — March 2026**
> Grade boundaries corrected to match academic reality (confirmed by Vidhya, approved by Vibhu).
> Original spec had `cambridge_lower = Grades 6–9` and `igcse = Grades 10–12` — BOTH WRONG.
> Science subjects split at IGCSE: `SCI` (integrated) is Lower Secondary only.
> `BIO`, `CHEM`, `PHY` are IGCSE only. `ENGL` (English Literature) added as non-core IGCSE.
> CONSTITUTION.md §1 updated to match. All scripts must use these boundaries.

> **📝 VIDHYA REVIEW (M1-2-T3) — 2026-03-25**
> `cambridge_v1.json` was reviewed and approved by Vidhya on 2026-03-25 per M1-2-T3.
> **Do NOT modify cambridge_v1.json without a new Vidhya review.**
> Verified: Trigonometry only in IGCSE (Grade 9-10), Statistics named correctly as "Statistics and Probability",
> ENGL is Literature (not Language), SCI topics appropriate for integrated science.

---

## Context

This script seeds the entire curriculum hierarchy into the database. It must run before
anything else in M1 — question import (M1-1-T1) and PDF ingestion (M1-2-T2) both depend
on `subtopics` rows existing.

Hierarchy: `curricula → curriculum_subjects → subjects → grades → topics → curriculum_topics → subtopics`

**Depends on:** M0-2-T1 (migrations — all curriculum tables exist)
**Must run before:** M1-1-T1, M1-2-T2

---

## Files to Create

```
CREATE  backend/scripts/seed_curriculum_graph.py
CREATE  backend/data/curriculum/cambridge_v1.json    ← already authored, do NOT regenerate
CREATE  backend/tests/unit/test_seed_curriculum_graph.py
```

---

## Database Tables Written

```sql
curricula            -- 2 rows: cambridge_lower, igcse
subjects             -- 7 rows: MATH, SCI, ENG, BIO, CHEM, PHY, ENGL
grades               -- 7 rows: levels 6–12
curriculum_subjects  -- 9 rows: explicit curriculum ↔ subject bindings
topics               -- ~35 unique topic strands (curriculum-agnostic)
curriculum_topics    -- 21 entries × avg 4 topics = ~84 rows
subtopics            -- 193 rows (embedding=NULL, populated in M1-2-T2)
subtopic_prerequisites -- prerequisite graph rows (inline in JSON)
```

---

## Authoritative Curriculum Map

### Programme Boundaries (CORRECTED)

| code              | name                       | Grades | Notes                             |
|-------------------|----------------------------|--------|-----------------------------------|
| `cambridge_lower` | Cambridge Lower Secondary  | 6, 7, 8 | 3-year programme (Stages 7–9)   |
| `igcse`           | Cambridge IGCSE            | 9, 10   | 2-year programme (Years 10–11)  |

### Subject Codes and Curriculum Binding

| code   | name                | cambridge_lower | igcse  | is_core |
|--------|---------------------|-----------------|--------|---------|
| `MATH` | Mathematics         | ✓               | ✓      | true    |
| `SCI`  | Integrated Science  | ✓               | ✗      | true    |
| `ENG`  | English Language    | ✓               | ✓      | true    |
| `BIO`  | Biology             | ✗               | ✓      | true    |
| `CHEM` | Chemistry           | ✗               | ✓      | true    |
| `PHY`  | Physics             | ✗               | ✓      | true    |
| `ENGL` | English Literature  | ✗               | ✓      | false   |

**Rule enforced by `curriculum_subjects` table:**
- `SCI` MUST NOT appear under `igcse`
- `BIO`, `CHEM`, `PHY`, `ENGL` MUST NOT appear under `cambridge_lower`

### Curriculum Tree — 21 Entries

| curriculum_code   | subject_code | grade_level |
|-------------------|--------------|-------------|
| cambridge_lower   | MATH         | 6           |
| cambridge_lower   | MATH         | 7           |
| cambridge_lower   | MATH         | 8           |
| cambridge_lower   | SCI          | 6           |
| cambridge_lower   | SCI          | 7           |
| cambridge_lower   | SCI          | 8           |
| cambridge_lower   | ENG          | 6           |
| cambridge_lower   | ENG          | 7           |
| cambridge_lower   | ENG          | 8           |
| igcse             | MATH         | 9           |
| igcse             | MATH         | 10          |
| igcse             | BIO          | 9           |
| igcse             | BIO          | 10          |
| igcse             | CHEM         | 9           |
| igcse             | CHEM         | 10          |
| igcse             | PHY          | 9           |
| igcse             | PHY          | 10          |
| igcse             | ENG          | 9           |
| igcse             | ENG          | 10          |
| igcse             | ENGL         | 9           |
| igcse             | ENGL         | 10          |

---

## Seed Data Format (`cambridge_v1.json`)

The file is at `backend/data/curriculum/cambridge_v1.json`.
**Do NOT regenerate** — it is the canonical curriculum definition authored by Vidhya.
Each `curriculum_tree` entry uses **`grade_level` (singular integer)**, not an array.

```json
{
  "_meta": { ... },
  "curricula": [ { "code": "cambridge_lower", ... }, { "code": "igcse", ... } ],
  "subjects": [ { "code": "MATH", "name": "Mathematics", "icon": "calculator", "color": "#0D9488" }, ... ],
  "grades": [ { "level": 6, "name": "Grade 6" }, ... ],
  "curriculum_subjects": [
    { "curriculum_code": "cambridge_lower", "subject_code": "MATH", "is_core": true, "sort_order": 1 },
    ...
  ],
  "curriculum_tree": [
    {
      "curriculum_code": "cambridge_lower",
      "subject_code": "MATH",
      "grade_level": 6,
      "standard_code_prefix": "6M",
      "topics": [
        {
          "name": "Number",
          "canonical_code": "MATH-NUM",
          "sequence_order": 1,
          "recommended_weeks": 7,
          "learning_objectives": ["...", "..."],
          "subtopics": [
            {
              "name": "Integers and Place Value",
              "canonical_code": "MATH-NUM-G6-01",
              "learning_objective": "Understand the value of each digit in integers...",
              "bloom_taxonomy_level": "Understand",
              "difficulty_level": 1,
              "estimated_minutes": 50,
              "sequence_order": 1,
              "prerequisites": []
            }
          ]
        }
      ]
    }
  ]
}
```

---

## Script Logic (`seed_curriculum_graph.py`)

```
Usage: python seed_curriculum_graph.py [--data-file path/to/cambridge_v1.json]
Default data file: backend/data/curriculum/cambridge_v1.json
```

### Insert Order (respect FK dependencies)

```
1. Upsert `curricula`           ON CONFLICT (code) DO NOTHING
2. Upsert `subjects`            ON CONFLICT (code) DO NOTHING
3. Upsert `grades`              ON CONFLICT (level) DO NOTHING
4. Upsert `curriculum_subjects` from top-level "curriculum_subjects" array
     ON CONFLICT (curriculum_id, subject_id) DO NOTHING
5. For each entry in "curriculum_tree":
   a. Resolve curriculum_id, subject_id, grade_id via code/level lookups
   b. For each topic:
      - Upsert `topics`           ON CONFLICT (canonical_code) DO NOTHING
      - Upsert `curriculum_topics` with all metadata fields
          ON CONFLICT (curriculum_id, subject_id, grade_id, topic_id) DO NOTHING
      - For each subtopic:
          Upsert `subtopics` with curriculum_topic_id FK
            embedding = NULL  (populated by M1-2-T2)
          ON CONFLICT (canonical_code) DO NOTHING
6. After ALL subtopics inserted, resolve prerequisites:
   - For each subtopic with non-empty "prerequisites" list:
     - Look up prerequisite subtopic by canonical_code within same curriculum_topic
     - Upsert subtopic_prerequisites (subtopic_id, prerequisite_subtopic_id)
       ON CONFLICT DO NOTHING
7. Log final stats
```

### Key Implementation Notes

- **`topics` table is curriculum-agnostic.** The same `canonical_code` (e.g. `MATH-NUM`)
  maps to one `topics` row, reused across all grades and curricula via separate
  `curriculum_topics` rows. Use `ON CONFLICT (canonical_code) DO NOTHING` — do not
  create duplicate topic rows.
- **`curriculum_subjects` is seeded from the top-level array**, NOT inferred from
  `curriculum_tree`. This is intentional — it enforces the subject binding rules above.
- **`subtopics.learning_objective` is singular (TEXT NOT NULL).** The JSON field is
  also `learning_objective` (singular). Map it directly.
- **`curriculum_topics.learning_objectives` is plural (TEXT[] ARRAY).** Map from the
  topic-level `learning_objectives` array in the JSON.
- **Prerequisites are resolved by `canonical_code`, not by name.** The JSON
  `prerequisites` field contains canonical_codes of prerequisite subtopics.
  If a prerequisite canonical_code is not found, log a WARNING and skip — do not crash.

### Idempotency

Every insert uses `ON CONFLICT DO NOTHING`. Re-running the script on an already-seeded
database produces zero new inserts and exits cleanly.

---

## Acceptance Criteria

### Unit Tests (`test_seed_curriculum_graph.py`)

- [ ] `test_seed_when_valid_json_then_all_tables_populated`
      Use minimal JSON: 1 curriculum, 2 subjects, 2 grades, 2 topics, 4 subtopics.
      After seed: all rows exist in correct tables with correct FK links.

- [ ] `test_seed_when_run_twice_then_no_duplicates`
      Run seed twice → row counts identical after second run.

- [ ] `test_curriculum_subjects_binding_respected`
      After seeding cambridge_v1.json: SCI does NOT appear under igcse.
      BIO, CHEM, PHY, ENGL do NOT appear under cambridge_lower.

- [ ] `test_topics_are_deduplicated_across_grades`
      MATH-NUM appears in multiple grades → only ONE row in `topics` table.
      Multiple rows in `curriculum_topics` (one per grade/curriculum combo).

- [ ] `test_prerequisites_when_subtopic_b_requires_a_then_row_exists`
      After seed: `subtopic_prerequisites` row exists for a known prerequisite pair.

- [ ] `test_prerequisites_when_unknown_canonical_code_then_warning_logged_not_crash`

- [ ] `test_subtopics_learning_objective_is_non_null`
      Every seeded subtopic has a non-null `learning_objective`.

- [ ] `test_subtopics_embedding_is_null`
      Every seeded subtopic has `embedding = NULL` (populated in M1-2-T2).

### Manual Verification After Full Seed

```sql
-- Counts to verify
SELECT COUNT(*) FROM curricula;            -- expected: 2
SELECT COUNT(*) FROM subjects;             -- expected: 7
SELECT COUNT(*) FROM grades;               -- expected: 7 (levels 6-12)
SELECT COUNT(*) FROM curriculum_subjects;  -- expected: 9
SELECT COUNT(*) FROM topics;               -- expected: ~35
SELECT COUNT(*) FROM curriculum_topics;    -- expected: ~84
SELECT COUNT(*) FROM subtopics;            -- expected: 193
SELECT COUNT(*) FROM subtopic_prerequisites; -- expected: > 0

-- Verify SCI is NOT linked to igcse
SELECT cs.* FROM curriculum_subjects cs
JOIN curricula c ON c.id = cs.curriculum_id
JOIN subjects s ON s.id = cs.subject_id
WHERE c.code = 'igcse' AND s.code = 'SCI';  -- must return 0 rows

-- Verify BIO/CHEM/PHY are NOT linked to cambridge_lower
SELECT cs.* FROM curriculum_subjects cs
JOIN curricula c ON c.id = cs.curriculum_id
JOIN subjects s ON s.id = cs.subject_id
WHERE c.code = 'cambridge_lower' AND s.code IN ('BIO','CHEM','PHY','ENGL');  -- 0 rows
```

---

## Output of This Task

- `seed_curriculum_graph.py` — idempotent seeder script
- `cambridge_v1.json` — already exists at `backend/data/curriculum/cambridge_v1.json`
- All unit tests passing
- Manual verification queries return expected counts

**Unlocks:** M1-1-T1 (question import), M1-2-T2 (PDF ingestion with embeddings)
