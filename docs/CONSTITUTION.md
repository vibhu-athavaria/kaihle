# Kaihle — Project Constitution
**Version:** 2.0 · Based on Product Plan v2.2
**Status:** AUTHORITATIVE — loaded in every KiloCode session, no exceptions
**Last updated:** March 2026
**Supersedes:** v1.0 (March 2026)

> This document is the permanent anchor for every coding session.
> It tells you WHAT the project is, WHAT rules are locked, and WHERE to find everything else.
> Do not duplicate content from task files here.

---

## 1. What Is Kaihle?

Kaihle is an AI-powered learning diagnostics platform for schools. It identifies knowledge gaps in students, generates personalised study plans, and gives teachers, school admins, and parents real-time visibility into student progress.

**Target users:** Students (age 11–18), Teachers, School Admins, Parents, Kaihle Admin (internal team).
**Curriculum scope (v1):** Cambridge Lower Secondary (Grades 6–8) + Cambridge IGCSE (Grades 9–10).

| Programme | Grades | Subjects |
|---|---|---|
| Cambridge Lower Secondary | 6, 7, 8 | Mathematics (MATH), Integrated Science (SCI), English Language (ENG) |
| Cambridge IGCSE | 9, 10 | Mathematics (MATH), Biology (BIO), Chemistry (CHEM), Physics (PHY), English Language (ENG), English Literature (ENGL — non-core) |

**Subject binding rules (absolute — enforced by `curriculum_subjects` table and seed script):**
- SCI belongs to `cambridge_lower` ONLY. It does not exist under `igcse`.
- BIO, CHEM, PHY, ENGL belong to `igcse` ONLY. They do not exist under `cambridge_lower`.
- MATH and ENG span both curricula.

**Cambridge AS & A Level (Grades 11–12)** is deferred. Will be added as `cambridge_as_a` when scoped.

**Pilot target:** micro-schools in Southeast Asia. Max 10 schools, ~400 students in v1.

---

## 2. Locked Tech Stack — Do Not Deviate

### Backend
| Concern | Choice |
|---|---|
| Language | Python 3.12 |
| Framework | FastAPI (async) |
| ORM | SQLAlchemy 2.x async + Alembic |
| Validation | Pydantic v2 |
| Auth | JWT (15min access + 7day refresh) + magic links via Resend |
| Task queue | Celery + Redis broker |
| Testing | pytest + pytest-asyncio + httpx |
| Logging | structlog, JSON to stdout |

### Frontend
| Concern | Choice |
|---|---|
| Framework | React + Vite + TypeScript (strict mode) |
| CSS | Tailwind CSS v3 — no custom CSS files |
| UI library | TailAdmin Free as the base admin/dashboard template |
| State | Zustand (global) + React Query v5 (server) |
| Forms | React Hook Form + Zod |
| Router | React Router v6 |
| Testing unit | Jest + React Testing Library |
| Testing E2E | Playwright |

### Infrastructure
| Concern | Choice |
|---|---|
| Database | PostgreSQL 16 + pgvector extension |
| Vector store | pgvector (inside PostgreSQL — no Pinecone) |
| Cache | Redis 7 |
| File storage | AWS S3 |
| Dev | Docker Compose |
| Production | Render.com |

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
        /rag/               ← embedder.py, retriever.py, curriculum.py
        /prompts/           ← .jinja2 prompt templates
        content_curator.py
        quiz_generator.py
      /tasks/               ← Celery task definitions
      /tests/unit/
      /tests/integration/
      /tests/e2e/
    /scripts/               ← seed_curriculum_graph.py, import_questions.py, ingest_curriculum.py
    /data/curriculum/       ← cambridge_v1.json (curriculum seed data)
  /frontend
    /apps/student/          ← Vite entrypoint, port 3002  (STUDENT role only)
    /apps/teacher/          ← Vite entrypoint, port 3001  (TEACHER role only)
    /apps/parent/           ← Vite entrypoint, port 3003  (PARENT role only)
    /apps/school-admin/     ← Vite entrypoint, port 3004  (SCHOOL_ADMIN role only)
    /apps/kaihle-admin/     ← Vite entrypoint, port 3005  (KAIHLE_ADMIN role only)
    /packages/ui/           ← shared Tailwind components (all roles)
    /packages/api-client/   ← shared Axios instance + typed hooks
    /packages/auth/         ← tokenStore, useAuth, PrivateRoute, RoleRoute,
                               OnboardingRoute, PasswordSetupRoute
    /packages/types/        ← shared TypeScript interfaces
  /docs/
    CONSTITUTION.md         ← this file
    /milestones/            ← M0_brief.md ... M6_brief.md
    /tasks/                 ← M0/M0-1-T1_*.md ... M6/M6-3-T5_*.md
    /design/
      DESIGN_SYSTEM.md      ← colors, fonts, layout patterns, role-specific specs
    /adr/
      ADR-001_five_app_frontend.md
