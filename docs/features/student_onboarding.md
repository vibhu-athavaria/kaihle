# Feature: Student Onboarding

## 1. Purpose

Student onboarding is the flow that takes a newly registered or invited student from **account creation → password setup (if needed) → learning profile questionnaire → dashboard**, and then they unlock class content independently per class enrollment.

Onboarding has **one distinct, independent gate** before dashboard access:
- **Global gate**: learning profile completion (`student_profiles.is_learning_profile_complete = TRUE`).

After dashboard access, per-class diagnostics (Tier 1) are **not required** to access class content — they only block study plan generation and show a pending indicator on class cards.

## 2. User flows (high level)

### 2.1 Account creation paths

**Path A – Invitation (magic link, for TEACHER, SCHOOL_ADMIN, PARENT):**
1. Admin calls `POST /schools/{school_id}/users` (invite).
2. User is created with unusable password hash, `is_active = TRUE`.
3. Magic link email is sent.
4. User clicks link → `GET /auth/magic-link/verify?token={token}` → receives scoped JWT (`scope: "password_setup"`).
5. User sets password via `POST /auth/set-password` → receives full-access JWT.

**Path B – Direct creation (for any role, admin-set password):**
1. Admin calls `POST /schools/{school_id}/users/create` with explicit password.
2. User is created with `must_change_password = TRUE`.
3. Welcome email is sent with credentials.
4. User logs in with provided password → forced to change password on first login.

### 2.2 Global onboarding gate (learning profile)

1. After first successful login, Student is redirected to learning profile questionnaire (`GET /onboarding/questionnaire`).
2. Student completes 10-question form (Q1–Q5 single-choice, Q6–Q10 multi-select) and submits via `POST /onboarding/questionnaire/submit`.
3. Backend (`OnboardingService.save_questionnaire_response`):
   - Calculates modality scores (visual, auditory, reading/writing, kinesthetic).
   - Derives work style flags (prefers_solo, short_sessions, concept_first, task_based).
   - Extracts interests (lowercase strings).
   - Creates/updates `student_learning_profiles` row.
   - Sets `student_profiles.is_learning_profile_complete = TRUE`.
4. Dashboard access is now allowed. Subsequent dashboard loads check `is_learning_profile_complete` and redirect to questionnaire if false.

### 2.3 Per-class diagnostic (Tier 1) – non-blocking

1. When a Student is enrolled in a class, a Celery task creates a Tier 1 diagnostic using `question_bank` questions for that subject/grade.
2. On the Student dashboard, enrolled class cards show a "Tier 1 pending" ticker/badge when `class_enrollments.onboarding_diagnostic_status = 'PENDING'`.
3. Student **can access class content** (lessons, materials) without completing Tier 1.
4. Student completes the MCQ-based Tier 1 diagnostic → backend calculates gap states, sets `onboarding_diagnostic_status = 'COMPLETED'`.
5. Once completed, the ticker is removed and the study plan is generated for that class.

## 3. Backend responsibilities

> Real implementation paths.

### 3.1 Auth and user creation

- Routes: `backend/app/api/v1/routes/auth.py`
  - `POST /auth/register` – register new user (inactive).
  - `POST /auth/login` – email/password login.
  - `POST /auth/magic-link` – send magic link.
  - `GET /auth/magic-link/verify?token={token}` – validate magic link, return scoped JWT.
  - `POST /auth/set-password` – set password using magic-link JWT.
  - `POST /auth/refresh`, `POST /auth/reset-password`, `POST /auth/forgot-password`, `POST /auth/logout`.

- Routes: `backend/app/api/v1/routes/users.py`
  - `POST /schools/{school_id}/users` – invite user (magic link flow).
  - `POST /schools/{school_id}/users/create` – create user with admin-set password.

- Services:
  - `backend/app/services/auth_service.py` – all auth operations.
  - `backend/app/services/user_service.py` – `invite_user`, `create_user_direct`.

### 3.2 Learning profile (global gate)

- Routes: `backend/app/api/v1/routes/onboarding.py`
  - `GET /onboarding/questionnaire` – fetch questionnaire definition.
  - `POST /onboarding/questionnaire/submit` – submit responses, returns `StudentLearningProfile`.
  - `GET /onboarding/learning-profile` (query: `student_id`) – get learning profile with role-based access.
  - `GET /onboarding/status/{student_id}` – get `{learning_profile_complete, diagnostics_by_class}`.
  - `GET /onboarding/students/pending` – list students with incomplete learning profiles (admins).

- Service: `backend/app/services/onboarding_service.py`
  - `save_questionnaire_response(student_id, responses)` – processes answers, computes scores, upserts profile, sets `is_learning_profile_complete = TRUE`.
  - `get_learning_profile_authorized(...)` – enforces role-based access.
  - `get_onboarding_status(student_id)` – returns completion status + per-class diagnostic breakdown.
  - `verify_teacher_student_relationship(teacher_id, student_id)` – checks class enrollment.

