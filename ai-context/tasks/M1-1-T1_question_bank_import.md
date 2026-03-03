# M1-1-T1 — Question Bank Import Script
**Milestone:** M1 — Core Diagnostics Flow
**Epic:** M1-1 — Question Bank Import
**Task:** T1 of 1 in this epic

---

## Context

The founder has 7,000 existing curriculum-aligned questions. This task imports them into the `question_bank` table. The import script must resolve each question's `subtopic_id` by joining through the curriculum hierarchy that was seeded in M1-2-T1.

**IMPORTANT:** Run `seed_curriculum_graph.py` (M1-2-T1) BEFORE this script. It will fail without the curriculum hierarchy in place.

**Depends on:** M0-2-T1 (migrations), M1-2-T1 (curriculum graph seeded)

---

## Files to Create

```
CREATE  backend/scripts/import_questions.py
CREATE  backend/data/questions/sample_questions.json    ← 5 sample questions for testing
CREATE  backend/tests/unit/test_import_questions.py
```

---

## Database Tables Used

```sql
-- question_bank (write target)
id               UUID PRIMARY KEY DEFAULT gen_random_uuid()
subtopic_id      UUID NOT NULL REFERENCES subtopics(id)
topic_id         UUID NOT NULL REFERENCES topics(id)          -- denormalised
subject_id       UUID NOT NULL REFERENCES subjects(id)        -- denormalised
grade_id         UUID NOT NULL REFERENCES grades(id)          -- denormalised
question_text    TEXT NOT NULL
question_type    question_type_enum   -- MCQ | TRUE_FALSE | SHORT_ANSWER
options          JSONB                -- [{"key":"A","text":"..."},...] or NULL
correct_answer   TEXT NOT NULL
explanation      TEXT
difficulty_level FLOAT                -- 1.0–5.0
bloom_taxonomy   VARCHAR(50)
canonical_form   TEXT UNIQUE          -- deduplication key
source           VARCHAR(10) DEFAULT 'BANK'
is_active        BOOLEAN DEFAULT TRUE

-- Read-only lookups (must exist from M1-2-T1 seed)
curricula, subjects, grades, topics, curriculum_topics, subtopics
```

---

## Input Format

Accept both CSV and JSON. JSON is preferred for richer structure.

### JSON format (`questions.json`):
```json
[
  {
    "question_text": "What is the value of x in 2x + 4 = 12?",
    "question_type": "MCQ",
    "options": [
      {"key": "A", "text": "3"},
      {"key": "B", "text": "4"},
      {"key": "C", "text": "5"},
      {"key": "D", "text": "6"}
    ],
    "correct_answer": "B",
    "explanation": "2x = 12 - 4 = 8, so x = 4",
    "difficulty_level": 2.0,
    "bloom_taxonomy": "Apply",
    "curriculum_code": "cambridge_lower",
    "subject_code": "MATH",
    "grade_level": 8,
    "topic_name": "Algebra",
    "subtopic_name": "Linear Equations"
  }
]
```

### CSV format (alternative):
Columns: `question_text, question_type, options_json, correct_answer, explanation, difficulty_level, bloom_taxonomy, curriculum_code, subject_code, grade_level, topic_name, subtopic_name`

---

## Script Logic (`import_questions.py`)

```
Usage: python import_questions.py --file questions.json [--format json|csv] [--dry-run]
```

For each question:

1. **Resolve `subtopic_id`:**
   ```
   curricula WHERE code = curriculum_code → curriculum_id
   subjects  WHERE code = subject_code   → subject_id
   grades    WHERE level = grade_level   → grade_id
   topics    WHERE name = topic_name     → topic_id
   curriculum_topics WHERE curriculum_id + subject_id + grade_id + topic_id → ct_id
   subtopics WHERE curriculum_topic_id = ct_id AND name = subtopic_name → subtopic_id
   ```
   If any step fails → log warning with row number + reason → skip row → continue

2. **Compute `canonical_form`:**
   ```python
   canonical_form = hashlib.sha256(
       question_text.strip().lower().encode()
   ).hexdigest()
   ```
   Used for deduplication — `UNIQUE` constraint on `canonical_form`.

3. **Insert** into `question_bank` with `source='BANK'`
   - On conflict (`canonical_form`) → skip (do not update)

4. **Log stats** at the end:
   ```
   Total rows:    7142
   Inserted:      7000
   Skipped (dup): 100
   Skipped (err): 42
   Errors logged: backend/logs/import_errors.log
   ```

5. **`--dry-run` flag:** resolve and validate all rows, print stats, make NO DB writes.

---

## Acceptance Criteria

### Unit Tests (`test_import_questions.py`)

- [ ] `test_import_when_valid_json_then_5_questions_inserted`
  - Use 5 sample questions from `sample_questions.json`
  - All 5 inserted, `subtopic_id` correctly resolved

- [ ] `test_import_when_duplicate_canonical_form_then_skipped_not_errored`
  - Insert same question twice → only 1 row in DB, no exception

- [ ] `test_import_when_unknown_subtopic_name_then_row_skipped_and_logged`
  - Question with `subtopic_name: "Nonexistent Topic"` → skipped, logged

- [ ] `test_import_when_unknown_curriculum_code_then_row_skipped_and_logged`

- [ ] `test_import_when_dry_run_then_no_db_writes`
  - `--dry-run` → stats printed, `question_bank` count unchanged

- [ ] `test_canonical_form_when_same_text_different_whitespace_then_same_hash`
  - `"  What is x?  "` and `"what is x?"` → same `canonical_form`

### Manual Verification

- [ ] Script runs against real 7,000 question file without crashing
- [ ] Re-running produces 0 new inserts (fully idempotent)
- [ ] Every inserted question has non-null `subtopic_id`, `topic_id`, `subject_id`, `grade_id`

---

## Output of This Task

- `import_questions.py` script
- `sample_questions.json` (5 questions covering Math, Science, English across 2 grades)
- All unit tests passing

**Next tasks (parallel):** M1-2-T2 (PDF ingestion also uses subtopics), M1-3-T1 (assessment service queries question_bank)
