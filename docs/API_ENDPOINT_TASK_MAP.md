# API Endpoint → Task File Master Map
**Last updated:** March 2026
**Status key:**
- ✅ Built — code exists in the repo, tested
- 🔧 Stubbed — route exists (returns empty/placeholder data), real implementation in named task
- 📋 Task exists — full task file written, not yet implemented
- ⚠️ GAP — no task file exists, needs to be written before M0-10 begins

---

## Authentication `/api/v1/auth`

| Endpoint | Status | Task File | Notes |
|---|---|---|---|
| `POST /auth/register` | ✅ Built | `M0/M0-3-T2_auth_routes.md` | Exists in `routes/auth.py` |
| `POST /auth/login` | ✅ Built | `M0/M0-3-T2_auth_routes.md` | Rate limit added in M6-3-T1 |
| `POST /auth/magic-link` | ✅ Built | `M0/M0-3-T2_auth_routes.md` | Rate limit added in M6-3-T1 |
| `GET /auth/magic-link/verify` | ✅ Built | `M0/M0-3-T2_auth_routes.md` | Updated by M0-9-T4 to return scoped JWT |
| `POST /auth/set-password` | 📋 Task exists | `M0/M0-9-T4_password_setup_flow.md` | Exchanges scoped JWT for full JWT |
| `POST /auth/refresh` | ✅ Built | `M0/M0-3-T2_auth_routes.md` | |
| `POST /auth/logout` | ✅ Built | `M0/M0-3-T2_auth_routes.md` | |

---

## Platform Management `/api/v1/platform`

| Endpoint | Status | Task File | Notes |
|---|---|---|---|
| `GET /platform/stats` | 🔧 Stubbed | `M0-10/M0-10-T6_parent_analytics_stubs.md` | Real impl: `M6/M6-1-T1_analytics_service_routes.md` |
| `POST /platform/schools/{id}/impersonate` | 🔧 Stubbed | `M0-10/M0-10-T6_parent_analytics_stubs.md` | Returns 501 stub; real impl: `M6/M6-1-T1_analytics_service_routes.md` |

---

## Schools `/api/v1/schools`

| Endpoint | Status | Task File | Notes |
|---|---|---|---|
| `POST /schools` | ✅ Built | `M0/M0-4-T1_school_management_api.md` | Currently at `/admin/schools` — renamed in `M0-10/M0-10-T7_backend_hard_cutover.md` |
| `GET /schools` | ✅ Built | `M0/M0-4-T1_school_management_api.md` | Same rename applies |
| `GET /schools/{school_id}` | ✅ Built | `M0/M0-4-T1_school_management_api.md` | Same rename applies |
| `PATCH /schools/{school_id}` | ✅ Built | `M0/M0-4-T1_school_management_api.md` | Same rename applies |
| `DELETE /schools/{school_id}` | 📋 Task exists | `M0-10/M0-10-T7_addendum_missing_stubs.md` | Returns 501 stub |
| `GET /schools/{school_id}/analytics` | 🔧 Stubbed | `M0-10/M0-10-T6_parent_analytics_stubs.md` | Real impl: `M6/M6-1-T1_analytics_service_routes.md` |
| `GET /schools/{school_id}/billing` | 🔧 Stubbed | `M0-10/M0-10-T13_billing_endpoints.md` | Returns TRIAL stub; real impl: M6-2-T1 |
| `PATCH /schools/{school_id}/billing` | 🔧 Stubbed | `M0-10/M0-10-T13_billing_endpoints.md` | Returns 501; KaihleAdmin only; real impl: M6 |

---

## Users `/api/v1/schools/{school_id}/users`

| Endpoint | Status | Task File | Notes |
|---|---|---|---|
| `GET /schools/{school_id}/users` | ✅ Built | `M0/M0-4-T2_user_management_api.md` | Exists in `routes/users.py` |
| `POST /schools/{school_id}/users` | ✅ Built | `M0/M0-4-T2_user_management_api.md` | Sends magic link invite |
| `GET /schools/{school_id}/users/{user_id}` | ✅ Built | `M0/M0-4-T2_user_management_api.md` | |
| `PATCH /schools/{school_id}/users/{user_id}` | ✅ Built | `M0/M0-4-T2_user_management_api.md` | |
| `DELETE /schools/{school_id}/users/{user_id}` | ✅ Built | `M0/M0-4-T2_user_management_api.md` | |

---

## Curriculum `/api/v1/curricula` — Global Read-Only