```

### App Isolation Rule (CRITICAL — never violate)

Each of the five frontend apps serves **exactly one role**. There is zero cross-role code inside any `apps/` directory. Shared code belongs exclusively in `packages/`. Specifically:

- School Admin pages **MUST NOT** live in `apps/teacher/`. They live in `apps/school-admin/`.
- Kaihle Admin pages **MUST NOT** live in `apps/teacher/`. They live in `apps/kaihle-admin/`.
- Any agent that places role-specific pages in the wrong app is violating this rule and must stop.

This rule corrects the v1.0 mistake of co-locating all admin roles inside the teacher app. See `docs/adr/ADR-001_five_app_frontend.md` for the full decision record. The migration of existing pages is tracked in M0-9-T2 and M0-9-T3.

---

## 4. Absolute Rules — Never Violate

**Rule 1 — Service layer owns all business logic.** Routes are thin: validate input, call a service, return response. Zero business logic in route handlers.

**Rule 2 — Every non-curriculum table has `school_id`.** Curriculum tables (`curricula`, `subjects`, `grades`, `topics`, `curriculum_topics`, `subtopics`, etc.) are school-agnostic by design.

**Rule 3 — All queries filter by `school_id`** unless the caller is `KAIHLE_ADMIN`. The bypass must be explicit (see Rule 12).

**Rule 4 — All LLM calls go through `LLMProvider` abstraction.** No feature code imports provider SDKs directly.

**Rule 5 — No hardcoded secrets.** All config comes from environment variables via `app/core/config.py`.

**Rule 6 — Test coverage ≥ 90%** on all `/services/` files. Enforced by CI. Pre-commit enforces ≥ 80% on unit tests locally.

**Rule 7 — Test naming:** `test_<what>_when_<condition>_then_<expected>`

**Rule 8 — `kaihle_v2_1_schema.sql` is the single source of truth for the database schema.** If a task file and the SQL file conflict, the SQL file wins.

**Rule 9 — Do not write migration SQL by hand.** Use `alembic revision --autogenerate -m "description"` and review the output.

**Rule 10 — Password setup is required for all magic-link-invited users before any other action.** This applies to School Admins, Teachers, and Students — all three are invited via magic link and all three must complete password setup on first login before proceeding to their next step. The magic-link-issued JWT carries `scope: "password_setup"` and is rejected by all non-password-setup endpoints. The `PasswordSetupRoute` guard in `packages/auth` enforces this client-side. The `PasswordSetupForm` component lives in `packages/ui` and is shared across all apps — no app may define its own version.

**Rule 11 — Student onboarding has two distinct, independent gates.**
- Gate 1 (global): Dashboard is inaccessible until `student_profiles.is_learning_profile_complete = TRUE`. Enforced by `OnboardingRoute` in `packages/auth`.
- Gate 2 (per-class): Class content (topics, lesson plans, resources, quizzes) is locked until `class_enrollments.onboarding_diagnostic_status = 'COMPLETED'` for that specific enrollment. Enforced by `require_diagnostic_complete(class_id)` API dependency and locked class card UI.
These gates are independent. Completing one class diagnostic does not unlock another class.

**Rule 12 — KaihleAdmin `school_id` bypass must always be explicit.** Every `_check_school_access` helper in every route file must follow exactly this pattern:
```python
if current_user.role == UserRole.KAIHLE_ADMIN:
    return  # KaihleAdmin can access any school — explicit bypass
if current_user.school_id != school_id:
    raise HTTPException(status_code=403, detail="Access denied")
```
Any helper missing the KaihleAdmin bypass is a bug.

**Rule 13 — No `# type: ignore` inline comments in production code.** Resolve via `mypy.ini`. Applies to all files including Celery tasks.

**Rule 14 — No additional UI kits** (MUI, Chakra, shadcn, Flowbite, DaisyUI, Bootstrap) without a documented ADR. TailAdmin Free is the canonical dashboard shell.

