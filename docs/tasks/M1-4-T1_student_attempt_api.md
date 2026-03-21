# M1-4-T1 — Student Attempt API (Stub Replacement)
**Milestone:** M1 · **Epic:** M1-4 · **Task:** T1
**Depends on:** M1-3-T2 (assessment routes live), M1-4-T3 (gap state task must be created before submit calls it), M0-6-T3 (onboarding completion service)
**Blocks:** M1-4-T4 (student UI calls these endpoints)
**Estimated effort:** 4–5 hours

---

## Critical Corrections from Previous Version

This task file supersedes the previous `M1-4-T1` completely. Three significant
corrections apply.

**Correction 1 — No `/start` endpoint.** The previous version described a
`POST /api/v1/assessments/{assessment_id}/start` endpoint. This endpoint does not
exist in the frozen API contract from M0-10. The contract is locked by CONSTITUTION
Rule 19 and cannot be changed. The attempt retrieval flow for each tier works as follows.

For Tier 1 diagnostics, the student's `StudentAttempt` row is created automatically
by the `trigger_onboarding_diagnostics` Celery task when the student is enrolled in a
class. The student retrieves it via `GET /classes/{class_id}/diagnostic`, which is a
stub in `routes/attempts.py` from M0-10-T3. This task replaces that stub.

For Tier 2 assessments, the teacher publishes an assessment and students see it listed
in `GET /classes/{class_id}/assessments`. The student begins taking it by calling
`GET /attempts/{attempt_id}`, which creates or retrieves an attempt row. This is the
"lazy creation" pattern — the attempt is created on first retrieval, not via a separate
start endpoint.

**Correction 2 — MCQ-only scoring, no LLM, no async.** All questions in the question
bank are MCQ. Scoring is a single deterministic operation performed inline in the
submit handler: `is_correct = (selected_key.strip().lower() == correct_answer_key.strip().lower())`.
There is no `scoring_service.py`, no `ScoredBy` enum, no `PENDING` state, no LLM
scoring task. The `scored_by` field does not exist in the response. Any reference to
short-answer questions, LLM scoring, or async scoring in the previous task file is
obsolete and must not be implemented.

**Correction 3 — Retired dependency.** `M1-4-T2` (answer scoring service) is retired.
This task does not depend on it. MCQ scoring logic lives inline in the `AttemptService`.

---

## User Story

As a student, I want to retrieve my diagnostic assessment, submit my answers one at
a time, and then submit the whole attempt to see my score and unlock class content.

---

## Files to Create / Modify

```
backend/app/services/attempt_service.py         ← CREATE: all attempt business logic
backend/app/api/v1/routes/attempts.py           ← MODIFY: replace stub bodies only
backend/app/tests/unit/test_attempt_service.py
backend/app/tests/integration/test_attempt_routes.py
```

The file `backend/app/api/v1/routes/attempts.py` already exists from M0-10-T3. Modify
it — do not create a new file. Replace only the stub function bodies.

---

## Custom Exceptions

Define these at the top of `attempt_service.py`.

```python
class AttemptNotFoundError(Exception):
    """Raised when no attempt exists for the given (student_id, assessment_id) pair."""
    pass

class AttemptAlreadyCompletedError(Exception):
    """Raised when a student tries to answer or submit a COMPLETED attempt."""
    pass

class QuestionNotInAssessmentError(Exception):
    """Raised when the submitted question_id does not belong to this assessment."""
    pass

class DuplicateResponseError(Exception):
    """Raised when the student submits a response for a question they already answered."""
    pass
```

---

## Service Class

```python
class AttemptService:

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
```

---

## Method: `get_or_create_attempt`

This method handles the lazy creation pattern for Tier 2 attempts. For Tier 1,
the attempt was pre-created by the Celery task — this method will always find an
existing row and return it.

Full signature:

```python
async def get_or_create_attempt(
    self,
    assessment_id: uuid.UUID,
    student_id: uuid.UUID,
    school_id: uuid.UUID,
) -> tuple[StudentAttempt, list[QuestionBank]]:
```

Step-by-step logic:

Step 1 — Verify the assessment exists, is ACTIVE, and belongs to `school_id`. If the
assessment has `status != "ACTIVE"`, raise `ValueError("Assessment is not active")`.

Step 2 — Look for an existing `StudentAttempt` where `assessment_id` and `student_id`
both match. If found, return it with its questions.