| Endpoint | Status | Task File | Notes |
|---|---|---|---|
| `GET /curricula` | 🔧 Stubbed | `M0-10/M0-10-T2b_curriculum_read_endpoints.md` | Fully implemented (static data) |
| `GET /curricula/{curriculum_id}` | 🔧 Stubbed | `M0-10/M0-10-T2b_curriculum_read_endpoints.md` | Fully implemented (static data) |
| `GET /grades` | 🔧 Stubbed | `M0-10/M0-10-T2b_curriculum_read_endpoints.md` | Fully implemented (static data) |
| `GET /subjects` | 🔧 Stubbed | `M0-10/M0-10-T2b_curriculum_read_endpoints.md` | Fully implemented (static data) |
| `GET /subjects/{subject_id}/topics` | 🔧 Stubbed | `M0-10/M0-10-T2b_curriculum_read_endpoints.md` | **CRITICAL PATH** — unblocks M1-3-T3 wizard |
| `GET /topics/{topic_id}/subtopics` | 🔧 Stubbed | `M0-10/M0-10-T2b_curriculum_read_endpoints.md` | Fully implemented (static data) |

> **Note:** `GET /classes/{class_id}/topics` (class-scoped, gated) exists in
> `routes/student_content.py` but is different from the global curriculum read
> endpoints above. The global endpoints return the full curriculum catalogue
> (used by the assessment wizard to populate topic selectors). They are not
> the same as the gated per-class topic list.

---

## Classes `/api/v1`

| Endpoint | Status | Task File | Notes |
|---|---|---|---|
| `POST /schools/{school_id}/classes` | ✅ Built | `M0/M0-4-T3_grade_class_enrollment_api.md` | Currently in `schools.py` — moves to `classes.py` in M0-10-T7 |
| `GET /schools/{school_id}/classes` | ✅ Built | `M0/M0-4-T3_grade_class_enrollment_api.md` | Moves to `classes.py` in M0-10-T7. **Student role added in M0-10-T7 Addendum 2** — returns enrolled classes only for students |
| `GET /students/me/classes` | 📋 Task exists | `M0-10/M0-10-T7_addendum2_student_classes.md` | **NEW** — student dashboard shortcut, returns `StudentClassResponse[]` with diagnostic status per class |
| `GET /classes/{class_id}` | 📋 Task exists | `M0-10/M0-10-T7_addendum_missing_stubs.md` | Single class GET stub — added in T7 addendum |
| `PATCH /classes/{class_id}` | 📋 Task exists | `M0-10/M0-10-T7_addendum_missing_stubs.md` | Returns 501 stub |
| `DELETE /classes/{class_id}` | 📋 Task exists | `M0-10/M0-10-T7_addendum_missing_stubs.md` | Returns 501 stub |
| `GET /classes/{class_id}/enrollments` | ✅ Built | `M0/M0-4-T3_grade_class_enrollment_api.md` | Currently `/students` — renamed in M0-10-T7 |
| `POST /classes/{class_id}/enrollments` | ✅ Built | `M0/M0-4-T3_grade_class_enrollment_api.md` | Currently `/enroll` — renamed in M0-10-T7 |
| `DELETE /classes/{class_id}/enrollments/{student_id}` | 📋 Task exists | `M0-10/M0-10-T7_addendum_missing_stubs.md` | Returns 501 stub |
| `GET /classes/{class_id}/summary` | 🔧 Stubbed | `M0-10/M0-10-T2_gap_map_stubs.md` | Real impl: `M2/M2-1-T2_gap_map_routes.md` |
| `GET /classes/{class_id}/gap-map` | 🔧 Stubbed | `M0-10/M0-10-T2_gap_map_stubs.md` | Real impl: `M2/M2-1-T2_gap_map_routes.md` |
| `GET /classes/{class_id}/topics` | ✅ Built | `M0/M0-9-T5_per_class_diagnostic_gate.md` | In `student_content.py`, gated by `require_diagnostic_complete` |
| `GET /classes/{class_id}/assessments` | 🔧 Stubbed | `M0-10/M0-10-T3_assessment_attempt_stubs.md` | Real impl: `M1/M1-3-T2_assessment_api_routes.md` |
| `POST /classes/{class_id}/assessments` | 🔧 Stubbed | `M0-10/M0-10-T3_assessment_attempt_stubs.md` | Real impl: `M1/M1-3-T2_assessment_api_routes.md` |
| `GET /classes/{class_id}/lesson-plans` | 🔧 Stubbed | `M0-10/M0-10-T5_lesson_plan_stubs.md` | Real impl: `M4/M4-1-T3_lesson_plan_routes.md` |
| `POST /classes/{class_id}/study-plans` | 🔧 Stubbed | `M0-10/M0-10-T4_study_plan_stubs.md` | Real impl: `M3/M3-2-T2_study_plan_routes.md` |
| `GET /classes/{class_id}/diagnostic` | 🔧 Stubbed | `M0-10/M0-10-T3_assessment_attempt_stubs.md` | Real impl: `M1/M1-4-T1_student_attempt_api.md` |

