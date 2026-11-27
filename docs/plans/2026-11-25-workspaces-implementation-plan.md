# Kaihle Workspaces: implementation plan

Status: v5, updated 2026-11-27. D1, D3 and D7 confirmed by Vibhu. S1, S2 and S3a done. Based on a read of the `kaihle` backend and frontend (main, last commit 2026-10-17, unchanged on 2026-11-25). Confidence tags: [Certain] seen in code, [Likely] strong inference, [Guessing] estimate.

A copy of this plan also lives in the Kaihle Claude Project (`claude/kaihle-workspaces-implementation-plan.md`). This repo copy is the one the coding agent should follow; update both when decisions change.

## Progress

| Slice | State |
|---|---|
| S1 data model | Built on branch `M7-1-T1_feature/workspace-school-type`, draft PR https://github.com/vibhu-athavaria/kaihle/pull/313. Migration `a3f5c1d2b7e4` was hand-written; verified 2026-11-26: `alembic check` reports no drift against the models, and downgrade then upgrade round-trips cleanly. |
| S2 authorization | Done on the same branch. Unit tests in `backend/app/tests/unit/test_workspace_service.py` (100% coverage of `workspace_service.py`); integration tests in `backend/app/tests/integration/test_workspace_authorization.py`, including the cross-tenant sweep over classes, assessments, gap maps, lesson plans and student info. `ClassService` now checks the class teacher on create, `update_teacher` and `update_class` (the last one previously accepted any `teacher_id`). Full unit and integration suites pass. |
| S3a signup | Done on branch `M7-1-T2_feature/workspace-signup`: `workspace_service.create_workspace` and `sign_up_workspace`, `POST /auth/signup/workspace` (flag `WORKSPACE_SIGNUP_ENABLED`, default false, 404 when off), welcome email `workspace_welcome.html.jinja2`, `POST /auth/register` restricted to KAIHLE_ADMIN. Signup always returns the same 202 body, including for an email already registered, so it cannot enumerate accounts. Tests: `backend/app/tests/integration/test_workspace_signup.py`, unit tests in `test_workspace_service.py`. |
| S3b handle generator | Not started. |
| S3c rate limit and CAPTCHA | Not started. CAPTCHA provider proposed: Cloudflare Turnstile (privacy-friendly, matters for D2). |
| S4 to S8 | Not started. |

Branch id `M7-1-T1` was invented and may need renaming.

## 1. Goal

Let independent teachers and homeschooling families sign up and use the full Kaihle product without a school contract. Real schools keep working exactly as today.

## 2. Design in one paragraph

Add a `type` to the existing `schools` table: `SCHOOL`, `TEACHER_WORKSPACE`, `FAMILY`. Every independent teacher and every family gets their own school row (a "workspace"), never a shared one. The workspace owner has role TEACHER and is allowed to do the few things that are SCHOOL_ADMIN-only today (create classes, create students) inside their own workspace. All existing `school_id` isolation keeps working unchanged. One invariant makes it sound: a workspace has exactly one operator (its owner) and no other teachers or admins.

## 3. What the code looks like today (findings)

