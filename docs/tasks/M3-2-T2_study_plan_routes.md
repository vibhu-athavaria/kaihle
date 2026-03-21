# M3-2-T2 — Study Plan API Routes (Stub Replacement)
**Milestone:** M3 · **Epic:** M3-2 · **Task:** T2
**Depends on:** M3-2-T1 (StudyPlanService must exist before routes call it)
**Blocks:** M3-2-T3 (student UI), M3-2-T4 (teacher assignment UI)
**Estimated effort:** 3–4 hours

---

## Context and Critical Instruction

The file `backend/app/api/v1/routes/study_plans.py` **already exists**. It was
created by M0-10-T4. It contains six stub implementations, each marked:

```python
# STUB — M0-10-T4 | Real implementation: M3-2-T2
# Replace this entire function body. Do not change the signature or response_model.
```

This task replaces those stub bodies with real service calls. It does **not** create
a new file. It does **not** change any route path, HTTP method, auth dependency,
query parameter, or response model. Those are frozen by CONSTITUTION Rule 19.

Before writing any code, open the existing file and read every stub. Replace only
the function bodies.

---

## User Story

As a teacher, I want to assign study plans to students from the gap map. As a student,
I want to view my assigned plans, consume resources, and take the practice quiz.

---

## Files to Modify (NOT Create)

```
backend/app/api/v1/routes/study_plans.py           ← MODIFY: replace stub bodies only
backend/app/tests/integration/test_study_plan_routes.py  ← CREATE
```

---

## The Six Stubs to Replace

### `assign_study_plans` — `POST /classes/{class_id}/study-plans`

Replace the 501 stub body with a call to `StudyPlanService.assign_plans`. The service
handles the per-student Celery task queueing and returns a list of plan stubs.

Authorization: verify `current_user.role == TEACHER` and that the class belongs to the
teacher. Add the class ownership check using the same pattern as `AssessmentService`:

```python
class_ = await db.scalar(
    select(Class).where(
        Class.id == class_id,
        Class.school_id == current_user.school_id,
    )
)
if not class_:
    raise HTTPException(status_code=404, detail="Class not found")
if class_.teacher_id != current_user.id:
    raise HTTPException(status_code=403, detail="You do not own this class")

service = StudyPlanService(db)
return await service.assign_plans(
    class_id=class_id,
    school_id=current_user.school_id,
    subtopic_id=body.subtopic_id,
    student_ids=body.student_ids,
    assigned_by=current_user.id,
)
```

### `list_my_study_plans` — `GET /students/me/study-plans`

Replace the empty `Page` stub with a real service call. The `/me` shortcut resolves
to `current_user.id`:

```python
service = StudyPlanService(db)
return await service.list_student_plans(
    student_id=current_user.id,
    school_id=current_user.school_id,
    status_filter=status_filter,
    subject_id=subject_id,
    page=page,
    page_size=page_size,
)
```

### `list_student_study_plans` — `GET /students/{student_id}/study-plans`

Apply the same role-based authorization logic as `GET /students/{id}/gap-map` in
M2-1-T2. A Student can only see their own plans; a Teacher only sees plans for
students in their own class; a Parent only sees plans for their linked child.

### `get_study_plan` — `GET /study-plans/{plan_id}`

Replace the 404 stub with a real service call. Map `StudyPlanNotFoundError` →
HTTP 404. Map ownership failures → HTTP 403.

```python
service = StudyPlanService(db)
try:
    return await service.get_plan(
        plan_id=plan_id,
        requesting_user_id=current_user.id,
        requesting_user_role=current_user.role,
        school_id=current_user.school_id,
    )
except StudyPlanNotFoundError:
    raise HTTPException(status_code=404, detail="Study plan not found")
except PermissionError:
    raise HTTPException(status_code=403, detail="Access denied")
```

### `mark_resource_watched` — `PATCH /study-plans/{plan_id}/resources/{resource_id}/watched`

Replace the stub response with a real DB write. Verify the student owns the plan
before updating. The stub returns `{"resource_id": ..., "is_watched": True}` — the
real implementation returns the same shape after writing to DB:

```python
service = StudyPlanService(db)
await service.mark_resource_watched(
    plan_id=plan_id,
    resource_id=resource_id,
    student_id=current_user.id,
)
return {"resource_id": str(resource_id), "is_watched": True}
```

### `submit_study_plan_quiz` — `POST /study-plans/{plan_id}/quiz/submit`