Step 3 — If not found (Tier 2 first visit), verify the student is enrolled in the
assessment's class. If not enrolled, raise `ValueError("Student not enrolled in class")`.
Then create a new `StudentAttempt` row with `status="NOT_STARTED"`.

Step 4 — Load questions for this attempt in the order defined by
`assessment_selected_questions.position`. Strip `correct_answer_key` before returning
(students never receive the answer during the attempt).

Return `(attempt, questions_without_answers)`.

---

## Method: `get_class_diagnostic`

This method handles the Tier 1 path — finding the student's existing Tier 1 attempt
for a specific class.

Full signature:

```python
async def get_class_diagnostic(
    self,
    class_id: uuid.UUID,
    student_id: uuid.UUID,
    school_id: uuid.UUID,
) -> tuple[StudentAttempt, list[QuestionBank]]:
```

Step 1 — Find the system-generated assessment for this class:

```python
assessment = await self.db.scalar(
    select(Assessment).where(
        Assessment.class_id == class_id,
        Assessment.school_id == school_id,
        Assessment.is_system_generated.is_(True),
        Assessment.status == "ACTIVE",
    )
)
if not assessment:
    raise ValueError("No active Tier 1 diagnostic found for this class")
```

Step 2 — Find the student's `StudentAttempt` for this assessment:

```python
attempt = await self.db.scalar(
    select(StudentAttempt).where(
        StudentAttempt.assessment_id == assessment.id,
        StudentAttempt.student_id == student_id,
    )
)
if not attempt:
    raise AttemptNotFoundError("Diagnostic attempt not yet created for this student")
```

The Celery task `trigger_onboarding_diagnostics` should have created this row at
enrollment time. If it is missing, it means the Celery task failed. Log this at
WARNING level with `class_id` and `student_id` before raising.

Step 3 — Load and return questions (stripped of answers) in `position` order.

---

## Method: `submit_response`

Handles one answer being saved for one question.

Full signature:

```python
async def submit_response(
    self,
    attempt_id: uuid.UUID,
    student_id: uuid.UUID,
    school_id: uuid.UUID,
    question_id: uuid.UUID,
    selected_key: str,
) -> None:
```

Step 1 — Load attempt. Verify `attempt.student_id == student_id` and
`attempt.school_id == school_id`. If not found or school mismatch, raise `ValueError`.
If `attempt.status == "COMPLETED"`, raise `AttemptAlreadyCompletedError`.

Step 2 — Verify `question_id` exists in `assessment_selected_questions` for this
attempt's `assessment_id`. If not, raise `QuestionNotInAssessmentError`.

Step 3 — Check for duplicate: if a `StudentResponse` row already exists for this
`(attempt_id, question_id)` pair, raise `DuplicateResponseError`.

Step 4 — Load the `QuestionBank` row to get `correct_answer_key`. Score inline:

```python
is_correct = selected_key.strip().lower() == question.correct_answer_key.strip().lower()
```

Step 5 — Insert `StudentResponse`:

```python
response = StudentResponse(
    id=uuid.uuid4(),
    attempt_id=attempt_id,
    question_id=question_id,
    answer_given=selected_key,
    is_correct=is_correct,
    time_taken_ms=None,   # not tracked in v1
)
self.db.add(response)
```

Step 6 — If `attempt.status == "NOT_STARTED"`, update it to `"IN_PROGRESS"`:

```python
if attempt.status == "NOT_STARTED":
    attempt.status = "IN_PROGRESS"
```

This method returns `None`. The HTTP route returns 204 No Content.

---

## Method: `submit_attempt`

Marks the attempt as complete, scores it, triggers gap calculation, and (for Tier 1)
triggers the onboarding completion check.

Full signature:

```python
async def submit_attempt(
    self,
    attempt_id: uuid.UUID,
    student_id: uuid.UUID,
    school_id: uuid.UUID,
    answers: list[dict],   # [{"question_id": UUID, "selected_key": str}]
    onboarding_service: OnboardingService,
) -> AttemptResultResponse:
```

Step 1 — Load and verify attempt ownership using same checks as `submit_response`.
If `status == "COMPLETED"`, raise `AttemptAlreadyCompletedError`.

Step 2 — Process any answers in `answers` that have not yet been saved. For each
answer in the list, call the same scoring logic as `submit_response` but skip if a
`StudentResponse` row already exists for that `question_id` (idempotent upsert-like
behaviour via check-then-insert).

Step 3 — Load all `StudentResponse` rows for this attempt to compute the final score:

