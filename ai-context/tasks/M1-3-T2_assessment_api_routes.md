# M1-3-T2 — Assessment API Routes
**Milestone:** M1 · **Epic:** M1-3 · **Task:** T2
**Depends on:** M1-3-T1 (assessment service)

---

## User Story
As a teacher, I want API endpoints to create, view, and publish assessments so I can manage the assessment lifecycle for my class.

---

## Files to Create / Modify

```
backend/app/api/v1/routes/assessments.py    # new file
backend/app/main.py                          # register router
backend/tests/integration/test_assessment_routes.py
```

---

## Endpoints

### `POST /api/v1/assessments`
Auth: Teacher | SchoolAdmin
```
Body: AssessmentConfig (from M1-3-T1)
Returns: AssessmentResponse (201 Created)
```
Delegates to `assessment_service.create_assessment(config, teacher_id, school_id)`.

---

### `GET /api/v1/assessments/{assessment_id}`
Auth: Teacher (own class only) | SchoolAdmin | KaihleAdmin
```
Returns: AssessmentResponse + list of selected questions (without correct_answer for students)
```
**Role-based field filtering:**
- Teacher/Admin: include `correct_answer` and `explanation` in question objects
- Student: exclude `correct_answer` and `explanation`

---

### `POST /api/v1/assessments/{assessment_id}/publish`
Auth: Teacher (own class only)
```
Body: { deadline: datetime | null }
Returns: AssessmentResponse with status='ACTIVE'
```
- Changes `status` from `DRAFT` → `ACTIVE`
- Sets `deadline` if provided
- Cannot publish if `assessment_selected_questions` is empty → 400
- Cannot publish an already ACTIVE or CLOSED assessment → 409

---

### `POST /api/v1/assessments/{assessment_id}/close`
Auth: Teacher (own class only)
```
Returns: AssessmentResponse with status='CLOSED'
```
Changes `status` from `ACTIVE` → `CLOSED`. No new attempts accepted after this.

---

### `GET /api/v1/classes/{class_id}/assessments`
Auth: Teacher (own class) | Student (enrolled in class) | SchoolAdmin
```
Query params: status (optional filter: DRAFT|ACTIVE|CLOSED)
Returns: list[AssessmentResponse]
```
- Teacher sees ALL statuses for own class
- Student sees only `ACTIVE` and `CLOSED` assessments (not DRAFT)
- Student also sees Tier 1 system-generated assessments for their class (`is_system_generated=TRUE`)

---

### `DELETE /api/v1/assessments/{assessment_id}`
Auth: Teacher (own class only)
- Only allowed on `DRAFT` assessments
- Returns 409 if ACTIVE or CLOSED

---

## Acceptance Criteria

- [ ] POST creates DRAFT assessment, returns 201
- [ ] GET returns questions without `correct_answer` when caller is Student
- [ ] Publish changes status to ACTIVE, is visible to students
- [ ] DRAFT assessment NOT visible to students in class list
- [ ] ACTIVE assessment visible to students in class list
- [ ] Student sees Tier 1 assessments (`is_system_generated=TRUE`) in class list
- [ ] Teacher cannot access another teacher's assessment → 403
- [ ] Publish on already-ACTIVE assessment → 409
- [ ] DELETE on ACTIVE assessment → 409

---

## Tests to Write

```python
test_create_assessment_when_teacher_then_201_draft()
test_get_assessment_when_student_then_correct_answer_excluded()
test_get_assessment_when_teacher_then_correct_answer_included()
test_publish_when_draft_then_status_active()
test_publish_when_already_active_then_409()
test_list_assessments_when_student_then_draft_excluded()
test_list_assessments_when_student_then_system_generated_included()
test_access_other_teachers_assessment_then_403()
test_delete_when_draft_then_200()
test_delete_when_active_then_409()
```
