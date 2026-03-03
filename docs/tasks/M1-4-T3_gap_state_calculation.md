# M1-4-T3 — Gap State Calculation (Celery Task)
**Milestone:** M1 · **Epic:** M1-4 · **Task:** T3
**Depends on:** M0-2-T2 (ORM models — `gap_states`), M1-4-T2 (scoring service — responses must be scored before gaps can be calculated)
**Triggered by:** M1-4-T1 (attempt submit endpoint)

---

## User Story
As the system, after a student submits an assessment, I want to update their mastery scores per subtopic so the gap map reflects their latest performance.

---

## Files to Create / Modify

```
backend/app/tasks/gap_tasks.py
backend/app/services/gap_service.py          # add: upsert_gap_state()
backend/tests/unit/test_gap_calculation.py
backend/tests/integration/test_gap_states_updated.py
```

---

## Celery Task

```python
# backend/app/tasks/gap_tasks.py

@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def calculate_gap_states(self, attempt_id: str):
    """
    Fired after every student attempt submission.
    Reads all scored responses for the attempt.
    Upserts gap_states for each subtopic touched.
    """
```

---

## Calculation Logic

```
1. Load all student_responses for attempt_id WHERE scored_by IN ('RULE', 'LLM')
   - Skip PENDING responses (LLM not yet returned)
   - If all responses are PENDING, re-queue this task with 30s delay

2. For each response:
   - Get subtopic_id via: question_bank.subtopic_id
   - Group responses by subtopic_id

3. For each subtopic_id group:
   - Load existing gap_state for (student_id, subtopic_id)
   - Compute new mastery_score:

     ROLLING AVERAGE of last 3 attempt scores for this subtopic:
       scores_history = load_last_3_attempt_scores(student_id, subtopic_id)
       # = list of per-attempt average scores, oldest first
       this_attempt_score = mean(responses in this group)
       scores_history.append(this_attempt_score)
       new_mastery = mean(scores_history[-3:])  # last 3 attempts

   - Update gap_state row (upsert):
       mastery_score = new_mastery
       attempt_count += 1
       total_correct += count(is_correct=True in group)
       total_attempted += count(responses in group)
       confidence = min(1.0, attempt_count / 5)  # confidence grows with attempts
       last_assessed_at = now()
       needs_review = (new_mastery < 0.4)

4. On DB error: retry up to 3 times
```

---

## `gap_service.upsert_gap_state()`

```python
async def upsert_gap_state(
    student_id: UUID,
    subtopic_id: UUID,
    school_id: UUID,
    class_id: UUID,
    new_mastery: float,
    correct_count: int,
    attempted_count: int,
    db: AsyncSession
) -> GapState:
    """
    INSERT ... ON CONFLICT (student_id, subtopic_id) DO UPDATE
    """
```

Use PostgreSQL upsert (`ON CONFLICT DO UPDATE`) not a read-then-write pattern — avoids race conditions if multiple tasks run concurrently.

---

## Key DB Details

```sql
-- gap_states unique constraint (check kaihle_v2_1_schema.sql):
UNIQUE (student_id, subtopic_id)

-- Fields to upsert:
mastery_score     FLOAT
confidence        FLOAT (0.0–1.0)
attempt_count     INT
total_correct     INT
total_attempted   INT
needs_review      BOOLEAN
last_assessed_at  TIMESTAMPTZ
class_id          UUID   -- update to latest class (student may switch classes)
school_id         UUID
```

---

## Acceptance Criteria

- [ ] First attempt, 3 questions on same subtopic: mastery = mean of those 3 scores
- [ ] Second attempt on same subtopic: rolling avg of 2 attempt averages
- [ ] Third+ attempt: rolling avg capped at last 3 attempt scores
- [ ] `confidence` = `min(1.0, attempt_count / 5)` — grows to 1.0 after 5 attempts
- [ ] `needs_review = True` when mastery < 0.4
- [ ] Questions with `scored_by=PENDING` excluded from calculation
- [ ] If ALL responses are PENDING: task re-queues itself with 30s delay
- [ ] Gap states updated within 5 seconds of attempt submission
- [ ] Subtopic with 0 scored responses: no gap_state row created / updated
- [ ] Task retries up to 3 times on DB error

---

## Tests to Write

```python
test_calculate_gap_states_when_first_attempt_then_mastery_is_mean()
test_calculate_gap_states_when_second_attempt_then_rolling_avg()
test_calculate_gap_states_when_third_attempt_then_last_3_only()
test_calculate_gap_states_when_mastery_below_04_then_needs_review_true()
test_calculate_gap_states_when_pending_responses_then_excluded()
test_calculate_gap_states_when_all_pending_then_task_requeued()
test_calculate_gap_states_when_db_error_then_task_retries()
test_upsert_gap_state_when_row_exists_then_updated_not_duplicated()
test_confidence_when_5_attempts_then_confidence_1()
```
