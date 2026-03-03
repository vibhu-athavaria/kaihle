# M0-3-T3 — Auth Middleware & Route Guards
**Milestone:** M0 — Foundations
**Epic:** M0-3 — Authentication System
**Task ID:** M0-3-T3
**Mode:** Code (MiniMax)
**Estimated effort:** 2–3 hours

---

## Context

This task creates FastAPI dependency functions that protect routes. Three guards are implemented: `get_current_user` (validates JWT), `require_role` (enforces role-based access), and `require_onboarding_complete` (NEW v2.1 — blocks students from the dashboard until onboarding is done).

**Depends on:** M0-3-T1 (decode_token), M0-2-T2 (User, StudentProfile, StudentLearningProfile models), M0-6-T3 (onboarding service — implements `require_onboarding_complete` last since it depends on onboarding service)

**Note:** `require_onboarding_complete` calls the onboarding service from M0-6-T3. If M0-6-T3 is not yet done, implement the guard as a stub that always passes — complete it once M0-6-T3 is merged.

---

## User Story

As the system, I want every protected endpoint to verify the caller's identity and role before processing any request.

---

## What To Build

### `/backend/app/core/deps.py`

```python
import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import InvalidTokenError, decode_token
from app.models.user import User

security = HTTPBearer()


# ---------------------------------------------------------------------------
# Core: extract and validate JWT
# ---------------------------------------------------------------------------

async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    FastAPI dependency. Extracts Bearer token, decodes JWT, loads User from DB.
    Raises 401 if token is missing, invalid, or expired.
    Raises 401 if user not found or inactive.
    """
    try:
        payload = decode_token(credentials.credentials)
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid token payload")

    user = await db.get(User, uuid.UUID(user_id_str))
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="User not found or inactive")

    return user


# ---------------------------------------------------------------------------
# Role guard
# ---------------------------------------------------------------------------

def require_role(*allowed_roles: str):
    """
    FastAPI dependency factory.
    Usage: Depends(require_role("TEACHER", "SCHOOL_ADMIN"))
    Raises 403 if the current user's role is not in allowed_roles.
    """
    async def _check_role(
        current_user: Annotated[User, Depends(get_current_user)]
    ) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role}' is not permitted for this action",
            )
        return current_user
    return _check_role


# ---------------------------------------------------------------------------
# School resource guard
# ---------------------------------------------------------------------------

def require_school_match(school_id: uuid.UUID):
    """
    FastAPI dependency factory.
    Ensures requesting user's school_id matches the resource's school_id.
    KaihleAdmin bypasses this check.
    Usage: Depends(require_school_match(school_id_from_path))
    """
    async def _check_school(
        current_user: Annotated[User, Depends(get_current_user)]
    ) -> User:
        if current_user.role == "KAIHLE_ADMIN":
            return current_user
        if current_user.school_id != school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this school's resources",
            )
        return current_user
    return _check_school


# ---------------------------------------------------------------------------
# Onboarding gate (NEW v2.1)
# ---------------------------------------------------------------------------

async def require_onboarding_complete(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    FastAPI dependency. For STUDENT role only.
    Blocks access unless BOTH conditions are met:
      1. student_profiles.onboarding_diagnostic_status == 'COMPLETED'
      2. student_learning_profiles.completed_at IS NOT NULL

    Non-student roles pass through without any check.
    KaihleAdmin passes through.

    Returns 403 with redirect hint if onboarding is incomplete:
      { "detail": "Onboarding not complete", "redirect": "/student/onboarding" }

    Apply to all student-facing routes EXCEPT /student/onboarding/* routes.
    """
    if current_user.role != "STUDENT":
        return current_user

    from sqlalchemy import select
    from app.models.user import StudentProfile
    from app.models.onboarding import StudentLearningProfile

    # Check diagnostic status
    profile = await db.scalar(
        select(StudentProfile).where(StudentProfile.user_id == current_user.id)
    )
    if not profile or profile.onboarding_diagnostic_status != "COMPLETED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": "Onboarding not complete",
                "redirect": "/student/onboarding",
            },
        )

    # Check learning profile
    learning_profile = await db.scalar(
        select(StudentLearningProfile).where(
            StudentLearningProfile.student_id == current_user.id
        )
    )
    if not learning_profile or learning_profile.completed_at is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": "Onboarding not complete",
                "redirect": "/student/onboarding",
            },
        )

    return current_user


# ---------------------------------------------------------------------------
# Convenience type aliases for route signatures
# ---------------------------------------------------------------------------

CurrentUser = Annotated[User, Depends(get_current_user)]
```