1. Tenancy is `school_id` on every non-curriculum table, and `users.school_id` is mandatory for every role except KAIHLE_ADMIN (CHECK `chk_user_school_id_required`). [Certain]
2. `schools` has no type or owner column. Only KAIHLE_ADMIN can create a school (`POST /schools`), and that also creates its SCHOOL_ADMIN. [Certain] (`services/school_service.py`)
3. There is no self-serve signup. `POST /auth/register` exists but accepts any `role` and `school_id` from the caller and creates the user inactive. No frontend calls it, only tests and docs reference it. [Certain] Do not build on it.
4. SCHOOL_ADMIN-only routes a solo user needs: `POST /schools/{id}/classes`, `PATCH /classes/{id}`, `DELETE /classes/{id}/enrollments` (`routes/classes.py`); `POST /users/create`, `POST /users`, `GET /users`, `PATCH /users/{id}`, `DELETE /users/{id}` (`routes/users.py`); `GET /schools/{id}` and `GET /schools/{id}/curricula` (`routes/schools.py`). [Certain]
5. Everything instructional is TEACHER-only: 14 assessment routes, lesson plans, subtopic content, content review, topics, study-plan teacher view. [Certain] This is why the family owner is a TEACHER too. Adding PARENT to roughly 40 routes is far larger and brittle.
6. `ClassService.create_class` requires the class teacher to be an active TEACHER in the same school and the school to hold a `school_curricula` row for the chosen curriculum. [Certain]
7. The parent backend is all stubs: `/parent/children` returns `[]`, reports return empty, gap map returns an empty object ("STUB, real implementation M5-1-T2"). The parent app has about 11 files. [Certain] The family workspace cannot depend on the parent app.
8. `users.username` is globally unique at the database level, while the service pre-checks only within a school. Students log in by username. Two workspaces creating "emma" collide and return a confusing 409. [Certain]
9. Billing is a model only (`SchoolSubscription`, keyed by `school_id`). No billing service, no trial logic, no enforcement. [Certain]
10. Lesson plan generation reads `school.city` and `school.country` for localisation (`tasks/lesson_plan_tasks.py`). [Certain]
11. No rate limiting exists in the backend. [Likely, based on grep]
12. `GET /students/{id}` lets any TEACHER read any student's basic info in the same school (`routes/students.py` line 128). Harmless in a one-teacher workspace, but an existing exposure in real schools. [Certain for the query, I did not read every later check]
13. LLM usage events carry `school_id`, so per-workspace cost caps are possible. The production eval sampler reads `llm_usage_events` text, which would include children's text from self-serve workspaces. [Certain]
14. Project rules that shape the plan: App Isolation Rule (no cross-role code in `apps/`, shared code in `packages/`), Rule 8 (`kaihle_v2_1_schema.sql` is the schema truth), Rule 9 (autogenerate migrations), Rule 12 (explicit KAIHLE_ADMIN bypass), Rule 20 (TDD with named tests), Rule 21 (Modal from `packages/ui`). [Certain] (`docs/CONSTITUTION.md`)

## 4. Decisions

| ID | Decision | Status |
|---|---|---|
| D1 | Family owner has role TEACHER, with a "family" UI skin driven by workspace type. Parent app stays for real schools. Known cost: a family cannot add a second parent login under the one-operator invariant; if wanted later, revisit with a `display_role` or the real PARENT role after M5. | CONFIRMED by Vibhu 2026-11-25 |
| D2 | Children's data, consent, privacy gaps | DEFERRED by Vibhu to a separate task. Public signup must not go live before it. |
| D3 | Student login handles: keep global uniqueness, auto-generate `firstname-xxxx` for workspace-created students. Real schools keep admin-chosen usernames. Rejected alternative: per-workspace username with a workspace code at login (changes DB constraint and every login path). | CONFIRMED by Vibhu 2026-11-25 |
| D4 | Curricula for a new workspace | Proposed: subscribe to the curriculum chosen at signup, add more in settings. |
| D5 | Free tiers | Vibhu: teachers get one free class, parents get one free month. Claude recommends two additions, not yet confirmed: (a) teacher student cap of about 10 on the free class, because a 30-student free class costs more in LLM usage than a paying one; (b) parent month starts when the first child is added, and after expiry the workspace goes read-only, data kept. Limits live in an entitlements model, designed in the billing task. |
| D6 | Teacher later joins a real school with existing students | Open. Cheapest path: workspace converts into a school (Phase 5). |
| D7 | `POST /auth/register`: restrict to KAIHLE_ADMIN, add the new workspace signup endpoint separately. | CONFIRMED by Vibhu 2026-11-25 (implemented in S3) |
| D8 | Billing | DEFERRED by Vibhu to the next task. |

Gate: public signup ships behind a feature flag (`WORKSPACE_SIGNUP_ENABLED`, default false) until D2 and D8 are done. This lets Phases 1 to 3 merge safely.

## 5. Implementation approach

