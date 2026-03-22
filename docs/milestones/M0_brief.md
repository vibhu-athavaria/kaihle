# M0 Brief — Foundations
**Milestone:** 0 of 6
**Estimated duration:** 4–5 weeks
**Previous milestone:** None — this is the start
**Constitution version:** 2.0

> Load this brief alongside CONSTITUTION.md when working on any M0 task.
> Load the specific task file for the task you are implementing.

---

## Goal

Working local dev environment, CI/CD pipeline, complete authentication system (including magic-link → password setup flow for all invited roles), multi-tenant data model, five separate frontend apps, and full student onboarding infrastructure. No AI or LLM calls in this milestone.

---

## Exit Criteria

- A developer can `docker-compose up` and have all five frontend apps plus the backend running
- All five frontend apps are fully separated — `apps/student`, `apps/teacher`, `apps/parent`, `apps/school-admin`, `apps/kaihle-admin` — each with its own port, Tailwind config, and Docker Compose service
- School Admin and Kaihle Admin UI does NOT exist inside `apps/teacher`
- A user invited via magic link must set a password before accessing anything else — enforced by scoped JWT (`scope: "password_setup"`) and `PasswordSetupRoute` guard
- Student onboarding enforces two independent gates: (1) learning profile questionnaire must be complete before dashboard access; (2) class content locked per class until that class's Tier 1 diagnostic is complete
- Enrolling a student in a class automatically triggers Tier 1 diagnostic creation via Celery, guarded against an empty question bank
- KaihleAdmin can access any school's data; all other roles are strictly school-scoped
- CI runs on every PR and enforces coverage

---

## What This Milestone Delivers

**Infrastructure:** Monorepo structure with all tooling configured (pnpm workspaces, pyproject.toml). Docker Compose with PostgreSQL (pgvector), Redis, backend, Celery worker, and all five frontend apps. GitHub Actions CI/CD pipeline with lint, test, coverage gate, and deploy to Render.

**Database:** All 35 database tables migrated via Alembic. All SQLAlchemy ORM models using SQLAlchemy 2.x async. `onboarding_diagnostic_status` on `class_enrollments` (not `student_profiles`). `is_learning_profile_complete` boolean on `student_profiles`. `User.school_id` nullable with CHECK constraint (KaihleAdmin has no school). Email uniqueness enforced as composite `UNIQUE(email, school_id)`.

**Authentication and Onboarding:** JWT utilities (bcrypt, 15-minute access tokens, 7-day refresh tokens). Magic link generation and verification (10-minute TTL, single-use, scoped JWT). `POST /api/v1/auth/set-password` endpoint that requires a scoped JWT and issues a full JWT on success. Auth middleware including `get_current_user`, `require_role`, `require_school_resource`, and `require_diagnostic_complete(class_id)`. Frontend guards: `PasswordSetupRoute` and `OnboardingRoute` in `packages/auth`.

**Backend APIs:** School management CRUD (KaihleAdmin). User invite/manage (SchoolAdmin) where invitation sends magic link. Grade, class management, and enrollment API where enrollment fires the `trigger_onboarding_diagnostics` Celery task. Learning profile questionnaire API with scoring logic. Onboarding completion tracking service. Structured logging and health check endpoints.

**Celery Tasks:** `create_class_diagnostic_task` fired on class creation — builds Tier 1 assessment pool, exits cleanly without creating an empty assessment if question bank is empty. `trigger_onboarding_diagnostics` fired on student enrollment — creates `StudentAttempt`, uses `new_event_loop()` pattern. Both tasks emit a `CRITICAL` structured log on final retry exhaustion.

**Frontend — Five Apps plus Shared Packages:** `packages/auth` provides `tokenStore`, `useAuth`, `PrivateRoute`, `RoleRoute`, `OnboardingRoute`, and `PasswordSetupRoute`. `packages/ui` provides `PasswordSetupForm`, `LoginForm`, `AuthLayout`, `OnboardingLayout`, `DashboardLayout` with teacher and school-admin variants, `AdminLayout`, `StudentLayout`, `ParentLayout`, and core components. `packages/types` provides `getMasteryStyle()` and shared TypeScript interfaces. `packages/api-client` provides shared Axios with JWT interceptor and refresh logic. Each of the five apps delivers its role-appropriate login screen, password setup screen, and dashboard scaffold.

