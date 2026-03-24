# M0-10-T7 Addendum 2 — Student Class Access
**Reads alongside:** `M0-10/M0-10-T7_backend_hard_cutover.md` and
`M0-10/M0-10-T7_addendum_missing_stubs.md`
**Must be executed as part of M0-10-T7** — same commit

---

## Problem

The student dashboard needs to show class cards — one card per enrolled class,
each showing the subject name, diagnostic status, and lock/unlock state. To render
these cards, the student app needs to know which classes the student is enrolled in.

The current `GET /schools/{school_id}/classes` endpoint does not allow the STUDENT
role. It only allows TEACHER (own classes), SCHOOL_ADMIN, and KAIHLE_ADMIN. A student
calling this endpoint gets HTTP 403 — meaning the student dashboard has no way to
populate its class card list.

Two fixes are needed:

1. **Add STUDENT role** to `GET /schools/{school_id}/classes`, filtering to only the
   classes the student is enrolled in.

2. **Add `GET /students/me/classes`** to `routes/students.py` as the shortcut the
   student app actually calls. This is the clean pattern — the student app should
   not need to construct `/schools/{schoolId}/classes` from parts; it should call
   `/students/me/classes` and get back exactly what the dashboard needs.

---

## What the Student Dashboard Class Card Needs

Each class card on the student dashboard shows:
- Class name (e.g. "8A Mathematics")
- Subject name
- Grade name
- Teacher name
- `onboarding_diagnostic_status` for this enrollment — "PENDING", "IN_PROGRESS",
  or "COMPLETED" — determines locked/unlocked state
- `attempt_id` of the Tier 1 diagnostic attempt (so the student can navigate
  directly to it if locked)

The current `ClassResponse` schema does not include enrollment status. A new response
schema `StudentClassResponse` is needed that enriches the class data with per-student
enrollment fields.

---

## Change 1 — Add STUDENT Role to `GET /schools/{school_id}/classes`

In `routes/classes.py`, update `list_classes` to accept STUDENT role:

```python
@router.get("/schools/{school_id}/classes", response_model=list[ClassResponse])
async def list_classes(
    school_id: uuid.UUID,
    current_user: CurrentUser = Depends(
        require_role(
            UserRole.KAIHLE_ADMIN,
            UserRole.SCHOOL_ADMIN,
            UserRole.TEACHER,
            UserRole.STUDENT,     # ← ADD
        )
    ),
    db: AsyncSession = Depends(get_db),
) -> list[ClassResponse]:
    """List classes for a school.

    - Teacher: returns only their own classes
    - Student: returns only classes they are enrolled in
    - SchoolAdmin: returns all classes in the school
    - KaihleAdmin: returns all classes in any school
    """
    _check_school_access(school_id, current_user)
    service = SchoolService(db)

    teacher_id = current_user.id if current_user.role == UserRole.TEACHER else None

    # NEW: students see only their enrolled classes
    student_id = current_user.id if current_user.role == UserRole.STUDENT else None

    classes = await service.list_classes(school_id, teacher_id, student_id)
    return [_class_to_response(c) for c in classes]
```

Update `SchoolService.list_classes` to accept the optional `student_id` parameter:

```python
async def list_classes(
    self,
    school_id: uuid.UUID,
    teacher_id: uuid.UUID | None = None,
    student_id: uuid.UUID | None = None,
) -> list[Class]:
    query = select(Class).where(
        Class.school_id == school_id,
        Class.is_active.is_(True),
    )
    if teacher_id:
        query = query.where(Class.teacher_id == teacher_id)
    if student_id:
        # Filter to classes the student is enrolled in
        query = query.join(
            ClassEnrollment,
            (ClassEnrollment.class_id == Class.id)
            & (ClassEnrollment.student_id == student_id)
            & (ClassEnrollment.is_active.is_(True)),
        )
    return list(await self.db.scalars(query.order_by(Class.name)))
```

---

## Change 2 — Add `StudentClassResponse` Schema

Add to `schemas/school.py`:

```python
class StudentClassResponse(BaseModel):
    """Enriched class response for the student dashboard.

    Includes enrollment-specific fields (diagnostic status, attempt ID)
    that the standard ClassResponse does not carry. Used exclusively by
    GET /students/me/classes.
    """
    id: uuid.UUID
    name: str
    subject_name: str        # resolved from subjects table
    grade_name: str          # resolved from grades table
    teacher_name: str        # resolved from users table (first_name + last_name)
    curriculum_id: uuid.UUID
    academic_year: str
    is_active: bool

    # Enrollment-specific fields
    onboarding_diagnostic_status: str   # "PENDING" | "IN_PROGRESS" | "COMPLETED"
    diagnostic_attempt_id: uuid.UUID | None  # None if Celery task hasn't run yet
```

---

## Change 3 — Add `GET /students/me/classes` to `routes/students.py`