```python
responses = await self.db.scalars(
    select(StudentResponse).where(StudentResponse.attempt_id == attempt_id)
)
total = len(list(responses))
correct = sum(1 for r in responses if r.is_correct)
score_pct = (correct / total * 100) if total > 0 else 0.0
```

Step 4 — Mark attempt as completed:

```python
attempt.status = "COMPLETED"
attempt.completed_at = datetime.now(timezone.utc)
attempt.score = correct / total if total > 0 else 0.0
```

Step 5 — Flush (not commit) so the attempt row is updated before the Celery task reads it:

```python
await self.db.flush()
```

Step 6 — Fire gap state calculation Celery task:

```python
from app.tasks.gap_tasks import calculate_gap_states
calculate_gap_states.delay(str(attempt_id))
```

Step 7 — If this is a Tier 1 (system-generated) assessment, call the onboarding
completion check synchronously. This is a fast DB query and does not need to be
async/Celery. The onboarding service is injected as a parameter so this service
stays testable without side effects:

```python
assessment = await self.db.get(Assessment, attempt.assessment_id)
if assessment.is_system_generated:
    await onboarding_service.check_and_update_onboarding_complete(
        student_id=student_id,
        class_id=assessment.class_id,
    )
```

Step 8 — Return `AttemptResultResponse`:

```python
return AttemptResultResponse(
    attempt_id=attempt_id,
    score=attempt.score,
    total_questions=total,
    correct_count=correct,
    time_taken_seconds=None,
    submitted_at=attempt.completed_at,
)
```

---

## Method: `get_attempt_results`

Full signature:

```python
async def get_attempt_results(
    self,
    attempt_id: uuid.UUID,
    requesting_user_id: uuid.UUID,
    requesting_user_role: str,
    school_id: uuid.UUID,
) -> AttemptResultResponse:
```

Load the `StudentAttempt`. Verify it is `COMPLETED` — if not, raise `ValueError`.

Authorization rules: Students may only retrieve their own attempts
(`attempt.student_id == requesting_user_id`). Teachers may retrieve any attempt for
students in their classes. SchoolAdmins and KaihleAdmins may retrieve any attempt in
the school. If authorization fails, raise `ValueError("Access denied")`.

Return `AttemptResultResponse` built from the attempt row.

---

## Stub Replacement in `routes/attempts.py`

Open `backend/app/api/v1/routes/attempts.py`. Find each stub function body. Replace
as follows.

`get_class_diagnostic` — replace stub body with:

```python
service = AttemptService(db)
try:
    attempt, questions = await service.get_class_diagnostic(
        class_id=class_id,
        student_id=current_user.id,
        school_id=current_user.school_id,
    )
    return AttemptResponse(
        id=attempt.id,
        assessment_id=attempt.assessment_id,
        student_id=attempt.student_id,
        status=attempt.status,
        started_at=attempt.started_at,
        submitted_at=attempt.completed_at,
        score=attempt.score,
        questions=questions,
    )
except (ValueError, AttemptNotFoundError) as e:
    raise HTTPException(status_code=404, detail=str(e))
```

`get_attempt` — replace stub body with:

```python
service = AttemptService(db)
try:
    attempt, questions = await service.get_or_create_attempt(
        assessment_id=_resolve_assessment_id_from_attempt(attempt_id, db),
        student_id=current_user.id,
        school_id=current_user.school_id,
    )
    ...
```

Note: `get_attempt` takes `attempt_id` directly. If the attempt does not yet exist
for Tier 2, create it lazily. If it does exist (Tier 1 or returning student), return it.

`submit_response` — replace stub body with a call to `AttemptService.submit_response`.
Map `DuplicateResponseError` → HTTP 409. Map `QuestionNotInAssessmentError` → HTTP 422.
Map `AttemptAlreadyCompletedError` → HTTP 409. Return 204 No Content.

`submit_attempt` — replace stub body with a call to `AttemptService.submit_attempt`.
Inject `OnboardingService(db)` as the onboarding_service parameter.

`get_attempt_results` — replace stub body with a call to
`AttemptService.get_attempt_results`.

---

## Acceptance Criteria

**Unit tests — `test_attempt_service.py`**

`test_get_class_diagnostic_when_attempt_exists_then_returns_with_questions` — Create
a Tier 1 assessment and a `StudentAttempt` row for it. Call `get_class_diagnostic`.
Assert the returned attempt has `status="NOT_STARTED"` and the questions list has
the correct count, with `correct_answer_key` stripped from every question.

