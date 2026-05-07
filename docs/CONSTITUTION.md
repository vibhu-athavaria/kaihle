# Kaihle — Project Constitution
**Version:** 2.1 · March 2026 · Supersedes v2.0
**Status:** AUTHORITATIVE — loaded in every session, no exceptions

> What Kaihle IS, what rules are LOCKED, and where to find everything else.
> Design details live in `docs/design/DESIGN_SYSTEM.md` — do not duplicate them here.

---

## 1. What Is Kaihle?

AI-powered learning diagnostics platform for schools. Identifies knowledge gaps, generates personalised study plans, gives teachers, school admins, and parents real-time visibility into student progress.

**Target users:** Students (age 11–18), Teachers, School Admins, Parents, Kaihle Admin (internal).
**Curriculum scope (v1):** Cambridge Lower Secondary (Grades 6–8) + Cambridge IGCSE (Grades 9–10).

| Programme | Grades | Subjects |
|---|---|---|
| Cambridge Primary | 5 | Mathematics (MATH), English Language (ENG) |
| Cambridge Lower Secondary | 6–8 | Mathematics (MATH), Integrated Science (SCI), English Language (ENG) |
| Cambridge IGCSE | 9–10 | Mathematics (MATH), Biology (BIO), Chemistry (CHEM), Physics (PHY), English Language (ENG), English Literature (ENGL) |
| Cambridge AS & A Level | 11–12 | Mathematics (MATH), Biology (BIO), Chemistry (CHEM), Physics (PHY), English Language (ENG) |

**Subject binding rules (absolute):**
- SCI belongs to `cambridge_lower` ONLY — not IGCSE or AS/A Level.
- BIO, CHEM, PHY, ENGL belong to `igcse` and `cambridge_as_a` — not Lower Secondary or Primary.
- MATH and ENG span all four programmes.
- Grade level constraint in `grades` table: `level BETWEEN 1 AND 13` (supports future expansion).

**Pilot target:** Micro-schools in Southeast Asia. Max 10 schools, ~400 students in v1.

---

## 2. Locked Tech Stack

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

**Rule 11 — Student onboarding has two distinct, independent gates.**
- Gate 1 (global): Dashboard inaccessible until `student_profiles.is_learning_profile_complete = TRUE`. Enforced by `OnboardingRoute` in `packages/auth`.
- Gate 2 (per-class): Class content locked until `class_enrollments.onboarding_diagnostic_status = 'COMPLETED'` for that enrollment. Enforced by `require_diagnostic_complete(class_id)` API dependency and ClassCard UI.
- These gates are **independent**. Completing one class diagnostic does not unlock another.

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

### 5.1 Magic Link → Password Setup → Role-Specific Next Step

```
Step 1 — Invitation
  Kaihle Admin creates school → invites School Admin via magic link
  School Admin invites Teacher → magic link
  School Admin invites Student → magic link

Step 2 — Magic Link Click
  GET /api/v1/auth/magic-link/verify?token=...
  Backend: validates token (single-use, 10min TTL), marks used=TRUE
  Issues SCOPED JWT { scope: "password_setup", sub: user_id, role, exp: 1hr }
  Frontend: PasswordSetupRoute detects scope → /[app]/setup-password

Step 3 — Password Setup
  POST /api/v1/auth/set-password (requires scope: "password_setup")
  Backend: hashes password, issues FULL-ACCESS JWT + refresh token
  Redirect:
    School Admin → /school-admin/dashboard
    Teacher      → /teacher/dashboard
    Student      → /student/onboarding/profile
```

### 5.2 Student Onboarding (after password setup)

```
Step 4 — Learning Profile Questionnaire
  /student/onboarding/profile
  POST /api/v1/onboarding/questionnaire/submit
  Sets student_profiles.is_learning_profile_complete = TRUE

Step 5 — Dashboard Access
  OnboardingRoute clears → /student/dashboard
  Class cards show independently: locked (diagnostic pending) or unlocked

Step 6 — Per-Class Diagnostic (Tier 1)
  Student clicks locked class card → takes Tier 1 assessment
  Submit → calculate_gap_states → class_enrollments.onboarding_diagnostic_status = COMPLETED
  That class unlocks independently of others
```

### 5.3 Email/Password Login (returning users)

```
POST /api/v1/auth/login → { email, password }
  Verify bcrypt hash, check is_active=TRUE
  Return { access_token (15min), refresh_token (7 days), user: { id, email, role, school_id } }
  Role-based redirect per §6
```

---

## 6. Role → App → Route Mapping

