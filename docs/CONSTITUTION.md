# Kaihle — Project Constitution
**Version:** 1.0 · Based on Product Plan v2.1
**Status:** AUTHORITATIVE — loaded in every KiloCode session, no exceptions
**Last updated:** March 2026

> This document is the permanent anchor for every coding session.
> It is intentionally short. It tells you WHAT the project is, WHAT rules are locked,
> and WHERE to find everything else. Do not duplicate content from task files here.

---

## 1. What Is Kaihle?

Kaihle is an AI-powered learning diagnostics platform for schools. It identifies knowledge gaps in students, generates personalised study plans, and gives teachers and parents real-time visibility into student progress.

**Target users:** Students (age 11–18), Teachers, School Admins, Parents.
**Curriculum scope (v1):** Cambridge Lower Secondary (Grades 6–8) + Cambridge IGCSE (Grades 9–10).

## Programme                        Grades                      Subjects
Cambridge Lower Secondary           6, 7, 8                     Mathematics (MATH), Integrated Science                                                         (SCI), English Language (ENG)
Cambridge IGCSE                     9, 10                       Mathematics (MATH), Biology(BIO),
                                                                Chemistry (CHEM), Physics (PHY), English Language (ENG),
                                                                English Literature (ENGL — non-core)

## Subject binding rules (absolute — enforced by curriculum_subjects table and seed script):
  - SCI (Integrated Science) belongs to cambridge_lower ONLY. It does not exist under igcse.
  - BIO, CHEM, PHY, ENGL belong to igcse ONLY. They do not exist under cambridge_lower.
  - MATH and ENG span both curricula.

**Cambridge AS & A Level (Grades 11–12)** is deferred to a later milestone.
It will be added as a separate curriculum entry cambridge_as_a when scoped.

**Pilot target:** micro-schools. Max 10 schools, ~400 students in v1.

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
| UI library |  TailAdmin Free as the base admin/dashboard template
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
      /api/v1/routes/     ← thin route handlers only, delegate to services
      /core/              ← config.py, security.py, database.py, redis.py
      /models/            ← SQLAlchemy ORM models (one file per domain)
      /schemas/           ← Pydantic request/response schemas
      /services/          ← ALL business logic lives here
      /ai/
        /providers/       ← base.py, gemini.py, openai.py, anthropic.py, router.py
        /rag/             ← embedder.py, retriever.py, curriculum.py
        /prompts/         ← .jinja2 prompt templates
        content_curator.py
        quiz_generator.py
      /tasks/             ← Celery task definitions
      /tests/unit/
      /tests/integration/
      /tests/e2e/
    /scripts/             ← seed_curriculum_graph.py, import_questions.py, ingest_curriculum.py
    /data/curriculum/     ← cambridge_v1.json (curriculum seed data)
  /frontend
    /apps/student/        ← Vite entrypoint, port 3002
    /apps/teacher/        ← Vite entrypoint, port 3001
    /apps/parent/         ← Vite entrypoint, port 3003
    /packages/ui/         ← shared Tailwind components
    /packages/api-client/ ← shared Axios instance + typed hooks
    /packages/auth/       ← tokenStore, useAuth, PrivateRoute, OnboardingRoute
    /packages/types/      ← shared TypeScript interfaces
  /docs/
    CONSTITUTION.md       ← this file
    /milestones/          ← M0_brief.md ... M6_brief.md
    /tasks/               ← M0/M0-1-T1_*.md ... M6/M6-3-T5_*.md
