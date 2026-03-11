# M0-4-T3 — Grade, Class & Enrollment API
**Milestone:** M0 · **Epic:** M0-4 · **Task:** T3
**Depends on:** M0-2-T2 (ORM models), M0-3-T3 (auth middleware), M0-6-T2 (Tier 1 trigger task)

---

## User Story
As a School Admin, I want to create subject classes for each grade, assign teachers. I want to view all classes and enroll students so the school is operationally set up in Kaihle.

---

## Files to Create / Modify

```
backend/app/services/school_service.py        # add class/enrollment methods
backend/app/api/v1/routes/schools.py          # add class/enrollment routes
backend/app/schemas/school.py                 #  ClassCreate, EnrollRequest schemas
backend/app/tasks/onboarding_tasks.py         # import here to fire Celery task on enroll
backend/tests/integration/test_enrollment.py
```

---

## API Endpoints


### Classes
```
POST   /api/v1/schools/{school_id}/classes
  Body:  { name: str, grade_id: UUID, subject_id: UUID,
           curriculum_id: UUID, teacher_id: UUID, academic_year: str }
  Auth:  SchoolAdmin | KaihleAdmin
  Returns: Class object

GET    /api/v1/schools/{school_id}/classes
  Auth:  Teacher (own classes only), SchoolAdmin (all), KaihleAdmin (all)
  Returns: list[Class]
```

### Enrollment
```
POST   /api/v1/schools/{school_id}/classes/{class_id}/enroll
  Body:  { student_ids: list[UUID] }
  Auth:  SchoolAdmin | KaihleAdmin
  Returns: { enrolled: int, skipped: int, errors: list }

GET    /api/v1/schools/{school_id}/classes/{class_id}/students
  Auth:  Teacher (own class) | SchoolAdmin | KaihleAdmin
  Returns: list[StudentSummary]
```

---

## Service Logic

### `enroll_students(class_id, student_ids, school_id)`

```python
for student_id in student_ids:
    # 1. Validate student belongs to this school
    # 3. Skip if already enrolled (no error, count as skipped)
    # 4. Insert class_enrollments row
    # 5. CRITICAL (v2.1): if student_profiles.onboarding_diagnostic_status == 'PENDING':
    #       trigger_onboarding_diagnostics.delay(student_id, class_id)
```

**The Celery task fires ONCE per student — if status is already IN_PROGRESS or COMPLETED, do not re-fire.**

### Teacher class filter
Teacher role: `WHERE classes.teacher_id = current_user.id AND classes.school_id = current_user.school_id`

---

## Schemas

```python

class ClassCreate(BaseModel):
    name: str
    grade_id: UUID
    subject_id: UUID
    curriculum_id: UUID
    teacher_id: UUID
    academic_year: str  # e.g. "2025-2026"

class EnrollRequest(BaseModel):
    student_ids: list[UUID] = Field(min_length=1, max_length=200)
```

---

## Acceptance Criteria

- [ ] SchoolAdmin creates a class, assigns teacher → teacher can see it via GET
- [ ] Teacher GET returns own classes only (not other teachers')
- [ ] Enroll 3 students → 3 `class_enrollments` rows created
- [ ] Each enrolled student with `onboarding_diagnostic_status='PENDING'` triggers `trigger_onboarding_diagnostics` Celery task
- [ ] Student already enrolled → counted as skipped, not error
- [ ] Student from different school → 400 Bad Request
- [ ] SchoolAdmin cannot manage classes in a different school → 403


---

## Tests to Write

```python
# test_grade_class_enrollment.py

test_create_class_when_valid_then_teacher_can_list()
test_list_classes_when_teacher_then_only_own_classes_returned()
test_enroll_students_when_valid_then_enrollment_rows_created()
test_enroll_students_when_onboarding_pending_then_celery_task_fired()
test_enroll_students_when_onboarding_in_progress_then_celery_task_not_fired()
test_enroll_students_when_already_enrolled_then_skipped_not_error()
test_enroll_students_when_wrong_school_then_400()
test_enroll_when_different_school_admin_then_403()

```