**LLM Infrastructure (scaffolding only — no calls in this milestone):** LiteLLM installed in `pyproject.toml`. `backend/app/ai/providers/router.py` implemented with task-to-model config mapping read entirely from environment variables, supporting self-hosted LLM server via `api_base` override.

---

## Tasks in This Milestone

| Task ID | File | Description | Status |
|---|---|---|---|
| M0-1-T1 | `M0/M0-1-T1_init_monorepo.md` | Initialise monorepo structure and tooling | Done |
| M0-1-T2 | `M0/M0-1-T2_docker_compose.md` | Docker Compose dev environment (was 3 apps) | Done |
| M0-1-T3 | `M0/M0-1-T3_ci_cd_pipeline.md` | GitHub Actions CI/CD | Done |
| M0-2-T1 | `M0/M0-2-T1_alembic_migrations.md` | Alembic setup and initial migration (35 tables) | Done |
| M0-2-T2 | `M0/M0-2-T2_sqlalchemy_models.md` | SQLAlchemy ORM models | Done |
| M0-3-T1 | `M0/M0-3-T1_core_auth_backend.md` | JWT security utilities | Done |
| M0-3-T2 | `M0/M0-3-T2_auth_routes.md` | Auth API endpoints | Done |
| M0-3-T3 | `M0/M0-3-T3_auth_middleware.md` | Route guards and onboarding gate middleware | Done |
| M0-3-T4 | `M0/M0-3-T4_auth_frontend.md` | Auth frontend package | Done |
| M0-3-T5 | `M0/M0-3-T5_login_ui.md` | Login UI | Done |
| M0-4-T1 | `M0/M0-4-T1_school_management_api.md` | School CRUD (KaihleAdmin) | Done |
| M0-4-T2 | `M0/M0-4-T2_user_management_api.md` | User invite/manage (SchoolAdmin) | Done |
| M0-4-T3 | `M0/M0-4-T3_grade_class_enrollment_api.md` | Grade/class/enroll and Tier 1 trigger | Done |
| M0-5-T1 | `M0/M0-5-T1_structured_logging.md` | structlog JSON logging | Done |
| M0-5-T2 | `M0/M0-5-T2_health_check.md` | /health and /ready endpoints | Done |
| M0-6-T1 | `M0/M0-6-T1_learning_profile_api.md` | Learning profile questionnaire API | Done |
| M0-6-T2 | `M0/M0-6-T2_tier1_diagnostic_trigger.md` | Celery: auto-create Tier 1 diagnostics | Done |
| M0-6-T3 | `M0/M0-6-T3_onboarding_completion_tracking.md` | Onboarding completion check service | Done |
| M0-6-T4 | `M0/M0-6-T4_onboarding_ui.md` | Student onboarding UI | Done |
| M0-7-T1 | `M0/M0-7-T1_layout_wrappers.md` | Shared layout wrappers in packages/ui | Done |
| M0-7-T2 | `M0/M0-7-T2_teacher_dashboard.md` | Teacher dashboard scaffold (apps/teacher) | Done |
| M0-7-T3 | `M0/M0-7-T3_student_dashboard.md` | Student dashboard scaffold (apps/student) | Done |
| M0-7-T4 | `M0/M0-7-T4_school_admin_ui.md` | School admin UI — placed in apps/teacher incorrectly | Superseded by M0-9-T2 |
| M0-7-T5 | `M0/M0-7-T5_kaihle_admin_ui.md` | Kaihle admin UI — placed in apps/teacher incorrectly | Superseded by M0-9-T3 |
| M0-8-T1 | `M0/M0-8-T1_backend_critical_fixes.md` | User.school_id nullable and Celery asyncio fix | Done |
| M0-8-T2 | `M0/M0-8-T2_backend_important_fixes.md` | Test fixtures, email uniqueness, coverage docs | Done |
| M0-8-T3 | `M0/M0-8-T3_frontend_critical_config.md` | Google Fonts, Tailwind configs, mastery.ts | Done |
| M0-8-T4 | `M0/M0-8-T4_shared_ui_foundation.md` | packages/ui core components and api-client | Done |
| M0-9-T1 | `M0/M0-9-T1_five_app_restructure.md` | NEW — Create apps/school-admin and apps/kaihle-admin Vite apps | Todo |
| M0-9-T2 | `M0/M0-9-T2_school_admin_app_migration.md` | NEW — Migrate school admin pages into apps/school-admin | Todo |
| M0-9-T3 | `M0/M0-9-T3_kaihle_admin_app_migration.md` | NEW — Migrate Kaihle admin pages into apps/kaihle-admin | Todo |
| M0-9-T4 | `M0/M0-9-T4_password_setup_flow.md` | NEW — Scoped JWT, set-password endpoint, PasswordSetupForm | Todo |
| M0-9-T5 | `M0/M0-9-T5_per_class_diagnostic_gate.md` | NEW — Per-class content gate backend and student UI | Todo |
| M0-9-T6 | `M0/M0-9-T6_backend_spec_corrections.md` | NEW — KaihleAdmin bypass bug, LiteLLM, type:ignore, Celery guards | Todo |
| M0-7-T2b | `M0/M0-7-T2b_teacher_settings_ui.md` | NEW — Teacher settings page (account, password) | Todo |
| M0-7-T3b | `M0/M0-7-T3b_student_settings_ui.md` | NEW — Student settings page (account, learning profile retake) | Todo |
| M0-7-T4b | `M0/M0-7-T4b_school_admin_settings_ui.md` | NEW — School Admin settings page (account, school profile view) | Todo |

