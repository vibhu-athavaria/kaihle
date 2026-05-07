# Feature: Student Learning Profile

## 1. Purpose

The Student Learning Profile captures each student’s learning modalities, work style, and interests. It is filled during onboarding and used to personalise content (study plans, quizzes, explanations) and to display context to Teachers. Completion of the learning profile is part of the global onboarding gate (`student_profiles.is_learning_profile_complete`) that must be satisfied before dashboard access.

## 2. Flows

### 2.1 Questionnaire submission

1. After login, Student must complete onboarding: first the learning profile questionnaire at `GET /onboarding/questionnaire` (retrieve definition) then `POST /onboarding/questionnaire/submit`.
2. Frontend posts 10 responses (Q1–Q5 single-choice, Q6–Q10 multi-select) to the submit endpoint.
3. Backend (`OnboardingService.save_questionnaire_response`):
   - Calculates modality scores from Q1–Q2 (visual, auditory, reading/writing, kinesthetic).
   - Derives work style flags from Q3–Q5 (prefers_solo, short_sessions, concept_first, task_based).
   - Extracts interests from Q6–Q10 (lowercase strings).
   - Creates/updates `student_learning_profiles` row and sets `student_profiles.is_learning_profile_complete = TRUE`.
4. On success, frontend redirects to dashboard. Until complete, the dashboard is inaccessible.

### 2.2 Usage in other features

- Content curator uses interests and modalities to prioritise resources.
- Quiz generator uses interests to contextualise questions.
- Teacher dashboards show a read-only snapshot of learning profile for each student (via `GET /onboarding/learning-profile?student_id={id}`).
- Gap map and study plan generation may use modality preferences to tailor presentation formats.

## 3. Backend responsibilities

> Real implementation paths.

- Routes: `backend/app/api/v1/routes/onboarding.py`
  - `GET /onboarding/questionnaire` – returns questionnaire definition (10 questions, options, scoring maps). Roles: STUDENT, KAIHLE_ADMIN.
  - `POST /onboarding/questionnaire/submit` – submit responses, returns `StudentLearningProfile`. Roles: STUDENT, KAIHLE_ADMIN.
  - `GET /onboarding/learning-profile` (query: `student_id` optional) – get a student's learning profile with role-based access (STUDENT, TEACHER, SCHOOL_ADMIN, KAIHLE_ADMIN). Students can only fetch their own; teachers must provide `student_id` and can only access students in their classes.
  - `GET /onboarding/status/{student_id}` – get onboarding status (learning_profile_complete + per-class diagnostic status). Role-based (TEACHER for own students, ADMIN for school, STUDENT for self).
  - `GET /onboarding/students/pending` – list students with `is_learning_profile_complete = FALSE` (admins only).

- Service: `backend/app/services/onboarding_service.py`
  - `save_questionnaire_response(student_id, responses)` – processes answers, computes modality scores, work style, interests; upserts `StudentLearningProfile`; sets `StudentProfile.is_learning_profile_complete = TRUE`.
  - `get_learning_profile_authorized(...)` – enforces role-based access (student own, teacher class ownership, school same-school, admin any).
  - `get_onboarding_status(student_id)` – returns `{learning_profile_complete, diagnostics_by_class}`.
  - `get_or_create_learning_profile(student_id, school_id)` – creates empty profile if none exists.
  - `verify_teacher_student_relationship(teacher_id, student_id)` – checks class enrollment for teacher authorization.

- Data:
  - `student_learning_profiles` table:
    - `student_id` (unique), `school_id`, `modality_scores` JSONB (`{"visual": float, "auditory": float, "reading_writing": float, "kinesthetic": float}`), `work_style` JSONB (`{"prefers_solo": bool, "short_sessions": bool, "concept_first": bool, "task_based": bool}`), `interests` TEXT[], `questionnaire_version`, `completed_at` (NULL = not submitted).
  - `student_profiles.is_learning_profile_complete` boolean – global onboarding gate.
  - Questionnaire definition in `app/core/questionnaire_config.py` (10 questions, option keys, `maps_to` rules for scoring).

Invariants:
- Learning profile is updated only via the questionnaire endpoint; other endpoints must not set `is_learning_profile_complete`.
- Interests are stored as human-readable lowercase strings and used directly in prompts (no ID-based lookup).
- Modality scores are normalized to [0.0, 1.0] (count / 2 for Q1+Q2).
- `task_based` is derived as `not concept_first`.
- Completion of the learning profile is required before dashboard access (enforced at the gateway/frontend level; backend gate is `student_profiles.is_learning_profile_complete`).

## 4. Frontend responsibilities

- Student app:
  - `GET /onboarding/questionnaire` → render 10-question form (Q1–Q5 single choice, Q6–Q10 multi-select).
  - On submit → `POST /onboarding/questionnaire/submit`. On success, redirect to dashboard.
  - Block dashboard access while `is_learning_profile_complete` is false (check via `/onboarding/status/me` or similar).

- Teacher app:
  - Read-only panel in student details view: `GET /onboarding/learning-profile?student_id={id}` (with proper authorization).
  - Show modality scores, work style, interests.

- Shared:
  - `frontend/packages/types` – types for `LearningProfile`, `ModalityScores`, `WorkStyle`, `QuestionnaireDefinition`, `QuestionnaireSubmitRequest`.
  - `frontend/packages/auth` – optional helper to check onboarding completion before route entry.

## 5. Tests

- Backend:
  - Unit tests for `OnboardingService.save_questionnaire_response` (correct modality calculation, work style derivation, interests extraction, idempotency).
  - Unit tests for authorization in `get_learning_profile_authorized` (student own, teacher class ownership, school admin same-school, KAIHLE_ADMIN any).
  - Integration tests for onboarding routes (questionnaire fetch/submit, learning profile fetch, status endpoint, pending list).
  - Tests to ensure `is_learning_profile_complete` is only set via questionnaire submit.

- Frontend:
  - Tests for questionnaire form (all question types, validation, submit success, redirect).
  - Tests for teacher learning profile view (authorization, rendering).
  - Tests for onboarding gate (dashboard inaccessible until complete).

## 6. Implementation notes

- 2026‑05‑07 – UPDATE: Aligned with actual implementation (`/onboarding/*` routes, `OnboardingService`, `student_profiles.is_learning_profile_complete` gate). Added per-class diagnostic status to onboarding status. Clarified 10-question structure and scoring.
- 2026‑05‑07 – INITIAL DOCUMENT
  - Notes: Paths updated to match real modules. Questionnaire config in `questionnaire_config.py`.