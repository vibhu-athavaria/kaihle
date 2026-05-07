# Feature: Gap Map Dashboard

## 1. Purpose

The gap map visualizes student mastery at the subtopic level within a class, driving instructional decisions and study plan generation. It is rendered under the **class detail view** for Teachers and School Admins (no separate gap-map dashboard). Students see their own personal gap map in their student app.

## 2. Flows

### 2.1 Class detail view (Teacher / School Admin)

1. User navigates to a class detail page.
2. The frontend fetches:
   - `GET /classes/{class_id}/summary` – lightweight mastery summary for the class card (avg mastery, assessed student count, students below threshold).
   - `GET /classes/{class_id}/gap-map?subject_id={subject_id}` – full per-student, per-subtopic heatmap for the selected subject.
3. The gap map is rendered as a heatmap table: rows = subtopics, columns = students (or collapsed to show class average), cells = mastery score with color coding.
4. The class summary is used to show an at-a-glance mastery indicator on the class card in the dashboard listing.

### 2.2 Student personal gap map

- Students access their own gap map via the student app: `GET /students/me/gap-map?subject_id={subject_id}`.
- Shows subtopic-level mastery with last assessed timestamps. Subtopics with no assessment appear as "Not assessed".

### 2.3 Data generation

- Gap states are computed asynchronously by `calculate_gap_states` (Celery task) after each completed assessment attempt.
- The task processes `StudentAttempt` responses, computes per-subtopic mastery (recency-weighted), and upserts `gap_states` rows.
- Tier 1 (onboarding) and Tier 2 (progress check) assessments both feed into gap states.
- Mastery formula uses rolling recency-weighted average (system-generated Tier 1 scores are discounted 0.7 on first attempt; direct scores for non-system assessments).

## 3. Backend responsibilities

> File paths from the real implementation.

- Routes: `backend/app/api/v1/routes/gap_map.py`
  - `GET /classes/{class_id}/gap-map` (query: `subject_id`) – returns `ClassGapMap` (per-student, per-subtopic heatmap). Roles: TEACHER, SCHOOL_ADMIN, KAIHLE_ADMIN. Teachers can only view their own classes.
  - `GET /classes/{class_id}/summary` – returns `ClassSummary` (lightweight aggregate for class cards). Roles: TEACHER, SCHOOL_ADMIN, KAIHLE_ADMIN.
  - `GET /students/me/gap-map` (query: `subject_id`) – returns `StudentGapMap` for the authenticated student.
  - `GET /students/{student_id}/gap-map` (query: `subject_id`) – returns `StudentGapMap` with role-based access (TEACHER, PARENT, SCHOOL_ADMIN, KAIHLE_ADMIN).

- Service: `backend/app/services/gap_service.py`
  - `get_class_gap_map(class_id, school_id, subject_id)` – aggregates gap states by subtopic with per-student scores; includes subtopics with no assessments (class_average = None).
  - `get_class_summary(class_id, school_id)` – returns avg mastery, assessed student count, total students, students below threshold (avg < 0.4), last updated.
  - `get_student_gap_map(student_id, school_id, subject_id)` – returns student's subtopic scores; unassessed subtopics have mastery_score = None.
  - `calculate_gap_states_for_attempt(attempt_id)` – computes and persists gap states from a completed attempt (used by Celery task).
  - `upsert_gap_state(...)` – atomic upsert into `gap_states` with confidence derived from attempt count.

- Tasks: `backend/app/tasks/gap_tasks.py`
  - `calculate_gap_states` (Celery) – triggered on assessment completion; calls `calculate_gap_states_for_attempt`.

- Data:
  - `gap_states` – per-student, per-subtopic, per-class mastery with confidence, attempt counts, needs_review flag (mastery < 0.4).
  - `student_attempt_subtopic_scores` – historical per-attempt subtopic scores for recency-weighted calculations.
  - `question_bank` – source of assessment questions.
  - Schemas: `backend/app/schemas/gap_map.py` (ClassGapMap, ClassSummary, StudentGapMap, GapMapNode, StudentGapScore, StudentSubtopicScore).

Invariants:
- Multi-tenancy: all queries scoped by `school_id` via class or user. Teachers can only access their own classes.
- No LLM scoring: MCQ scoring is deterministic string comparison.
- Subtopics with no gap_state rows are included with `class_average = None` (not conflated with low mastery).
- Confidence grows with attempt count: min(attempt_count / 5, 1.0).
- `needs_review` is TRUE when mastery < 0.4.

## 4. Frontend responsibilities

- Class detail view (Teacher / School Admin apps):
  - Fetch and render class summary on class cards (avg mastery indicator, student counts, below-threshold count).
  - Fetch and render gap map heatmap per subject: subtopic rows × student columns with color-coded mastery cells.
  - Show "Not assessed" state for subtopics with no gap_state rows.
  - Include filters for subject and controls to expand/collapse student columns.

- Student app:
  - Render personal gap map: subtopic list with mastery scores, last assessed timestamps, and topic grouping.
  - Grey out subtopics with no assessment (mastery_score = None).

- Shared UI (`frontend/packages/ui`):
  - Mastery color scale component (consistent with design system thresholds).
  - Heatmap table component, loading/empty states, and responsive collapse for mobile.

## 5. Tests

- Backend:
  - Unit tests for `gap_service` (gap state upsert, recency-weighted mastery, confidence, needs_review).
  - Unit tests for `calculate_gap_states_for_attempt` (Tier 1 and Tier 2 scoring, empty responses, missing questions).
  - Integration tests for gap-map routes (multi-tenancy, role access, teacher class ownership).
  - Tests for class summary aggregates and below-threshold counts.

- Frontend:
  - Tests for class detail gap map rendering and filters.
  - Tests for student personal gap map.
  - Tests for mastery color scale and heatmap interactions.

## 6. Implementation notes

- 2026‑05‑07 – UPDATE: Gap map is shown under class detail view for Teachers and School Admins (no separate dashboard). Student personal gap map remains in student app.
- 2026‑05‑07 – INITIAL DOCUMENT
  - Notes: Aligns with Constitution gap-map definitions. Uses real implementation paths (`gap_service.py`, `gap_map.py` routes, `gap_map.py` schemas).