Work on a feature branch per slice, each slice small enough to review alone, all behind the flag where user-visible. TDD per Rule 20: write the named tests first, then the code. Run the existing backend suite and frontend tests before every slice is considered done.

| Slice | Content | Depends on |
|---|---|---|
| S1 | Migration, `School` model fields, `SchoolType`, schema SQL update | none |
| S2 | `require_school_operator`, apply to the routes in finding 4, owner restrictions (STUDENT only), `MeResponse` fields, invariant checks | S1 |
| S3 | `workspace_service` and `POST /auth/signup/workspace` (flagged), rate limit, handle generator, `/auth/register` restriction | S1, S2 |
| S4 | Extract create-class and create-student modals and hooks to shared packages, no behaviour change, ADR-004 | none (can run in parallel with S1 to S3) |
| S5 | Teacher app: `/signup`, workspace-aware classes and students UI, family skin | S2, S3, S4 |
| S6 | Website CTAs, student app login copy | S5 |
| S7 | Kaihle Admin filters, analytics split, eval sampler exclusion | S1 |
| S8 | Entitlements and LLM caps | billing task |

## 6. Phases (task detail)

### Phase 1: data model and authorization (S1, S2) - DONE

1. Migration (autogenerate, Rule 9): `schools.type` VARCHAR(20) NOT NULL DEFAULT `SCHOOL` with CHECK in the three values; `schools.owner_user_id` UUID NULL FK to `users` ON DELETE SET NULL; unique partial index on `owner_user_id` where not null. Existing rows become `SCHOOL`. Update `kaihle_v2_1_schema.sql` (Rule 8). A DB CHECK requiring an owner for workspaces would fail at insert (school and user are created in one transaction), so enforce it in the service.
2. `School` model: add `type`, `owner_user_id`, and `SchoolType` constants.
3. Invariant: a non-`SCHOOL` workspace cannot get a second TEACHER or any SCHOOL_ADMIN. Enforce in `UserService.invite_user`, `create_user_direct`, `AuthService.register`, and in `ClassService` wherever a class teacher is set (`create_class`, `update_teacher`, `update_class`). Done.
4. `core/deps.py`: add `require_school_operator` (SCHOOL_ADMIN, KAIHLE_ADMIN, or the owner of a workspace-type school). Apply to the routes in finding 4. Keep `_check_school_access` after it (Rule 12). In a workspace the owner may create only STUDENT users.
5. `GET /users/me`: add `workspace_type` (null for real schools) and `is_workspace_owner`.
6. Optional hardening: restrict `GET /students/{id}` for teachers to students in their own classes (finding 12). Not done.

Tests (Rule 7 naming)
- `test_invite_user_when_school_is_workspace_and_role_teacher_then_raises`
- `test_create_user_direct_when_workspace_owner_and_role_student_then_creates_in_own_school`
- `test_create_user_direct_when_workspace_owner_and_role_parent_then_403`
- `test_create_class_when_workspace_owner_then_201_and_owner_is_teacher`
- `test_create_class_when_owner_targets_another_workspace_then_403`
- `test_list_users_when_workspace_owner_then_only_own_workspace_users`
- `test_require_school_operator_when_plain_teacher_in_real_school_then_403`
- `test_get_me_when_workspace_owner_then_returns_workspace_type`
- Cross-tenant isolation test: two workspaces, assert owner A gets 403 or 404 on every route touching B's class, student, assessment, gap map, lesson plan. (Done: `test_cross_tenant_when_owner_a_targets_workspace_b_resource_then_403_or_404`, 18 routes.)

### Phase 2: signup and onboarding (S3)

