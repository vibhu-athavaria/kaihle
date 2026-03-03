# M1-4-T1 — Student Attempt API
**Milestone:** M1 · **Epic:** M1-4 · **Task:** T1
**Depends on:** M1-3-T2 (assessment routes), M1-4-T2 (scoring service), M1-4-T3 (gap state task), M0-6-T3 (onboarding completion service)

---

## User Story
As a student, I want API endpoints to start an assessment, submit my answers, and see my results so I can complete diagnostics and practice quizzes.

---

## Files to Create / Modify

```
backend/app/services/attempt_service.py
backend/app/api/v1/routes/attempts.py
backend/app/schemas/attempt.py
backend/tests/integration/test_attempt_api.py
```

---

## Endpoints

### `POST /api/v1/assessments/{assessment_id}/start`
Auth: Student (enrolled in assessment's class)
```
Returns: AttemptResponse (201 Created)
```

Logic:
```
1. Verify assessment is ACTIVE
2. Verify student is enrolled in assessment's class
3. Check for existing attempt:
   - If IN_PROGRESS → return existing attempt (idempotent)
   - If COMPLETED → return 409 "Already completed"
   - If NOT_STARTED or none → create new student_attempts row
4. Load questions (without correct_answer) in randomised order
5. Return { attempt_id, assessment_id, questions: [...], started_at }
```

---

### `POST /api/v1/attempts/{attempt_id}/responses`
Auth: Student (own attempt only)
```
Body: {
  "question_id": UUID,
  "answer_given": str,
  "time_taken_ms": int
}
Returns: {
  "response_id": UUID,
  "scored": bool,       # true if rule-based (immediate), false if LLM (async)
  "is_correct": bool | null,   # null if scored=false (async)
  "score": float | null
}
```

Logic:
```
1. Validate attempt is IN_PROGRESS and belongs to current student
2. Validate question belongs to this assessment
3. Prevent duplicate response (same question answered twice → 409)
4. Score via scoring_service.score_response(question, answer_given):
   - MCQ/TRUE_FALSE → immediate rule-based
   - SHORT_ANSWER → store with scored_by='PENDING', queue LLM scoring task
5. Insert student_responses row
6. Return scoring result
```

---

### `POST /api/v1/attempts/{attempt_id}/submit`
Auth: Student (own attempt only)
```
Returns: {
  "attempt_id": UUID,
  "status": "COMPLETED",
  "score_summary": {
    "total_questions": int,
    "answered": int,
    "correct": int,
    "score_pct": float
  }
}
```

Logic:
```
1. Validate attempt is IN_PROGRESS
2. Mark attempt: status='COMPLETED', completed_at=now()
3. Calculate score_summary from student_responses
4. Fire Celery: calculate_gap_states.delay(str(attempt_id))
5. CRITICAL (v2.1): If assessment.is_system_generated == TRUE:
     await onboarding_service.check_and_update_onboarding_complete(student_id)
6. Return score_summary
```

The onboarding check (step 5) is synchronous — fast DB query, not a Celery task.

---

### `GET /api/v1/attempts/{attempt_id}/results`
Auth: Student (own only) | Teacher (any attempt in own class) | Parent (own child)
```
Returns: {
  "attempt_id": UUID,
  "assessment_id": UUID,
  "student_id": UUID,
  "status": str,
  "score_summary": { ... },
  "responses": [
    {
      "question_id": UUID,
      "question_text": str,
      "answer_given": str,
      "correct_answer": str,
      "is_correct": bool,
      "score": float,
      "explanation": str,
      "time_taken_ms": int
    }
  ]
}
```

---

## Schemas

```python
class AttemptResponse(BaseModel):
    id: UUID
    assessment_id: UUID
    student_id: UUID
    status: AttemptStatus
    started_at: datetime
    completed_at: datetime | None
    questions: list[QuestionForStudent]  # no correct_answer field

class ResponseSubmit(BaseModel):
    question_id: UUID
    answer_given: str
    time_taken_ms: int = Field(ge=0)
```

---

## Acceptance Criteria

- [ ] Student starts assessment → `student_attempts` row with `status='IN_PROGRESS'`
- [ ] Starting twice returns same attempt (idempotent)
- [ ] Starting a COMPLETED attempt → 409
- [ ] Submitting MCQ response → immediate `is_correct` in response
- [ ] Submitting SHORT_ANSWER → `scored=false`, LLM task queued
- [ ] Submitting same question twice → 409
- [ ] Submit attempt → `status='COMPLETED'`, gap state task fired
- [ ] Submit Tier 1 attempt → `check_and_update_onboarding_complete` called
- [ ] Submit Tier 2 attempt → onboarding check NOT called
- [ ] GET results → includes `correct_answer` and `explanation`
- [ ] Student cannot view another student's results → 403

---

## Tests to Write

```python
test_start_when_active_assessment_then_attempt_created()
test_start_when_already_in_progress_then_returns_existing()
test_start_when_already_completed_then_409()
test_submit_response_when_mcq_then_immediate_score()
test_submit_response_when_short_answer_then_pending_and_task_queued()
test_submit_response_when_duplicate_question_then_409()
test_submit_attempt_when_in_progress_then_completed()
test_submit_attempt_when_tier1_then_onboarding_check_called()
test_submit_attempt_when_tier2_then_onboarding_check_not_called()
test_submit_attempt_fires_gap_state_celery_task()
test_get_results_when_student_own_attempt_then_200()
test_get_results_when_other_student_then_403()
```