`test_get_class_diagnostic_when_no_attempt_then_raises_attempt_not_found_error` —
Call `get_class_diagnostic` for a class where `trigger_onboarding_diagnostics` never
ran. Assert `AttemptNotFoundError` raised.

`test_get_class_diagnostic_when_no_active_tier1_assessment_then_raises_value_error` —
Call for a class that has no system-generated ACTIVE assessment. Assert `ValueError`.

`test_submit_response_when_correct_mcq_then_is_correct_true` — Submit the correct
`selected_key` for an MCQ question. Assert the `StudentResponse` row has
`is_correct=True`.

`test_submit_response_when_wrong_mcq_then_is_correct_false` — Submit the wrong key.
Assert `is_correct=False`.

`test_submit_response_when_case_different_then_still_correct` — Submit `"B"` when
`correct_answer_key = "b"`. Assert `is_correct=True` (case-insensitive).

`test_submit_response_when_duplicate_question_then_raises_duplicate_response_error` —
Submit the same `question_id` twice. Assert `DuplicateResponseError` on the second call.

`test_submit_response_when_attempt_completed_then_raises_attempt_already_completed_error`
— Try to submit a response to a COMPLETED attempt. Assert `AttemptAlreadyCompletedError`.

`test_submit_response_when_question_not_in_assessment_then_raises_error` — Submit a
`question_id` that belongs to a different assessment. Assert `QuestionNotInAssessmentError`.

`test_submit_response_transitions_attempt_from_not_started_to_in_progress` — Submit
one response to a NOT_STARTED attempt. Assert `attempt.status == "IN_PROGRESS"`.

`test_submit_attempt_when_10_correct_then_score_1_0` — Answer all 10 questions
correctly. Call `submit_attempt`. Assert `result.score == 1.0` and
`result.correct_count == 10`.

`test_submit_attempt_when_7_correct_of_10_then_score_0_7` — Answer 7 correctly. Assert
`result.score == 0.7`.

`test_submit_attempt_when_tier1_then_onboarding_check_called` — Use a mock
`OnboardingService`. Call `submit_attempt` for a Tier 1 (system-generated) assessment.
Assert `mock_onboarding_service.check_and_update_onboarding_complete` was called once
with the correct `student_id` and `class_id`.

`test_submit_attempt_when_tier2_then_onboarding_check_not_called` — Same setup but
with a Tier 2 assessment (`is_system_generated=False`). Assert the onboarding service
was NOT called.

`test_submit_attempt_fires_calculate_gap_states_celery_task` — Use
`unittest.mock.patch("app.tasks.gap_tasks.calculate_gap_states.delay")`. Assert it
was called once with `str(attempt_id)`.

`test_submit_attempt_idempotent_when_some_responses_already_saved` — Save 5 responses
before calling `submit_attempt` with all 10 answers. Assert `submit_attempt` succeeds
and does not create duplicate response rows.

`test_get_results_when_own_student_then_200_with_score` — Create a completed attempt.
Call `get_attempt_results` as the student who owns it. Assert score is correct.

`test_get_results_when_different_student_then_raises_access_denied` — Call
`get_attempt_results` as a different student. Assert `ValueError("Access denied")`.

**Integration tests — `test_attempt_routes.py`**

`test_get_class_diagnostic_when_enrolled_student_then_200_with_questions` — Full
integration test with real DB. Enroll a student (which fires the Celery task via a
mock). Verify the diagnostic attempt exists. Call the endpoint. Assert HTTP 200 and
`questions` is non-empty.

`test_submit_response_when_valid_then_204` — Submit a response. Assert HTTP 204.

`test_submit_response_when_duplicate_then_409` — Submit same question twice.
Assert HTTP 409 on second call.

`test_submit_attempt_when_valid_then_200_with_score` — Submit all responses, then
submit the attempt. Assert HTTP 200 and `score` field is present.

`test_submit_attempt_when_already_completed_then_409` — Submit once, then again.
Assert HTTP 409 on second submission.

---

## Do NOT Touch

The following must not change. Any change is a CONSTITUTION Rule 19 violation.

Every route decorator, path string, `response_model`, `status_code`, and `Depends()`
call in `routes/attempts.py`. The schemas in `schemas/attempts.py`. The Celery task
in `tasks/gap_tasks.py` (created by M1-4-T3 — these tasks run in dependency order but
can be worked in parallel as long as the Celery task file exists before `submit_attempt`
is called). The `check_and_update_onboarding_complete` method in `onboarding_service.py`.
