# Feature: Authentication

## 1. Purpose

Authentication handles user account creation, login, and session management. Accounts can be created by Kaihle Admin (for School Admin) or School Admin (for Teacher, Student, Parent) via two flows: **invitation** (magic link) or **direct creation** (admin-set password). All non-parent users must complete onboarding (learning profile + per-class diagnostics) before full access.

Supported roles: STUDENT, TEACHER, SCHOOL_ADMIN, PARENT, KAIHLE_ADMIN.

## 2. Flows (high level)

### 2.1 Account creation – Invitation (magic link)

- Kaihle Admin creates a school and invites a School Admin via `POST /schools/{school_id}/users` (invite).
- School Admin invites Teachers and Parents via the same endpoint.
- User is created with `is_active = TRUE` and a random unusable password hash.
- A magic link email is sent. The link contains a JWT token (type: `magic_link`).
- User clicks link → `GET /auth/magic-link/verify?token={token}` validates token, marks it used, returns a **new** magic-link JWT with `scope: "password_setup"`.
- Frontend uses this JWT to call `POST /auth/set-password` to set a real password, receiving full-access JWT + refresh token.

### 2.2 Account creation – Direct (admin-set password)

- Kaihle Admin or School Admin calls `POST /schools/{school_id}/users/create` with an explicit password.
- User is created with `is_active = TRUE`, `must_change_password = TRUE`, and the admin-set password.
- A welcome email is sent with login credentials.
- On first login, user must change password (enforced by `must_change_password` flag).

### 2.3 Password setup (from magic link)

1. User clicks magic link, receives scoped JWT.
2. Frontend posts new password to `POST /auth/set-password` with the scoped JWT.
3. Backend validates token scope/type, hashes password, issues full-access JWT + refresh token.
4. User is redirected to role-specific app.

### 2.4 Normal login and refresh

- `POST /auth/login` with email/password → returns access + refresh JWTs.
- `POST /auth/refresh` rotates refresh token, returns new access token.

### 2.5 Forgot / reset password

1. User enters email on forgot password page → `POST /auth/forgot-password`.
2. System sends password reset email with link containing a `PASSWORD_RESET` token.
3. Link directs to `/reset-password?token={token}`.
4. User submits new password → `POST /auth/reset-password`.
5. Backend validates token, hashes new password, invalidates all existing refresh tokens for the user.

## 3. Backend responsibilities

> Real implementation paths.

- Routes: `backend/app/api/v1/routes/auth.py`
  - `POST /auth/register` – register new user (inactive, no tokens).
  - `POST /auth/login` – email/password login.
  - `POST /auth/magic-link` – send magic link email.
  - `GET /auth/magic-link/verify?token={token}` – validate magic link, return scoped JWT.
  - `POST /auth/set-password` – set password using magic-link scoped JWT.
  - `POST /auth/refresh` – refresh access token.
  - `POST /auth/forgot-password` – send password reset email.
  - `POST /auth/reset-password` – reset password with reset token.
  - `POST /auth/logout` – invalidate refresh token.
  - `POST /auth/change-password` – change password (full-access token required).

- User management routes: `backend/app/api/v1/routes/users.py`
  - `POST /schools/{school_id}/users` – invite user (magic link flow).
  - `POST /schools/{school_id}/users/create` – create user with admin-set password.

- Services:
  - `backend/app/services/auth_service.py`
    - `register(...)` – create inactive user.
    - `login(...)` – verify credentials, issue tokens.
    - `send_magic_link(...)` – generate and email magic link.
    - `verify_magic_link(...)` – validate magic link, issue full-access tokens.
    - `verify_magic_link_get_token(...)` – validate magic link, return scoped JWT (for password setup).
    - `set_password_from_scoped_token(...)` – set password using magic-link JWT.
    - `refresh_access_token(...)` – rotate refresh token.
    - `reset_password(...)` – validate reset token, set new password, invalidate refresh tokens.
    - `send_password_reset_email(...)` – generate and email reset link.
  - `backend/app/services/user_service.py`
    - `invite_user(...)` – create user with unusable password, send magic link.
    - `create_user_direct(...)` – create user with admin-set password, send welcome email.

- Data:
  - `users` table: `email`, `hashed_password`, `role`, `school_id`, `is_active`, `must_change_password`.
  - `auth_tokens` table: `token_hash`, `type` (MAGIC_LINK, REFRESH, PASSWORD_RESET), `expires_at`, `used_at`.
  - `student_profiles.is_learning_profile_complete` – global onboarding gate.
  - `class_enrollments.onboarding_diagnostic_status` – per-class diagnostic gate.

Invariants:
- Magic link tokens are single-use with TTL; verification marks them used.
- Password reset invalidates all existing refresh tokens for the user.
- `must_change_password` forces password change on next login (for direct-creation users).
- All writes respect `school_id` multi-tenancy (CONSTITUTION Rule 3).

## 4. Frontend responsibilities

- Shared auth package (`frontend/packages/auth`):
  - `PasswordSetupRoute` – validates `scope: "password_setup"` JWT, allows access to setup-password pages.
  - `ResetPasswordRoute` – validates password reset token, allows access to reset-password page.
  - `OnboardingRoute` – enforces learning profile completion before dashboard access.
  - `useAuth`, `tokenStore` – JWT storage, refresh, and role-based route guards.

- Auth forms (`frontend/packages/ui`):
  - `PasswordSetupForm`, `ResetPasswordForm`, `ForgotPasswordForm`, `LoginForm`.

- Role-specific apps:
  - Each app (`student`, `teacher`, `school-admin`, `kaihle-admin`) has login and password setup/reset routes.
  - After password setup or login, redirect to role-specific dashboard.

## 5. Tests

- Backend:
  - Unit tests for `auth_service` (login, magic link, password setup, refresh, reset, change password).
  - Unit tests for `user_service` (invite, direct create).
  - Integration tests for auth routes (multi-tenancy, token validation, password reset flow).
  - Tests for token invalidation on password reset and logout.

- Frontend:
  - Tests for login, magic link, password setup, and reset flows.
  - Tests for onboarding gate (dashboard inaccessible until learning profile complete).

## 6. Implementation notes

- 2026‑05‑07 – UPDATE: Aligned with actual implementation. Two account creation flows: invitation (magic link) and direct (admin-set password). Magic link verification returns a scoped JWT for password setup. Password reset invalidates refresh tokens.
- 2026‑05‑07 – INITIAL DOCUMENT
  - Notes: Paths updated to match real modules (`auth_service.py`, `user_service.py`, `auth.py`, `users.py`).