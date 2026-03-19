# M0-9-T4 — Password Setup Flow (All Invited Roles)
**Milestone:** M0 — Foundations
**Epic:** M0-9 — Architecture Corrections and Spec Alignment
**Task ID:** M0-9-T4
**Depends on:** M0-3-T1 (JWT utilities), M0-3-T2 (auth routes), M0-3-T4 (auth frontend package), M0-8-T4 (packages/ui components)
**Blocks:** M1 must not begin until this task is complete
**Estimated effort:** 4–5 hours

---

## Context

The current auth flow has a critical gap: when a user clicks a magic link, they receive
a full-access JWT immediately and can proceed to the app without ever setting a password.
This contradicts the authoritative product spec, which requires all magic-link-invited
users (School Admin, Teacher, Student) to set a password before accessing anything else.

This task implements the complete corrected flow:

```
Magic link click
  → Backend issues SCOPED JWT { scope: "password_setup" }
  → PasswordSetupRoute guard detects scope
  → User completes PasswordSetupForm (shared component)
  → Backend POST /api/v1/auth/set-password issues FULL JWT
  → User proceeds to role-specific next step
```

Read `CONSTITUTION.md` §5.1 (Magic Link → Password Setup → Role-Specific Next Step)
and §13 (Shared packages/ui components) before writing any code.

---

## User Story

As any user invited via magic link (School Admin, Teacher, or Student), I want to be
required to create a password on my first login so that I have a secure credential for
all future logins.

---

## Files to Create / Modify

```
backend/app/core/security.py                    ← MODIFY: add scope to magic-link JWT
backend/app/api/v1/routes/auth.py               ← MODIFY: update verify_magic_link + add set-password endpoint
backend/app/services/auth_service.py            ← MODIFY: add set_password() method
backend/app/schemas/auth.py                     ← MODIFY: add SetPasswordRequest schema
backend/app/tests/integration/test_auth_routes.py ← MODIFY: update magic link tests + add set-password tests

frontend/packages/ui/src/components/PasswordSetupForm.tsx   ← CREATE
frontend/packages/ui/src/index.ts                           ← MODIFY: export PasswordSetupForm
frontend/packages/auth/src/PasswordSetupRoute.tsx           ← CREATE
frontend/packages/auth/src/index.ts                         ← MODIFY: export PasswordSetupRoute

frontend/apps/student/src/pages/PasswordSetupPage.tsx       ← CREATE
frontend/apps/teacher/src/pages/PasswordSetupPage.tsx       ← CREATE
frontend/apps/school-admin/src/pages/PasswordSetupPage.tsx  ← CREATE

frontend/apps/student/src/App.tsx       ← MODIFY: wire PasswordSetupPage
frontend/apps/teacher/src/App.tsx       ← MODIFY: wire PasswordSetupPage
frontend/apps/school-admin/src/App.tsx  ← MODIFY: wire PasswordSetupPage (replaces placeholder from M0-9-T1)
```

---

## Backend Changes

### 1. Scoped magic-link JWT (`backend/app/core/security.py`)

Update `create_magic_link_token` to include a `scope` claim in the JWT payload:

```python
def create_magic_link_token(
    user_id: uuid.UUID,
    expires_in_minutes: int = 10,
) -> str:
    """Create a one-time magic link JWT with scope: password_setup.

    This token grants ONLY the ability to call POST /api/v1/auth/set-password.
    All other protected endpoints must reject tokens with this scope.
    """
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "scope": "password_setup",   # ← ADDED: limits what this token can do
        "exp": now + timedelta(minutes=expires_in_minutes),
        "iat": now,
        "type": "magic_link",
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
```

Add a helper that reads the scope from a decoded JWT payload:

```python
def get_token_scope(payload: dict[str, Any]) -> str | None:
    """Return the scope claim from a decoded JWT payload, or None if absent."""
    return payload.get("scope")
```

### 2. `require_full_access` dependency (`backend/app/core/deps.py`)

Add a FastAPI dependency that rejects scoped (password_setup) tokens on all regular
protected endpoints:

```python
async def require_full_access(
    current_user: CurrentUser = Depends(get_current_user),
    token_payload: dict = Depends(get_token_payload),
) -> CurrentUser:
    """Reject tokens that only have password_setup scope.

    Apply this dependency to all protected endpoints that should not be
    accessible until after the user has set their password.
    """
    if get_token_scope(token_payload) == "password_setup":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "PASSWORD_SETUP_REQUIRED",
                "message": "You must set your password before accessing this resource.",
                "redirect": "/{role}/setup-password",
            },
        )
    return current_user
```

