# M0-10-T7 Addendum — Missing CRUD Stubs + Learning Profile Path Rename
**Reads alongside:** `M0-10/M0-10-T7_backend_hard_cutover.md`
**Must be executed as part of M0-10-T7** — not a separate task

---

## Purpose

After a full API audit, seven endpoints from the canonical API design were found to
have no stub or task file at all. This addendum adds them. It also documents the
learning profile path rename that must happen in the same commit as the other
M0-10-T7 changes.

All changes in this addendum follow the same rules as M0-10-T7: hard cutover in a
single commit, no dual-path transition, all tests updated in the same commit.

---

## Section 1 — Missing CRUD Stubs

These seven endpoints belong in existing route files. Add them in the same commit as
the M0-10-T7 rename work. Each stub follows the standard pattern:

```python
# STUB — M0-10-T7 addendum | Real implementation: [milestone]
# Replace this function body. Do not change the signature or response_model.
```

### 1a. `DELETE /schools/{school_id}` — Add to `routes/schools.py`

```python
@router.delete("/{school_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_school(
    school_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> None:
    # STUB — M0-10-T7 addendum | Real implementation: M6 (platform management)
    # Deactivates the school — does not delete the row.
    # M6 adds: set school.status = 'inactive', cascade deactivate all users.
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="School deactivation is available from M6.",
    )
```

### 1b. `GET /classes/{class_id}` — Add to `routes/classes.py`

```python
@router.get("/classes/{class_id}", response_model=ClassResponse)
async def get_class(
    class_id: uuid.UUID,
    current_user: CurrentUser = Depends(
        require_role(UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.KAIHLE_ADMIN)
    ),
    db: AsyncSession = Depends(get_db),
) -> ClassResponse:
    # STUB — M0-10-T7 addendum | Real implementation: M1 (class management)
    service = SchoolService(db)
    try:
        class_ = await service.get_class(class_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")
    _check_school_access(class_.school_id, current_user)
    return _class_to_response(class_)
```

Note: `get_class(class_id)` is a simple `SELECT * FROM classes WHERE id = ?`. Add it
to `SchoolService` if it does not already exist.

### 1c. `PATCH /classes/{class_id}` — Add to `routes/classes.py`

```python
from app.schemas.school import ClassUpdate  # add this schema if it does not exist

@router.patch("/classes/{class_id}", response_model=ClassResponse)
async def update_class(
    class_id: uuid.UUID,
    body: ClassUpdate,
    current_user: CurrentUser = Depends(
        require_role(UserRole.SCHOOL_ADMIN, UserRole.KAIHLE_ADMIN)
    ),
    db: AsyncSession = Depends(get_db),
) -> ClassResponse:
    # STUB — M0-10-T7 addendum | Real implementation: M1
    # M1 adds: update class name, teacher_id, academic_year.
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Class update is available from M1.",
    )
```

Add `ClassUpdate` to `schemas/school.py`:

```python
class ClassUpdate(BaseModel):
    """All fields optional — PATCH applies only the fields provided."""
    name: str | None = None
    teacher_id: uuid.UUID | None = None
    academic_year: str | None = None
    is_active: bool | None = None
```

### 1d. `DELETE /classes/{class_id}` — Add to `routes/classes.py`

```python
@router.delete("/classes/{class_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_class(
    class_id: uuid.UUID,
    current_user: CurrentUser = Depends(
        require_role(UserRole.SCHOOL_ADMIN, UserRole.KAIHLE_ADMIN)
    ),
    db: AsyncSession = Depends(get_db),
) -> None:
    # STUB — M0-10-T7 addendum | Real implementation: M1
    # Deactivates the class (sets is_active = False). Does not delete enrollments.
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Class deactivation is available from M1.",
    )
```

### 1e. `DELETE /classes/{class_id}/enrollments/{student_id}` — Add to `routes/classes.py`

