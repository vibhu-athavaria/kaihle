# M0 Brief — Foundations
**Milestone:** 0 of 6
**Estimated duration:** 3–4 weeks
**Previous milestone:** None — this is the start

> Load this brief alongside CONSTITUTION.md when working on any M0 task.
> Load the specific task file for the task you are implementing.

---

## Goal

Working local dev environment, CI/CD pipeline, auth system, multi-tenant model, and student onboarding infrastructure. No product features. No LLM calls.

## Exit Criteria

- A developer can `docker-compose up` and have the full stack running
- A user can register, log in, and receive a valid JWT
- Enrolling a student automatically triggers Tier 1 diagnostic creation (Celery)
- A student cannot access the dashboard until learning profile + Tier 1 diagnostics are complete
- CI runs and enforces coverage on every PR

---

## What This Milestone Delivers

- Monorepo structure with all tooling configured
- Docker Compose with PostgreSQL (pgvector), Redis, backend, Celery, 3 frontend apps
- GitHub Actions CI/CD pipeline
- All 35 database tables migrated (Alembic)
- All SQLAlchemy ORM models
- Full authentication system: email/password, magic link, JWT, refresh, logout
- Auth middleware including `require_onboarding_complete` guard
- School management API (KaihleAdmin)
- User management API (SchoolAdmin)
- Grade + class management + enrollment API (fires Tier 1 Celery task on enroll)
- Structured logging + health check endpoints
  - Learning profile questionnaire API + scoring logic
  - Tier 1 auto-diagnostic Celery trigger on enrollment
  - Onboarding completion tracking service
  - Onboarding UI in student app (questionnaire + diagnostic hub)

---

## Tasks in This Milestone

| Task ID | File | Description |
|---|---|---|
| M0-1-T1 | `M0/M0-1-T1_init_monorepo.md` | Initialise monorepo structure and tooling |
| M0-1-T2 | `M0/M0-1-T2_docker_compose.md` | Docker Compose dev environment |
| M0-1-T3 | `M0/M0-1-T3_ci_cd_pipeline.md` | GitHub Actions CI/CD |
| M0-2-T1 | `M0/M0-2-T1_alembic_migrations.md` | Alembic setup + initial migration (35 tables) |
| M0-2-T2 | `M0/M0-2-T2_sqlalchemy_models.md` | SQLAlchemy ORM models |
| M0-3-T1 | `M0/M0-3-T1_core_auth_backend.md` | JWT security utilities |
| M0-3-T2 | `M0/M0-3-T2_auth_routes.md` | Auth API endpoints |
| M0-3-T3 | `M0/M0-3-T3_auth_middleware.md` | Route guards + onboarding gate middleware |
| M0-3-T4 | `M0/M0-3-T4_auth_frontend.md` | Auth frontend package (tokenStore, hooks, guards) |
| M0-3-T5 | `M0/M0-3-T5_login_ui.md` | Login UI for all 3 apps |
| M0-4-T1 | `M0/M0-4-T1_school_management_api.md` | School CRUD (KaihleAdmin) |
| M0-4-T2 | `M0/M0-4-T2_user_management_api.md` | User invite/manage (SchoolAdmin) |
| M0-4-T3 | `M0/M0-4-T3_grade_class_enrollment_api.md` | Grade/class/enroll + Tier 1 trigger |
| M0-5-T1 | `M0/M0-5-T1_structured_logging.md` | structlog JSON logging |
| M0-5-T2 | `M0/M0-5-T2_health_check.md` | /health and /ready endpoints |
| M0-6-T1 | `M0/M0-6-T1_learning_profile_api.md` | Learning profile questionnaire API |
| M0-6-T2 | `M0/M0-6-T2_tier1_diagnostic_trigger.md` | Celery task: auto-create Tier 1 diagnostics |
| M0-6-T3 | `M0/M0-6-T3_onboarding_completion_tracking.md` | Onboarding completion check service |
| M0-6-T4 | `M0/M0-6-T4_onboarding_ui.md` | Student onboarding UI (questionnaire + diagnostic hub) |
| M0-8-T1 | `M0/M0-8-T1_backend_critical_fixes.md`   | User.school_id nullable + Celery asyncio.run fix |
| M0-8-T2 | `M0/M0-8-T2_backend_important_fixes.md`  | Test fixtures, email uniqueness, coverage docs, route refactor, OpenAPI tags |
| M0-8-T3 | `M0/M0-8-T3_frontend_critical_config.md` | Google Fonts, tailwind configs, mastery.ts, LoginForm brand fix |
| M0-8-T4 | `M0/M0-8-T4_shared_ui_foundation.md`     | packages/ui core components + packages/api-client scaffold |