---

### Apply Guards to `main.py`

Add a middleware note in `main.py` — the guards are applied per-route via `Depends()`, not as global middleware. Document this clearly:

```python
# Authentication: applied per-route via Depends(get_current_user)
# Role enforcement: applied per-route via Depends(require_role(...))
# Onboarding gate: applied to all /student/* routes except /student/onboarding/*
#                  via Depends(require_onboarding_complete)
```

---

## Files To Create

```
/backend/app/core/deps.py
```

---

## Tests To Write

**`/backend/app/tests/integration/test_auth_middleware.py`:**

```python
# Use httpx AsyncClient against the running FastAPI app

async def test_get_current_user_when_no_token_then_returns_401():
    ...

async def test_get_current_user_when_expired_token_then_returns_401():
    ...

async def test_get_current_user_when_valid_token_then_returns_user():
    ...

async def test_require_role_when_correct_role_then_passes():
    ...

async def test_require_role_when_student_calls_teacher_route_then_returns_403():
    ...

async def test_require_role_when_kaihle_admin_calls_any_route_then_passes():
    ...

async def test_require_school_match_when_teacher_accesses_other_school_then_returns_403():
    ...

async def test_require_school_match_when_kaihle_admin_accesses_any_school_then_passes():
    ...

async def test_require_onboarding_complete_when_student_with_incomplete_onboarding_then_returns_403_with_redirect():
    # Student exists, onboarding_diagnostic_status = 'PENDING'
    # Call a student dashboard route
    # Expect 403 with { "redirect": "/student/onboarding" }
    ...

async def test_require_onboarding_complete_when_student_with_completed_onboarding_then_passes():
    # Student with onboarding_diagnostic_status = 'COMPLETED'
    # AND learning profile completed_at IS NOT NULL
    ...

async def test_require_onboarding_complete_when_teacher_then_passes_without_check():
    # Teacher role — onboarding gate must not apply
    ...
```

---

## Acceptance Criteria

- [ ] Integration test: request without `Authorization` header to protected route returns 401
- [ ] Integration test: request with expired token returns 401
- [ ] Integration test: request with valid token returns the route's normal response
- [ ] Integration test: student calling a teacher-only route returns 403
- [ ] Integration test: teacher accessing another school's class returns 403
- [ ] Integration test: KaihleAdmin can access any school's data (bypasses school guard)
- [ ] Integration test: student with `onboarding_diagnostic_status = 'PENDING'` calling `/student/dashboard` returns 403 with `redirect` field
- [ ] Integration test: student with completed onboarding can access dashboard normally
- [ ] Integration test: teacher calling a student route with `require_onboarding_complete` passes without check

---

## Dependencies

- M0-3-T1 — `decode_token`, `InvalidTokenError`
- M0-2-T2 — `User`, `StudentProfile`, `StudentLearningProfile` models
- M0-6-T3 — onboarding completion tracking (partially — `require_onboarding_complete` reads DB directly, does not call the service)

## Output (What Next Tasks Can Use)

- `get_current_user` — applied to every protected route in the project
- `require_role(...)` — applied to role-restricted routes
- `require_school_match(school_id)` — applied to school-scoped routes
- `require_onboarding_complete` — applied to all `/student/*` routes except `/student/onboarding/*`
- `CurrentUser` type alias — cleaner route signatures throughout the project
