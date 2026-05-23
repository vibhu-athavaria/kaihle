# Kaihle — Project Constitution
**Version:** 2.1 · March 2026 · Supersedes v2.0
**Status:** AUTHORITATIVE — loaded in every session, no exceptions

> What Kaihle IS, what rules are LOCKED, and where to find everything else.
> Design details live in `docs/design/DESIGN_SYSTEM.md` — do not duplicate them here.

---

## 1. What Is Kaihle?

AI-powered learning diagnostics platform for international schools (Cambridge, IB). Identifies knowledge gaps, generates personalised study plans, gives teachers, school admins, and parents real-time visibility into student progress.

**Target users:** Students (age 11–18), Teachers, School Admins, Parents, Kaihle Admin (internal).
**Pilot target:** Micro-schools in Southeast Asia. Max 10 schools, ~400 students in v1.

> Curriculum scope table and subject binding rules: `brv query "Kaihle curriculum scope and subject binding rules"`

---

## 2. Locked Tech Stack

**Backend:** Python 3.12, FastAPI (async), SQLAlchemy 2.x + Alembic, Pydantic v2, JWT + magic links, Celery + Redis, pytest + pytest-asyncio.
**Frontend:** React + Vite + TypeScript (strict), Tailwind CSS v3, Zustand + React Query v5, React Hook Form + Zod, React Router v6.
**Infrastructure:** PostgreSQL 16 + pgvector, Redis 7, AWS S3, Docker Compose, Render.com.

> Full tech stack detail: `brv query "Kaihle locked tech stack"`

---

## 3. Repository Structure

```
/kaihle
  /backend
    /app
      /api/v1/routes/       ← thin route handlers only, delegate to services
      /core/                ← config.py, security.py, database.py, redis.py
      /models/              ← SQLAlchemy ORM models (one file per domain)
      /schemas/             ← Pydantic request/response schemas
      /services/            ← ALL business logic lives here
      /ai/
        /providers/         ← router.py only (LiteLLM handles all provider adaption)
        /prompts/           ← .jinja2 prompt templates
        content_curator.py
        quiz_generator.py
      /tasks/               ← Celery task definitions
      /tests/unit/
      /tests/integration/
      /tests/e2e/
    /scripts/               ← seed_curriculum_graph.py, import_questions.py
    /data/curriculum/       ← cambridge_v1.json
  /frontend
    /apps/student/          ← port 3002  (STUDENT only)
    /apps/teacher/          ← port 3001  (TEACHER only)
    /apps/parent/           ← port 3003  (PARENT only)
    /apps/school-admin/     ← port 3004  (SCHOOL_ADMIN only)
    /apps/kaihle-admin/     ← port 3005  (KAIHLE_ADMIN only)
    /packages/ui/           ← shared Tailwind components (all roles)
    /packages/api-client/   ← shared Axios instance + typed hooks
    /packages/auth/         ← tokenStore, useAuth, route guards
    /packages/types/        ← shared TypeScript interfaces + getMasteryStyle()
  /docs/
    CONSTITUTION.md
    /design/
      DESIGN_SYSTEM.md      ← colors, fonts, layouts, role specs, accessibility
    /adr/
```

### App Isolation Rule (CRITICAL — never violate)

Each of the five frontend apps serves **exactly one role**. Zero cross-role code inside any `apps/` directory. Shared code belongs exclusively in `packages/`.

- School Admin pages **MUST NOT** live in `apps/teacher/` — they live in `apps/school-admin/`.
- Kaihle Admin pages **MUST NOT** live in `apps/teacher/` — they live in `apps/kaihle-admin/`.

---

## 4. Absolute Rules — Never Violate

**Rule 1 — Service layer owns all business logic.** Routes are thin: validate input, call a service, return response. Zero business logic in route handlers.

**Rule 2 — Every non-curriculum table has `school_id`.** Curriculum tables (`curricula`, `subjects`, `grades`, `topics`, `curriculum_topics`, `subtopics`) are school-agnostic by design.

**Rule 3 — All queries filter by `school_id`** unless the caller is `KAIHLE_ADMIN`. The bypass must be explicit (see Rule 12).

**Rule 4 — All LLM calls go through `router.py` (LiteLLM).** No feature code imports provider SDKs directly.

**Rule 5 — No hardcoded secrets.** All config from environment variables via `app/core/config.py`.

**Rule 6 — Test coverage ≥ 90%** on all `/services/` files. CI enforced.

**Rule 7 — Test naming:** `test_<what>_when_<condition>_then_<expected>`

**Rule 8 — `kaihle_v2_1_schema.sql` is the single source of truth for the database schema.** Task file conflicts with SQL → SQL wins.

**Rule 9 — Do not write migration SQL by hand.** Use `alembic revision --autogenerate -m "description"`.

**Rule 10 — Password setup is required for all magic-link-invited users.** School Admins, Teachers, Students — all must complete password setup on first login. Magic-link JWT carries `scope: "password_setup"` and is rejected by all other endpoints. `PasswordSetupRoute` guard in `packages/auth` enforces this. `PasswordSetupForm` lives in `packages/ui` — no app defines its own version.

**Rule 11 — Student onboarding has one gate; study plans require diagnostic completion.**
- Gate 1 (learning profile): Dashboard inaccessible until `student_profiles.is_learning_profile_complete = TRUE`. Enforced by `OnboardingRoute` in `packages/auth`.
- Class content: Immediately accessible after enrollment — no diagnostic gate.
- Study plans: Only generated after student completes the diagnostic for that class. This is enforced at the service layer.