Apply `require_full_access` to every protected route that currently uses
`get_current_user` or `require_role`. This is done by replacing the base dependency
in `deps.py` so it applies globally — not by updating every route individually.
Specifically, update `get_current_user` to call `require_full_access` internally if
the route is not `/api/v1/auth/set-password`.

The cleanest implementation: keep `get_current_user` as-is, but add a separate
`CurrentFullUser = Annotated[User, Depends(require_full_access)]` type alias that
routes can opt into. The `set-password` endpoint uses `get_current_user` directly.
All other endpoints use `CurrentFullUser`.

### 3. `POST /api/v1/auth/set-password` endpoint (`backend/app/api/v1/routes/auth.py`)

```python
@router.post("/set-password", response_model=LoginResponse)
async def set_password(
    body: SetPasswordRequest,
    # Uses get_current_user (not require_full_access) — this endpoint
    # is the one place where a password_setup scoped token IS valid.
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """Set password for a magic-link-invited user on first login.

    Requires a JWT with scope: password_setup (issued by verify_magic_link).
    Returns a full-access JWT pair (access + refresh) on success.
    Raises 403 if called with a full-access token (password already set).
    """
    service = AuthService(db)
    try:
        return await service.set_password(
            user_id=current_user.id,
            new_password=body.password,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
```

### 4. `SetPasswordRequest` schema (`backend/app/schemas/auth.py`)

```python
class SetPasswordRequest(BaseModel):
    """Request body for POST /api/v1/auth/set-password."""
    password: str = Field(
        ...,
        min_length=8,
        description="New password — minimum 8 characters",
    )
    confirm_password: str = Field(..., description="Must match password")

    @model_validator(mode="after")
    def passwords_match(self) -> "SetPasswordRequest":
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self
```

### 5. `set_password()` method (`backend/app/services/auth_service.py`)

```python
async def set_password(
    self,
    user_id: uuid.UUID,
    new_password: str,
) -> LoginResponse:
    """Hash and store the user's password, then issue a full-access JWT pair.

    Raises ValueError if the user already has a password set (prevents
    re-use of a magic link token that was somehow replayed after setup).
    """
    user = await self.db.get(User, user_id)
    if not user:
        raise ValueError("User not found")
    if user.hashed_password is not None:
        raise ValueError("Password already set — use the login endpoint")

    user.hashed_password = hash_password(new_password)
    await self.db.flush()

    # Issue full-access tokens (no scope restriction)
    access_token = create_access_token(
        user_id=user.id,
        school_id=user.school_id,
        role=user.role,
    )
    refresh_token_value = generate_refresh_token()
    await store_refresh_token(self.db, user.id, hash_token(refresh_token_value))

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token_value,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )
```

### 6. Update `verify_magic_link` response (`backend/app/api/v1/routes/auth.py`)

The `verify_magic_link` endpoint currently returns a `LoginResponse` with a full JWT.
Change it to return a new `MagicLinkVerifyResponse` that contains only the scoped token:

```python
class MagicLinkVerifyResponse(BaseModel):
    """Response from magic link verification — scoped token only."""
    setup_token: str       # JWT with scope: password_setup
    token_type: str = "bearer"
    requires_password_setup: bool = True
```

The frontend `PasswordSetupRoute` reads `requires_password_setup: true` from this
response and routes to the password setup screen. It stores `setup_token` temporarily
in component state (NOT in localStorage or the main token store) — it is discarded
after the password is set and replaced with the full JWT from `set-password`.

---

## Frontend Changes

### `PasswordSetupForm` component (`frontend/packages/ui/src/components/PasswordSetupForm.tsx`)

This is a shared component used identically by all five apps. It has no knowledge of
routing — it accepts a submit callback and delegates navigation to the page that hosts it.

```tsx
interface PasswordSetupFormProps {
  onSubmit: (password: string) => Promise<void>
  isLoading?: boolean
  error?: string | null
  logoLabel?: string   // e.g. "Teacher Portal", "School Admin Portal"
}

export function PasswordSetupForm({
  onSubmit,
  isLoading = false,
  error = null,
  logoLabel = 'Kaihle',
}: PasswordSetupFormProps) {
  // Uses React Hook Form + Zod for validation.
  // Password requirements shown inline as user types:
  //   - Minimum 8 characters (shown as green checkmark when met)
  //   - Passwords match (shown as green checkmark when met)
  // Submit button is disabled until both requirements are met.
  // AuthLayout wrapper from packages/ui for centered card layout.
}
```

The component renders inside `AuthLayout` and displays:
- Kaihle logo
- `logoLabel` subtitle
- "Set your password" heading
- Password field with show/hide toggle
- Confirm password field with show/hide toggle
- Inline validation indicators (minimum length, passwords match)
- Submit button: "Set password & continue"
- No "back" link — the user cannot return to the magic link

