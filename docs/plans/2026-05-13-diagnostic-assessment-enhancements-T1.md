# T1 — Assessment Schema Migration
**Branch:** `feat/diagnostic-enhancements-T1_migration/assessment-schema-v2`
**Parent:** `main`
**Executor:** Coding agent
**Status:** Ready

---

## What This Task Does

Replaces the `config` JSONB blob and dead `is_system_generated` / `diagnostic_topic_ids` columns on
the `assessments` table with properly-typed columns. Adds a new `assessment_topic_config` junction
table for per-assessment topic selection (supports prior-grade topics). Backfills existing rows from
`config` before dropping it.

---

## Schema Changes

### Columns ADDED to `assessments`

| Column | Type | Nullable | Default | Constraint |
|---|---|---|---|---|
| `time_limit_minutes` | Integer | No | 0 | CHECK >= 0 · 0 means untimed |
| `question_types` | ARRAY(Text) | No | `['MCQ', 'TRUE_FALSE']` | — |
| `minimum_difficulty` | Integer | No | 1 | CHECK >= 1 |
| `maximum_difficulty` | Integer | No | 5 | CHECK <= 5 |
| `questions_per_topic` | Integer | No | 2 | CHECK >= 1 |

### Columns DROPPED from `assessments`

- `config` JSONB — backfill before drop (see migration logic below)
- `is_system_generated` BOOLEAN — always FALSE, dead code
- `diagnostic_topic_ids` UUID[] — replaced by `assessment_topic_config`
- `curriculum_topic_id` UUID FK — also vestigial (was for single-topic assessments, no longer used)

### New table `assessment_topic_config`

```sql
CREATE TABLE assessment_topic_config (
    assessment_id       UUID NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    curriculum_topic_id UUID NOT NULL REFERENCES curriculum_topics(id) ON DELETE RESTRICT,
    grade_id            UUID NOT NULL REFERENCES grades(id) ON DELETE RESTRICT,
    PRIMARY KEY (assessment_id, curriculum_topic_id)
);
CREATE INDEX idx_atc_assessment ON assessment_topic_config(assessment_id);
```

---

## Backfill Strategy (in the migration's `upgrade()`)

Run these SQL updates BEFORE dropping `config`:

```sql
-- minimum_difficulty from config['difficulty_range'][0], else 1
UPDATE assessments
SET minimum_difficulty = COALESCE((config->>'difficulty_range')::jsonb->0)::int, 1)
WHERE config ? 'difficulty_range';

-- maximum_difficulty from config['difficulty_range'][1], else 5
UPDATE assessments
SET maximum_difficulty = COALESCE(((config->>'difficulty_range')::jsonb->1)::int, 5)
WHERE config ? 'difficulty_range';

-- question_types from config['question_types'], else ['MCQ']
UPDATE assessments
SET question_types = ARRAY(
    SELECT jsonb_array_elements_text(config->'question_types')
)
WHERE config ? 'question_types' AND jsonb_array_length(config->'question_types') > 0;

-- time_limit_minutes: 0 = untimed. Backfill from config where a real value was set.
UPDATE assessments
SET time_limit_minutes = COALESCE(
    NULLIF((config->>'time_limit_minutes'), 'null')::int,
    0
);
```

Backfill `assessment_topic_config` from `diagnostic_topic_ids`:

```sql
INSERT INTO assessment_topic_config (assessment_id, curriculum_topic_id, grade_id)
SELECT
    a.id,
    topic_id,
    ct.grade_id
FROM assessments a,
     UNNEST(a.diagnostic_topic_ids) AS topic_id
JOIN curriculum_topics ct ON ct.id = topic_id
WHERE a.diagnostic_topic_ids IS NOT NULL;
```

Then DROP `config`, `is_system_generated`, `diagnostic_topic_ids`, `curriculum_topic_id`.

The `downgrade()` must re-add `config` as JSONB with `default={}` and restore the dropped columns
as nullable (data loss is acceptable on downgrade — document this explicitly in the migration file).

---

## Model Changes

**`backend/app/models/assessment.py`**

1. Remove `is_system_generated`, `diagnostic_topic_ids`, `curriculum_topic_id`, `config` mapped columns.
2. Add `time_limit_minutes`, `question_types`, `minimum_difficulty`, `maximum_difficulty`, `questions_per_topic` mapped columns (with CheckConstraints).
3. Add new `AssessmentTopicConfig` ORM model with `assessment_id`, `curriculum_topic_id`, `grade_id`.

Remove the `is_system_generated` field from `AssessmentResponse` and `AssessmentWithClassResponse`
schemas (`backend/app/schemas/assessments.py`). Update `topic_ids` field in response schemas to be
populated from `assessment_topic_config` rows.

---

## Acceptance Criteria

- [ ] `alembic upgrade head` runs clean on a fresh DB with seed data.
- [ ] `alembic downgrade -1` runs without error (data loss on downgrade is acceptable and documented).
- [ ] All existing rows have correct values in new columns after backfill.
- [ ] `assessment_topic_config` is populated for any existing diagnostic with `diagnostic_topic_ids`.
- [ ] `config`, `is_system_generated`, `diagnostic_topic_ids`, `curriculum_topic_id` columns do not exist after migration.
- [ ] `AssessmentResponse` schema no longer includes `is_system_generated`.
- [ ] All unit and integration tests pass after model/schema updates.

---

## TDD Spec

**Test file:** `backend/app/tests/unit/test_assessment_schema_migration.py` (new)

```python
def test_assessment_model_has_no_config_column_when_<condition>_then_<expected>():
    # Arrange: instantiate Assessment() without config kwarg
    # Act: create instance, check attributes
    # Assert: hasattr(assessment, 'config') is False

def test_assessment_model_has_typed_difficulty_columns_when_defaults_applied_then_correct_values():
    # Arrange: Assessment() with no difficulty args
    # Act: check minimum_difficulty, maximum_difficulty
    # Assert: minimum_difficulty == 1, maximum_difficulty == 5

def test_assessment_topic_config_model_when_created_then_persists_grade_id():
    # Arrange: AssessmentTopicConfig with valid assessment_id, curriculum_topic_id, grade_id
    # Act: db.add + flush
    # Assert: row queryable with correct grade_id

def test_assessment_topic_config_primary_key_when_duplicate_then_raises_integrity_error():
    # Arrange: two AssessmentTopicConfig rows with same (assessment_id, curriculum_topic_id)
    # Act: db.add_all + flush
    # Assert: IntegrityError raised
```

**Update existing tests** in:
- `test_assessment_service_tier1.py` — remove any assertions on `assessment.config` or `assessment.is_system_generated`; replace with `minimum_difficulty`, `maximum_difficulty` assertions.
- `test_onboarding_tasks.py:149` — remove `assessment.config["max_questions_per_attempt"]` assertion; replace with `assessment.question_count`.
- `test_tier1_trigger.py:177` — same replacement.

---

## Files Changed

```
backend/app/models/assessment.py
backend/app/schemas/assessments.py
backend/alembic/versions/<new_migration>.py   ← generated, not hand-written
backend/app/tests/unit/test_assessment_schema_migration.py   ← new
backend/app/tests/unit/test_assessment_service_tier1.py      ← updated
backend/app/tests/unit/test_onboarding_tasks.py              ← updated
backend/app/tests/integration/test_tier1_trigger.py          ← updated
```