| Role | App | Port | First login | Returning |
|---|---|---|---|---|
| STUDENT | `apps/student` | 3002 | `/student/setup-password` | `/student/dashboard` (or profile if incomplete) |
| TEACHER | `apps/teacher` | 3001 | `/teacher/setup-password` | `/teacher/dashboard` |
| SCHOOL_ADMIN | `apps/school-admin` | 3004 | `/school-admin/setup-password` | `/school-admin/dashboard` |
| PARENT | `apps/parent` | 3003 | `/parent/dashboard` | `/parent/dashboard` |
| KAIHLE_ADMIN | `apps/kaihle-admin` | 3005 | `/kaihle-admin/dashboard` | `/kaihle-admin/dashboard` |

Parents are not invited via magic link in v1 — no password setup step.

---

## 7. Multi-Tenancy Rules

Single database. `school_id` on every non-curriculum table. Enforced at the service layer (not PostgreSQL RLS). `KAIHLE_ADMIN` bypasses `school_id` filters with explicit bypass (Rule 12). All other roles must filter by `school_id`. Cross-school access returns **403**, not 404.

---

## 8. LLM Provider Routing

All LLM calls go through `backend/app/ai/providers/router.py` via LiteLLM. Switching providers requires only an environment variable change — no code changes.

| Task | Default model | Max latency |
|---|---|---|
| `gap_classification` | `gemini/gemini-2.5-flash` | 5s |
| `study_plan` | `gpt-4.1-mini` | 10s |
| `lesson_plan` | `openrouter/anthropic/claude-sonnet-4-6` | 90s |
| `student_pack` | `gemini/gemini-2.5-pro` | 30s |

**Note:** pgvector embeddings are not used in v1. `subtopic_content` table (structured SQL) replaces cosine similarity for all content curation. Do not add embedding calls without an ADR.

**Note:** Question generation and answer scoring are NOT LLM tasks. Questions come from the pre-built `question_bank` table. MCQ scoring is deterministic string comparison.

---

## 9. Environment Variables

All config comes from environment variables via `app/core/config.py` (Rule 5). Required for every environment:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/kaihle
REDIS_URL=redis://localhost:6379/0

# Auth
JWT_SECRET_KEY=<random 64-char hex>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# Email
RESEND_API_KEY=<key>
FROM_EMAIL=no-reply@kaihle.ai

# LLM — provider API keys
GOOGLE_API_KEY=<key>
OPENAI_API_KEY=<key>
OPENROUTER_API_KEY=<key>

# LLM — model routing (all overridable, defaults shown)
LLM_GAP_CLASSIFICATION_MODEL=gemini/gemini-2.5-flash
LLM_GAP_CLASSIFICATION_API_BASE=
LLM_STUDY_PLAN_MODEL=gpt-4.1-mini
LLM_STUDY_PLAN_API_BASE=
LLM_LESSON_PLAN_MODEL=openrouter/anthropic/claude-sonnet-4-6
LLM_LESSON_PLAN_API_BASE=
LLM_STUDENT_PACK_MODEL=gemini/gemini-2.5-pro
LLM_STUDENT_PACK_API_BASE=

# Storage
AWS_ACCESS_KEY_ID=<key>
AWS_SECRET_ACCESS_KEY=<key>
AWS_S3_BUCKET=kaihle-assets
AWS_REGION=ap-southeast-1

# App
ENVIRONMENT=development   # development | staging | production
LOG_LEVEL=INFO
```

**To route a task to a self-hosted LLM server** (no code change needed):
```bash
LLM_LESSON_PLAN_MODEL=openai/kaihle-llm-v1
LLM_LESSON_PLAN_API_BASE=http://your-llm-server:8000
```


---

## 10. Diagnostic Assessment — Two Tiers (CRITICAL)

| | Tier 1 — Onboarding Diagnostic | Tier 2 — Progress Check |
|---|---|---|
| Created by | System (Celery: `create_class_diagnostic_task`) | Teacher via API |
| `is_system_generated` | TRUE | FALSE |
| Scope | ALL topics for subject + grade | Specific topics teacher selects |
| Blocks class content? | YES — until COMPLETED on that enrollment | NO |
| Updates gap states? | YES | YES |

---

## 11. Student Learning Profile

Table: `student_learning_profiles` — one row per student, created on questionnaire submit.

- `modality_scores` JSONB: `{ "visual": 0.8, "auditory": 0.3, "reading_writing": 0.6, "kinesthetic": 0.5 }`
- `work_style` JSONB: `{ "prefers_solo": true, "short_sessions": false, "task_based": true }`
- `interests` TEXT[]: `["football", "music", "gaming"]` — human-readable, used directly in prompts.

Used by: content curator (resource ranking), quiz generator (interest contextualisation), lesson planner (class-level interest aggregation), teacher gap map panel (read-only display), AI Concept Guide (personalised explanations).

---

## 12. Mastery Thresholds

Use `getMasteryStyle(score)` from `packages/types/src/mastery.ts` — never inline mastery color logic. Full implementation in `docs/design/DESIGN_SYSTEM.md` §2.

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
| Environment variables | §9 of this document |