Replace the zero-score stub with a real call to `StudyPlanService.submit_quiz`.
The service scores the MCQ responses inline (same deterministic pattern as
`AttemptService`), updates `gap_states` for the subtopic, and transitions the plan
status to `COMPLETED` if the score meets the threshold (≥ 0.8).

---

## Frozen Contracts (Reference Only — Do Not Change)

`POST /classes/{class_id}/study-plans` — body: `StudyPlanAssignRequest`, response:
`StudyPlanAssignResponse`, status 202.

`GET /students/me/study-plans` and `GET /students/{id}/study-plans` — query params:
`status` (optional), `subject_id` (optional), `page`, `page_size`. Response:
`Page[StudyPlanResponse]`.

`GET /study-plans/{plan_id}` — response: `StudyPlanResponse`.

`PATCH /study-plans/{plan_id}/resources/{resource_id}/watched` — no body, response:
`dict` with `resource_id` and `is_watched`.

`POST /study-plans/{plan_id}/quiz/submit` — body: `QuizSubmitRequest`, response:
`QuizSubmitResponse`.

---

## Acceptance Criteria

All tests go in `test_study_plan_routes.py`. Each description specifies the full
arrange-act-assert.

`test_assign_plans_when_teacher_owns_class_then_202_with_generating_plans` — Seed a
class with three enrolled students, assign teacher as class owner. POST to
`/classes/{id}/study-plans` with a `subtopic_id`. Assert HTTP 202 and the response
`plans` list contains one entry per student with `status: "GENERATING"`.

`test_assign_plans_when_teacher_does_not_own_class_then_403` — POST as a teacher who
is not the class owner. Assert HTTP 403.

`test_assign_plans_when_student_role_then_403` — POST as a student. Assert HTTP 403.

`test_list_my_study_plans_when_student_has_plans_then_200_with_data` — Create two
study plans for the authenticated student. Call `GET /students/me/study-plans`. Assert
HTTP 200, `total == 2`, and both plans appear in `data`.

`test_list_my_study_plans_when_no_plans_then_200_empty_page` — Authenticate as a
student with no plans. Assert HTTP 200 with `data: []` and `total: 0`.

`test_list_student_study_plans_when_teacher_own_class_then_200` — Create plans for a
student in the teacher's class. Call as the teacher. Assert HTTP 200.

`test_list_student_study_plans_when_teacher_other_class_student_then_403` — Call as
a teacher for a student not in their class. Assert HTTP 403.

`test_get_plan_when_student_owns_then_200_with_resources_and_quiz` — Create a
completed study plan with three resources and five quiz questions. Call `GET /study-plans/{id}`
as the owning student. Assert HTTP 200 and that `resources` has three items and
`quiz_questions` has five items.

`test_get_plan_quiz_questions_never_include_correct_answer` — Fetch a plan as a
student. Assert that no item in `quiz_questions` has a `correct_answer` or
`correct_answer_key` field anywhere in the response JSON.

`test_get_plan_when_different_student_then_403` — Call `GET /study-plans/{id}` as
a student who does not own that plan. Assert HTTP 403.

`test_mark_resource_watched_when_student_owns_plan_then_200` — Call the `PATCH`
endpoint. Assert HTTP 200 and the DB row for that resource has `is_watched=True`.

`test_mark_resource_watched_when_student_does_not_own_plan_then_403` — Call for a
plan belonging to a different student. Assert HTTP 403.

`test_submit_quiz_when_4_correct_of_5_then_score_0_8_and_plan_completed` — Submit
answers where 4 of 5 are correct. Assert HTTP 200, `score == 0.8`, and
`plan_status == "COMPLETED"`. Verify in DB that the plan's `status` field is
`COMPLETED`.

`test_submit_quiz_when_2_correct_of_5_then_score_0_4_and_plan_active` — Submit with
2 correct. Assert `score == 0.4` and `plan_status` remains `"IN_PROGRESS"` (threshold
not met).

`test_submit_quiz_updates_gap_states_for_subtopic` — After quiz submission, query the
`gap_states` table for `(student_id, subtopic_id)`. Assert that a row exists or has
been updated with a non-null `mastery_score`.

---

## Do NOT Touch

Every route decorator, path string, `response_model`, `status_code`, and `Depends()`
in `routes/study_plans.py`. The `schemas/study_plans.py` file. `routes/attempts.py`.
`backend/app/main.py` — router already registered.