---

## Task Execution Order for M0-9

The M0-1 through M0-8 tasks are complete. The M0-9 tasks must be completed before M1 can begin. They are largely independent of each other and can be parallelised across agents.

M0-9-T1 must come first since it creates the scaffold that T2 and T3 migrate into. M0-9-T2 and M0-9-T3 can then run in parallel with each other once T1 is done. M0-9-T4, T5, and T6 have no dependency on T1 through T3 and can run in parallel with all of the above. All six M0-9 tasks must be complete and CI passing before M1 begins.

**M0-7-T2b and M0-7-T3b** (teacher settings and student settings) can run in parallel with M0-10 — they touch only `apps/teacher/src/pages/settings/` and `apps/student/src/pages/settings/` with zero overlap with M0-10 changes. Queue them immediately.

**M0-7-T4b** (school admin settings) must wait until M0-10 completes — M0-10-T10 is modifying `apps/school-admin` hooks and running in parallel risks a merge conflict on `useSchoolAdmin.ts`.

---

## Definition of Done

- `docker-compose up` starts all seven services (backend, celery, five frontend apps) with no errors
- All five apps serve their correct role with zero cross-role code in any `apps/` directory
- Magic link → scoped JWT → password setup → full JWT flow works end-to-end for School Admin, Teacher, and Student
- Student cannot reach `/student/dashboard` without completing the learning profile questionnaire
- Student cannot access class content without completing that class's Tier 1 diagnostic, independently of other classes
- KaihleAdmin can access any school's classes and users; SchoolAdmin cannot cross schools
- `create_class_diagnostic_task` exits cleanly when question bank is empty — no empty assessment created
- Both Celery tasks use `new_event_loop()`, not `asyncio.run()`
- Both Celery tasks emit `CRITICAL` log on final retry exhaustion
- LiteLLM installed; `router.py` reads all model config from environment variables
- Zero inline `# type: ignore` comments in production code
- CI passes: ruff, mypy, pytest with coverage, Playwright E2E

---

## Key Tables Touched in This Milestone

`users`, `student_profiles`, `teacher_profiles`, `auth_tokens`, `schools`, `school_curricula`, `classes`, `class_enrollments`, `grades`, `subjects`, `curricula`, `assessments`, `student_attempts`, `student_learning_profiles`, `subscription_plans`, `school_subscriptions`

Full schema: `kaihle_v2_1_schema.sql`