**Rule 12 — KaihleAdmin `school_id` bypass must always be explicit.**
```python
if current_user.role == UserRole.KAIHLE_ADMIN:
    return  # explicit bypass
if current_user.school_id != school_id:
    raise HTTPException(status_code=403, detail="Access denied")
```

**Rule 13 — No `# type: ignore` in production code.** Resolve via `mypy.ini`.

**Rule 14 — No additional UI kits** (MUI, Chakra, shadcn, DaisyUI, Bootstrap) without a documented ADR.

**Rule 15 — All new layout components live in `packages/ui/src/layouts/`.** Route files compose from wrappers — they never define layout structure.

**Rule 16 — All frontend tasks must load `docs/design/DESIGN_SYSTEM.md` before writing any component.** Five roles. Five distinct design specs.

**Rule 17 — Celery tasks must guard against an empty question bank.** Log `WARNING` and exit if no questions exist for the target subject/grade — never create an empty assessment.

**Rule 18 — Celery tasks must emit a `CRITICAL` log on final retry exhaustion.** Include `class_id`, `student_id` (if applicable), task name, `exc_info=True`.

**Rule 20 — Test-Driven Development is non-negotiable.** Every task file creating or modifying backend service/route logic MUST include: (1) named unit test functions with mock setup and assertions, (2) named integration test functions, (3) test file paths. Acceptance criteria checkboxes alone are not sufficient.

**Rule 21 — All modals must trap focus.** Use the `Modal` component from `packages/ui` (Radix UI Dialog wrapper). Tab cycles within modal, Escape closes, focus returns to trigger. Custom div-based modals without focus trapping are WCAG 2.1 Level AA violations. See `docs/design/DESIGN_SYSTEM.md` §9 for the canonical pattern.

**Rule 22 — Loading states must follow the loading state standard.** Page initial loads use skeletons. Button actions use button spinners. Background generation uses pulsing badges. No spinner on full-page initial data load. Every list component must have an explicit empty state. See `docs/design/DESIGN_SYSTEM.md` §10.

**Rule 23 — Curriculum compliance boundary.** Kaihle is a delivery aid. Schools are solely responsible for compliance with their curriculum framework. Generated content is "curriculum-informed" — never "Cambridge-compliant," "IB-aligned," or "examination-ready." No task file may introduce logic validating actions against examination board policy, mark scheme language, or assessment weighting rules.

---

## 5. Authentication and Onboarding Flows

> Full step-by-step flows (magic link, password setup, student onboarding, email/password login):
> `brv query "Kaihle feature: auth (magic links, password setup, login, JWT scopes)"`

**Summary:** Magic link → password setup (scoped JWT) → role-specific redirect. Student additionally completes learning profile questionnaire before dashboard access. Parents skip password setup in v1.

---

## 6. Role → App → Route Mapping

| Role | App | Port | First login | Returning |
|---|---|---|---|---|
| STUDENT | `apps/student` | 3002 | `/student/setup-password` | `/student/dashboard` (or profile if incomplete) |
| TEACHER | `apps/teacher` | 3001 | `/teacher/setup-password` | `/teacher/dashboard` |
| SCHOOL_ADMIN | `apps/school-admin` | 3004 | `/school-admin/setup-password` | `/school-admin/dashboard` |
| PARENT | `apps/parent` | 3003 | `/parent/dashboard` | `/parent/dashboard` |
| KAIHLE_ADMIN | `apps/kaihle-admin` | 3005 | `/kaihle-admin/dashboard` | `/kaihle-admin/dashboard` |

---

## 7. Multi-Tenancy Rules

Single database. `school_id` on every non-curriculum table. Enforced at the service layer (not PostgreSQL RLS). `KAIHLE_ADMIN` bypasses `school_id` filters with explicit bypass (Rule 12). All other roles must filter by `school_id`. Cross-school access returns **403**, not 404.

---

## 8. LLM Provider Routing

All LLM calls go through `backend/app/ai/providers/router.py` via LiteLLM. All models are fully env-var driven — no model names in code. pgvector embeddings not used in v1. MCQ scoring is deterministic string comparison (not LLM).

> Task→env-var routing table and self-hosting instructions: `brv query "Kaihle LLM provider routing"`

---

## 12. Mastery Thresholds

Use `getMasteryStyle(score)` from `packages/types/src/mastery.ts` — never inline mastery color logic.

| Score | Label | Token |
|---|---|---|
| > 0.7 | Strong | `brand-green` |
| 0.4–0.7 | Developing | `brand-amber` |
| < 0.4 | Needs Work | `brand-red` |
| null | Not assessed | `brand-muted` |

Boundary: `score = 0.7` → Developing. `score = 0.71` → Strong.

---

## 13. Where To Find Things

| What | Where |
|---|---|
| Full DB schema (columns, indexes, constraints) | `kaihle_v2_1_schema.sql` |
| LLM prompt templates | `backend/app/ai/prompts/*.jinja2` |
| Design tokens, component patterns, role specs, accessibility | `docs/design/DESIGN_SYSTEM.md` |
| Screen specs per role (page inventory, component specs, data map) | `docs/design/screens/TEACHER_SCREENS.md` etc. |
| Architecture decisions | `docs/adr/ADR-*.md` |
| Environment variables | `brv query "Kaihle environment variables"` |
| Auth/onboarding flows | `brv query "Kaihle feature: auth"` |
| Diagnostic assessment detail | `brv query "Kaihle feature: student onboarding"` |
| Student learning profile schema | `brv query "Kaihle student learning profile"` |
| Curriculum scope and subject bindings | `brv query "Kaihle curriculum scope"` |