1. `workspace_service.create_workspace(kind, owner_data, country, timezone, city, curriculum_id)`: creates school (slug `ws-<8 hex>`, status active), owner user (role TEACHER, `TeacherProfile`), sets `owner_user_id`, adds the chosen `SchoolCurriculum`, one transaction.
2. `POST /auth/signup/workspace` (public, behind the flag). Body: kind (`teacher` or `family`), name, email, country, timezone, optional city, curriculum. Sends the existing magic link so email ownership is proven and Rule 10 (password setup) applies.
3. Abuse protection: per-IP and per-email rate limit in Redis, plus a server-verified CAPTCHA. Neither exists today.
4. Student handle generator for workspace-created students: `slug(first_name)[:12]` plus 4 characters from an unambiguous alphabet (no 0, o, 1, l), retry on `IntegrityError`, shown once with the password. Collision messages stay generic.
5. Restrict `POST /auth/register` to KAIHLE_ADMIN and update its tests.
6. Email templates: welcome for teacher and family.

Tests: signup happy path, duplicate email, rate limit returns 429, invalid kind, magic link scope is `password_setup`, flag off returns 404, handle collision retries, handle never reused across workspaces.

### Phase 3: frontend (S4, S5, S6)

1. ADR-004: the workspace owner is a TEACHER and uses school-operation components imported from `packages/`. Needed because the App Isolation Rule forbids school-admin pages inside `apps/teacher`.
2. Extract `CreateClassModal` (580 lines) and `CreateStudentModal` (333 lines) from `apps/school-admin/src/pages` into shared packages (UI in `packages/ui`, data hooks in `packages/api-client`). Their hooks currently live in `apps/school-admin/src/hooks/useSchoolAdmin`. School-admin imports them from the package, behaviour unchanged. Use `Modal` from `packages/ui` (Rule 21).
3. Teacher app: public `/signup` route (kind switch) and workspace-aware UI. `ClassesPage` empty state currently says "Classes will appear here once your school admin creates them". For owners show "Create class" and "Add student". Family skin: "children" instead of "students", simplified create-class flow.
4. Website (`kaihle-www`): teachers audience CTA goes to teacher signup, parents audience to family signup, schools audience stays on the demo form. The consent banner for tracking scripts (documented as not built) is a prerequisite for EU and UK traffic.
5. Student app login copy: replace "use your school's teacher portal" so a homeschool child is not sent to a non-existent school portal.
6. Tests: component tests for the extracted modals, Playwright e2e of signup, create class, add student for each kind.

### Phase 4: platform operations (S7, S8)

1. Kaihle Admin: `type` filter and tabs on the schools list (`list_schools` has no filter).
2. `analytics_service` counts all active schools. Count `SCHOOL` separately from workspaces.
3. Per-workspace LLM cost cap using `llm_usage_events.school_id`. Free signup plus LLM generation is a cost exposure with no guard today. [Likely]
4. Exclude workspace schools from the production eval sampler by default (`services/eval_prod/sampler.py`).
5. Entitlements (max classes, max students, trial end) and enforcement: designed in the billing task.

### Phase 5: upgrade path (after launch)

- Workspace to school: flip `type` to `SCHOOL`, invite a SCHOOL_ADMIN, owner stays a teacher. `school_id` does not change, so no data moves.
- Teacher joins an existing school with their students: needs a data transfer. Decide whether it is needed (D6).

## 7. Risks

1. Compliance (D2): highest risk, deferred, blocks public launch.
2. LLM cost abuse from free signups.
3. Role overloading: the owner is a TEACHER with admin-like powers by workspace type. Every new SCHOOL_ADMIN-only route must decide whether owners may use it. Mitigation: use `require_school_operator` by default for school-operation routes.
4. Many tiny schools in one table: filters and indexes on `type`.
5. Family model fit: a class is one teacher, one subject, one grade. A family with two children and three subjects creates several classes. Acceptable for MVP, a later "learning track" helper can hide it.
6. Single-operator limit: a family cannot give a second parent their own login (consequence of D1).

## 8. Rough sizing [Guessing]

S1 and S2: 3 to 4 days. S3: 3 days. S4 and S5: 5 to 7 days (modal extraction is the bulk). S6 and S7: 3 days. Billing and compliance are separate tasks.

## 9. Not covered

I did not audit all 28 route modules line by line, the Celery tasks beyond lesson plans, or the student app screens. The Phase 1 isolation test is the safety net for what I missed.