**Rule 15 — All new layout components live in `packages/ui/src/layouts/`.** Route files compose from wrappers — they never define layout structure.

**Rule 16 — All frontend tasks must load `docs/design/DESIGN_SYSTEM.md` before writing any component.** Five roles. Five distinct design specs. Apply the correct spec for the role being implemented.

**Rule 17 — Celery tasks must guard against an empty question bank.** `create_class_diagnostic_task` must verify that at least one question exists for the target subject/grade before creating an assessment. If no questions are found, log at `WARNING` level and exit without creating an empty assessment.

**Rule 18 — Celery tasks must emit a CRITICAL log on final retry exhaustion.** When all retries are consumed, emit a structured `structlog` event at level `CRITICAL` including `class_id`, `student_id` (if applicable), task name, and `exc_info=True`. This is the operational dead-letter signal.

**Rule 19 — API contracts are frozen once published.** Once an endpoint's path, HTTP method, request body schema, and response body schema are defined in any M0-10-T* task file, they are permanently frozen. Future milestones replace only the stub function body with real business logic. They never change the path, method, or schema shape. Any breaking change requires a new API version prefix (`/api/v2/`) and an ADR entry in `docs/adr/`. This rule exists to guarantee that frontend code written against a stub never needs to change when the real implementation ships.

**Rule 20 — Test-Driven Development is non-negotiable.** Every task file that
creates or modifies backend service or route logic MUST include:
1. Named unit test functions (e.g. `test_submit_when_duplicate_then_raises_409`)
   with explicit mock setup, inputs, and assertions spelled out
2. Named integration test functions that hit real DB or real HTTP endpoints
3. The test file path(s) listed under "Files to Create / Modify"

Acceptance criteria checkboxes alone are NOT sufficient. A coding agent must be
able to implement the tests without making design decisions. If a task file does
not name its tests, it is incomplete and must not be handed to a coding agent.

**Rule 21 — All modals must trap focus.** Any component that opens as a modal overlay
MUST use the `Modal` component from `packages/ui` (Radix UI Dialog wrapper). This
guarantees: Tab cycles within modal, Escape closes, focus returns to trigger.
Custom div-based modals without focus trapping are WCAG 2.1 Level AA violations.
See `docs/design/DESIGN_SYSTEM_ACCESSIBILITY_ADDENDUM.md` §9 for the canonical pattern.

**Rule 22 — Loading states must follow the loading state standard.** Page initial
loads use skeletons. Button actions use button spinners. Background generation uses
pulsing badges. No spinner on full-page initial data load. Every list component must
have an explicit empty state. See `docs/design/DESIGN_SYSTEM_ACCESSIBILITY_ADDENDUM.md`
§10 for the full standard.
---

## 5. Authentication and Onboarding Flows (CRITICAL)

These flows are the authoritative reference. Any code that deviates is a bug.

### 5.1 Magic Link → Password Setup → Role-Specific Next Step

All invited role types (School Admin, Teacher, Student) follow this sequence without exception:

```
Step 1 — Invitation
  Kaihle Admin creates school → invites School Admin via magic link email
  School Admin invites Teacher → magic link email
  School Admin invites Student → magic link email

Step 2 — Magic Link Click
  User clicks link → GET /api/v1/auth/magic-link/verify?token=...
  Backend: validates token (single-use, 10-minute TTL), marks used=TRUE
  Backend: issues SCOPED JWT { scope: "password_setup", sub: user_id, role: ..., exp: 1hr }
  Frontend: PasswordSetupRoute detects scope → routes to /[app-prefix]/setup-password

Step 3 — Password Setup (PasswordSetupForm from packages/ui)
  User enters password + confirm password → submits
  POST /api/v1/auth/set-password (requires scope: "password_setup" JWT)
  Backend: hashes password, stores, issues FULL-ACCESS JWT + refresh token
  Frontend: stores tokens → redirects to role-specific next step:
    School Admin → /school-admin/dashboard
    Teacher      → /teacher/dashboard
    Student      → /student/onboarding/profile
```

### 5.2 Student Onboarding (After Password Setup)

