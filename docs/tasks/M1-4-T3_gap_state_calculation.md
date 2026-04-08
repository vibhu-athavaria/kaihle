# M1-4-T3 — Gap State Calculation (Celery Task)
**Milestone:** M1 · **Epic:** M1-4 · **Task:** T3
**Depends on:** M0-2-T2 (ORM models — `gap_states`), M1-4-T1 (attempt submit triggers this task)
**Blocks:** M2-1-T1 (gap map service reads `gap_states` — needs real data)
**Estimated effort:** 3–4 hours

---

## Context

This task creates the Celery task that fires after every attempt submission and
updates the student's mastery scores per curriculum subtopic. It is the core of
Kaihle's diagnostic intelligence — every heatmap cell, study plan assignment, and
lesson plan focus area derives from what this task writes.

The task must be idempotent. If it fires twice for the same `attempt_id` (due to a
retry), it must produce the same final state without creating duplicate rows or
corrupting rolling averages.

The task uses PostgreSQL's `INSERT ... ON CONFLICT DO UPDATE` (upsert) pattern — not
a read-then-write pattern — to avoid race conditions when two attempts for the same
student complete within the same second.

Read CONSTITUTION.md Rule 2 (school_id on every table) and Rule 18 (dead-letter
CRITICAL log on final retry) before writing any code.

---

## User Story

As the system, after a student submits an assessment, I want to update their mastery
score for each curriculum subtopic covered by that assessment so the gap map reflects
their latest performance.

---

## Files to Create

```
backend/app/tasks/gap_tasks.py
backend/app/services/gap_service.py         ← CREATE: upsert logic lives here
backend/app/tests/unit/test_gap_calculation.py
backend/app/tests/integration/test_gap_states_updated.py
```

---

## The Mastery Calculation Algorithm

This algorithm is the source of truth for all mastery scores in Kaihle. Do not
deviate from it.

A student's mastery score for a subtopic is a **recency-weighted moving average**
of their last three attempt scores for that subtopic. An "attempt score" for a
subtopic within one attempt is the mean of all responses for that subtopic in that
attempt. This means if a student answers five questions all mapped to "Algebraic
Fractions" and gets three correct, their attempt score for that subtopic is 0.6.

```
attempt_score_for_subtopic =
    count(is_correct=True for responses in this attempt mapped to subtopic)
    / count(all responses in this attempt mapped to subtopic)

# Confirmed formula — recency-weighted, last 3 attempts:
mastery_score =
    (attempt_n   × 0.5)   # most recent — highest weight
  + (attempt_n-1 × 0.3)   # second most recent
  + (attempt_n-2 × 0.2)   # oldest of the three

# Normalise for fewer than 3 attempts:
1 attempt:  mastery_score = attempt_n × 1.0
2 attempts: mastery_score = (attempt_n × 0.65) + (attempt_n-1 × 0.35)
3+ attempts: full weighted formula above
```

The weighting reflects a key pedagogical insight: a student who failed twice but
just scored 0.9 is more likely to have genuinely understood the material than a
simple average would suggest. Recency carries more weight.

The "last 3" is determined by attempt `completed_at` timestamp, not by attempt ID.

**Enrollment diagnostic seeding:** When an enrollment diagnostic (Tier 1,
`is_system_generated=True`) is the first and only attempt for a student, the
mastery score is seeded at **70% of face value** to reflect reduced confidence
from a single short assessment:

```
enrollment_initial_mastery = attempt_score × 0.7
```

After the first post-lesson quiz or Tier 2 attempt, the normal weighted formula
takes over completely. The 0.7 factor only applies to the seeded state, not to
subsequent recalculations.

---

## Celery Task: `calculate_gap_states`

```python
@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    name="app.tasks.gap_tasks.calculate_gap_states",
)
def calculate_gap_states(self, attempt_id: str) -> dict[str, object]:
    """Update gap_states after a student attempt is submitted.

    Called by: AttemptService.submit_attempt (M1-4-T1)
    Idempotent: safe to call multiple times for the same attempt_id.

    Args:
        attempt_id: UUID string of the completed StudentAttempt.

    Returns:
        Dict with subtopics_updated count and attempt_id.
    """
```

The task uses `asyncio.new_event_loop()` + `run_until_complete()` + `loop.close()`
(the same pattern as `onboarding_tasks.py` from M0-8-T1). Do not use `asyncio.run()`.

The `on_failure` callback must emit a CRITICAL log per CONSTITUTION Rule 18:

```python
def on_failure(self, exc, task_id, args, kwargs, einfo):
    logger.critical(
        "calculate_gap_states_permanently_failed",
        task_id=task_id,
        attempt_id=args[0] if args else kwargs.get("attempt_id"),
        error=str(exc),
        exc_info=True,
    )
```

---

## Task Logic — Step by Step

**Step 1 — Load the attempt.** Verify it exists and has `status="COMPLETED"`. If
the attempt does not exist or is not completed, log at WARNING level and return early
— do not raise, do not retry. This handles the edge case of a task firing before the
DB commit lands.