---

## Onboarding `/api/v1/onboarding`

| Endpoint | Status | Task File | Notes |
|---|---|---|---|
| `GET /onboarding/status` | ✅ Built | `M0/M0-6-T1_learning_profile_api.md` | Bare `/status` (no student_id) — returns own status for students. Called by `OnboardingRoute` guard in `packages/auth` |
| `GET /onboarding/status/{student_id}` | ✅ Built | `M0/M0-6-T1_learning_profile_api.md` | For teachers/admins to check a specific student |
| `GET /onboarding/questionnaire` | ✅ Built | `M0/M0-6-T1_learning_profile_api.md` | |
| `POST /onboarding/questionnaire/submit` | ✅ Built | `M0/M0-6-T1_learning_profile_api.md` | |
| `GET /onboarding/pending` | 📋 Task exists | `M0-10/M0-10-T7_addendum_missing_stubs.md` | Stub returns empty Page; real impl in M1 |

---

## Learning Profiles `/api/v1/students`

| Endpoint | Status | Task File | Notes |
|---|---|---|---|
| `GET /students/me/learning-profile` | 📋 Task exists | `M0-10/M0-10-T7_addendum_missing_stubs.md` | Renamed from `/onboarding/learning-profile` in M0-10-T7 addendum |
| `GET /students/{student_id}/learning-profile` | 📋 Task exists | `M0-10/M0-10-T7_addendum_missing_stubs.md` | Same rename applies |

---

## Assessments `/api/v1/assessments`

| Endpoint | Status | Task File | Notes |
|---|---|---|---|
| `GET /assessments/{assessment_id}` | 🔧 Stubbed | `M0-10/M0-10-T3_assessment_attempt_stubs.md` | Real impl: `M1/M1-3-T2_assessment_api_routes.md` |
| `PATCH /assessments/{assessment_id}` | 📋 Task exists | `M0-10/M0-10-T7_addendum_missing_stubs.md` | Stub returns 404; real impl in M1-3-T2 |
| `POST /assessments/{assessment_id}/publish` | 🔧 Stubbed | `M0-10/M0-10-T3_assessment_attempt_stubs.md` | Real impl: `M1/M1-3-T2_assessment_api_routes.md` |
| `POST /assessments/{assessment_id}/close` | 🔧 Stubbed | `M0-10/M0-10-T3_assessment_attempt_stubs.md` | Real impl: `M1/M1-3-T2_assessment_api_routes.md` |

---

## Attempts `/api/v1/attempts`

| Endpoint | Status | Task File | Notes |
|---|---|---|---|
| `GET /classes/{class_id}/diagnostic` | 🔧 Stubbed | `M0-10/M0-10-T3_assessment_attempt_stubs.md` | Real impl: `M1/M1-4-T1_student_attempt_api.md` |
| `GET /attempts/{attempt_id}` | 🔧 Stubbed | `M0-10/M0-10-T3_assessment_attempt_stubs.md` | Real impl: `M1/M1-4-T1_student_attempt_api.md` |
| `POST /attempts/{attempt_id}/responses` | 🔧 Stubbed | `M0-10/M0-10-T3_assessment_attempt_stubs.md` | Real impl: `M1/M1-4-T1_student_attempt_api.md` |
| `POST /attempts/{attempt_id}/submit` | 🔧 Stubbed | `M0-10/M0-10-T3_assessment_attempt_stubs.md` | Real impl: `M1/M1-4-T1_student_attempt_api.md` |
| `GET /attempts/{attempt_id}/results` | 🔧 Stubbed | `M0-10/M0-10-T3_assessment_attempt_stubs.md` | Real impl: `M1/M1-4-T1_student_attempt_api.md` |

---

## Gap Map

| Endpoint | Status | Task File | Notes |
|---|---|---|---|
| `GET /classes/{class_id}/gap-map` | 🔧 Stubbed | `M0-10/M0-10-T2_gap_map_stubs.md` | Real impl: `M2/M2-1-T2_gap_map_routes.md` |
| `GET /students/me/gap-map` | 🔧 Stubbed | `M0-10/M0-10-T2_gap_map_stubs.md` | Real impl: `M2/M2-1-T2_gap_map_routes.md` |
| `GET /students/{student_id}/gap-map` | 🔧 Stubbed | `M0-10/M0-10-T2_gap_map_stubs.md` | Real impl: `M2/M2-1-T2_gap_map_routes.md` |

---

## Study Plans