```
- All dashboard-style layouts (teacher, school admin, KaihleAdmin) MUST follow a shared TailAdmin-style layout implemented in `packages/ui` (e.g. `DashboardLayout`), not custom per-app shells.

---

## 4. Absolute Rules — Never Violate

1. **Service layer owns all business logic.** Routes are thin — validate input, call a service, return response. Zero business logic in route handlers.
2. **Every table has `school_id`.** Except curriculum tables (`curricula`, `subjects`, `grades`, `topics`, `curriculum_topics`, `subtopics`, etc.) which are school-agnostic by design.
3. **All queries filter by `school_id`** unless the caller role is `KAIHLE_ADMIN`.
4. **All LLM calls go through `LLMProvider` abstraction.** No feature code imports provider SDKs directly. Use `router.py` to select provider.
5. **No hardcoded secrets.** All config comes from environment variables via `app/core/config.py` (Pydantic Settings).
6. **Test coverage ≥ 80%** on all files in `/services/`. Enforced by CI — no merge to `main` if below.
7. **Test naming:** `test_<what>_when_<condition>_then_<expected>`
8. **`kaihle_v2_1_schema.sql` is the single source of truth for the database schema.** If a task file and the SQL file conflict, the SQL file wins. Always check it for exact column names, types, and constraints.
9. **Do not write migration SQL by hand.** Use `alembic revision --autogenerate -m "description"` and review the output.
10. **Student onboarding gate.** Students cannot access any route outside `/student/onboarding/*` until both their learning profile questionnaire AND all Tier 1 diagnostics are marked complete. Enforced by `require_onboarding_complete` FastAPI dependency.
11. Frontend apps MUST use TailAdmin as the base layout and design system for all dashboard-style pages (teacher, school admin, internal admin).
    - Agents MUST NOT introduce additional UI kits (e.g. MUI, Chakra, shadcn) without an explicit ADR.
    - Any new layout components MUST be implemented as TailAdmin-style Tailwind components in packages/ui.


---

## 5. Multi-Tenancy Rules

- Single database. `school_id` on every non-curriculum table.
- Enforced at **service layer** — not PostgreSQL RLS.
- `KaihleAdmin` role bypasses school_id filters.
- All other roles: service methods must filter by `school_id`.
- Cross-school data access returns **403 Forbidden**, not 404.

---

## 6. LLM Provider Routing

```python
from app.ai.providers.router import get_provider
provider = get_provider(task="question_generation")
response = await provider.complete(request)
```

| Task string | Provider | Max latency |
|---|---|---|
| `question_generation` | Gemini 2.5 Flash | 8s |
| `answer_scoring` | Rule-based → LLM fallback | 50ms / 3s |
| `gap_classification` | Gemini 2.5 Flash | 5s |
| `study_plan` | GPT-4.1 mini | 10s |
| `lesson_plan` | GPT-4.1 | 15s |
| `embeddings` | text-embedding-004 (Google) | — |

---

## 7. Diagnostic Assessment — Two Tiers (CRITICAL)

**Agents must never confuse these.**

| | Tier 1 (Onboarding) | Tier 2 (Ongoing) |
|---|---|---|
| Created by | System (Celery task) | Teacher (API) |
| When | On student class enrollment | Anytime teacher decides |
| `is_system_generated` | `TRUE` | `FALSE` |
| Scope | ALL topics for subject+grade | Specific topics teacher selects |
| Blocks dashboard? | YES | NO |
| Gap states | Same `calculate_gap_states` task | Same task |

Both tiers use the **identical** student-facing UI and API for taking assessments.

---

## 8. Student Learning Profile (Quick Reference)

Table: `student_learning_profiles` — one row per student, created during onboarding.

- `modality_scores` JSONB: `{ "visual": 0.8, "auditory": 0.3, "reading_writing": 0.6, "kinesthetic": 0.5 }` — floats 0.0–1.0
- `work_style` JSONB: `{ "prefers_solo": true, "short_sessions": false, "task_based": true }`
- `interests` TEXT[]: e.g. `['football', 'music', 'gaming']`

**Used by:**
- Content curator: modality multipliers on resource ranking (visual → VIDEO ×1.3, reading_writing → ARTICLE ×1.3, kinesthetic → INTERACTIVE ×1.3)
- Quiz generator: top 2 interests injected into question generation prompt
- Teacher gap map panel: dominant modality icon shown (read-only)

---

## 9. Enums Reference

```
assessment_type:     DIAGNOSTIC | TOPIC_SPECIFIC | PROGRESS_CHECK | FINAL
assessment_status:   DRAFT | ACTIVE | CLOSED
attempt_status:      NOT_STARTED | IN_PROGRESS | COMPLETED | ABANDONED
question_type:       MCQ | TRUE_FALSE | SHORT_ANSWER
scored_by:           RULE | LLM | PENDING
study_plan_status:   GENERATING | ACTIVE | COMPLETED | ABANDONED
resource_type:       VIDEO | ARTICLE | INTERACTIVE
lesson_plan_status:  GENERATED | EDITED | USED | ARCHIVED
user_role:           STUDENT | TEACHER | SCHOOL_ADMIN | PARENT | KAIHLE_ADMIN
subscription_tier:   TRIAL | STARTER | GROWTH | SCALE
subscription_status: ACTIVE | PAST_DUE | CANCELLED | EXPIRED
payment_status:      PENDING | SUCCEEDED | FAILED | REFUNDED | DISPUTED
token_type:          MAGIC_LINK | REFRESH
onboarding_status:   PENDING | IN_PROGRESS | COMPLETED
```

---

## 10. Mastery Score Colour Bands

Used consistently across all UI and API.

| Score | Label | Colour |
|---|---|---|
| < 0.4 | Needs Work | Red `#EF4444` |
| 0.4 – 0.7 | Developing | Amber `#F59E0B` |
| > 0.7 | Strong | Green `#10B981` |
| Not assessed | — | Grey `#9CA3AF` |

---

## 11. Where To Find Things

| What you need | Where to look |
|---|---|
| Full DB schema (columns, indexes, constraints) | `kaihle_v2_1_schema.sql` |
| Full product plan with all task details | `kaihle_product_plan_v2_1.md` |
| This milestone's goals + DoD | `/docs/milestones/M{N}_brief.md` |
| This specific task's instructions | `/docs/tasks/M{N}/M{N}-{E}-T{T}_*.md` |
| LLM prompt templates | `/backend/app/ai/prompts/*.jinja2` |
| Key environment variables | `kaihle_product_plan_v2_1.md` Part 6 |

---

*Kaihle Project Constitution v1.0 · March 2026 · LOAD THIS FILE IN EVERY KILOCODE SESSION.*
