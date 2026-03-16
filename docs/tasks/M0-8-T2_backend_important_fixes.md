# M0-8-T2 — Backend Important & Minor Fixes
**Milestone:** M0 — Foundations
**Epic:** M0-8 — Pre-flight Fixes
**Task ID:** M0-8-T2
**Depends on:** M0-8-T1 (user model change affects auth service tests)
**Blocks:** M0-6-T4 (test infrastructure must be clean before UI tasks add more tests)
**Estimated effort:** 4–5 hours

---

## Context

Five improvements found in the M0 audit. None are as urgent as M0-8-T1 but all will
cause maintenance pain in M1+ if left unaddressed. Grouped here to keep the blast
radius small — one PR, one review.

---

## Fix 1 — Consolidate test fixtures into shared `conftest.py`

### Problem

Four integration test files each define their own `school`, `other_school`, `school_admin`,
`teacher`, `student_user` fixtures — identical code copied verbatim across:
- `test_auth_routes.py`
- `test_user_routes.py`
- `test_auth_middleware.py`
- `test_onboarding_api.py`
- `test_onboarding_learning_profile_api.py`

Any change to the User or School model requires updating 4–5 identical fixture definitions.
This is a significant maintenance burden.

### Fix

Create `backend/app/tests/integration/conftest.py` with shared fixtures:

```python
# backend/app/tests/integration/conftest.py
"""Shared fixtures for all integration tests.

All integration tests in this directory can use these fixtures
without importing them — pytest discovers conftest.py automatically.
"""
import uuid
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import create_access_token, hash_password
from app.models.school import Class, School
from app.models.user import User, UserRole


def make_auth_header(user: User) -> dict[str, str]:
    """Generate Authorization header with a real JWT for any user."""
    token = create_access_token(
        user_id=user.id,
        school_id=user.school_id,
        role=user.role,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def school(db_session: AsyncSession) -> School:
    s = School(id=uuid.uuid4(), name="Test School",
               slug=f"test-{uuid.uuid4().hex[:8]}", status="active")
    db_session.add(s)
    await db_session.commit()
    return s


@pytest_asyncio.fixture
async def other_school(db_session: AsyncSession) -> School:
    s = School(id=uuid.uuid4(), name="Other School",
               slug=f"other-{uuid.uuid4().hex[:8]}", status="active")
    db_session.add(s)
    await db_session.commit()
    return s


@pytest_asyncio.fixture
async def kaihle_admin(db_session: AsyncSession) -> User:
    u = User(id=uuid.uuid4(), school_id=None,
             email=f"admin-{uuid.uuid4().hex[:8]}@kaihle.ai",
             first_name="Kaihle", last_name="Admin",
             role=UserRole.KAIHLE_ADMIN, is_active=True)
    db_session.add(u)
    await db_session.commit()
    return u


@pytest_asyncio.fixture
async def school_admin(db_session: AsyncSession, school: School) -> User:
    u = User(id=uuid.uuid4(), school_id=school.id,
             email=f"sadmin-{uuid.uuid4().hex[:8]}@test.com",
             first_name="School", last_name="Admin",
             role=UserRole.SCHOOL_ADMIN, is_active=True)
    db_session.add(u)
    await db_session.commit()
    return u


@pytest_asyncio.fixture
async def teacher(db_session: AsyncSession, school: School) -> User:
    u = User(id=uuid.uuid4(), school_id=school.id,
             email=f"teacher-{uuid.uuid4().hex[:8]}@test.com",
             first_name="Test", last_name="Teacher",
             role=UserRole.TEACHER, is_active=True)
    db_session.add(u)
    await db_session.commit()
    return u


@pytest_asyncio.fixture
async def student(db_session: AsyncSession, school: School) -> User:
    u = User(id=uuid.uuid4(), school_id=school.id,
             email=f"student-{uuid.uuid4().hex[:8]}@test.com",
             first_name="Test", last_name="Student",
             role=UserRole.STUDENT, is_active=True)
    db_session.add(u)
    await db_session.commit()
    return u


@pytest_asyncio.fixture
async def student_with_password(db_session: AsyncSession, school: School) -> User:
    u = User(id=uuid.uuid4(), school_id=school.id,
             email=f"student-pw-{uuid.uuid4().hex[:8]}@test.com",
             hashed_password=hash_password("correct-password"),
             first_name="Test", last_name="Student",
             role=UserRole.STUDENT, is_active=True)
    db_session.add(u)
    await db_session.commit()
    return u
```

