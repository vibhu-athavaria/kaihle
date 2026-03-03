# M3-2-T2 — Study Plan API Routes
**Milestone:** M3 — Smart Study Plans
**Epic:** M3-2 — Study Plan Lifecycle
**Task:** T2 of 4

---

## Context

Thin route handlers exposing the study plan service to API clients. Teachers assign plans; students view and interact with them.

**Depends on:** M3-2-T1 (study_plan_service.py)

---

## Files to Create / Modify

```
CREATE  backend/app/api/v1/routes/study_plans.py
MODIFY  backend/app/api/v1/__init__.py    ← register router
CREATE  backend/tests/integration/test_study_plan_routes.py
```

---

## API Endpoints

### `POST /api/v1/classes/{class_id}/study-plans` — Assign Study Plans
**Role:** Teacher (own class)
**Body:**
```json
{
  "student_ids": ["uuid1", "uuid2"] | "all",
  "subtopic_id": "uuid"
}
```
**Logic:**
- If `student_ids = "all"`: load all enrolled students in class
- For each student: call `study_plan_service.create_study_plan(...)`
- Returns immediately with `{ status: "generating", plans: [{ plan_id, student_id, status: "GENERATING" }] }`
- Plans fill out asynchronously via Celery

---

### `GET /api/v1/study-plans/{plan_id}` — Get Single Plan
**Role:** Student (own plan), Teacher (own class), Parent (own child)
**Returns:** `StudyPlanResponse` with resources + quiz

---

### `GET /api/v1/students/{student_id}/study-plans` — List Student Plans
**Role:** Student (own — use `me` or explicit `student_id`), Teacher (own class), Parent (own child)
**Query params:** `?status=active|completed&subject_id=uuid`
**Returns:** `list[StudyPlanResponse]`

---

### `PATCH /api/v1/study-plans/{plan_id}/resources/{resource_id}/watched` — Mark Resource Watched
**Role:** Student (own plan only)
**Body:** None
**Logic:** `study_plan_service.mark_resource_watched(plan_id, resource_id, student_id)`
**Returns:** `{ resource_id, is_watched: true }`

---

### `POST /api/v1/study-plans/{plan_id}/quiz/submit` — Submit Quiz
**Role:** Student (own plan only)
**Body:** `{ responses: [{ question_index: int, answer: str }] }`
**Logic:** `study_plan_service.submit_quiz(plan_id, student_id, responses)`
**Returns:** `{ score: float, correct_count: int, total_questions: int, plan_status: str }`

---

## Acceptance Criteria

### Integration Tests (`test_study_plan_routes.py`)

- [ ] `test_assign_plans_when_teacher_and_valid_class_then_plans_created_for_all_students`

- [ ] `test_assign_plans_when_student_calls_then_403`

- [ ] `test_assign_plans_when_class_not_teachers_then_403`

- [ ] `test_get_plan_when_student_owns_it_then_200_with_resources_and_quiz`

- [ ] `test_get_plan_when_student_does_not_own_then_403`

- [ ] `test_get_plan_quiz_response_does_not_include_correct_answer`
  - `StudyPlanQuizResponse.questions` must not expose `correct_answer`

- [ ] `test_mark_resource_watched_when_student_owns_plan_then_is_watched_true`

- [ ] `test_submit_quiz_when_3_correct_of_5_then_score_0_6_and_plan_still_active`

- [ ] `test_submit_quiz_when_4_correct_of_5_then_score_0_8_and_plan_completed`

---

## Output of This Task

- `api/v1/routes/study_plans.py` with 5 endpoints
- All integration tests passing

**Next task:** M3-2-T3 (student study plan UI)