**Step 2 — Load all StudentResponse rows for this attempt.** Only load rows where
the attempt's assessment has questions mapped to this student. This is a single query:

```python
responses = await db.scalars(
    select(StudentResponse)
    .where(StudentResponse.attempt_id == uuid.UUID(attempt_id))
)
responses = list(responses)
```

If no responses are found, log at WARNING and return early with `{"subtopics_updated": 0}`.

**Step 3 — Map each response to its subtopic.** Each `StudentResponse` has a
`question_id`. Each `QuestionBank` row has a `subtopic_id`. Join them:

```python
question_ids = [r.question_id for r in responses]
questions = await db.scalars(
    select(QuestionBank).where(QuestionBank.id.in_(question_ids))
)
question_map = {q.id: q for q in questions}
```

If a response's `question_id` is not in `question_map` (data integrity issue), log
at ERROR level for that response and skip it — do not crash the whole task.

**Step 4 — Group responses by subtopic and compute attempt scores.**

```python
subtopic_responses: dict[uuid.UUID, list[StudentResponse]] = defaultdict(list)
for response in responses:
    question = question_map.get(response.question_id)
    if question:
        subtopic_responses[question.subtopic_id].append(response)

attempt_scores: dict[uuid.UUID, float] = {}
for subtopic_id, sub_responses in subtopic_responses.items():
    correct = sum(1 for r in sub_responses if r.is_correct)
    attempt_scores[subtopic_id] = correct / len(sub_responses)
```

**Step 5 — For each subtopic, compute the rolling average.**

Load the last 2 completed attempts (before this one) for this student and subtopic.
"Before this one" means `completed_at < current_attempt.completed_at`:

```python
previous_scores = await db.scalars(
    select(StudentAttemptSubtopicScore)  # a helper table or use gap_states history
    .where(
        StudentAttemptSubtopicScore.student_id == attempt.student_id,
        StudentAttemptSubtopicScore.subtopic_id == subtopic_id,
    )
    .order_by(StudentAttemptSubtopicScore.attempted_at.desc())
    .limit(2)
)
```

Note on `StudentAttemptSubtopicScore`: this is a lightweight helper table that must
be created in a new Alembic migration in this task. It stores one row per
`(student_id, subtopic_id, attempt_id)` with the per-attempt score and timestamp.
This avoids recomputing historical scores from `student_responses` on every task run.
The table definition:

```sql
CREATE TABLE student_attempt_subtopic_scores (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subtopic_id UUID NOT NULL REFERENCES subtopics(id) ON DELETE CASCADE,
    attempt_id  UUID NOT NULL REFERENCES student_attempts(id) ON DELETE CASCADE,
    score       FLOAT NOT NULL,
    attempted_at TIMESTAMPTZ NOT NULL,
    UNIQUE (student_id, subtopic_id, attempt_id)
);
CREATE INDEX idx_subtopic_scores_student_sub ON student_attempt_subtopic_scores(student_id, subtopic_id);
```

With the history loaded, compute the recency-weighted mastery score:

```python
history = [row.score for row in previous_scores]
history.append(attempt_scores[subtopic_id])  # add current attempt
recent = history[-3:]  # keep last 3 only

is_enrollment_diagnostic = assessment.is_system_generated

if is_enrollment_diagnostic and len(history) == 1:
    # First-ever score is an enrollment diagnostic — seed at 70% confidence
    new_mastery = recent[0] * 0.7
elif len(recent) == 1:
    new_mastery = recent[0]
elif len(recent) == 2:
    # 2-attempt normalised weights: 0.65 / 0.35
    new_mastery = (recent[-1] * 0.65) + (recent[-2] * 0.35)
else:
    # Full 3-attempt weighted formula: most recent carries highest weight
    new_mastery = (recent[-1] * 0.5) + (recent[-2] * 0.3) + (recent[-3] * 0.2)

# Clamp to valid range
new_mastery = max(0.0, min(1.0, new_mastery))
```

**Step 6 — Upsert the `gap_states` row.** Use PostgreSQL's `ON CONFLICT DO UPDATE`
to make this atomic and safe against concurrent updates. Do not use a read-then-write
pattern.

```python
await db.execute(
    insert(GapState)
    .values(
        id=uuid.uuid4(),
        student_id=attempt.student_id,
        subtopic_id=subtopic_id,
        school_id=attempt_school_id,
        class_id=assessment.class_id,
        mastery_score=new_mastery,
        attempt_count=len(rolling_scores),
        last_assessed_at=attempt.completed_at,
        needs_review=(new_mastery < 0.4),
    )
    .on_conflict_do_update(
        index_elements=["student_id", "subtopic_id"],
        set_={
            "mastery_score": new_mastery,
            "attempt_count": GapState.attempt_count + 1,
            "last_assessed_at": attempt.completed_at,
            "needs_review": (new_mastery < 0.4),
        },
    )
)
```

**Step 7 — Insert the helper row for this attempt's per-subtopic score.**

