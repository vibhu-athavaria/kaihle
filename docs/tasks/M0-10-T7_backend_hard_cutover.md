# M0-10-T7 — Backend Hard Cutover: Rename + Restructure Existing Routes
**Milestone:** M0 · **Epic:** M0-10 · **Task:** T7
**Depends on:** ALL of M0-10-T2 through T6 must pass CI before this task starts
**Blocks:** M0-10-T8 through T12 (frontend updates)
**Estimated effort:** 4–5 hours

---

## Context

This is the highest-risk task in the M0-10 epic. It makes four structural changes to
existing, tested backend code in a single commit. The reason all four are in one task
is that they are deeply coupled — changing the `schools.py` router prefix requires
simultaneously updating every test that references the old paths, and those same tests
also need the enrollment path change. Splitting this into two tasks would leave the
codebase in a broken state between them.

The four changes are: rename the `schools.py` router prefix from `/admin/schools` to
`/schools`, split class and enrollment routes from `schools.py` into a new `classes.py`
file, rename the enrollment endpoint from the verb `/enroll` to the noun `/enrollments`,
and fix the missing KaihleAdmin bypass in `_check_school_access`.

Read CONSTITUTION.md Rule 12 (KaihleAdmin bypass pattern) before writing any code.
Run the existing test suite before starting so you have a clean baseline. Every test
that was green before this task must be green after it.

---

## Pre-Flight Check (run before touching any file)

```bash
# Confirm current test baseline — every test must pass before you start
cd backend && pytest app/tests/ -v --tb=short 2>&1 | tail -30

# Find every file that references the old paths
grep -rn "/admin/schools" backend/ --include="*.py"
grep -rn "/enroll" backend/app/ --include="*.py"
grep -rn "_check_school_access" backend/ --include="*.py"
```

Record the output. Every file returned by these greps must be updated in this task.
If you find a file not listed in the "Files to Modify" section below, add it.

---

## Files to Create

```
backend/app/api/v1/routes/classes.py    ← NEW: class + enrollment routes (moved from schools.py)
```

## Files to Modify

```
backend/app/api/v1/routes/schools.py    ← router prefix change + remove class/enrollment routes
backend/app/main.py                     ← register new classes.py router
backend/app/tests/integration/test_school_routes.py        ← update all path references
backend/app/tests/integration/test_enrollment.py           ← update all path references
backend/app/tests/integration/test_enrollment_api.py       ← update all path references
```

---

## Change 1 — `schools.py` router prefix + KaihleAdmin bypass fix

### Step 1a: Change the router prefix

```python
# BEFORE:
router = APIRouter(prefix="/admin/schools", tags=["schools"])

# AFTER:
router = APIRouter(prefix="/schools", tags=["schools"])
```

This single change means every route in `schools.py` shifts:
`/api/v1/admin/schools` → `/api/v1/schools`
`/api/v1/admin/schools/{school_id}` → `/api/v1/schools/{school_id}`

### Step 1b: Fix KaihleAdmin bypass in `get_school` handler

The `get_school` handler currently has inline authorization logic that uses the old
string comparison pattern. Replace it with the standard pattern from CONSTITUTION Rule 12:

```python
@router.get("/{school_id}", response_model=SchoolResponse)
async def get_school(
    school_id: uuid.UUID,
    current_user: CurrentUser = Depends(
        require_role(UserRole.KAIHLE_ADMIN, UserRole.SCHOOL_ADMIN)
    ),
    db: AsyncSession = Depends(get_db),
) -> SchoolResponse:
    """Get a single school. KaihleAdmin sees any school. SchoolAdmin sees own only."""
    # CONSTITUTION Rule 12: KaihleAdmin bypass must be explicit
    if current_user.role != UserRole.KAIHLE_ADMIN:
        if current_user.school_id != school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot access school from different organization",
            )
    service = SchoolService(db)
    try:
        school = await service.get_school(school_id)
        return _school_to_response(school)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="School not found")
```

### Step 1c: Remove class and enrollment routes from schools.py

Delete everything from schools.py after the school CRUD section. Specifically, remove:
- The `_class_to_response` helper function
- The `_check_school_access` helper function
- `create_class` route
- `list_classes` route
- `enroll_students` route
- `get_class_students` route

These move to `classes.py` in Change 2. After deletion, `schools.py` should contain
only: the router definition, `_school_to_response` helper, `create_school`, `list_schools`,
`get_school`, and `update_school`.