- Data:
  - `student_learning_profiles` table: `student_id`, `school_id`, `modality_scores` JSONB, `work_style` JSONB, `interests` TEXT[], `completed_at`, `questionnaire_version`.
  - `student_profiles.is_learning_profile_complete` boolean – global onboarding gate.
  - Questionnaire definition in `app/core/questionnaire_config.py`.

### 3.3 Per-class diagnostics (Tier 1)

- Routes: `backend/app/api/v1/routes/diagnostics.py`
  - `POST /classes/{class_id}/onboarding_diagnostic/submit`
  - `GET /classes/{class_id}/onboarding_diagnostic`

- Service: `backend/app/services/diagnostics_service.py`
  - `create_onboarding_diagnostic_for_class(class_id, ...)`
  - `submit_onboarding_diagnostic(class_id, student_id, responses, ...)`

- Tasks: `backend/app/tasks/create_class_diagnostic_task.py`
  - `calculate_gap_states` (Celery) – triggered on assessment completion.

- Data:
  - `class_enrollments.onboarding_diagnostic_status` enum: `PENDING`, `IN_PROGRESS`, `COMPLETED`.
  - `gap_states` table – per-student, per-subtopic mastery.

Invariants:
- Tier 1 diagnostics always use existing `question_bank` questions; no LLM question generation.
- Dashboard access is blocked until `is_learning_profile_complete = TRUE`.
- Class content is accessible regardless of Tier 1 completion; only study plan generation depends on it.

## 4. Frontend responsibilities (Student app)

### 4.1 Routes and navigation

- `GET /onboarding/questionnaire` → render 10-question form.
- `POST /onboarding/questionnaire/submit` → on success, redirect to `/student/dashboard`.
- Dashboard route (`/student/dashboard`):
  - Uses `OnboardingRoute` guard from `frontend/packages/auth`:
    - Checks `is_learning_profile_complete` (via `/onboarding/status/me` or similar).
    - If false, redirect to `/student/onboarding/profile`.
- Password setup route (`/student/setup-password`):
  - Protected by `PasswordSetupRoute` guard (validates `scope: "password_setup"` JWT).

### 4.2 Class cards

- `frontend/packages/ui/components/ClassCard` (or equivalent):
  - Shows "Tier 1 pending" badge when `onboarding_diagnostic_status === 'PENDING'`.
  - Badge removed when status is `COMPLETED`.
  - Class content accessible regardless of status.

### 4.3 Shared packages

- `frontend/packages/auth`:
  - `OnboardingRoute` – enforces learning profile completion before dashboard access.
  - `PasswordSetupRoute` – enforces password setup before full access.
  - `useAuth` – JWT storage, refresh, role checks.

- `frontend/packages/types`:
  - Types for `LearningProfile`, `ModalityScores`, `WorkStyle`, `QuestionnaireDefinition`, `OnboardingStatus`.

## 5. Tests

### 5.1 Backend tests

- `backend/app/tests/unit/services/test_onboarding_service.py`:
  - `save_questionnaire_response` – correct modality calculation, work style derivation, interests extraction, idempotency.
  - `get_learning_profile_authorized` – student own, teacher class ownership, school admin same-school, KAIHLE_ADMIN any.
  - `get_onboarding_status` – returns correct completion flags.

- `backend/app/tests/unit/services/test_diagnostics_service.py`:
  - `create_onboarding_diagnostic_for_class`, `submit_onboarding_diagnostic` – gap state updates.

- Integration tests:
  - `test_onboarding_routes.py` – questionnaire fetch/submit, learning profile fetch, status endpoint, pending list.
  - `test_diagnostics_routes.py` – diagnostic submission, multi-tenancy.

### 5.2 Frontend tests

- `frontend/apps/student/src/__tests__/OnboardingProfilePage.test.tsx`:
  - Renders questionnaire, submits, asserts redirect and API calls.

- `frontend/apps/student/src/__tests__/StudentDashboard.test.tsx`:
  - Mocks `is_learning_profile_complete = false` → asserts redirect to onboarding.
  - Mocks `is_learning_profile_complete = true` → asserts dashboard renders.

- `frontend/apps/student/src/__tests__/ClassCard.test.tsx`:
  - Renders with `onboarding_diagnostic_status = 'PENDING'` → asserts badge shown.
  - Renders with `onboarding_diagnostic_status = 'COMPLETED'` → asserts badge hidden.

## 6. Implementation notes

- 2026‑05‑07 – UPDATE: Clarified that Tier 1 diagnostic is **non-blocking** for content access (only blocks study plan generation). Learning profile completion is the sole global onboarding gate before dashboard access.
- 2026‑05‑07 – INITIAL DOCUMENT
  - Notes: Routes aligned with real implementation (`/onboarding/*`, `/auth/*`, `/users/*`). Questionnaire config in `questionnaire_config.py`.