```python
@router.delete(
    "/classes/{class_id}/enrollments/{student_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_enrollment(
    class_id: uuid.UUID,
    student_id: uuid.UUID,
    current_user: CurrentUser = Depends(
        require_role(UserRole.SCHOOL_ADMIN, UserRole.TEACHER, UserRole.KAIHLE_ADMIN)
    ),
    db: AsyncSession = Depends(get_db),
) -> None:
    # STUB — M0-10-T7 addendum | Real implementation: M1
    # Removes a student from a class. Does not delete gap_states.
    # Teacher may only unenroll from their own class.
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Unenrollment is available from M1.",
    )
```

### 1f. `PATCH /assessments/{assessment_id}` — Add to `routes/assessments.py`

```python
from app.schemas.assessments import AssessmentUpdateRequest  # add if not exists

@router.patch("/assessments/{assessment_id}", response_model=AssessmentResponse)
async def update_assessment(
    assessment_id: uuid.UUID,
    body: AssessmentUpdateRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER)),
    db: AsyncSession = Depends(get_db),
) -> AssessmentResponse:
    # STUB — M0-10-T7 addendum | Real implementation: M1-3-T2
    # Allows updating title and deadline before publish.
    # Only allowed on DRAFT assessments owned by the requesting teacher.
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="No assessments exist yet.",
    )
```

Add `AssessmentUpdateRequest` to `schemas/assessments.py`:

```python
class AssessmentUpdateRequest(BaseModel):
    """All fields optional — PATCH applies only the fields provided.
    Only allowed on DRAFT assessments.
    """
    title: str | None = None
    deadline: datetime | None = None
```

### 1g. `GET /onboarding/pending` — Add to `routes/onboarding.py`

```python
@router.get("/pending", response_model=Page[dict])
async def list_pending_onboarding(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: CurrentUser = Depends(
        require_role(UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.KAIHLE_ADMIN)
    ),
    db: AsyncSession = Depends(get_db),
) -> Page[dict]:
    # STUB — M0-10-T7 addendum | Real implementation: M1 (school admin views)
    # Returns students who have not completed their learning profile or
    # at least one Tier 1 diagnostic. Used by school admin and teachers
    # to follow up with students who have fallen behind onboarding.
    # M1 adds: real query against student_profiles + class_enrollments.
    return Page(data=[], total=0, page=page, page_size=page_size)
```

---

## Section 2 — Learning Profile Path Rename

The existing onboarding routes expose learning profiles at the wrong paths. The
canonical design puts them under `/students/` not `/onboarding/`.

**Current paths (wrong):**
- `GET /api/v1/onboarding/learning-profile` (own profile, student)
- `GET /api/v1/onboarding/learning-profile?student_id={id}` (specific student)

**Correct paths:**
- `GET /api/v1/students/me/learning-profile`
- `GET /api/v1/students/{student_id}/learning-profile`

### Step 1 — Create `routes/students.py`

Create a new file `backend/app/api/v1/routes/students.py` that houses the student-
scoped endpoints. Move the learning profile logic here. The `/me` shortcut and the
explicit `{student_id}` endpoint are separate routes — do not use a query parameter
to distinguish them.

```python
"""Student-scoped API routes.

Endpoints that operate on a specific student's data and use the /students/
URL namespace. This is distinct from the student *role* — these endpoints
are also accessible to teachers and admins for viewing their students' data.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, require_role, require_full_access
from app.models.user import UserRole
from app.services.onboarding_service import OnboardingService

router = APIRouter(prefix="/students", tags=["students"])


@router.get("/me/learning-profile")
async def get_my_learning_profile(
    current_user: CurrentUser = Depends(require_role(UserRole.STUDENT)),
    db: AsyncSession = Depends(get_db),
):
    # STUB — M0-10-T7 addendum | Real implementation: already exists in onboarding.py
    # This endpoint delegates to the same OnboardingService.get_learning_profile()
    # method. The path is updated; the logic is identical.
    service = OnboardingService(db)
    profile = await service.get_learning_profile(current_user.id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Learning profile not yet completed",
        )
    return profile


@router.get("/{student_id}/learning-profile")
async def get_student_learning_profile(
    student_id: UUID,
    current_user: CurrentUser = Depends(require_full_access),
    db: AsyncSession = Depends(get_db),
):
    # STUB — M0-10-T7 addendum | Real implementation: already exists in onboarding.py
    # Teacher/admin access: verify relationship in OnboardingService.
    service = OnboardingService(db)
    profile = await service.get_learning_profile_authorized(
        requester=current_user,
        target_student_id=student_id,
    )
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Learning profile not yet completed",
        )
    return profile
```