### `PasswordSetupRoute` guard (`frontend/packages/auth/src/PasswordSetupRoute.tsx`)

```tsx
/**
 * Route guard that intercepts a scoped password_setup JWT and redirects
 * to the password setup screen before allowing access to protected routes.
 *
 * How it works:
 * 1. Reads the access token from the Zustand tokenStore
 * 2. Decodes the JWT (client-side, no verification — verification is server-side)
 * 3. If payload.scope === "password_setup" → redirect to /{rolePrefix}/setup-password
 * 4. Otherwise → render children normally
 */
export function PasswordSetupRoute({ children }: { children: ReactNode }) {
  const { accessToken, user } = useAuthStore()

  const needsPasswordSetup = useMemo(() => {
    if (!accessToken) return false
    try {
      const payload = jwtDecode(accessToken)
      return (payload as any).scope === 'password_setup'
    } catch {
      return false
    }
  }, [accessToken])

  if (needsPasswordSetup && user?.role) {
    const prefix = roleToPathPrefix(user.role)  // e.g. TEACHER → "teacher"
    return <Navigate to={`/${prefix}/setup-password`} replace />
  }

  return <>{children}</>
}
```

### `PasswordSetupPage` (one per app, thin wrapper)

Each app's `PasswordSetupPage` is a thin wrapper that imports `PasswordSetupForm`
from `packages/ui` and provides the submit handler:

```tsx
// frontend/apps/teacher/src/pages/PasswordSetupPage.tsx

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@kaihle/auth'
import { PasswordSetupForm } from '@kaihle/ui'

export function PasswordSetupPage() {
  const { setPassword } = useAuth()   // calls POST /api/v1/auth/set-password
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)

  const handleSubmit = async (password: string) => {
    setIsLoading(true)
    setError(null)
    try {
      await setPassword(password)
      // setPassword() exchanges scoped token for full JWT in the token store
      navigate('/teacher/dashboard')
    } catch (err: any) {
      setError(err.message ?? 'Something went wrong. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <PasswordSetupForm
      onSubmit={handleSubmit}
      isLoading={isLoading}
      error={error}
      logoLabel="Teacher Portal"
    />
  )
}
```

Apply the same pattern for `apps/student` (navigate to `/student/onboarding/profile`
after setup) and `apps/school-admin` (navigate to `/school-admin/dashboard`).

Add a `setPassword(password: string)` method to `useAuth()` in `packages/auth` that:
1. Posts to `POST /api/v1/auth/set-password` with the current scoped token
2. On success, stores the returned full JWT in the tokenStore (replacing the scoped token)
3. On failure, throws so the page can display an error

---

## Acceptance Criteria

**Backend:**
- `GET /api/v1/auth/magic-link/verify?token=...` returns `{ setup_token, token_type, requires_password_setup: true }` — not a full JWT
- Decoding `setup_token` reveals `scope: "password_setup"` in the payload
- `POST /api/v1/auth/set-password` with a valid scoped token sets the password and returns `{ access_token, refresh_token }` with no scope restriction
- `POST /api/v1/auth/set-password` with a full-access JWT (no scope) returns 400 "Password already set"
- Any non-setup-password endpoint called with a scoped JWT returns 403 with `code: PASSWORD_SETUP_REQUIRED`
- Integration test: full flow — magic link verify → scoped token → set-password → full token → access dashboard endpoint → 200
- Integration test: scoped token used on `/api/v1/schools/...` returns 403
- Integration test: set-password called twice with same user returns 400

**Frontend:**
- `PasswordSetupForm` exported from `packages/ui` with no TypeScript errors
- `PasswordSetupRoute` exported from `packages/auth` with no TypeScript errors
- Student clicking magic link lands on `/student/setup-password` — not on the dashboard or onboarding directly
- Teacher clicking magic link lands on `/teacher/setup-password`
- School admin clicking magic link lands on `/school-admin/setup-password`
- After password setup, student is redirected to `/student/onboarding/profile`
- After password setup, teacher is redirected to `/teacher/dashboard`
- After password setup, school admin is redirected to `/school-admin/dashboard`
- Submit button is disabled when passwords do not match
- Submit button is disabled when password is fewer than 8 characters
- `tsc --noEmit` passes in all three apps and both packages

---

## Do NOT Touch

- `POST /api/v1/auth/login` (email/password login for returning users — unaffected)
- `POST /api/v1/auth/refresh` (token refresh — unaffected)
- The `OnboardingRoute` guard — it guards the learning profile step, which comes AFTER password setup for students
- Any database migration — no schema changes are required for this task