---

## Change 2 — Create `classes.py` with moved + corrected routes

Create `backend/app/api/v1/routes/classes.py` with the following content. Note
the two key differences from the old code in `schools.py`: the `_check_school_access`
helper now includes the KaihleAdmin bypass (Rule 12), and the enrollment endpoint
uses `/enrollments` instead of `/enroll`.

```python
"""Class management and enrollment API routes.

Separated from schools.py because class operations are a distinct domain concern
from school metadata management. School CRUD is a platform admin concern (KaihleAdmin).
Class and enrollment management is a school operational concern (SchoolAdmin, Teacher).

Prefix note: class list/create is nested under /schools/{school_id}/classes because
the school context is needed to scope the list. Individual class operations use
/classes/{class_id} without the school prefix because the class_id globally
identifies the class.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, require_role
from app.models.school import Class
from app.models.user import UserRole
from app.schemas.school import (
    ClassCreate,
    ClassResponse,
    EnrollRequest,
    EnrollResponse,
    StudentSummary,
)
from app.services.school_service import SchoolService

router = APIRouter(tags=["classes"])


def _class_to_response(class_: Class) -> ClassResponse:
    """Convert Class ORM model to ClassResponse schema."""
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
    )


def _check_school_access(school_id: uuid.UUID, current_user: CurrentUser) -> None:
    """Verify the requesting user can access the given school's data.

    CONSTITUTION Rule 12: KaihleAdmin bypass must be explicit and first.
    """
    if current_user.role == UserRole.KAIHLE_ADMIN:
        return  # KaihleAdmin can access any school — explicit bypass per Rule 12
    if current_user.school_id != school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this school's data",
        )


# ── School-scoped class list + create ────────────────────────────────────────

@router.post(
    "/schools/{school_id}/classes",
    response_model=ClassResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_class(
    school_id: uuid.UUID,
    body: ClassCreate,
    current_user: CurrentUser = Depends(
        require_role(UserRole.SCHOOL_ADMIN, UserRole.KAIHLE_ADMIN)
    ),
    db: AsyncSession = Depends(get_db),
) -> ClassResponse:
    """Create a class for a school. SchoolAdmin or KaihleAdmin only."""
    _check_school_access(school_id, current_user)
    service = SchoolService(db)
    try:
        class_ = await service.create_class(school_id, body)
        return _class_to_response(class_)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/schools/{school_id}/classes", response_model=list[ClassResponse])
async def list_classes(
    school_id: uuid.UUID,
    current_user: CurrentUser = Depends(
        require_role(UserRole.KAIHLE_ADMIN, UserRole.SCHOOL_ADMIN, UserRole.TEACHER)
    ),
    db: AsyncSession = Depends(get_db),
) -> list[ClassResponse]:
    """List classes. Teacher sees own classes only. SchoolAdmin/KaihleAdmin see all."""
    _check_school_access(school_id, current_user)
    service = SchoolService(db)
    teacher_id = current_user.id if current_user.role == UserRole.TEACHER else None
    classes = await service.list_classes(school_id, teacher_id)
    return [_class_to_response(c) for c in classes]


# ── Class-scoped operations ───────────────────────────────────────────────────

@router.get("/classes/{class_id}", response_model=ClassResponse)
async def get_class(
    class_id: uuid.UUID,
    current_user: CurrentUser = Depends(
        require_role(UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.KAIHLE_ADMIN)
    ),
    db: AsyncSession = Depends(get_db),
) -> ClassResponse:
    """Get a single class by ID."""
    service = SchoolService(db)
    try:
        class_ = await service.get_class(class_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")
    _check_school_access(class_.school_id, current_user)
    return _class_to_response(class_)


# ── Enrollment (noun-based resource) ─────────────────────────────────────────

@router.get("/classes/{class_id}/enrollments", response_model=list[StudentSummary])
async def list_enrollments(
    class_id: uuid.UUID,
    current_user: CurrentUser = Depends(
        require_role(UserRole.KAIHLE_ADMIN, UserRole.SCHOOL_ADMIN, UserRole.TEACHER)
    ),
    db: AsyncSession = Depends(get_db),
) -> list[StudentSummary]:
    """List students enrolled in a class."""
    service = SchoolService(db)
    try:
        class_ = await service.verify_class_school(class_id, class_.school_id)
    except (ValueError, AttributeError):
        class_ = await service.get_class(class_id)
    _check_school_access(class_.school_id, current_user)
    if current_user.role == UserRole.TEACHER and class_.teacher_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view students in your own classes",
        )
    return await service.get_class_students(class_id)


@router.post("/classes/{class_id}/enrollments", response_model=EnrollResponse)
async def create_enrollments(
    class_id: uuid.UUID,
    body: EnrollRequest,
    current_user: CurrentUser = Depends(
        require_role(UserRole.SCHOOL_ADMIN, UserRole.TEACHER, UserRole.KAIHLE_ADMIN)
    ),
    db: AsyncSession = Depends(get_db),
) -> EnrollResponse:
    """Enroll one or more students in a class.

    Body: { student_ids: list[UUID] }
    Response: { enrolled: int, skipped: int, errors: list[str] }

    Idempotent: enrolling an already-enrolled student is counted as skipped, not an error.
    """
    service = SchoolService(db)
    try:
        class_ = await service.get_class(class_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")
    _check_school_access(class_.school_id, current_user)
    if current_user.role == UserRole.TEACHER and class_.teacher_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only enroll students in your own classes",
        )
    return await service.enroll_students(class_id, body.student_ids)
```