```python
await db.execute(
    insert(StudentAttemptSubtopicScore)
    .values(
        student_id=attempt.student_id,
        subtopic_id=subtopic_id,
        attempt_id=uuid.UUID(attempt_id),
        score=attempt_scores[subtopic_id],
        attempted_at=attempt.completed_at,
    )
    .on_conflict_do_nothing()   # idempotent: if row exists, skip
)
```

**Step 8 — Commit and return.**

```python
await db.commit()
logger.info(
    "gap_states_updated",
    attempt_id=attempt_id,
    student_id=str(attempt.student_id),
    subtopics_updated=len(attempt_scores),
)
return {"attempt_id": attempt_id, "subtopics_updated": len(attempt_scores)}
```

---

## GapService: `upsert_gap_state`

The upsert logic from Step 6 is encapsulated in `GapService.upsert_gap_state` so
it can be unit-tested independently of the Celery task machinery.

Full signature:

```python
class GapService:

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def upsert_gap_state(
        self,
        student_id: uuid.UUID,
        subtopic_id: uuid.UUID,
        school_id: uuid.UUID,
        class_id: uuid.UUID,
        new_mastery: float,
        rolling_attempt_count: int,
        last_assessed_at: datetime,
    ) -> None:
        """Atomically upsert a gap_state row using ON CONFLICT DO UPDATE.

        This method is safe to call concurrently — it uses PostgreSQL's native
        upsert and will not produce duplicate rows or lost updates.
        """
        ...
```

The Celery task calls this method rather than writing the SQL directly.

---

## Alembic Migration

This task requires a new migration to create `student_attempt_subtopic_scores`.
Run `alembic revision --autogenerate -m "add_student_attempt_subtopic_scores"` and
review the output before committing. The migration must include a `downgrade()` that
drops the table and index.

---

## Acceptance Criteria

**Unit tests — `test_gap_calculation.py`**

Each test below specifies what to set up, what to call, and what to assert.

`test_calculate_when_first_attempt_5_questions_all_correct_then_mastery_1_0` — Create
a completed attempt with 5 responses all `is_correct=True` mapped to one subtopic.
Call the gap calculation logic (extracted into a pure function for testability). Assert
`gap_state.mastery_score == 1.0` and `attempt_count == 1`.

`test_calculate_when_first_attempt_3_of_5_correct_then_mastery_0_6` — 3 correct out
of 5. Assert `mastery_score == 0.6`.

`test_calculate_when_second_attempt_higher_score_then_mastery_is_average` — First
attempt score 0.4, second attempt score 0.8. Assert `mastery_score == 0.6` (average
of two).

`test_calculate_when_four_attempts_then_only_last_three_count` — Scores: [0.2, 0.4,
0.6, 0.8]. After the fourth attempt, assert `mastery_score == 0.6` (average of
0.4, 0.6, 0.8 — the oldest 0.2 drops off).

`test_calculate_when_multiple_subtopics_then_each_updated_independently` — Create an
attempt with 4 questions: 2 mapped to subtopic A, 2 mapped to subtopic B. Both
correct for A, both wrong for B. Assert `gap_states` for subtopic A has
`mastery_score == 1.0` and subtopic B has `mastery_score == 0.0`.

`test_calculate_when_response_has_unknown_question_id_then_skipped_not_crashed` —
Insert a `StudentResponse` with a `question_id` that does not exist in `question_bank`.
Assert the task completes successfully and an ERROR log is emitted for that response.

`test_upsert_gap_state_when_called_twice_same_values_then_one_row_only` — Call
`GapService.upsert_gap_state` twice with identical parameters. Assert exactly one row
exists in `gap_states` for `(student_id, subtopic_id)`.

`test_upsert_gap_state_when_called_twice_different_values_then_row_updated` — Call
once with `mastery_score=0.4`, then again with `mastery_score=0.8`. Assert the single
row has `mastery_score=0.8`.

`test_needs_review_when_mastery_below_0_4_then_true` — Assert `needs_review=True` when
`mastery_score=0.39`.

`test_needs_review_when_mastery_at_0_4_then_false` — Boundary: `mastery_score=0.4`
should set `needs_review=False` (0.4 is the Developing threshold — not Needs Work).

**Integration tests — `test_gap_states_updated.py`**

`test_gap_states_updated_within_reasonable_time_after_submit` — Submit a complete
attempt via the API, wait up to 5 seconds (with polling), then query `gap_states`
directly. Assert at least one row exists for the student with a non-null `mastery_score`.

`test_gap_states_correct_after_submit_10_correct_of_10` — Submit 10 correct answers.
After the Celery task runs, assert `mastery_score == 1.0` for each subtopic covered.

`test_celery_task_idempotent_when_called_twice` — Call `calculate_gap_states.delay`
twice with the same `attempt_id`. Assert the final `gap_states` row is the same as
after one call (no doubled counts, no duplicate rows).

---

## Do NOT Touch

`backend/app/tasks/onboarding_tasks.py` — do not modify.
`backend/app/services/assessment_service.py` — do not modify.
`backend/app/schemas/` — do not modify any existing schema file.
Any existing Alembic migration — only add a new one.
