# Feature: Diagnostic Assessments

## 1. Purpose

Diagnostic assessments measure student mastery at two levels:

- **Tier 1 – Onboarding diagnostic**: system-generated per class, taken once at enrollment time. Not required to access class content, but required to generate a study plan. Until completed, a ticker/badge appears on the class card and the study plan is unavailable.
- **Tier 2 – Progress checks**: teacher-created diagnostics targeting specific topics, do not block access.

Both tiers update gap state tables and drive gap maps, study plans, and teacher dashboards.

## 2. Flows

### 2.1 Onboarding prerequisite

- After login, a Student must complete the onboarding learning profile before accessing the dashboard.
- Once the learning profile is complete, the Student can access the dashboard and see classes they have been enrolled in (by School Admin or Teacher).

### 2.2 Tier 1 – Onboarding diagnostic (per-class)

1. When a Student is enrolled in a class, a Celery task creates a Tier 1 diagnostic for that class using prebuilt `question_bank` questions for that subject/grade.[cite:29]
2. On the Student dashboard, enrolled class cards show a "Tier 1 pending" ticker/badge when the diagnostic is incomplete.
3. Student can access class content (lessons, materials) without completing Tier 1.
4. Student completes the MCQ-based Tier 1 diagnostic (optional to access content, required for study plan generation).
5. Backend calculates gap states and sets `class_enrollments.onboarding_diagnostic_status = 'COMPLETED'` for that enrollment.
6. Once completed, the ticker is removed and the study plan is generated for that class.

Constraints:
- Tier 1 diagnostics are **system-generated** (`is_system_generated = TRUE`) and always use the question bank; no LLM question generation.[cite:29]
- Tier 1 is not a content gate — it only blocks study plan generation and shows a pending indicator.

### 2.3 Tier 2 – Progress checks

1. Teacher configures a progress check selecting topics for a class.
2. Backend creates the assessment instance and assigns it to students.
3. After submission, backend updates gap states without locking content.

Constraints:
- `is_system_generated = FALSE` for Tier 2.
- Does not block class content.

## 3. Backend responsibilities

> Adjust file names to actual modules.

- Routes:
  - `backend/app/api/v1/routes/diagnostics.py`
    - `POST /classes/{class_id}/onboarding_diagnostic/submit`
    - `GET /classes/{class_id}/onboarding_diagnostic`
    - `POST /classes/{class_id}/progress_checks`
    - `POST /classes/{class_id}/progress_checks/{assessment_id}/submit`
  - `backend/app/api/v1/routes/onboarding.py`
    - `GET /onboarding/learning-profile` – get learning profile (with role-based access)
    - `GET /onboarding/status/{student_id}` – check learning profile + diagnostic completion status
    - `POST /onboarding/questionnaire/submit` – complete learning profile (required before dashboard access)

- Services:
  - `backend/app/services/diagnostics_service.py`
    - `create_onboarding_diagnostic_for_class(class_id, ...)`
    - `submit_onboarding_diagnostic(class_id, student_id, responses, ...)`
    - `create_progress_check(class_id, topics, ...)`
    - `submit_progress_check(...)`
  - `backend/app/services/onboarding_service.py`
    - `complete_learning_profile(student_id, profile_data, ...)`
    - `get_learning_profile_status(student_id)`

- Tasks:
  - `backend/app/tasks/create_class_diagnostic_task.py`
    - Called when classes are created or when new subject/grade combos are introduced.
    - Must guard against empty `question_bank` and log WARNING rather than create empty assessments.[cite:29]

- Data:
  - `question_bank` – structured source of questions.
  - Diagnostic tables – store attempts/results, link to gap states.
  - Gap-state tables per student, subject, topic.
  - `students.learning_profile_completed` (or similar) flag to gate dashboard access.
  - `class_enrollments.onboarding_diagnostic_status` – values: 'PENDING', 'COMPLETED'.

Invariants:
- No LLM-based scoring: MCQ scoring is deterministic string comparison.[cite:29]
- All writes respect `school_id` and multi-tenancy rules.[file:59]
- Dashboard access is blocked until `learning_profile_completed = TRUE`.
- Class content is accessible regardless of Tier 1 completion; only study plan generation and ticker display depend on Tier 1.

## 4. Frontend responsibilities

- Student app:
  - Learning profile onboarding screen (gate before dashboard access).
  - Dashboard showing enrolled classes with Tier 1 pending ticker/badge on class cards when incomplete.
  - Screens for taking Tier 1 onboarding diagnostic and Tier 2 progress checks.
  - Clear status indicators (pending/completed) on class cards for Tier 1.

- Teacher app:
  - Screens for configuring progress checks (select topics, schedule).
  - Views for results and gap states.

Shared UI:
- Components for question rendering, option selection, and submission.
- Loading and empty states consistent with design system.
- Tier 1 pending ticker/badge component for class cards.

## 5. Tests

- Backend:
  - Unit tests for diagnostics service (creation, submission, gap updates).
  - Unit tests for onboarding service (learning profile completion, dashboard gating).
  - Integration tests for diagnostic routes, ensuring multi-tenancy and gating rules.
  - Tests verifying class content is accessible without Tier 1 completion, but study plan is not generated.

- Frontend:
  - Tests for Student flows (learning profile gate, taking diagnostics, handling pending indicators).
  - Tests for Teacher configuration UI.

## 6. Implementation notes

- 2026‑05‑07 – UPDATE: Changed Tier 1 diagnostic from content-blocking to non-blocking (only blocks study plan generation). Added learning profile onboarding prerequisite before dashboard access. Added Tier 2 progress checks as teacher-created diagnostics.
- 2026‑05‑07 – INITIAL DOCUMENT
  - Notes: Align paths and function names with actual modules. Tier 1/Tier 2 definitions copy Constitution’s semantics.