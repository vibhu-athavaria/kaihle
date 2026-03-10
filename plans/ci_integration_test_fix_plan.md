# Fix Plan: CI Integration Test Failures

## Issue 1: Database Unique Constraint Violation

**Error:** `IntegrityError: duplicate key on constraint "grades_level_key"`

**Root Cause:** Test data from previous test runs is not being cleaned up properly. The `grades` table has a unique constraint on `(school_id, level)` and data is persisting between tests.

**Fix:** Ensure database is properly cleaned between tests. The `db_session` fixture should drop and recreate all tables before each test.

---

## Issue 2: Unauthorized API Responses (401 Errors)

**Error:** All school API tests receive HTTP 401 instead of expected status codes.

**Root Cause:** The test uses a mock auth format:
```python
def auth_header(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer mock:{user.id}:{user.email}:{user.role}:{user.school_id}"}
```

This mock format is not recognized by the auth middleware (`get_current_user`), which expects either:
1. A valid JWT token, OR
2. A bypass mechanism for testing

**Fix:** Generate real JWT tokens for testing.

---

## Step-by-Step Fix Plan

### Step 1: Generate Real JWT Tokens for Tests

Modify `test_school_routes.py` to use real JWT tokens instead of mock tokens.

**File:** `backend/app/tests/integration/test_school_routes.py`

**Changes:**
1. Import the token creation function:
```python
from app.core.security import create_access_token
```

2. Update the `auth_header` function to generate real tokens:
```python
def auth_header(user: User) -> dict[str, str]:
    """Generate Authorization header with real JWT for a user."""
    token = create_access_token(user.id, user.school_id, user.role)
    return {"Authorization": f"Bearer {token}"}
```

### Step 2: Ensure Database Cleanup

The database cleanup should already be working via the `db_session` fixture in `conftest.py`:
```python
async def db_session(engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
```

If this isn't working, check that:
1. The fixture is being used correctly
2. The `Base.metadata.drop_all` is actually deleting data

---

## Why This Works

1. **Real JWT tokens:** The `create_access_token` function generates a valid JWT that the `get_current_user` dependency can decode and validate.

2. **Database cleanup:** Dropping and recreating all tables ensures no leftover data from previous tests.

---

## Alternative: Test Token Bypass (Not Recommended)

An alternative would be to modify the auth middleware to recognize a test token format, but this is not recommended because:
- It bypasses security in tests
- It could accidentally be left in production code
- It doesn't test the real authentication flow

The real JWT approach is better because it tests the actual authentication flow.
