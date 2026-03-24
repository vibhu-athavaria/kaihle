# M0-10-T7 Addendum B — Student Class Access Fix
**Reads alongside:** `M0-10/M0-10-T7_backend_hard_cutover.md` and `M0-10-T7_addendum_missing_stubs.md`
**Must be executed as part of M0-10-T7** — not a separate task

---

## Problem

The current `GET /schools/{school_id}/classes` route and the new
`GET /classes/{class_id}` stub (added in M0-10-T7 Addendum A) both use
`require_role(TEACHER, SCHOOL_ADMIN, KAIHLE_ADMIN)`. The STUDENT role is absent.

This means a student calling either endpoint receives HTTP 403. The student dashboard
has no way to fetch the class cards it needs to render — there is no other endpoint
that returns a student's enrolled classes. Without this fix, the student app is
broken from first login.

---

## Design Decision

Students are added to both class read endpoints with a specific filter rule:

**A student may only see classes they are currently enrolled in.**

This is enforced in the service layer using a JOIN on `class_enrollments`, not by
trusting the student to pass only their own class IDs. The school_id scoping from
CONSTITUTION Rule 3 still applies — the student's JWT carries their `school_id`
and the query filters by it.

Students never see:
- Classes at a different school
- Classes they are not enrolled in
- Other students' data within a class

---

## Files to Modify (in the same M0-10-T7 commit)

```
backend/app/api/v1/routes/classes.py    ← update two route handlers
backend/app/services/school_service.py  ← add list_enrolled_classes() method
backend/app/tests/integration/test_class_routes.py  ← add student-role tests
```

---

## Change 1 — `list_classes` route (`GET /schools/{school_id}/classes`)

Replace the current implementation in `classes.py`:

```python
@router.get("/schools/{school_id}/classes", response_model=list[ClassResponse])
async def list_classes(
    school_id: uuid.UUID,
    current_user: CurrentUser = Depends(
        require_role(
            UserRole.KAIHLE_ADMIN,
            UserRole.SCHOOL_ADMIN,
            UserRole.TEACHER,
            UserRole.STUDENT,   # ← ADD
        )
    ),
    db: AsyncSession = Depends(get_db),
) -> list[ClassResponse]:
    """List classes for a school.

    Role-based filtering:
    - STUDENT: only classes the student is enrolled in
    - TEACHER: only classes the teacher is assigned to
    - SCHOOL_ADMIN: all active classes in the school
    - KAIHLE_ADMIN: all active classes in any school

    Students use this endpoint to populate their dashboard class cards.
    """
    _check_school_access(school_id, current_user)
    service = SchoolService(db)

    if current_user.role == UserRole.STUDENT:
        # Students see only their enrolled classes
        classes = await service.list_enrolled_classes(
            student_id=current_user.id,
            school_id=school_id,
        )
    elif current_user.role == UserRole.TEACHER:
        classes = await service.list_classes(
            school_id=school_id,
            teacher_id=current_user.id,
        )
    else:
        # SCHOOL_ADMIN and KAIHLE_ADMIN see all classes
        classes = await service.list_classes(school_id=school_id)

    return [_class_to_response(c) for c in classes]
```

---

## Change 2 — `get_class` route (`GET /classes/{class_id}`)

Update the stub added in Addendum A to also allow STUDENT, with an enrollment check:

```python
@router.get("/classes/{class_id}", response_model=ClassResponse)
async def get_class(
    class_id: uuid.UUID,
    current_user: CurrentUser = Depends(
        require_role(
            UserRole.TEACHER,
            UserRole.SCHOOL_ADMIN,
            UserRole.KAIHLE_ADMIN,
            UserRole.STUDENT,   # ← ADD
        )
    ),
    db: AsyncSession = Depends(get_db),
) -> ClassResponse:
    """Get a single class by ID.

    Students may only fetch classes they are enrolled in.
    """
    service = SchoolService(db)
    try:
        class_ = await service.get_class(class_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class not found",
        )

    # School-scoping check (KAIHLE_ADMIN bypasses per Rule 12)
    _check_school_access(class_.school_id, current_user)

    # Students: verify enrollment — return 404 (not 403) to avoid leaking
    # that the class exists at all for non-enrolled students
    if current_user.role == UserRole.STUDENT:
        enrolled = await service.is_student_enrolled(
            student_id=current_user.id,
            class_id=class_id,
        )
        if not enrolled:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Class not found",
            )

    return _class_to_response(class_)
```