Then **remove the duplicate fixture definitions** from each test file and replace with
a comment: `# Fixtures provided by conftest.py`.

---

## Fix 2 — Resolve email uniqueness: global DB constraint vs per-school service check

### Problem

`User.email` has `unique=True` at the DB level — globally unique across ALL schools.
But `AuthService.register()` only checks uniqueness within the school. If the same
email exists at two different schools, the service passes validation but the INSERT
fails with an uncaught `IntegrityError` → unhandled 500 error.

### Decision (document this clearly)

**Email is globally unique.** One email address = one Kaihle account. Rationale:
- A teacher at two schools is one person, not two accounts
- Magic link login requires a globally unique email to route correctly
- Per-school email uniqueness adds complexity with no benefit at v1 scale

### Fix

**Remove the per-school uniqueness check** from `AuthService.register()` and make it
a **global uniqueness check**:

```python
# BEFORE (wrong — only checks within school)
stmt = select(User).where(User.email == email)
if school_id:
    stmt = stmt.where(User.school_id == school_id)

# AFTER (correct — email is globally unique)
stmt = select(User).where(User.email == email)
existing = await self.db.scalar(stmt)
if existing:
    raise ValueError("Email already registered")
# The DB unique constraint is the final safety net — but service check handles it gracefully
```

Also add an `IntegrityError` catch in the register route to return 409 (not 500) if the
DB constraint fires as a safety net:

```python
# In auth.py route
from sqlalchemy.exc import IntegrityError

try:
    result = await service.register(...)
except ValueError as e:
    raise HTTPException(status_code=409, detail=str(e))
except IntegrityError:
    raise HTTPException(status_code=409, detail="Email already registered")
```

Add a note to `kaihle_v2_1_schema.sql` and AGENTS.md:
> Email addresses are globally unique across all schools. One email = one Kaihle account.

---

## Fix 3 — Update CONSTITUTION §4 Rule 6 to reflect actual CI coverage threshold

### Problem

CONSTITUTION §4 Rule 6 says: `Test coverage ≥ 80% on all files in /services/`
But `ci.yml` enforces `--cov-fail-under=90`.

Agents reading the spec think 80% is acceptable. CI will reject their PRs at 90%.
This creates confusion and wasted CI cycles.

### Fix

**Update `docs/CONSTITUTION.md` §4 Rule 6:**

```
FIND:
6. **Test coverage ≥ 80%** on all files in `/services/`. Enforced by CI — no merge to `main` if below.

REPLACE WITH:
6. **Test coverage ≥ 90%** on all files in `/services/`. Enforced by CI — no merge to `main` if below.
   Pre-commit hook enforces ≥ 80% on unit tests locally. Full 90% threshold is verified in CI
   against both unit and integration tests combined.
```

---

## Fix 4 — Refactor onboarding route access control (eliminate duplication)

### Problem

`GET /api/v1/onboarding/learning-profile` in `onboarding.py` manually replicates
`require_school_match` logic that already exists as a FastAPI dependency. It also
makes a separate `verify_teacher_student_relationship()` DB call that could be
combined with the profile fetch.

### Fix

Refactor `get_learning_profile` in `backend/app/api/v1/routes/onboarding.py`:

```python
@router.get("/learning-profile", response_model=StudentLearningProfileResponse)
async def get_learning_profile(
    current_user: CurrentUser = Depends(
        require_role(UserRole.KAIHLE_ADMIN, UserRole.SCHOOL_ADMIN, UserRole.TEACHER, UserRole.STUDENT)
    ),
    student_id: UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> StudentLearningProfile:
    service = OnboardingService(db)
    # Resolve which student's profile we're fetching
    target_id = _resolve_target_student(current_user, student_id)
    # Service handles all authorization — raises 403 via standard patterns
    profile = await service.get_learning_profile_authorized(
        requester=current_user,
        target_student_id=target_id,
    )
    return profile

def _resolve_target_student(current_user: CurrentUser, student_id: UUID | None) -> UUID:
    """Resolve target student ID. Students always get their own."""
    if current_user.role == UserRole.STUDENT:
        return current_user.id
    if student_id is None:
        raise HTTPException(status_code=400, detail="student_id is required for this role")
    return student_id
```