```
Step 4 — Learning Profile Questionnaire
  Student lands on /student/onboarding/profile
  Completes 10-question questionnaire → POST /api/v1/onboarding/questionnaire/submit
  Backend: stores StudentLearningProfile, sets student_profiles.is_learning_profile_complete = TRUE

Step 5 — Dashboard Access
  OnboardingRoute gate clears → /student/dashboard loads
  Dashboard shows enrolled class cards (enrollment done by teacher or school admin)
  Each class card independently shows:
    - "Complete diagnostic" alert + locked content → if onboarding_diagnostic_status != COMPLETED
    - Normal state + full content access → if COMPLETED
    - Additional alert icons for new teacher messages or new progress check assessments

Step 6 — Per-Class Diagnostic (Tier 1)
  Student clicks "Start Diagnostic" on a locked class card
  Takes Tier 1 assessment → submits → calculate_gap_states fires
  class_enrollments.onboarding_diagnostic_status → COMPLETED for that class
  That class's content unlocks independently of other classes
```

### 5.3 Email/Password Login (Returning Users)

```
POST /api/v1/auth/login → { email, password }
  Verify bcrypt hash, check is_active=TRUE
  Return { access_token (15min), refresh_token (7 days), user: { id, email, role, school_id } }
  Frontend: role-based redirect per §6 table
```

---

## 6. Role → App → Route Mapping

| Role | App | Port | Post-Login Route (first login) | Post-Login Route (returning) |
|---|---|---|---|---|
| `STUDENT` | `apps/student` | 3002 | `/student/setup-password` | `/student/dashboard` or `/student/onboarding/profile` if profile incomplete |
| `TEACHER` | `apps/teacher` | 3001 | `/teacher/setup-password` | `/teacher/dashboard` |
| `SCHOOL_ADMIN` | `apps/school-admin` | 3004 | `/school-admin/setup-password` | `/school-admin/dashboard` |
| `PARENT` | `apps/parent` | 3003 | `/parent/dashboard` | `/parent/dashboard` |
| `KAIHLE_ADMIN` | `apps/kaihle-admin` | 3005 | `/kaihle-admin/dashboard` | `/kaihle-admin/dashboard` |

Parents are not invited via magic link in v1. No password setup step applies to parents.

---

## 7. Multi-Tenancy Rules

Single database. `school_id` on every non-curriculum table. Enforced at the service layer — not PostgreSQL RLS. `KAIHLE_ADMIN` bypasses school_id filters (explicit bypass required per Rule 12). All other roles: service methods must filter by `school_id`. Cross-school access returns **403 Forbidden**, not 404.

---

## 8. LLM Provider Routing