---

## Task Execution Order

Tasks within the same epic can be parallelised if working with multiple agents. Cross-epic dependencies:

```
M0-1-T1 (monorepo)
  → M0-1-T2 (Docker)
  → M0-1-T3 (CI/CD)
  → M0-2-T1 (migrations) ← must come before M0-2-T2
    → M0-2-T2 (models)
      → M0-3-T1 (auth backend)
        → M0-3-T2 (auth routes)
        → M0-3-T3 (middleware) ← depends on M0-6-T3
      → M0-4-T1, M0-4-T2
      → M0-4-T3 ← depends on M0-6-T2
      → M0-6-T1 (learning profile API)
        → M0-6-T2 (Tier 1 trigger)
          → M0-6-T3 (completion tracking)
            → M0-6-T4 (onboarding UI) ← last
  → M0-3-T4 (auth frontend) ← parallel with backend work
    M0-3-T5 (login UI)
      → M0-8-T1 (backend critical fixes)  ← can run in parallel with T2/T3/T4
      → M0-8-T2 (backend important fixes) ← can run in parallel with T1/T3/T4
      → M0-8-T3 (frontend config fixes)   ← can run in parallel with T1/T2
        → M0-8-T4 (shared UI components)  ← needs fonts + tokens from T3
          → M0-7-T1 (layout wrappers)     ← needs shared components from T4

            ← ALL of M0-8-T1, M0-8-T2, M0-8-T3, M0-8-T4, M0-7-T1 must be
              complete before any of the following start:

            → M0-6-T4 (onboarding UI)     ← first feature UI — needs wrappers, types, clean backend
            → M0-7-T2 (teacher dashboard) ← parallel with M0-6-T4 once M0-7-T1 done
            → M0-7-T3 (student dashboard) ← parallel
            → M0-7-T4 (school admin UI)   ← parallel
            → M0-7-T5 (kaihle admin UI)   ← parallel
  → M0-5-T1, M0-5-T2 ← can run anytime after M0-2-T2
```
Note on backend/frontend parallelism: M0-8-T1 and M0-8-T2 are backend-only and can
run at the same time as M0-8-T3 and M0-8-T4 if multiple agents are available.
However ALL four M0-8 tasks must be complete and passing before M0-6-T4 begins.
M0-8-T1 specifically must be done before M0-6-T4 acceptance tests can pass cleanly
(the onboarding API tests depend on a valid auth setup including the KaihleAdmin fix).
---

## Definition of Done

- [ ] `docker-compose up` starts all services without manual steps
- [ ] CI pipeline runs on every PR, enforces ≥ 80% coverage on service files
- [ ] Full auth flow works end-to-end (register, login, magic link, refresh, logout)
- [ ] KaihleAdmin can create schools and invite users
- [ ] SchoolAdmin can create grades, classes, and enroll students
- [ ] Student enrollment triggers Tier 1 diagnostic Celery task
- [ ] Onboarding gate enforced — student cannot access dashboard until profile + diagnostics complete
- [ ] Learning profile questionnaire submits and stores correctly
- [ ] All M0 tests pass (backend unit + integration, frontend unit + E2E login flow)
- [ ] No hardcoded secrets anywhere in codebase

---

## Key Tables Used in This Milestone

`users`, `student_profiles`, `teacher_profiles`, `auth_tokens`, `schools`, `school_curricula`, `classes`, `class_enrollments`, `assessments`, `assessment_selected_questions`, `student_attempts`, `student_learning_profiles`

Full schema: `kaihle_v2_1_schema.sql`

---

## What M1 Expects From M0

- All 35 tables exist and are migrated
- Auth system functional (JWT issued and validated)
- A student can be enrolled in a class
- Enrollment automatically creates Tier 1 `assessments` rows with `is_system_generated=TRUE`
- `student_profiles.onboarding_diagnostic_status` column exists and defaults to `PENDING`
- `student_learning_profiles` table exists
- Question bank import script can resolve `subtopic_id` (requires curriculum tables to exist from M0-2-T1)