| Endpoint | Status | Task File | Notes |
|---|---|---|---|
| `GET /students/me/study-plans` | 🔧 Stubbed | `M0-10/M0-10-T4_study_plan_stubs.md` | Real impl: `M3/M3-2-T2_study_plan_routes.md` |
| `GET /students/{student_id}/study-plans` | 🔧 Stubbed | `M0-10/M0-10-T4_study_plan_stubs.md` | Real impl: `M3/M3-2-T2_study_plan_routes.md` |
| `GET /study-plans/{plan_id}` | 🔧 Stubbed | `M0-10/M0-10-T4_study_plan_stubs.md` | Real impl: `M3/M3-2-T2_study_plan_routes.md` |
| `PATCH /study-plans/{plan_id}/resources/{resource_id}/watched` | 🔧 Stubbed | `M0-10/M0-10-T4_study_plan_stubs.md` | Real impl: `M3/M3-2-T2_study_plan_routes.md` |
| `POST /study-plans/{plan_id}/quiz/submit` | 🔧 Stubbed | `M0-10/M0-10-T4_study_plan_stubs.md` | Real impl: `M3/M3-2-T2_study_plan_routes.md` |

---

## Lesson Plans

| Endpoint | Status | Task File | Notes |
|---|---|---|---|
| `GET /classes/{class_id}/lesson-plans` | 🔧 Stubbed | `M0-10/M0-10-T5_lesson_plan_stubs.md` | Real impl: `M4/M4-1-T3_lesson_plan_routes.md` |
| `GET /lesson-plans/{plan_id}` | 🔧 Stubbed | `M0-10/M0-10-T5_lesson_plan_stubs.md` | Real impl: `M4/M4-1-T3_lesson_plan_routes.md` |
| `PATCH /lesson-plans/{plan_id}` | 🔧 Stubbed | `M0-10/M0-10-T5_lesson_plan_stubs.md` | Real impl: `M4/M4-1-T3_lesson_plan_routes.md` |
| `POST /lesson-plans/{plan_id}/regenerate` | 🔧 Stubbed | `M0-10/M0-10-T5_lesson_plan_stubs.md` | Real impl: `M4/M4-1-T3_lesson_plan_routes.md` |
| `PATCH /lesson-plans/{plan_id}/status` | 🔧 Stubbed | `M0-10/M0-10-T5_lesson_plan_stubs.md` | Real impl: `M4/M4-1-T3_lesson_plan_routes.md` |

---

## Parent Portal

| Endpoint | Status | Task File | Notes |
|---|---|---|---|
| `GET /parent/children` | 🔧 Stubbed | `M0-10/M0-10-T6_parent_analytics_stubs.md` | Real impl: `M5/M5-1-T2_parent_portal_api.md` |
| `GET /parent/children/{student_id}/reports` | 🔧 Stubbed | `M0-10/M0-10-T6_parent_analytics_stubs.md` | Real impl: `M5/M5-1-T2_parent_portal_api.md` |
| `GET /parent/children/{student_id}/reports/{report_id}` | 🔧 Stubbed | `M0-10/M0-10-T6_parent_analytics_stubs.md` | Real impl: `M5/M5-1-T2_parent_portal_api.md` |
| `GET /parent/children/{student_id}/gap-map` | 🔧 Stubbed | `M0-10/M0-10-T6_parent_analytics_stubs.md` | Real impl: `M5/M5-1-T2_parent_portal_api.md` |

---

## Infrastructure

| Endpoint | Status | Task File | Notes |
|---|---|---|---|
| `GET /health` | ✅ Built | `M0/M0-5-T2_health_check.md` | Registered at root (no `/api/v1/` prefix) |
| `GET /ready` | ✅ Built | `M0/M0-5-T2_health_check.md` | Registered at root |

---

## Gap Summary — All Gaps Now Resolved

All endpoints have been accounted for. The previous gap summary has been superseded.
See individual task files for implementation details.

**New endpoints added after initial audit:**
- `GET /students/me/classes` — student dashboard class list with diagnostic status
- `GET /schools/{id}/subscription` — school billing read
- `GET /schools/{id}/invoices` — invoice list
- `GET /subscription-plans` — global plan catalogue
- Six curriculum read endpoints (`/curricula`, `/grades`, `/subjects`, etc.)
- Seven CRUD stubs (DELETE school/class, PATCH class, DELETE enrollment, PATCH assessment, GET onboarding/pending)

**One endpoint intentionally 501 in v1:**
- `PATCH /schools/{id}/billing` — subscription changes are sales-led, no self-serve API

**Billing read design (finalized):**
The canonical "billing" endpoints map to `GET /schools/{id}/subscription` and
`GET /schools/{id}/invoices` in the implementation. The original design used
`GET /schools/{id}/billing` as a single envelope — the implementation splits this
into two focused endpoints matching what the billing UI actually needs.