Move the authorization logic into `OnboardingService.get_learning_profile_authorized()`.
The service raises `PermissionError` → route maps to 403. No business logic in the route.

---

## Fix 5 — Add OpenAPI router tags + clean up port config doc

### Fix 5a — OpenAPI tags

Add `tags=` to every router that is missing them:

```python
# backend/app/api/v1/routes/onboarding.py
router = APIRouter(prefix="/onboarding", tags=["onboarding"])

# backend/app/api/v1/routes/schools.py  
router = APIRouter(prefix="/admin/schools", tags=["schools"])

# backend/app/api/v1/routes/users.py
router = APIRouter(prefix="", tags=["users"])
```

Also move the usage documentation from `main.py`'s module docstring into the FastAPI
app constructor's `description=` parameter:

```python
app = FastAPI(
    title="Kaihle API",
    version="0.1.0",
    description="""
## Authentication

Use `Authorization: Bearer <access_token>` on all protected endpoints.

### Route Guards
- `get_current_user` — validates JWT Bearer token
- `require_role(*roles)` — enforces role-based access control
- `require_school_match` — ensures user's school matches resource school
- `require_onboarding_complete` — blocks students until onboarding is done
    """,
    lifespan=lifespan,
)
```

### Fix 5b — Delete oversized port configuration document

Delete `docs/testing/port_configuration_test_plan.md`.

Replace its content with a comment in `docker-compose.yml` and `.env.example`:

```yaml
# docker-compose.yml — postgres service
ports:
  - "5433:5432"  # Host port 5433 to avoid conflicts with local PostgreSQL on 5432.
                 # CI uses port 5432 (GitHub Actions service containers use standard ports).
                 # Tests run locally should use: DATABASE_URL=...@localhost:5433/...
```

---

## Files to Modify

```
backend/app/tests/integration/conftest.py              ← CREATE (shared fixtures)
backend/app/tests/integration/test_auth_routes.py      ← REMOVE duplicate fixtures
backend/app/tests/integration/test_user_routes.py      ← REMOVE duplicate fixtures
backend/app/tests/integration/test_auth_middleware.py  ← REMOVE duplicate fixtures
backend/app/tests/integration/test_onboarding_api.py   ← REMOVE duplicate fixtures
backend/app/tests/integration/test_onboarding_learning_profile_api.py ← REMOVE duplicates
backend/app/services/auth_service.py                   ← global email uniqueness check
backend/app/api/v1/routes/auth.py                      ← catch IntegrityError → 409
backend/app/api/v1/routes/onboarding.py                ← refactor access control
backend/app/services/onboarding_service.py             ← add get_learning_profile_authorized()
backend/app/api/v1/routes/schools.py                   ← add tags=
backend/app/api/v1/routes/users.py                     ← add tags=
backend/app/main.py                                    ← move docs to description= param
docs/CONSTITUTION.md                                   ← §4 Rule 6: 80% → 90%
docs/testing/port_configuration_test_plan.md           ← DELETE
docker-compose.yml                                     ← add port explanation comment
```

---

## Acceptance Criteria

- [ ] All integration test files pass with fixtures from `conftest.py` (no local fixture redefinitions)
- [ ] `pytest app/tests/integration/ -v` shows no fixture-not-found errors after removing duplicates
- [ ] Integration test: `POST /auth/register` with duplicate email returns 409 (not 500)
- [ ] Integration test: same email at two different schools returns 409 on second registration
- [ ] Integration test: `GET /onboarding/learning-profile` by teacher for student NOT in their class returns 403
- [ ] `GET /docs` (Swagger UI) shows endpoints grouped under "auth", "schools", "users", "onboarding" tags
- [ ] `docs/CONSTITUTION.md` §4 Rule 6 reads "≥ 90%"
- [ ] `docs/testing/port_configuration_test_plan.md` no longer exists
- [ ] `docker-compose.yml` has comment explaining port 5433 mapping
- [ ] `mypy app/` passes with zero errors
- [ ] All existing integration tests continue to pass (no regressions from fixture consolidation)