### Step 2 — Remove from `routes/onboarding.py`

Delete the `GET /learning-profile` route handler from `routes/onboarding.py`. The
route no longer lives there.

### Step 3 — Register `students.py` in `main.py`

```python
from app.api.v1.routes import students   # add to imports
app.include_router(students.router, prefix="/api/v1")
```

### Step 4 — Update integration tests

Find all tests referencing `/api/v1/onboarding/learning-profile` and update them to
the new paths. Use grep:

```bash
grep -rn "onboarding/learning-profile" backend/ --include="*.py"
```

Update each reference:
- `GET /api/v1/onboarding/learning-profile` (student's own) → `GET /api/v1/students/me/learning-profile`
- `GET /api/v1/onboarding/learning-profile?student_id={id}` → `GET /api/v1/students/{id}/learning-profile`

### Step 5 — Update frontend hooks

In `M0-10-T8` (student app) and `M0-10-T9` (teacher app), find any hook calling the
old path and update:

```typescript
// OLD:
apiClient.get('/onboarding/learning-profile')
apiClient.get(`/onboarding/learning-profile?student_id=${studentId}`)

// NEW:
apiClient.get('/students/me/learning-profile')
apiClient.get(`/students/${studentId}/learning-profile`)
```

---

## Post-Addendum Verification

After all addendum changes are made in the same commit as the M0-10-T7 main changes,
run these checks alongside the M0-10-T7 post-cutover verification:

```bash
# Confirm no old learning-profile path remains in backend code
grep -rn "onboarding/learning-profile" backend/app/api/ --include="*.py"
# Expected: zero results

# Confirm all seven new stubs appear in OpenAPI spec
# Start the server, then:
curl http://localhost:8000/openapi.json | python -m json.tool | grep -E '"path".*classes.*class_id'
# Should show: GET /classes/{class_id}, PATCH /classes/{class_id}, DELETE /classes/{class_id}
```

---

## Acceptance Criteria (additions to M0-10-T7 checklist)

- `GET /api/v1/classes/{id}` with teacher JWT returns `200` with class data
- `PATCH /api/v1/classes/{id}` with school admin JWT returns `501`
- `DELETE /api/v1/classes/{id}` with school admin JWT returns `501`
- `DELETE /api/v1/classes/{id}/enrollments/{student_id}` with school admin JWT returns `501`
- `DELETE /api/v1/schools/{id}` with KaihleAdmin JWT returns `501`
- `PATCH /api/v1/assessments/{id}` with teacher JWT returns `404` (correct stub for no-data state)
- `GET /api/v1/onboarding/pending` with teacher JWT returns `200` with `{ data: [], total: 0, page: 1, page_size: 20 }`
- `GET /api/v1/students/me/learning-profile` with student JWT returns `200` or `404` (depending on whether profile exists)
- `GET /api/v1/students/{id}/learning-profile` with teacher JWT returns `200` or `404`
- `GET /api/v1/onboarding/learning-profile` (OLD PATH) returns `404` — route no longer exists
- `grep -rn "onboarding/learning-profile" backend/app/api/` returns zero results
- All existing learning profile tests pass against the new paths
- `mypy app/` passes with zero errors