---

## Change 3 — New `SchoolService` methods

Add two methods to `backend/app/services/school_service.py`.

### `list_enrolled_classes`

```python
async def list_enrolled_classes(
    self,
    student_id: uuid.UUID,
    school_id: uuid.UUID,
) -> list[Class]:
    """Return all active classes a student is enrolled in, filtered by school.

    Args:
        student_id: The student's UUID (from JWT — do not trust client input).
        school_id: Multi-tenancy guard — only returns classes in this school.

    Returns:
        List of Class models the student is actively enrolled in.
    """
    result = await self.db.execute(
        select(Class)
        .join(ClassEnrollment, ClassEnrollment.class_id == Class.id)
        .where(
            ClassEnrollment.student_id == student_id,
            ClassEnrollment.is_active.is_(True),
            Class.school_id == school_id,
            Class.is_active.is_(True),
        )
        .order_by(Class.name)
    )
    return list(result.scalars().all())
```

### `is_student_enrolled`

```python
async def is_student_enrolled(
    self,
    student_id: uuid.UUID,
    class_id: uuid.UUID,
) -> bool:
    """Check whether a student has an active enrollment in a class.

    Used by route handlers to gate per-class access.

    Args:
        student_id: The student's UUID.
        class_id: The class to check enrollment for.

    Returns:
        True if an active ClassEnrollment row exists, False otherwise.
    """
    enrollment = await self.db.scalar(
        select(ClassEnrollment).where(
            ClassEnrollment.student_id == student_id,
            ClassEnrollment.class_id == class_id,
            ClassEnrollment.is_active.is_(True),
        )
    )
    return enrollment is not None
```

---

## ClassResponse Schema Update

The student app needs to know the diagnostic status for each class card (locked vs
unlocked). Add `onboarding_diagnostic_status` to `ClassResponse` in `schemas/school.py`
so the student dashboard can render the correct card state without a second API call:

```python
class ClassResponse(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID
    grade_id: uuid.UUID
    subject_id: uuid.UUID
    curriculum_id: uuid.UUID
    teacher_id: uuid.UUID
    name: str
    academic_year: str
    is_active: bool
    # Added for student dashboard — shows whether Tier 1 diagnostic is complete
    # for the requesting student's enrollment in this class.
    # None when the requesting user is not a student (teacher/admin views).
    onboarding_diagnostic_status: str | None = None
    # Human-readable subject and grade names — avoids extra API calls from frontend
    subject_name: str | None = None
    grade_name: str | None = None
```

Update `_class_to_response` in `classes.py` to accept an optional enrollment row
when building the response for a student caller:

```python
def _class_to_response(
    class_: Class,
    enrollment: ClassEnrollment | None = None,
) -> ClassResponse:
    return ClassResponse(
        id=class_.id,
        school_id=class_.school_id,
        grade_id=class_.grade_id,
        subject_id=class_.subject_id,
        curriculum_id=class_.curriculum_id,
        teacher_id=class_.teacher_id,
        name=class_.name,
        academic_year=class_.academic_year,
        is_active=class_.is_active,
        onboarding_diagnostic_status=(
            enrollment.onboarding_diagnostic_status if enrollment else None
        ),
    )
```

Update `list_enrolled_classes` to return both the Class and its ClassEnrollment row
so `list_classes` can pass the enrollment to `_class_to_response`:

```python
async def list_enrolled_classes(
    self,
    student_id: uuid.UUID,
    school_id: uuid.UUID,
) -> list[tuple[Class, ClassEnrollment]]:
    """Return (Class, ClassEnrollment) pairs for a student."""
    result = await self.db.execute(
        select(Class, ClassEnrollment)
        .join(ClassEnrollment, ClassEnrollment.class_id == Class.id)
        .where(
            ClassEnrollment.student_id == student_id,
            ClassEnrollment.is_active.is_(True),
            Class.school_id == school_id,
            Class.is_active.is_(True),
        )
        .order_by(Class.name)
    )
    return list(result.all())
```

Then in the route:

```python
if current_user.role == UserRole.STUDENT:
    pairs = await service.list_enrolled_classes(
        student_id=current_user.id,
        school_id=school_id,
    )
    return [_class_to_response(c, e) for c, e in pairs]
```

---

## Frontend Hook Update (`apps/student`)

The student dashboard currently has no hook to fetch classes. Add this to
`frontend/apps/student/src/hooks/useStudentClasses.ts` (create if it does not exist,
update if it does):

```typescript
import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@kaihle/api-client'
import { useAuthStore } from '@kaihle/auth'

export const useMyClasses = () => {
  const { user } = useAuthStore()
  return useQuery({
    queryKey: ['student', 'classes', user?.school_id],
    queryFn: () =>
      apiClient.get(`/schools/${user?.school_id}/classes`),
    enabled: !!user?.school_id,
  })
}

export const useMyClass = (classId: string) =>
  useQuery({
    queryKey: ['student', 'class', classId],
    queryFn: () => apiClient.get(`/classes/${classId}`),
    enabled: !!classId,
  })
```

The `onboarding_diagnostic_status` field in each class response drives the class card
locked/unlocked state on the student dashboard — no separate API call needed.

---

## Updated API Endpoint Map Entry

Replace the existing entries in `docs/API_ENDPOINT_TASK_MAP.md`:

| `GET /schools/{school_id}/classes` | ✅ Built + updated | `M0/M0-4-T3` + this addendum | **STUDENT role added** — students see enrolled classes only |
| `GET /classes/{class_id}` | 🔧 Stubbed + updated | M0-10-T7 addendum A + this addendum | **STUDENT role added** — 404 if not enrolled |

---

## Acceptance Criteria

**New tests to add to `test_class_routes.py`:**

`test_list_classes_when_student_enrolled_then_returns_enrolled_classes_only` — Enroll
a student in 2 of 3 classes in their school. Call `GET /schools/{school_id}/classes`
as the student. Assert HTTP 200 and exactly 2 classes returned — the 3rd class the
student is not enrolled in must not appear.

`test_list_classes_when_student_returns_onboarding_status_in_response` — Enroll a
student. Set their `onboarding_diagnostic_status = 'COMPLETED'` for one class and
`'PENDING'` for another. Call the endpoint. Assert each class in the response has
the correct `onboarding_diagnostic_status` value.

`test_list_classes_when_student_no_enrollments_then_empty_list` — A student with no
enrollments. Assert HTTP 200 with `[]` — not 404.

`test_list_classes_when_student_different_school_then_403` — Authenticate as a
student from school A and call `GET /schools/{school_B_id}/classes`. Assert HTTP 403.

`test_get_class_when_student_enrolled_then_200` — Authenticate as an enrolled
student. Call `GET /classes/{class_id}`. Assert HTTP 200.

`test_get_class_when_student_not_enrolled_then_404` — Authenticate as a student not
enrolled in the class. Assert HTTP 404 (not 403 — we do not reveal that the class
exists to non-enrolled students).

`test_list_classes_when_teacher_then_only_own_classes` — Unchanged behaviour — still
returns only the teacher's assigned classes.

`test_list_classes_when_school_admin_then_all_classes` — Unchanged behaviour.

---

## Do NOT Touch

The `require_diagnostic_complete` dependency in `student_content.py` — it is a
separate gate that applies to class *content*, not to the class list itself. A student
can always see their class list even before completing the diagnostic — that is how
they know which diagnostic to take.
