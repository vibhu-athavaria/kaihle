# M1-3-T2 — Assessment API Routes (Stub Replacement)
**Milestone:** M1 · **Epic:** M1-3 · **Task:** T2
**Depends on:** M1-3-T1 (AssessmentService must exist before routes call it)
**Blocks:** M1-3-T3 (teacher UI needs real data from these routes)
**Estimated effort:** 2–3 hours

---

## Context and Critical Instruction

The file `backend/app/api/v1/routes/assessments.py` **already exists**. It was created
by M0-10-T3 as part of the API Contract Finalization phase. It contains stub
implementations — functions that return the correct HTTP status codes and response
shapes but with no real database logic.

This task replaces the function bodies inside that existing file. It does NOT create
a new file. It does NOT change the route paths, HTTP methods, auth dependencies,
request schemas, or response models. Those are frozen by CONSTITUTION Rule 19.

Before writing any code, open `backend/app/api/v1/routes/assessments.py` and read
it in full. Every stub function is marked with a comment like:

```python
# STUB — M0-10-T3 | Real implementation: M1-3-T2
# Replace this entire function body. Do not change the signature or response_model.
```

Replace every such function body. Leave every decorator, path, dependency, and
response_model declaration exactly as it is.

---

## User Story

As a teacher, I want to create, list, view, publish, and close assessments via the
API so I can manage the full assessment lifecycle for my class.

---

## Files to Modify (NOT Create)

```
backend/app/api/v1/routes/assessments.py    ← MODIFY: replace stub bodies only
backend/app/tests/integration/test_assessment_routes.py  ← CREATE: integration tests
```

---

## Stub Functions to Replace

The following describes what each stub function body must be replaced with. The function
signatures shown are already in the file — do not change them.

### `list_class_assessments` — `GET /classes/{class_id}/assessments`

The stub returns an empty `Page`. Replace it with a real DB query.

The implementation must call `assessment_service.list_class_assessments(class_id, school_id, status_filter)`.
Add a `list_class_assessments` method to `AssessmentService` that queries `assessments`
filtered by `class_id` and `school_id`, optionally filtered by `status`. Apply
pagination using `page` and `page_size`.

Role-based visibility rules that must be enforced in the service, not the route:
a Teacher sees all statuses for their own classes; a Student sees only `ACTIVE` and
`CLOSED` assessments (not `DRAFT`); a Student also sees Tier 1 system-generated
assessments for enrolled classes regardless of status.

Teacher access check: if `current_user.role == TEACHER`, verify `class_.teacher_id == current_user.id`.
If not, raise HTTP 403. SchoolAdmin and KaihleAdmin see all classes within the
`school_id` scope.

### `create_assessment` — `POST /classes/{class_id}/assessments`

The stub returns 501. Replace with a call to `AssessmentService.create_assessment`.

Extract `class_id` from the path parameter and inject it into the request body before
calling the service. The `AssessmentCreateRequest` schema does not include `class_id`
as a body field — the route adds it from the path.

Map service exceptions to HTTP responses:
- `TeacherNotClassOwnerError` → HTTP 403 "You do not own this class"
- `InsufficientQuestionsError` → HTTP 422 with detail containing `available` count and `criteria`
- `ValueError` → HTTP 404 (class not found case)

Return HTTP 201 on success.

### `get_assessment` — `GET /assessments/{assessment_id}`

The stub returns 404. Replace with a call to `AssessmentService.get_assessment`,
passing the `current_user.role` so the service can strip `correct_answer_key` for
Student callers.

Multi-tenancy: pass `current_user.school_id` as `school_id`. For KaihleAdmin
(who has `school_id=None`), derive the `school_id` from the assessment row itself —
load the row first, then verify KaihleAdmin can access it (unrestricted).

Return an `AssessmentResponse` that combines the `Assessment` fields with a
`questions` list. For Students, every question in the list must have
`correct_answer_key` omitted (the service handles this — do not strip it in the route).

### `publish_assessment` — `POST /assessments/{assessment_id}/publish`

The stub returns 404. Replace with a call to `AssessmentService.publish_assessment`.

The request body is optional: `{ deadline: datetime | None }`. Extract `deadline`
from the body if provided, else pass `None`. Map `ValueError` → HTTP 400 or 409
depending on the error message:
- If error message contains "status" → HTTP 409 (conflict — wrong state transition)
- If error message contains "not found" → HTTP 404
- If error message contains "questions" → HTTP 422 (no questions in assessment)

### `close_assessment` — `POST /assessments/{assessment_id}/close`