**Library:** [LiteLLM](https://github.com/BerriAI/litellm) — provider-agnostic abstraction layer. All LLM calls go through `litellm.acompletion()` and `litellm.aembedding()`. Feature code never imports provider SDKs directly. Switching providers or routing a task to a self-hosted LLM server requires only an environment variable change — zero code changes.

**Why LiteLLM:** It exposes a single OpenAI-compatible interface regardless of the underlying provider (OpenAI, Anthropic, Google, or any self-hosted server running an OpenAI-compatible API such as vLLM, Ollama, or a custom inference stack). When Kaihle moves to its own LLM server, the only change required is setting `LLM_<TASK>_API_BASE` in the environment to point at the server URL.

**The only file in `app/ai/providers/` is `router.py`.** There are no separate `gemini.py`, `openai.py`, or `anthropic.py` adapter files — LiteLLM replaces all of them.

```python
# backend/app/ai/providers/router.py

import litellm
from app.core.config import settings

# Task → model mapping is entirely config-driven.
# To switch lesson_plan from GPT-4.1 to your own server:
#   LLM_LESSON_PLAN_MODEL=openai/your-model-name
#   LLM_LESSON_PLAN_API_BASE=http://your-llm-server:8000
TASK_MODEL_MAP: dict[str, str] = {
    "gap_classification": settings.llm_gap_classification_model,
    "study_plan":         settings.llm_study_plan_model,
    "lesson_plan":        settings.llm_lesson_plan_model,
    "embeddings":         settings.llm_embeddings_model,
}

TASK_API_BASE_MAP: dict[str, str | None] = {
    "gap_classification": settings.llm_gap_classification_api_base,
    "study_plan":         settings.llm_study_plan_api_base,
    "lesson_plan":        settings.llm_lesson_plan_api_base,
    "embeddings":         settings.llm_embeddings_api_base,
}

async def complete(task: str, messages: list[dict], **kwargs) -> str:
    """Call the configured LLM for a given task. Provider-agnostic."""
    response = await litellm.acompletion(
        model=TASK_MODEL_MAP[task],
        api_base=TASK_API_BASE_MAP.get(task),  # None → use provider default
        messages=messages,
        **kwargs,
    )
    return response.choices[0].message.content

async def embed(task: str, text: str) -> list[float]:
    """Generate an embedding vector. Provider-agnostic."""
    response = await litellm.aembedding(
        model=TASK_MODEL_MAP["embeddings"],
        api_base=TASK_API_BASE_MAP.get("embeddings"),
        input=text,
    )
    return response.data[0]["embedding"]
```

**Task routing table (current defaults — all overridable via environment variables):**

| Task string | Default model | Default provider | Max latency |
|---|---|---|---|
| `gap_classification` | `gemini/gemini-2.5-flash` | Google | 5s |
| `study_plan` | `gpt-4.1-mini` | OpenAI | 10s |
| `lesson_plan` | `gpt-4.1` | OpenAI | 15s |
| `embeddings` | `text-embedding-004` | Google | — |

**Note — question generation and answer scoring are NOT LLM tasks.** All questions come from the pre-built question bank (`question_bank` table, populated by `import_questions.py`). All answers are MCQ — scoring is a deterministic string comparison (`student_response.selected_key == question.correct_answer_key`) with no LLM involvement. This eliminates the two highest-volume LLM call types from the system entirely.

**Self-hosted LLM server configuration example:**
```bash
# Route lesson planning to your own server — no code change required
LLM_LESSON_PLAN_MODEL=openai/kaihle-llm-v1
LLM_LESSON_PLAN_API_BASE=http://your-llm-server:8000

# Leave other tasks on hosted providers
LLM_GAP_CLASSIFICATION_MODEL=gemini/gemini-2.5-flash
LLM_GAP_CLASSIFICATION_API_BASE=   # empty = use provider default
```

---

## 9. Diagnostic Assessment — Two Tiers (CRITICAL)

Agents must never confuse these two tiers.

| | Tier 1 — Onboarding Diagnostic | Tier 2 — Progress Check |
|---|---|---|
| Created by | System (Celery: `create_class_diagnostic_task` on class creation) | Teacher via API |
| Student attempt created | System (Celery: `trigger_onboarding_diagnostics` on enrollment) | When teacher publishes |
| `is_system_generated` | `TRUE` | `FALSE` |
| Scope | ALL topics for subject + grade | Specific topics teacher selects |
| Blocks class content? | YES — until `COMPLETED` on that enrollment | NO |
| Updates gap states? | YES | YES |
| Student-facing UI | Identical to Tier 2 | Identical to Tier 1 |

---

## 10. Student Learning Profile (Quick Reference)

Table: `student_learning_profiles` — one row per student, created when questionnaire is submitted.

- `modality_scores` JSONB: `{ "visual": 0.8, "auditory": 0.3, "reading_writing": 0.6, "kinesthetic": 0.5 }`
- `work_style` JSONB: `{ "prefers_solo": true, "short_sessions": false, "task_based": true }`
- `interests` TEXT[]: e.g. `["football", "music", "gaming"]`

Used by: content curator (resource ranking), quiz generator (interest contextualisation), lesson planner (aggregated class interests), teacher gap map panel (read-only display).

---

## 11. Mastery Thresholds

Always use `getMasteryStyle(score)` from `packages/types/src/mastery.ts` — never inline mastery color logic.

| Score range | Label | Tailwind classes |
|---|---|---|
| `score < 0.4` | Needs Work | `text-red-600 bg-red-50` |
| `0.4 ≤ score ≤ 0.7` | Developing | `text-amber-600 bg-amber-50` |
| `score > 0.7` | Strong | `text-green-700 bg-green-50` |
| `null` | Not assessed | `text-gray-400 bg-gray-50` |

Boundary values: `0.4` → Developing, `0.7` → Developing, `0.71` → Strong.

---

## 12. Five-Role Design System Summary

Read `docs/design/DESIGN_SYSTEM.md` before writing any frontend component. This table is a quick-reference only.

| Role | App | Layout | Action color | Heading font | Body font |
|---|---|---|---|---|---|
| Kaihle Admin | `apps/kaihle-admin` | `AdminLayout` | Green | Inter | Inter |
| School Admin | `apps/school-admin` | `DashboardLayout variant="school-admin"` | Green | Fraunces | Nunito |
| Teacher | `apps/teacher` | `DashboardLayout variant="teacher"` | **Gold** `#c9932a` | Fraunces | Nunito |
| Student | `apps/student` | `StudentLayout` | Green | Fraunces | Nunito |
| Parent | `apps/parent` | `ParentLayout` | — (text links) | Lora | Nunito |

Critical rules: Kaihle Admin uses Inter only — no Fraunces, no Lora. Teacher action buttons are gold — never green. Green in the teacher app means mastery only. Student app has no sidebar; uses bottom nav on mobile. Parent app uses a narrow reading column with warm cream background.

---

## 13. Shared `packages/ui` Components

These components are shared across all five apps. No app may define its own version.

| Component | Purpose |
|---|---|
| `PasswordSetupForm` | First-login password creation (magic-link flow) — all 5 apps |
| `LoginForm` | Email/password + magic link — all 5 apps |
| `AuthLayout` | Centered card layout for auth screens — all 5 apps |
| `DashboardLayout` | Sidebar shell with teacher/school-admin variants |
| `AdminLayout` | Platform admin shell (Kaihle Admin only) |
| `StudentLayout` | Top nav + bottom mobile nav |
| `ParentLayout` | Top nav only |
| `OnboardingLayout` | Full-screen centered layout for questionnaire |

---

## 14. Where To Find Things

| What you need | Where to look |
|---|---|
| Full DB schema (columns, indexes, constraints) | `kaihle_v2_1_schema.sql` |
| Full product plan with milestone task details | `docs/kaihle_product_plan.md` |
| This milestone's goals + DoD | `docs/milestones/M{N}_brief.md` |
| This specific task's instructions | `docs/tasks/M{N}/M{N}-{E}-T{T}_*.md` |
| LLM prompt templates | `backend/app/ai/prompts/*.jinja2` |
| Design tokens, component patterns, role palettes | `docs/design/DESIGN_SYSTEM.md` |
| Architecture decisions | `docs/adr/ADR-*.md` |
| Environment variables reference | `docs/kaihle_product_plan.md` Part 6 |
| Screen design specs (per-role UI page inventory, component specs, data map) | `docs/design/screens/TEACHER_SCREENS.md` · `STUDENT_SCREENS.md` · `SCHOOL_ADMIN_SCREENS.md` · `KAIHLE_ADMIN_SCREENS.md` · `PARENT_SCREENS.md` |
| Mastery threshold rationale | `docs/design/MASTERY_THRESHOLD_RATIONALE.md` |
| Questionnaire design decisions | `docs/design/QUESTIONNAIRE_DESIGN_RATIONALE.md` |
| Modal + loading state standards | `docs/design/DESIGN_SYSTEM_ACCESSIBILITY_ADDENDUM.md` |

---

## 15. Architecture Decision Records

### ADR-001 — Five Separate Frontend Apps

**Date:** March 2026 · **Status:** Accepted · **Supersedes:** v1.0 single-app-with-folders approach

**Context:** v1.0 placed School Admin and Kaihle Admin pages inside `apps/teacher`. This weakened security isolation (admin code in the same JavaScript origin as teacher code), created deployment coupling (any teacher UI change triggered admin rebuilds), and produced design drift (admin pages inherited teacher-specific color tokens and layout patterns).

**Decision:** Five fully separate Vite apps — one per role — each with its own `index.html`, `tailwind.config.js`, `tsconfig.json`, Docker Compose service, and Render deployment. Shared logic lives exclusively in `packages/`.

**Ports:** student: 3002, teacher: 3001, parent: 3003, school-admin: 3004, kaihle-admin: 3005.

**Migration:** Existing `apps/teacher/src/pages/school-admin/` content migrates to `apps/school-admin/src/pages/`. Existing `apps/teacher/src/pages/kaihle-admin/` content migrates to `apps/kaihle-admin/src/pages/`. Both source directories are deleted after migration. Tracked in tasks M0-9-T2 and M0-9-T3.

---

*Kaihle Project Constitution v2.0 · March 2026*
*LOAD THIS FILE IN EVERY KILOCODE SESSION — no exceptions.*
*Key changes from v1.0: five-app architecture (ADR-001), mandatory password setup for all magic-link roles, two-layer student onboarding gate (global + per-class), explicit KaihleAdmin bypass rule (Rule 12), Celery dead-letter rule (Rule 18), empty question bank guard (Rule 17), PasswordSetupForm as shared package component, LiteLLM as provider-agnostic abstraction layer replacing individual provider adapters, question_generation and answer_scoring removed from LLM task routing (all questions are pre-built MCQ, scoring is deterministic).*
