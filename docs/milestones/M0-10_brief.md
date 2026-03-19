# M0-10 Brief — API Contract Finalization
**Milestone:** M0 — Foundations
**Epic:** M0-10 (new — supersedes M0-9-T7)
**Constitution version:** 2.0
**Must complete before:** M1 begins

> Load this brief alongside CONSTITUTION.md when working on any M0-10 task.
> Load the specific task file for the task you are implementing.

---

## Goal

Every API endpoint for the entire Kaihle platform — across all six milestones — has a
locked, correct, RESTful contract defined and stubbed before M1 implementation begins.
Existing routes that use wrong URL prefixes, verb-based paths, or incorrect file placement
are renamed and moved in a single hard cutover. The result is a codebase where frontend
developers and implementing engineers can work against a stable, complete API surface
with no path or schema changes for the lifetime of the product.

---

## Why This Epic Exists

During the M0 technical audit, three structural problems were found in the existing
backend routes. First, the `schools.py` router uses the prefix `/admin/schools`, which
leaks a role name into the URL — a REST anti-pattern. Authorization is the job of
middleware, not URL paths. Second, the enrollment endpoint uses the verb `/enroll`
instead of the noun `/enrollments`, which is inconsistent with REST conventions and
creates a precedent for verb-based URLs that becomes harder to maintain as features
grow. Third, class management routes live inside `schools.py` alongside school CRUD,
mixing two distinct domain concerns in one file.

Beyond these fixes, the audit revealed that stub endpoints created in M0-9-T7 used
the old wrong prefixes throughout, making that task a source of confusion rather than
clarity. M0-9-T7 is retired and replaced by this epic.

---

## Guiding Principles (read before writing any code)

**Resources, not roles, in URLs.** The URL identifies what you are operating on.
Authorization is handled by `require_role()` dependencies. So `/admin/schools` is
wrong — `/schools` with a `require_role(KAIHLE_ADMIN)` dependency is right.

**Nouns for resources, HTTP verbs for actions.** `POST /classes/{id}/enrollments`
creates an enrollment. Never `POST /classes/{id}/enroll` — that puts a verb in the
URL, which forces you to invent new verbs as features grow.

**Frozen contracts.** Once an endpoint contract is published in this epic, the path,
method, request body shape, and response body shape are permanently frozen. Later
milestones replace only the stub body logic. Any breaking change requires a version
increment and an ADR. This rule is added to CONSTITUTION.md in M0-10-T1.

**Hard cutover.** When existing routes are renamed in M0-10-T7, both the old and new
paths are never live simultaneously. The old route is removed in the exact same commit
that creates the new one. All references — route files, tests, frontend hooks — are
updated in the same task.

**Stubs return correct shape, never 501 for reads.** Read endpoints return 200 with
empty arrays or zero values. Write endpoints that queue significant async work return
501. Simple sync writes return a plausible stub response. The frontend must never
encounter an unexpected error shape from a stub.

---

## Task Execution Order

The tasks are organized into four sequential groups. Within each group, tasks marked
as parallel can be worked by separate agents simultaneously.

```
Group A — Foundation (must complete first, everything depends on it)
  M0-10-T1: API contract foundation
    (shared schemas, CONSTITUTION frozen contract rule,
     CORS fix, pagination envelope, error shape)

Group B — New stub endpoints (all parallel, all depend on T1)
  M0-10-T2: Gap map + class summary stubs
  M0-10-T3: Assessments + attempts stubs
  M0-10-T4: Study plans stubs
  M0-10-T5: Lesson plans stubs
  M0-10-T6: Parent portal + analytics stubs

Group C — Hard cutover of existing routes (sequential, depend on all of Group B)
  M0-10-T7: Backend rename + restructure
    (schools prefix fix, classes.py split,
     enrollments rename, KaihleAdmin bypass fix,
     all backend tests updated)

Group D — Frontend updates (all parallel, depend on T7)
  M0-10-T8:  apps/student API client update
  M0-10-T9:  apps/teacher API client update
  M0-10-T10: apps/school-admin API client update
  M0-10-T11: apps/kaihle-admin API client update
  M0-10-T12: apps/parent API client update
```

---

## Task List

| Task ID | File | Description |
|---|---|---|
| M0-10-T1 | `M0-10/M0-10-T1_api_contract_foundation.md` | Shared schemas, CONSTITUTION update, CORS, envelope |
| M0-10-T2 | `M0-10/M0-10-T2_gap_map_stubs.md` | Gap map + class summary stub routes |
| M0-10-T3 | `M0-10/M0-10-T3_assessment_attempt_stubs.md` | Assessment + attempt stub routes |
| M0-10-T4 | `M0-10/M0-10-T4_study_plan_stubs.md` | Study plan stub routes |
| M0-10-T5 | `M0-10/M0-10-T5_lesson_plan_stubs.md` | Lesson plan stub routes |
| M0-10-T6 | `M0-10/M0-10-T6_parent_analytics_stubs.md` | Parent portal + analytics stub routes |
| M0-10-T7 | `M0-10/M0-10-T7_backend_hard_cutover.md` | Rename + restructure all existing routes |
| M0-10-T8 | `M0-10/M0-10-T8_student_app_update.md` | Update apps/student to new API paths |
| M0-10-T9 | `M0-10/M0-10-T9_teacher_app_update.md` | Update apps/teacher to new API paths |
| M0-10-T10 | `M0-10/M0-10-T10_school_admin_app_update.md` | Update apps/school-admin to new API paths |
| M0-10-T11 | `M0-10/M0-10-T11_kaihle_admin_app_update.md` | Update apps/kaihle-admin to new API paths |
| M0-10-T12 | `M0-10/M0-10-T12_parent_app_update.md` | Update apps/parent to new API paths |

---

## Definition of Done

- [ ] `GET /docs` (Swagger UI) shows the complete platform API with correct paths,
      correct tags, and correct role annotations — no `/admin/` prefix anywhere
- [ ] Zero routes use verb-based paths (`/enroll`, `/submit` as path segments)
- [ ] `grep -r "/admin/schools" backend/` returns zero results
- [ ] `grep -r "/enroll" backend/app/api/` returns zero results
- [ ] All existing integration tests pass against new paths
- [ ] All five frontend apps make zero API calls to old paths
- [ ] All new stub read endpoints return 200 with empty/zero data
- [ ] CONSTITUTION.md contains the frozen contract rule
- [ ] `mypy app/` passes with zero errors
- [ ] CI passes: ruff, mypy, pytest, Playwright E2E

---

## Retired Task

**M0-9-T7** (`M0-9-T7_role_dashboard_api_contracts.md`) is retired and superseded by
this epic. It is kept in the docs directory for reference but must not be executed.
Its stubs used the old `/admin/schools` prefix and mixed new endpoint creation with
rename work in a single task, which is the wrong sequencing.

---

## What M1 Gets From This Epic

When M1 begins, every API endpoint it needs to implement already has a route file,
a schema, a stub response, and an integration test skeleton. M1's job is to replace
stub function bodies with real service calls. No paths change. No schemas change.
No frontend updates are needed when M1 ships. This is the value of contract-first design.