Add to the `routes/students.py` file created in M0-10-T7 Addendum 1:

```python
from app.schemas.school import StudentClassResponse

@router.get("/me/classes", response_model=list[StudentClassResponse])
async def get_my_classes(
    current_user: CurrentUser = Depends(require_role(UserRole.STUDENT)),
    db: AsyncSession = Depends(get_db),
) -> list[StudentClassResponse]:
    """Return all classes the authenticated student is enrolled in.

    Each class includes the enrollment's onboarding_diagnostic_status and
    the Tier 1 diagnostic attempt_id. This is the primary endpoint for
    populating the student dashboard class card list.

    Returns classes ordered alphabetically by name. Active enrollments only.
    """
    # STUB — M0-10-T7 addendum 2 | Real implementation: M1 (student dashboard)
    # M1 adds: real JOIN through class_enrollments → classes → subjects → grades
    #          → users (teacher) → student_attempts (Tier 1 attempt_id)
    # The stub returns an empty list so the dashboard renders its empty state.
    return []
```

The real implementation in M1 should execute a single query with all necessary joins
rather than N+1 queries per class. The query structure is:

```python
# M1 implementation pattern (not the stub — for reference when M1 implements this):
results = await db.execute(
    select(
        Class.id,
        Class.name,
        Class.curriculum_id,
        Class.academic_year,
        Class.is_active,
        Subject.name.label("subject_name"),
        Grade.name.label("grade_name"),
        (User.first_name + " " + User.last_name).label("teacher_name"),
        ClassEnrollment.onboarding_diagnostic_status,
        StudentAttempt.id.label("diagnostic_attempt_id"),
    )
    .join(ClassEnrollment, ClassEnrollment.class_id == Class.id)
    .join(Subject, Subject.id == Class.subject_id)
    .join(Grade, Grade.id == Class.grade_id)
    .join(User, User.id == Class.teacher_id)
    .outerjoin(
        Assessment,
        (Assessment.class_id == Class.id)
        & (Assessment.is_system_generated.is_(True))
        & (Assessment.status == "ACTIVE"),
    )
    .outerjoin(
        StudentAttempt,
        (StudentAttempt.assessment_id == Assessment.id)
        & (StudentAttempt.student_id == current_user.id),
    )
    .where(
        ClassEnrollment.student_id == current_user.id,
        ClassEnrollment.is_active.is_(True),
        Class.is_active.is_(True),
    )
    .order_by(Class.name)
)
```

---

## Change 4 — Update Student App Frontend Hook

In `M0-10-T8` (student app update), add the classes hook to `useStudentDashboard.ts`
or a new `useMyClasses.ts`:

```typescript
// frontend/apps/student/src/hooks/useMyClasses.ts
import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@kaihle/api-client'

export const useMyClasses = () =>
  useQuery({
    queryKey: ['student', 'my-classes'],
    queryFn: () => apiClient.get('/students/me/classes'),
    // This is the core student dashboard data — keep it fresh
    staleTime: 2 * 60 * 1000,
  })
```

The student dashboard class cards component consumes this hook. Each card reads
`onboarding_diagnostic_status` from the response to determine whether to show a
locked or unlocked state, and uses `diagnostic_attempt_id` to build the link to the
diagnostic when the card is in locked state.

---

## Acceptance Criteria

`test_list_classes_when_student_role_then_enrolled_classes_only` — Enroll student A
in class X and student B in class Y. Call `GET /schools/{id}/classes` as student A.
Assert only class X is returned and class Y is not.

`test_list_classes_when_student_not_enrolled_then_empty_list` — Call with a student
who has no enrollments. Assert HTTP 200 with an empty list.

`test_get_my_classes_when_student_enrolled_then_returns_list_with_diagnostic_status` —
Call `GET /students/me/classes` as a student enrolled in two classes. Assert HTTP 200
and each item contains `onboarding_diagnostic_status` as a non-null string.

`test_get_my_classes_when_diagnostic_pending_then_attempt_id_may_be_null` — Enroll a
student (which fires `trigger_onboarding_diagnostics` Celery task). If the task has
not yet run, `diagnostic_attempt_id` may be null. Assert the endpoint does not crash
when `diagnostic_attempt_id` is null.

`test_get_my_classes_when_teacher_role_then_403` — Call `GET /students/me/classes`
with a teacher JWT. Assert HTTP 403 — only students may call this endpoint.

`test_get_my_classes_returns_subject_grade_teacher_names` — Assert the response
contains `subject_name`, `grade_name`, and `teacher_name` as non-empty strings
(not UUIDs — these must be resolved joins, not raw foreign keys).

---

## Do NOT Touch

The existing `ClassResponse` schema — do not add enrollment fields to it. The
`StudentClassResponse` is a separate schema used only by `/students/me/classes`.
Any existing test for `GET /schools/{id}/classes` that uses TEACHER or SCHOOL_ADMIN
role — those tests must still pass unchanged.