The stub returns 404. Replace with `AssessmentService.close_assessment`. Map
`ValueError("Cannot publish: status is DRAFT")` → HTTP 409.

---

## Request/Response Contracts (Frozen — Do Not Change)

These are documented here for reference only. They are already defined in the file.

`GET /classes/{class_id}/assessments` — query params: `status` (optional, string),
`page` (int, default 1), `page_size` (int, default 20, max 100). Response:
`Page[AssessmentResponse]` — the `Page` generic from `schemas/common.py`.

`POST /classes/{class_id}/assessments` — body: `AssessmentCreateRequest` from
`schemas/assessments.py`. Response: `AssessmentResponse`, HTTP 201.

`GET /assessments/{assessment_id}` — no body. Response: `AssessmentResponse`.

`POST /assessments/{assessment_id}/publish` — body: `{ deadline: str | None }`.
Response: `AssessmentResponse`.

`POST /assessments/{assessment_id}/close` — no body. Response: `AssessmentResponse`.

---

## Acceptance Criteria

All tests go in `test_assessment_routes.py`. Each test description specifies the
full arrange-act-assert — not just the test name.

`test_list_class_assessments_when_teacher_own_class_then_returns_200_with_page` —
Create a class with `teacher_id=teacher.id`. Create two DRAFT and one ACTIVE
assessment for that class. Call `GET /classes/{class_id}/assessments` as the teacher.
Assert HTTP 200, `data` contains all three assessments, `total == 3`.

`test_list_class_assessments_when_teacher_other_class_then_403` — Create a class with
a different teacher. Call the endpoint as the first teacher. Assert HTTP 403.

`test_list_class_assessments_when_student_then_draft_excluded` — Create one DRAFT and
one ACTIVE assessment. Call as a student enrolled in the class. Assert `data` contains
only the ACTIVE assessment.

`test_list_class_assessments_when_student_then_system_generated_tier1_included` —
Create a system-generated assessment (`is_system_generated=True`, status `ACTIVE`).
Call as an enrolled student. Assert the Tier 1 assessment appears in the response.

`test_create_assessment_when_teacher_owns_class_then_201_draft` — POST a valid
`AssessmentCreateRequest` as a teacher who owns the class. Assert HTTP 201, response
has `status="DRAFT"` and `is_system_generated=False`.

`test_create_assessment_when_teacher_does_not_own_class_then_403` — POST as a teacher
who does not own the class. Assert HTTP 403.

`test_create_assessment_when_insufficient_questions_then_422` — Set up a question bank
with 2 rows for the subject/grade. Request 10 questions. Assert HTTP 422 and that the
response body contains an `available` field showing 2.

`test_get_assessment_when_student_then_correct_answer_excluded` — Create an ACTIVE
assessment with questions that have `correct_answer_key` set. Call `GET /assessments/{id}`
as a student enrolled in the class. Assert HTTP 200 and that no question in the response
has a `correct_answer_key` field.

`test_get_assessment_when_teacher_then_correct_answer_included` — Same setup. Call as
the teacher. Assert every question has a non-null `correct_answer_key`.

`test_get_assessment_when_different_school_then_403` — Call as a user whose
`school_id` does not match the assessment's `school_id`. Assert HTTP 403.

`test_publish_when_draft_then_status_active` — Create a DRAFT assessment with at least
one question. POST to publish. Assert HTTP 200, `status="ACTIVE"`, `published_at` is
not null.

`test_publish_when_already_active_then_409` — Publish an assessment, then attempt to
publish it again. Assert HTTP 409.

`test_publish_when_different_teacher_then_403` — Attempt to publish an assessment
created by teacher A while authenticated as teacher B. Assert HTTP 403.

`test_close_when_active_then_200_with_closed_status` — Publish an assessment, then
close it. Assert HTTP 200 and `status="CLOSED"`.

`test_close_when_draft_then_409` — Attempt to close a DRAFT assessment. Assert HTTP 409.

---

## Do NOT Touch

The following must remain exactly as they are. Any change to these constitutes a
CONSTITUTION Rule 19 violation.

The route decorators (`@router.get`, `@router.post`), path strings, `response_model`
parameters, `status_code` parameters, and `Depends()` calls in every function signature
in `assessments.py` must not be changed.

`backend/app/schemas/assessments.py` — do not modify.
`backend/app/schemas/common.py` — do not modify.
`backend/app/tasks/onboarding_tasks.py` — do not touch.
`backend/app/main.py` — the router is already registered; do not re-register it.