---

## Change 3 — Register `classes.py` in `main.py`

```python
from app.api.v1.routes import classes   # add to existing imports

# Add after the schools router registration:
app.include_router(classes.router, prefix="/api/v1")
```

---

## Change 4 — Update all integration tests

This is the step that takes the most care. For every test file identified in the
pre-flight check, update path references as follows. Do not change any assertion
logic — only the URL strings.

**Path substitutions to apply across all test files:**

```python
# School routes (apply to test_school_routes.py):
"/api/v1/admin/schools"           → "/api/v1/schools"
"/api/v1/admin/schools/{id}"      → "/api/v1/schools/{id}"

# Class routes (apply to test_school_routes.py, test_enrollment.py, test_enrollment_api.py):
"/api/v1/admin/schools/{sid}/classes"                    → "/api/v1/schools/{sid}/classes"
"/api/v1/admin/schools/{sid}/classes/{cid}/enroll"       → "/api/v1/classes/{cid}/enrollments"
"/api/v1/admin/schools/{sid}/classes/{cid}/students"     → "/api/v1/classes/{cid}/enrollments"
```

After making these substitutions, run the full test suite:

```bash
pytest app/tests/integration/ -v --tb=short
```

Every test that was passing before this task must still pass. If any test fails,
fix it before committing. Do not suppress or delete failing tests.

---

## Post-Cutover Verification

After all changes are made and tests pass, run these final checks:

```bash
# Confirm no old paths remain anywhere in backend code
grep -rn "/admin/schools" backend/ --include="*.py"
# Expected output: zero lines

grep -rn '"/enroll"' backend/app/ --include="*.py"
# Expected output: zero lines

# Confirm new paths work
pytest app/tests/integration/ -v --tb=short

# Confirm type checking
mypy app/

# Confirm OpenAPI docs show correct paths
# Start the server and check GET /docs manually:
# - /schools (not /admin/schools)
# - /classes/{id}/enrollments (not /enroll)
```

---

## Acceptance Criteria

- `grep -rn "/admin/schools" backend/ --include="*.py"` returns zero results
- `grep -rn '"/enroll"' backend/app/ --include="*.py"` returns zero results
- `pytest app/tests/integration/` passes with the same number of tests as before (no tests deleted)
- `GET /api/v1/schools` with KaihleAdmin JWT returns `200`
- `GET /api/v1/schools/{id}` with KaihleAdmin JWT returns `200` for any school (bypass verified)
- `GET /api/v1/schools/{id}` with SchoolAdmin JWT returns `200` for own school, `403` for other
- `POST /api/v1/classes/{id}/enrollments` with school admin JWT returns `200` with `{ enrolled, skipped, errors }`
- `GET /api/v1/classes/{id}/enrollments` with teacher JWT returns `200`
- `GET /api/v1/classes/{id}` (new single-class endpoint) with teacher JWT returns `200`
- `mypy app/` passes with zero errors
- `GET /docs` shows `/schools` prefix — no `/admin/` prefix appears anywhere

---

## Do NOT Touch

- `routes/auth.py`
- `routes/users.py`
- `routes/onboarding.py`
- `routes/health.py`
- Any M0-10-T2 through T6 route files (they are already using correct paths)
- Any frontend file (handled in T8–T12)
