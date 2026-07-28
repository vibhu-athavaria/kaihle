# Kaihle — Engineering Product Plan
**Version:** 1.0
**Prepared by:** Kramer (Technical Lead) + Nancy (Strategy)
**Date:** March 2026
**Audience:** Coding agents + senior full-stack engineer oversight
**Status:** Authoritative engineering source — supersedes v2.0 and all prior planning documents

## Document Purpose

This plan is the canonical reference for engineering execution. It is structured so that every task can be picked up by a coding agent or junior engineer without ambiguity. Each task has explicit inputs, outputs, and acceptance criteria. Nothing is left to interpretation.

Read the entire Architecture Decisions section before beginning any milestone.

---

## Part 1: Architecture Decisions (Locked for v1)

These decisions are final for v1. Do not deviate without a documented ADR (Architecture Decision Record).

### 1.1 Frontend

| Decision | Choice | Rationale |
|---|---|---|
| Framework | React + Vite | Fast HMR, modern build tooling, aligns with founder preference |
| Language | TypeScript (strict mode) | Type safety critical for multi-role auth flows |
| CSS | Tailwind CSS v3 | Utility-first, no custom CSS files unless absolutely necessary |
| App structure | Monorepo: `/apps/teacher`, `/apps/student`, `/apps/parent` | Separate entrypoints, shared `/packages/ui` and `/packages/api-client` |
| State management | Zustand (global) + React Query (server state) | Lightweight, no Redux overhead |
| Forms | React Hook Form + Zod validation | Schema-driven, minimal re-renders |
| Router | React Router v6 | File-based route organisation |
| Testing (unit) | Jest + React Testing Library | Component-level tests |
| Testing (E2E) | Playwright | Cross-browser, CI-friendly |

**Frontend directory structure:**
```
/frontend
  /apps
    /student       # Student app (Vite entrypoint)
    /teacher       # Teacher app (Vite entrypoint)
    /parent        # Parent app (Vite entrypoint)
  /packages
    /ui            # Shared Tailwind components (Button, Card, Modal, etc.)
    /api-client    # Shared Axios instance + typed API hooks
    /auth          # JWT decode, token refresh, route guards
    /types         # Shared TypeScript interfaces (User, School, Assessment, etc.)
```

### 1.2 Backend

| Decision | Choice | Rationale |
|---|---|---|
| Framework | FastAPI (Python 3.12+) | Async, auto OpenAPI docs, type hints via Pydantic |
| Language | Python 3.12 | Stable, mature AI/ML library ecosystem |
| API style | REST (JSON) | Simpler than GraphQL for this scope |
| ORM | SQLAlchemy 2.x (async) + Alembic migrations | Industry standard, async support |
| Validation | Pydantic v2 | Native FastAPI integration |
| Auth | JWT (access + refresh tokens) + magic links via email | Email/password primary; magic link as passwordless option |
| Task queue | Celery + Redis broker | Async LLM calls, weekly Teacher Copilot jobs |
| Email | Resend (transactional) | Simple API, magic link delivery |
| Testing | pytest + pytest-asyncio + httpx (async test client) | |

**Backend directory structure:**
```
/backend
  /app
    /api
      /v1
        /routes
          auth.py
          schools.py
          users.py
          assessments.py
          gap_map.py
          study_plans.py
          teacher_copilot.py
          parent.py
          onboarding.py        # NEW v2.1 — learning profile + onboarding status
    /core
      config.py
      security.py
      database.py
      redis.py
    /models
    /schemas
    /services
    /ai
      /providers
        base.py
        gemini.py
        openai.py
        anthropic.py
        router.py
      /rag
        embedder.py
        retriever.py
        curriculum.py
    /tasks
    /tests
      /unit
      /integration
      /e2e
  Dockerfile
  pyproject.toml
  alembic.ini
```

### 1.3 Data & Infrastructure

| Decision | Choice | Notes |
|---|---|---|
| Primary DB | PostgreSQL 16 with pgvector extension | Self-hosted in Docker (dev), managed RDS or Render PostgreSQL (prod) |
| Vector store | pgvector inside same PostgreSQL instance | Avoids separate Pinecone/Weaviate infra in v1 |
| Cache / Queue | Redis 7 | Caching, Celery broker, session store, rate limiting |
| File storage | AWS S3 (or Render persistent volume) | Curriculum PDFs, quiz assets |
| Dev environment | Docker Compose | All services in one `docker-compose.yml` |
| Production | **Recommendation: Render.com** | See Section 1.4 |
| Logging | structlog (Python) — structured JSON to stdout | Collected by cloud platform log aggregator |
| Secret management | Environment variables via `.env` (dev) / platform secrets (prod) | Never commit secrets |

### 1.4 Production Deployment Recommendation: Render.com

**Recommendation for v1: Render.com over AWS**

Rationale: At v1 scale (10 schools max, ~400 students), the operational overhead of managing ECS/EKS, VPCs, ALBs, and IAM on AWS is disproportionate. Render provides:
- Managed PostgreSQL with pgvector support
- Redis as a managed add-on
- Docker-based deploys from GitHub
- Automatic SSL, custom domains
- Preview environments per PR
- Cost at v1 scale: ~$50–100/month total vs ~$300–500/month AWS equivalent

**Production architecture on Render:**
```
GitHub PR → Render build → Docker image
  → Web Service (FastAPI app, 2 instances, auto-scale)
  → Background Worker (Celery, 1 instance)
  → PostgreSQL (Render managed, pgvector enabled)
  → Redis (Render managed)
  → S3 (AWS, just for file storage)
```

### 1.5 Multi-Tenancy Model

- **Single database, `school_id` (tenant_id) on every table**
- Row-Level Security enforced at application layer via service-level filters
- All queries in services must include `school_id` filter unless the caller is `KaihleAdmin`
- All API endpoints must validate that the requesting user's `school_id` matches the resource being accessed

### 1.6 LLM Provider Abstraction

All LLM calls go through a single abstraction layer. No feature code calls a provider SDK directly.

```python
# /backend/app/ai/providers/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class LLMRequest:
    task: str              # "question_generation" | "answer_scoring" | "gap_classification" | "study_plan" | "lesson_plan"
    prompt: str
    system_prompt: str
    max_tokens: int
    temperature: float
    metadata: dict

@dataclass
class LLMResponse:
    content: str
    provider: str
    model: str
    tokens_used: int
    latency_ms: int

class LLMProvider(ABC):
    @abstractmethod
    async def complete(self, request: LLMRequest) -> LLMResponse: ...

    @abstractmethod
    async def embed(self, text: str) -> list[float]: ...
```

**Task → Provider routing (router.py):**
```
question_generation   → Gemini 2.5 Flash
answer_scoring        → Rule-based first; LLM fallback for open-ended only
gap_classification    → Gemini 2.5 Flash
study_plan            → GPT-4.1 mini
lesson_plan           → GPT-4.1
embeddings            → text-embedding-004 (Google)
```

**Latency SLAs:**
| Task | Max latency |
|---|---|
| Answer scoring (rule-based) | 50ms |
| Answer scoring (LLM) | 3 seconds |
| Gap classification | 5 seconds |
| Question generation | 8 seconds |
| Study plan generation | 10 seconds |
| Lesson plan generation | 15 seconds |

### 1.7 Authentication Flow

```
Email/Password:
  POST /api/v1/auth/login → { email, password }
    → Verify bcrypt hash
    → Return { access_token (15min), refresh_token (7 days) }

Magic Link:
  POST /api/v1/auth/magic-link → { email }
    → Generate signed token (JWT, 10min expiry)
    → Send via Resend email
    → GET /api/v1/auth/magic-link/verify?token=xxx
    → Return { access_token, refresh_token }

Token Refresh:
  POST /api/v1/auth/refresh → { refresh_token }
    → Return new access_token

All protected routes:
  Authorization: Bearer <access_token>
  Middleware extracts user_id, school_id, role from JWT claims
```

### 1.8 Role Permission Matrix

| Action | Student | Teacher | School Admin | Parent | Kaihle Admin |
|---|---|---|---|---|---|
| Take diagnostic | ✓ (own) | — | — | — | — |
| Complete learning profile | ✓ (own) | — | — | — | — |
| View own gap map | ✓ | — | — | — | — |
| View class gap map | — | ✓ (own classes) | ✓ | — | ✓ |
| View study plan | ✓ (own) | ✓ (class) | — | — | — |
| Assign study plan | — | ✓ (own classes) | — | — | — |
| Generate lesson plan | — | ✓ (own classes) | — | — | — |
| View child progress | — | — | — | ✓ (own child) | — |
| Manage school users | — | — | ✓ | — | — |
| Approve schools | — | — | — | — | ✓ |
| View all schools | — | — | — | — | ✓ |

### 1.9 Curriculum Scope (v1)

- **Curricula:** Cambridge Lower Secondary + IGCSE
- **Subjects:** Mathematics, Science, English Language
- **Grades:** 6–12
- **Seed order:** `seed_curriculum_graph.py` first, then `ingest_curriculum.py`
- **Question bank:** 7,000 existing questions — imported via `import_questions.py`

### 1.10 Testing Standards

- **Backend:** pytest. Minimum 80% coverage on all service layer files.
- **Frontend:** Jest + RTL for components. Playwright for E2E flows.
- **CI gate:** No merge to `main` if coverage drops below 80% or any Playwright test fails.
- **Test naming convention:** `test_<what>_when_<condition>_then_<expected>`

### 1.11 Diagnostic Assessment Model — Two-Tier Architecture (v2.1)

**CRITICAL:** There are two distinct types of diagnostic in Kaihle. Agents must never confuse them.

**Tier 1 — Onboarding Diagnostic (System-Triggered)**
- Created automatically by the system when a student is enrolled in a class
- One assessment created per subject for the student's grade and curriculum
- Marked with `is_system_generated = TRUE` on the `assessments` table
- Covers ALL topics for that subject at the student's grade level (broad sweep)
- The student is required to complete all Tier 1 assessments before accessing any other part of the student app — this is an onboarding gate enforced by middleware
- Status tracked per class enrollment in `class_enrollments.onboarding_diagnostic_status`: `PENDING` → `IN_PROGRESS` → `COMPLETED`
- A student is considered fully diagnostically onboarded when ALL active `class_enrollments` rows have status = `COMPLETED`
- Triggered by: `POST /api/v1/schools/{school_id}/classes/{class_id}/enroll` completing successfully
- Handled by Celery task: `trigger_onboarding_diagnostics(student_id, class_id)`

**Tier 2 — Ongoing Assessments (Teacher-Created)**
- Created manually by a teacher for a specific class
- `is_system_generated = FALSE`
- Types: `TOPIC_SPECIFIC`, `PROGRESS_CHECK`, `FINAL` (DIAGNOSTIC type can also be teacher-created for a fresh broad sweep mid-year)
- No onboarding gate — students see these alongside their normal dashboard
- Everything in Epic M1-3 and M1-4 refers to Tier 2 assessments

**Why this matters for gap_states:**
Both tiers write to the same `gap_states` table via the same `calculate_gap_states` Celery task. The distinction is only in how the assessment is created and whether it blocks student access.

### 1.12 Student Learning Profile (v2.1)

Every student has a learning profile collected via an onboarding questionnaire. This profile is used by the content curation engine and quiz generator to personalise study plans.

**What it captures:**
- **Learning modalities** (scored 0.0–1.0 each, not binary): Visual, Auditory, Reading/Writing, Kinesthetic. Scores derived from questionnaire responses — a student can score high on multiple.
- **Work style preferences**: solo vs group, short sessions vs deep sessions, task-based vs concept-first.
- **Personal interests**: free-text tags entered by student (e.g. football, music, gaming, cooking, animals). Used to contextualise quiz question scenarios.

**How it affects study plans:**
- Content curator weights resource types: Visual-dominant students get YouTube videos prioritised. Reading/Writing-dominant students get article/text resources prioritised. Kinesthetic students get interactive exercises prioritised.
- Quiz generator injects top 2 interests into the question generation prompt so example scenarios feel personally relevant.
- Learning profile is displayed to the teacher in the student gap panel (read-only) so they understand the student's learning style.

**Onboarding sequence (new in v2.1):**
```
Student first login
  → Onboarding gate middleware checks:
      1. Has learning_profile? No → /student/onboarding/profile (questionnaire, ~5 min)
      2. Tier 1 diagnostics completed? No → /student/onboarding/diagnostics
      3. Both done → /student/dashboard (normal access)
```

---

## Part 2: Database Schema (v2.1)

**Canonical SQL source:** `kaihle_v2_1_schema.sql` — for full column definitions, indexes, and constraints. This section is a structured summary.

**Key changes in v2.1 vs v2.0:**
- `assessments` table: new column `is_system_generated BOOLEAN DEFAULT FALSE`
- `student_profiles` table: new column `onboarding_diagnostic_status` (enum: `PENDING`, `IN_PROGRESS`, `COMPLETED`)
- New table: `student_learning_profiles` (see §2.12 below)
- New enum: `onboarding_status_enum` (`PENDING`, `IN_PROGRESS`, `COMPLETED`)

---

### 2.1 Enums

| Enum | Values |
|---|---|
| `assessment_type_enum` | `DIAGNOSTIC`, `TOPIC_SPECIFIC`, `PROGRESS_CHECK`, `FINAL` |
| `assessment_status_enum` | `DRAFT`, `ACTIVE`, `CLOSED` |
| `attempt_status_enum` | `NOT_STARTED`, `IN_PROGRESS`, `COMPLETED`, `ABANDONED` |
| `scored_by_enum` | `RULE`, `LLM`, `PENDING` |
| `question_type_enum` | `MCQ`, `TRUE_FALSE`, `SHORT_ANSWER` |
| `plan_status_enum` | `PENDING`, `IN_PROGRESS`, `COMPLETED`, `SKIPPED` |
| `lesson_plan_status_enum` | `GENERATING`, `READY`, `USED`, `ARCHIVED` |
| `user_role_enum` | `STUDENT`, `TEACHER`, `SCHOOL_ADMIN`, `PARENT`, `KAIHLE_ADMIN` |
| `subscription_tier_enum` | `TRIAL`, `STARTER`, `GROWTH`, `SCALE` |
| `subscription_status_enum` | `TRIALING`, `ACTIVE`, `PAST_DUE`, `CANCELLED`, `EXPIRED` |
| `payment_status_enum` | `PENDING`, `SUCCEEDED`, `FAILED`, `REFUNDED`, `DISPUTED` |
| `token_type_enum` | `MAGIC_LINK`, `REFRESH` |
| `onboarding_status_enum` | `PENDING`, `IN_PROGRESS`, `COMPLETED` *(NEW v2.1)* |

---

### 2.2 Curriculum Tables (School-Agnostic)

```
curricula                   Curriculum boards (Cambridge LS, IGCSE, IB MYP...)
  └── curriculum_subjects   Junction: which subjects belong to which curriculum
subjects                    Academic disciplines — global reference (Math, Science, English)
grades                      Grade levels 6–12 — global reference, ordered by level INT
topics                      Named topic units (Algebra, Forces...) — curriculum-agnostic
curriculum_topics           THE PIVOT TABLE — binds curriculum_id + subject_id + grade_id + topic_id
  └── subtopics             Atomic learning unit
                            embedding VECTOR(768) — RAG anchor
subtopic_prerequisites      Prerequisite graph at subtopic level
topic_prerequisites         Prerequisite graph at topic level
curriculum_chunks           PDF-sourced paragraph chunks for rich LLM context
```

---

### 2.3 Question Bank

```sql
question_bank
  subtopic_id         UUID FK → subtopics        -- PRIMARY curriculum position
  topic_id            UUID FK → topics            -- denormalised convenience
  subject_id          UUID FK → subjects          -- denormalised convenience
  grade_id            UUID FK → grades            -- denormalised convenience
  question_text       TEXT NOT NULL
  question_type       question_type_enum
  options             JSONB
  correct_answer      TEXT NOT NULL
  explanation         TEXT
  difficulty_level    FLOAT (1.0–5.0)
  bloom_taxonomy      VARCHAR(50)
  canonical_form      TEXT UNIQUE
  source              VARCHAR(10)                 -- 'BANK' | 'LLM'
  is_active           BOOLEAN DEFAULT TRUE
```

---

### 2.4 School & Organisational

```
schools                 Tenant root
school_curricula        Junction: which curricula a school has adopted
classes                 Teacher + students + subject + curriculum + grade
                        FK: school_id, grade_id, subject_id, curriculum_id, teacher_id
class_enrollments       Student ↔ class membership
```

---

### 2.5 Users & Roles

```
users                   Single table for all roles
                        school_id NULL only for KAIHLE_ADMIN
student_profiles        Extended student data
                        v2.1: onboarding_diagnostic_status moved to class_enrollments (per-class tracking)
teacher_profiles        Extended teacher data
parent_student          Parent ↔ student links (many-to-many)
auth_tokens             JWT refresh tokens + magic links
```

---

### 2.6 Assessment (Three-Table Split)

```
assessments             DEFINITION — teacher creates, or system creates (Tier 1)
                        NEW v2.1: is_system_generated BOOLEAN DEFAULT FALSE
                        assessment_type: DIAGNOSTIC | TOPIC_SPECIFIC | PROGRESS_CHECK | FINAL
                        curriculum_topic_id: NULL for broad DIAGNOSTIC, populated for focused types
assessment_selected_questions   Bridge: which question_bank rows are in this assessment
student_attempts        Per-student execution
                        status: NOT_STARTED → IN_PROGRESS → COMPLETED | ABANDONED
student_responses       Per-question answer
                        scored_by: RULE (MCQ/TRUE_FALSE) | PENDING → LLM (SHORT_ANSWER)
```

---

### 2.7 Gap Tracking

```sql
gap_states
  student_id        UUID FK → users
  subtopic_id       UUID FK → subtopics
  school_id         UUID FK → schools
  class_id          UUID FK → classes
  mastery_score     FLOAT (0.0–1.0)   -- < 0.4 = RED, 0.4–0.7 = AMBER, > 0.7 = GREEN
  confidence        FLOAT (0.0–1.0)
  attempt_count     INT
  total_correct     INT
  total_attempted   INT
  needs_review      BOOLEAN
  last_assessed_at  TIMESTAMPTZ
  UNIQUE (student_id, subtopic_id)
```

---

### 2.8 Study Plans

```
study_plans             One plan per student per subtopic assignment
                        FK: student_id, subtopic_id, class_id, school_id, assigned_by
study_plan_resources    Curated external resources
                        alignment_score = cosine_sim(resource_embedding, subtopic.embedding)
                        resource_type: VIDEO | ARTICLE | INTERACTIVE
                        Only resources > 0.72 threshold included
study_plan_quizzes      AI-generated practice quiz — one per plan
                        5 questions: 4 MCQ + 1 SHORT_ANSWER
```

---

### 2.9 Teacher Copilot & Parent Portal

```
lesson_plans            One per class per week — UNIQUE(class_id, week_start)
                        generated_plan JSONB (GPT-4.1, 15s SLA)
                        teacher_edits JSONB — delta, never replaces generated_plan
                        status: GENERATING → READY → USED | ARCHIVED
parent_report_snapshots One per student per week — UNIQUE(student_id, week_start)
                        narrative TEXT (Gemini Flash, 150-word limit)
                        gap_summary JSONB
```

---

### 2.10 Billing & Subscriptions

```
subscription_plans      Global tier definitions — seeded at deploy time
                        TRIAL ($0, 30 students, 15 days)
                        STARTER ($75/student/year, 100 max)
                        GROWTH ($100/student/year, 500 max)
                        SCALE ($125/student/year, unlimited)
school_subscriptions    One active subscription per school
subscription_invoices   Per billing cycle
payments                Payment attempts per invoice
trial_extensions        Audit trail for Kaihle Admin trial extensions
```

---

### 2.11 Table Inventory

| Group | Tables |
|---|---|
| Curriculum (school-agnostic) | `curricula`, `subjects`, `grades`, `topics`, `curriculum_subjects`, `curriculum_topics`, `subtopics`, `subtopic_prerequisites`, `topic_prerequisites`, `curriculum_chunks` |
| School & Org | `schools`, `school_curricula`, `classes`, `class_enrollments` |
| Users | `users`, `student_profiles`, `teacher_profiles`, `parent_student`, `auth_tokens` |
| Assessment | `assessments`, `assessment_selected_questions`, `student_attempts`, `student_responses` |
| Gap Tracking | `gap_states` |
| Study Plans | `study_plans`, `study_plan_resources`, `study_plan_quizzes` |
| Teacher Copilot | `lesson_plans` |
| Parent Portal | `parent_report_snapshots` |
| Billing | `subscription_plans`, `school_subscriptions`, `subscription_invoices`, `payments`, `trial_extensions` |
| Onboarding | `student_learning_profiles` *(NEW v2.1)* |
| System | `alembic_version` |
| **Total** | **35 tables, 14 enums** |

---

### 2.12 Student Learning Profiles (NEW v2.1)

```sql
student_learning_profiles
  id                      UUID PRIMARY KEY DEFAULT gen_random_uuid()
  student_id              UUID NOT NULL UNIQUE REFERENCES users(id)
  school_id               UUID NOT NULL REFERENCES schools(id)  -- tenant isolation
  modality_scores         JSONB NOT NULL DEFAULT '{}'
    -- { "visual": 0.8, "auditory": 0.3, "reading_writing": 0.6, "kinesthetic": 0.5 }
    -- Scores are 0.0–1.0 floats derived from questionnaire item scoring
    -- Multiple high scores are valid — a student can be both visual and kinesthetic
  work_style              JSONB NOT NULL DEFAULT '{}'
    -- { "prefers_solo": true, "short_sessions": false,
    --   "task_based": true, "group_learning": false,
    --   "concept_first": false }
  interests               TEXT[]
    -- Free-text tags entered by student, stored lowercase
    -- e.g. ['football', 'music', 'gaming', 'cooking', 'animals']
    -- Top 2 injected into quiz generation prompt
  questionnaire_version   VARCHAR(10) NOT NULL DEFAULT 'v1'
    -- Allows future questionnaire redesigns without data loss
  completed_at            TIMESTAMPTZ
    -- NULL = questionnaire not yet completed (student abandoned partway)
  created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
  updated_at              TIMESTAMPTZ

-- Index for fast lookup by student
CREATE UNIQUE INDEX idx_slp_student ON student_learning_profiles(student_id);
CREATE INDEX idx_slp_school ON student_learning_profiles(school_id);
```

**Questionnaire design (v1 — 10 questions, ~5 minutes):**

Questions use a scenario-choice format, not Likert scales — more engaging for students aged 11–18.

| Q# | Scenario | Maps to |
|---|---|---|
| 1 | "When learning something new, I prefer to..." (watch a video / read about it / try it out / discuss it) | modality |
| 2 | "I remember things best when..." (I see diagrams / I hear them explained / I write notes / I do an exercise) | modality |
| 3 | "I prefer to study..." (alone / with friends) | work_style.prefers_solo |
| 4 | "I prefer study sessions that are..." (short & frequent / long & deep) | work_style.short_sessions |
| 5 | "I learn better by..." (understanding the theory first / jumping into tasks) | work_style.concept_first |
| 6–10 | "Pick topics that interest you most" (multi-select from: sports, music, gaming, animals, cooking, art, technology, nature, fashion, travel) | interests |

**Scoring modality from Q1 + Q2:**
Each answer maps to a modality. Student's final `modality_scores` are normalised across both questions:
- Q1: watch video → visual +1, read → reading_writing +1, try it → kinesthetic +1, discuss → auditory +1
- Q2: diagrams → visual +1, hear → auditory +1, write notes → reading_writing +1, exercise → kinesthetic +1
- Final score per modality = count / 2 (max 1.0)

---

## Part 3: Phased Roadmap

---

# MILESTONE 0: Foundations
**Goal:** Working local dev environment, CI/CD pipeline, auth system, tenant model, and base infrastructure. No product features. No LLM calls.
**Exit criteria:** A developer can `docker-compose up` and have the entire stack running. A user can register, log in, and receive a JWT. CI runs on every PR.
**Estimated duration:** 2–3 weeks

---

### EPIC M0-1: Repository & Project Setup

**User Story:** As a developer, I want a clean monorepo structure with consistent tooling so I can start writing features without fighting configuration.

#### Tasks

**M0-1-T1: Initialise monorepo**
- Create root `/kaihle` directory
- Backend: `uv` or `pip` + `pyproject.toml`, Python 3.12, FastAPI, SQLAlchemy, Alembic, Pydantic v2, pytest, structlog, celery, redis, httpx
- Frontend: Vite + React + TypeScript, Turborepo or simple workspaces in `package.json`, Tailwind CSS v3, Zustand, React Query v5, React Router v6, Axios, Zod, Jest, Playwright
- Root `.gitignore`, `.env.example`, `README.md`
- Pre-commit hooks: `ruff` (Python linting), `mypy` (type checking), `prettier` + `eslint` (frontend)

**Acceptance criteria:**
- [ ] `cd backend && uvicorn app.main:app --reload` starts without errors
- [ ] `cd frontend && pnpm dev` starts the teacher app without errors
- [ ] `ruff check .` and `mypy .` pass with zero errors on clean checkout
- [ ] `prettier --check .` passes on frontend

---

**M0-1-T2: Docker Compose dev environment**
- `docker-compose.yml` at root with services:
  - `postgres`: postgres:16-alpine, pgvector extension installed on init, port 5432
  - `redis`: redis:7-alpine, port 6379
  - `backend`: mounts `/backend`, hot-reload via `uvicorn --reload`, port 8000
  - `celery-worker`: same image as backend, runs `celery -A app.tasks worker`
  - `frontend-teacher`: mounts `/frontend/apps/teacher`, port 3001
  - `frontend-student`: mounts `/frontend/apps/student`, port 3002
  - `frontend-parent`: mounts `/frontend/apps/parent`, port 3003
- `.env.example` with all required vars documented

**Acceptance criteria:**
- [ ] `docker-compose up` starts all services without errors
- [ ] `GET http://localhost:8000/health` returns `{ "status": "ok", "db": "connected", "redis": "connected" }`
- [ ] `GET http://localhost:3001` renders React app with no console errors
- [ ] pgvector: `SELECT * FROM pg_extension WHERE extname = 'vector'` returns one row

---

**M0-1-T3: CI/CD pipeline (GitHub Actions)**
- `.github/workflows/ci.yml`:
  - Trigger: every PR to `main` and `develop`
  - Jobs: `lint-backend`, `test-backend` (pytest, coverage ≥ 80%), `lint-frontend`, `test-frontend-unit`, `test-e2e` (Playwright, headless)
  - Coverage report posted as PR comment
- `.github/workflows/deploy.yml`:
  - Trigger: merge to `main`
  - Deploy backend to Render via deploy hook
  - Deploy frontend apps to Render static sites

**Acceptance criteria:**
- [ ] Every PR triggers CI within 2 minutes of push
- [ ] PR with coverage < 80% on service files fails the `test-backend` job
- [ ] PR with failing Playwright test fails the `test-e2e` job
- [ ] Merge to `main` triggers deploy to Render staging environment

---

### EPIC M0-2: Database & Migrations

**User Story:** As a developer, I want a versioned database schema so that schema changes are tracked, reversible, and applied consistently across environments.

#### Tasks

**M0-2-T1: Alembic setup and initial migration**
- Configure `alembic.ini` to use `DATABASE_URL` from environment
- Create `env.py` with async SQLAlchemy engine support
- Write `001_initial_schema.py` migration creating all 35 tables defined in `kaihle_v2_1_schema.sql` and Part 2 of this plan (v2.1). Table creation order must respect FK dependencies.
- Enable pgvector: `CREATE EXTENSION IF NOT EXISTS vector` in migration
- `assessments` table must include `is_system_generated BOOLEAN DEFAULT FALSE` column
- `student_profiles` table must include `onboarding_diagnostic_status onboarding_status_enum DEFAULT 'PENDING'` column
- Create `student_learning_profiles` table per §2.12
- Create all indexes

**Acceptance criteria:**
- [ ] `alembic upgrade head` runs without errors on clean database
- [ ] `alembic downgrade -1` reverses the migration cleanly
- [ ] All 35 tables exist with correct columns after upgrade
- [ ] `SELECT extname FROM pg_extension WHERE extname = 'vector'` returns row
- [ ] `student_learning_profiles` table exists with all columns from §2.12
- [ ] `assessments.is_system_generated` column exists with DEFAULT FALSE
- [ ] `student_profiles.onboarding_diagnostic_status` column exists with DEFAULT 'PENDING'
- [ ] Test: migration can be applied and reversed 3× consecutively without errors

---

**M0-2-T2: SQLAlchemy async models**
- Create `/backend/app/models/` with one file per domain: `school.py`, `user.py`, `curriculum.py`, `assessment.py`, `gap.py`, `study_plan.py`, `lesson_plan.py`, `parent.py`, `onboarding.py`
- `onboarding.py` must define `StudentLearningProfile` model per §2.12
- `assessment.py` must include `is_system_generated: Mapped[bool]` field
- `user.py` `StudentProfile` model must include `onboarding_diagnostic_status: Mapped[OnboardingStatus]`
- All models use `mapped_column()` syntax (SQLAlchemy 2.x)
- All UUID primary keys default to `uuid4()`
- `Base` class with `created_at` and `updated_at` via mixin

**Acceptance criteria:**
- [ ] `mypy` passes on all model files with no errors
- [ ] Unit test: `StudentLearningProfile` can be instantiated with required fields
- [ ] Unit test: `Assessment` model has `is_system_generated` field defaulting to False
- [ ] Integration test: each model can be written to and read from test database

---

### EPIC M0-3: Authentication System

**User Story:** As any user, I want to log in with my email and password (or magic link) and receive a JWT so I can access protected resources.

#### Tasks

**M0-3-T1: Core auth backend**
- `/backend/app/core/security.py`:
  - `hash_password(plain: str) → str` using `bcrypt`
  - `verify_password(plain: str, hashed: str) → bool`
  - `create_access_token(payload: dict, expires_in: int) → str` — 15-minute expiry
  - `create_refresh_token(user_id: UUID) → str` — 7-day expiry, stored in `auth_tokens`
  - `decode_token(token: str) → dict` — raises `InvalidTokenError` on failure
- JWT payload must include: `sub` (user_id), `school_id`, `role`, `exp`, `iat`

**Acceptance criteria:**
- [ ] Unit test: `hash_password` + `verify_password` round-trip passes
- [ ] Unit test: `create_access_token` with 15min expiry — decoding after 16min raises error
- [ ] Unit test: `decode_token` with tampered signature raises `InvalidTokenError`
- [ ] Unit test: JWT payload contains `sub`, `school_id`, `role`, `exp`, `iat`

---

**M0-3-T2: Auth routes**

`POST /api/v1/auth/register`
- Body: `{ email, password, role, school_id, first_name, last_name }`
- Validates email uniqueness within school
- Role must be `student`, `teacher`, or `school_admin`
- Returns: `{ user_id, email, role }`

`POST /api/v1/auth/login`
- Body: `{ email, password }`
- Returns: `{ access_token, refresh_token, token_type: "bearer", user: { id, email, role, school_id } }`

`POST /api/v1/auth/refresh`
- Body: `{ refresh_token }`
- Returns new `access_token`

`POST /api/v1/auth/magic-link`
- Body: `{ email }`
- Generates JWT token (10 min expiry), stores hash in `auth_tokens`
- Returns: `{ message: "Magic link sent" }` (always, even if email not found)

`GET /api/v1/auth/magic-link/verify?token=xxx`
- Validates token, marks as used
- Returns: `{ access_token, refresh_token }`

`POST /api/v1/auth/logout`
- Marks refresh token as used
- Returns: `{ message: "Logged out" }`

**Acceptance criteria:**
- [ ] Integration test: full login flow returns valid JWT with correct claims
- [ ] Integration test: login with wrong password returns 401
- [ ] Integration test: magic link flow — send, verify, returns JWT
- [ ] Integration test: expired magic link returns 401
- [ ] Integration test: used magic link cannot be used again (401)
- [ ] Integration test: refresh token returns new access token
- [ ] Integration test: logout invalidates refresh token
- [ ] Security test: SQL injection attempt in email field returns 400

---

**M0-3-T3: Auth middleware and route guards**
- `get_current_user` dependency: extracts JWT from `Authorization: Bearer` header
- `require_role(*roles)` dependency factory: raises 403 if role not in list
- `require_school_resource(school_id)` helper: raises 403 if user's school_id ≠ resource school_id (unless KaihleAdmin)
- **NEW v2.1:** `require_onboarding_complete` dependency: for student routes outside `/onboarding/*`, checks that `student_profiles.onboarding_diagnostic_status = 'COMPLETED'` AND `student_learning_profiles` row exists with non-null `completed_at`. Returns 403 with body `{ redirect: "/student/onboarding" }` if not complete.

**Acceptance criteria:**
- [ ] Integration test: request without token returns 401
- [ ] Integration test: request with expired token returns 401
- [ ] Integration test: teacher accessing another school's data returns 403
- [ ] Integration test: `require_role("school_admin")` called by student returns 403
- [ ] Integration test: KaihleAdmin can access any school's data
- [ ] Integration test: student accessing `/student/dashboard` without completed onboarding returns 403 with redirect field
- [ ] Integration test: student who has completed onboarding can access dashboard normally

---

**M0-3-T4: Auth frontend (shared package)**
- `/frontend/packages/auth/`:
  - `tokenStore.ts`: Zustand store with `accessToken`, `refreshToken`, `user` state
  - `useAuth()` hook: `login()`, `logout()`, `refreshToken()`, `isAuthenticated`, `user`
  - `PrivateRoute` component: redirects to `/login` if not authenticated
  - `RoleRoute` component: redirects to `/unauthorised` if role doesn't match
  - **NEW v2.1:** `OnboardingRoute` component: if user is STUDENT and onboarding not complete, redirects to `/student/onboarding`
  - Axios interceptor: auto-attach `Authorization` header; auto-refresh on 401

**Acceptance criteria:**
- [ ] Unit test: `useAuth().login()` stores tokens
- [ ] Unit test: `PrivateRoute` redirects unauthenticated user to `/login`
- [ ] Unit test: `OnboardingRoute` redirects student without completed onboarding to `/student/onboarding`
- [ ] Unit test: Axios interceptor retries with refreshed token on 401
- [ ] E2E test: user logs in → sees dashboard → refreshes page → remains logged in

---

**M0-3-T5: Login UI (all three apps)**
- Shared `/packages/ui/LoginForm` component
- Fields: email, password, "Forgot password / Use magic link" toggle
- Magic link UI: email input + "Send login link" button + success message
- Error states: invalid credentials, account not found, account inactive
- Responsive, Tailwind styled

**Acceptance criteria:**
- [ ] E2E test: teacher logs in with email/password → lands on teacher dashboard
- [ ] E2E test: student logs in → redirected to onboarding (if not complete)
- [ ] E2E test: parent logs in → lands on parent dashboard
- [ ] E2E test: invalid credentials shows error message
- [ ] Accessibility: all form inputs have labels, form is keyboard-navigable

---

### EPIC M0-4: School & User Management (Kaihle Admin)

**User Story:** As a Kaihle Admin, I want to approve schools and manage users so that only legitimate schools can access the platform.

#### Tasks

**M0-4-T1: School management API**

`POST /api/v1/admin/schools` (KaihleAdmin only)
- Body: `{ name, slug, subscription_tier }`
- Returns school object

`GET /api/v1/admin/schools` (KaihleAdmin only)
- List all schools with pagination

`PATCH /api/v1/admin/schools/{school_id}` (KaihleAdmin only)
- Update school status

`GET /api/v1/schools/{school_id}` (SchoolAdmin of that school, KaihleAdmin)

**Acceptance criteria:**
- [ ] Integration test: KaihleAdmin can create, list, and update schools
- [ ] Integration test: Teacher calling admin endpoints returns 403
- [ ] Integration test: School slug must be unique — duplicate returns 409

---

**M0-4-T2: User management API (School Admin)**

`POST /api/v1/schools/{school_id}/users` (SchoolAdmin, KaihleAdmin)
- Invite user: create record with `is_active=false`, send magic link
- Body: `{ email, role, first_name, last_name }`

`GET /api/v1/schools/{school_id}/users` (SchoolAdmin, KaihleAdmin)
`PATCH /api/v1/schools/{school_id}/users/{user_id}` (SchoolAdmin, KaihleAdmin)
`DELETE /api/v1/schools/{school_id}/users/{user_id}` (SchoolAdmin, KaihleAdmin) — soft delete

**Acceptance criteria:**
- [ ] Integration test: SchoolAdmin invites teacher → teacher receives magic link email
- [ ] Integration test: SchoolAdmin cannot manage users in a different school
- [ ] Integration test: Deactivated user cannot log in (401)
- [ ] Integration test: Pagination works correctly

---

**M0-4-T3: Grade and class management API**

`POST /api/v1/schools/{school_id}/grades` (SchoolAdmin)
`GET /api/v1/schools/{school_id}/grades` (Teacher, SchoolAdmin)
`POST /api/v1/schools/{school_id}/classes` (SchoolAdmin)
`GET /api/v1/schools/{school_id}/classes` (Teacher sees own; SchoolAdmin sees all)
`POST /api/v1/schools/{school_id}/classes/{class_id}/enroll` (SchoolAdmin)
- **NEW v2.1:** After successful enrollment, fires Celery task `trigger_onboarding_diagnostics(student_id, class_id)` if student's `onboarding_diagnostic_status = 'PENDING'`
`GET /api/v1/schools/{school_id}/classes/{class_id}/students` (Teacher, SchoolAdmin)

**Acceptance criteria:**
- [ ] Integration test: SchoolAdmin creates grade, class, assigns teacher, enrolls 3 students
- [ ] Integration test: enrolling a student fires `trigger_onboarding_diagnostics` Celery task
- [ ] Integration test: Teacher sees own classes only
- [ ] Integration test: Enrolling student not belonging to school returns 400

---

### EPIC M0-5: Observability & Health

**M0-5-T1: Structured logging**
- Configure `structlog` with JSON output
- All log entries include: `timestamp`, `level`, `service`, `request_id`, `user_id`, `school_id`, `event`, `duration_ms`
- Request middleware: inject `request_id` (UUID) into each request context

**M0-5-T2: Health check endpoint**
- `GET /health`: checks DB + Redis connectivity, returns `{ status, db, redis, version }`
- `GET /ready`: same — used by Render readiness probe

**Acceptance criteria:**
- [ ] `GET /health` returns 200 with all services connected
- [ ] `GET /health` returns 503 if DB is down
- [ ] Every request produces structured JSON log line with request_id
- [ ] Log lines include user_id when authenticated

---

### EPIC M0-6: Student Onboarding Flow *(NEW v2.1)*

**User Story:** As a student, I want to complete a short learning style questionnaire and my subject diagnostics when I first join Kaihle, so the platform can personalise my experience from day one.

**Context:** This epic covers two sequential onboarding steps. Both must be completed before a student accesses the main dashboard. The sequence is: (1) Learning Profile Questionnaire → (2) Tier 1 Diagnostic Assessments. Neither step can be skipped.

#### Tasks

**M0-6-T1: Learning profile data model and API**
- `/backend/app/services/onboarding_service.py`:
  - `get_or_create_learning_profile(student_id, school_id) → StudentLearningProfile`
  - `save_questionnaire_response(student_id, responses: list[QuestionnaireResponse]) → StudentLearningProfile`
    - `QuestionnaireResponse`: `{ question_id: str, answer_key: str }` — answer_key maps to modality/work_style/interest
    - Scoring logic: compute `modality_scores` dict from Q1+Q2 answers (see §2.12 scoring)
    - Compute `work_style` dict from Q3–Q5 answers
    - Compute `interests` list from Q6–Q10 multi-select
    - Set `completed_at = now()`
  - `get_onboarding_status(student_id) → OnboardingStatus`:
    - Returns `{ learning_profile_complete: bool, diagnostics_complete: bool, overall: 'PENDING' | 'IN_PROGRESS' | 'COMPLETED' }`

`GET /api/v1/onboarding/status` (Student)
- Returns `OnboardingStatus` for current user

`GET /api/v1/onboarding/questionnaire` (Student)
- Returns the questionnaire definition (questions + answer options) — static, from config
- Response: `{ version: "v1", questions: [{ id, text, type: "single_select"|"multi_select", options: [{ key, text, modality_map? }] }] }`

`POST /api/v1/onboarding/questionnaire/submit` (Student)
- Body: `{ responses: [{ question_id, answer_key | answer_keys }] }`
- Calls `save_questionnaire_response`
- Returns completed `StudentLearningProfile`

`GET /api/v1/onboarding/learning-profile` (Student — own; Teacher — for students in their class)
- Returns the student's learning profile (modality_scores, work_style, interests)

**Acceptance criteria:**
- [ ] Unit test: questionnaire response with Q1=watch_video, Q2=see_diagrams → visual score = 1.0, others < 1.0
- [ ] Unit test: Q1=try_it_out, Q2=do_exercise → kinesthetic = 1.0
- [ ] Unit test: Q6–Q10 multi-select ["football","music"] → interests = ["football","music"]
- [ ] Unit test: `get_onboarding_status` returns `overall: 'COMPLETED'` only when both profile and diagnostics done
- [ ] Integration test: submit questionnaire → `student_learning_profiles` row created with correct scores and `completed_at` set
- [ ] Integration test: re-submitting questionnaire updates scores (does not create duplicate row)
- [ ] Integration test: teacher can read a student's learning profile via API

---

**M0-6-T2: Tier 1 auto-diagnostic trigger (Celery task)**
- `/backend/app/tasks/onboarding_tasks.py`:
  - `trigger_onboarding_diagnostics(student_id: UUID, class_id: UUID)` — Celery task
  - Fired automatically when a student is enrolled in a class (from M0-4-T3)
  - Logic:
    1. Load student's `grade_id` and `curriculum_id` from `student_profiles` and `classes`
    2. Load all subjects for that curriculum from `curriculum_subjects`
    3. For each subject, check if a Tier 1 diagnostic already exists for this student + subject (idempotent — do not create duplicate)
    4. Create `assessments` row: `{ class_id, assessment_type: 'DIAGNOSTIC', is_system_generated: TRUE, status: 'ACTIVE', curriculum_topic_id: NULL }` — NULL topic means broad sweep across all topics
    5. Question selection: sample questions from `question_bank` covering all `curriculum_topics` for that subject + grade, max 20 questions, weighted across topics
    6. Populate `assessment_selected_questions` bridge table
    7. Create `student_attempts` row for this student + assessment: `{ status: 'NOT_STARTED' }`
    8. Update `student_profiles.onboarding_diagnostic_status = 'IN_PROGRESS'`

**Acceptance criteria:**
- [ ] Unit test: student enrolled in a class with 3 subjects → 3 diagnostic assessments created
- [ ] Unit test: re-triggering for same student + class → no duplicate assessments created (idempotent)
- [ ] Unit test: questions sampled span all curriculum_topics for the grade (not just one topic)
- [ ] Unit test: each diagnostic has exactly 20 questions or all available questions if bank has < 20
- [ ] Integration test: `trigger_onboarding_diagnostics` fires → `assessments` rows created with `is_system_generated=TRUE`
- [ ] Integration test: `student_profiles.onboarding_diagnostic_status` set to `IN_PROGRESS` after task completes

---

**M0-6-T3: Onboarding completion tracking service**
- `/backend/app/services/onboarding_service.py` (extend from M0-6-T1):
  - `check_and_update_onboarding_complete(student_id: UUID)`:
    - Called after every Tier 1 diagnostic attempt submission
    - Checks: all `student_attempts` for `is_system_generated=TRUE` assessments for this student have `status='COMPLETED'`
    - If yes: set `student_profiles.onboarding_diagnostic_status = 'COMPLETED'`
  - This service method is called at the end of `POST /api/v1/attempts/{attempt_id}/submit` (see M1-4-T1) when the attempt is for a system-generated assessment

**Acceptance criteria:**
- [ ] Unit test: student with 3 Tier 1 diagnostics, 2 completed → status stays `IN_PROGRESS`
- [ ] Unit test: student completes final Tier 1 diagnostic → status set to `COMPLETED`
- [ ] Integration test: student submits last Tier 1 attempt → can now access `/student/dashboard` without redirect

---

**M0-6-T4: Onboarding UI (Student app)**
- Route: `/student/onboarding` — entry point, checks which step is next
- Step 1: `/student/onboarding/profile` — Learning Profile Questionnaire
  - Visual, card-based UI — not a plain HTML form
  - Progress indicator: "Question 3 of 10"
  - Q1–Q5: single-select card options with icons
  - Q6–Q10: multi-select interest tiles with emoji icons
  - "Next" / "Back" navigation, answers stored locally until final submit
  - Submit → loading spinner → "Your profile is ready!" confirmation → redirect to Step 2
- Step 2: `/student/onboarding/diagnostics` — Tier 1 Diagnostic Hub
  - Lists all Tier 1 diagnostic assessments (one per subject)
  - Each card: subject name, status badge (Not Started / In Progress / Completed), estimated time "~15 minutes"
  - Student takes each one in the same assessment UI as Tier 2 (M1-4-T4) — no separate UI needed
  - Progress summary: "2 of 3 subjects completed"
  - Once all completed: "You're all set!" screen → redirect to `/student/dashboard`
- Onboarding routes are accessible without `require_onboarding_complete` guard

**Acceptance criteria:**
- [ ] E2E test: student logs in for first time → redirected to `/student/onboarding/profile`
- [ ] E2E test: student completes questionnaire → profile saved → redirected to `/student/onboarding/diagnostics`
- [ ] E2E test: student completes all Tier 1 diagnostics → redirected to `/student/dashboard`
- [ ] E2E test: student refreshes mid-questionnaire → previous answers preserved (local state)
- [ ] E2E test: student who has already completed onboarding is NOT redirected to onboarding
- [ ] Unit test: interest tile multi-select correctly tracks selected/deselected state
- [ ] Responsive: all onboarding screens correct at 375px (mobile) viewport

---

## MILESTONE 0 — Definition of Done
- [ ] `docker-compose up` starts all services without manual steps
- [ ] CI pipeline runs on every PR, enforces coverage ≥ 80% on service files
- [ ] Full auth flow works end-to-end (register, login, magic link, refresh, logout)
- [ ] KaihleAdmin can create schools and invite users
- [ ] SchoolAdmin can create grades, classes, and enroll students
- [ ] Student enrollment triggers Tier 1 diagnostic creation (Celery task)
- [ ] Student onboarding gate enforced — cannot access dashboard until profile + diagnostics complete
- [ ] Learning profile questionnaire submits and stores correctly
- [ ] All M0 tests pass
- [ ] No hardcoded secrets anywhere in codebase
- [ ] M0-8 pre-flight fixes complete: User.school_id nullable, Celery asyncio.run fixed
- [ ] Test fixtures consolidated into shared conftest.py (no duplicate fixtures across test files)
- [ ] Email uniqueness is globally enforced: duplicate email returns 409 not 500
- [ ] `packages/ui` has Button, Card, Badge, Input, Skeleton, EmptyState, ProgressBar components
- [ ] `packages/types` exports getMasteryStyle() and scoreToPercent() from @kaihle/types
- [ ] `packages/api-client` re-exports apiClient (scaffold for M1+ typed hooks)
- [ ] Google Fonts (Nunito + Fraunces + Inter + Lora) load in all three apps
- [ ] Brand tokens (bg-brand-primary, bg-role-student-bg, bg-role-parent-bg, etc.) resolve correctly in student and parent apps
- [ ] CONSTITUTION §4 Rule 6 reads "≥ 90%" coverage threshold (matches actual CI config)
---

# MILESTONE 1: Core Diagnostics Flow
**Goal:** A student can complete their Tier 1 onboarding diagnostics AND a teacher can create and assign Tier 2 assessments. Results from both tiers are scored and gap states are populated.
**Exit criteria:** End-to-end: student completes Tier 1 diagnostic → gap_states populated → student accesses dashboard. Teacher creates Tier 2 diagnostic → student takes it → gap_states updated.
**Estimated duration:** 3–4 weeks

**IMPORTANT — Tier 1 vs Tier 2 in this milestone:**
- Tier 1 assessment *creation* is handled by the Celery task in M0-6-T2 — do not re-implement here
- Tier 1 assessment *taking* uses the same API and UI as Tier 2 (student attempt API + assessment UI)
- The `is_system_generated` flag on `assessments` is irrelevant to the student-facing flow — students take both tiers identically
- The only difference: after submitting a Tier 1 attempt, `check_and_update_onboarding_complete()` must be called (M0-6-T3)

---

### EPIC M1-1: Question Bank Import

**User Story:** As a developer, I want to import the founder's 7,000 existing questions into the database so that assessments can be generated from real curriculum-aligned content.

#### Tasks

**M1-1-T1: Question bank data model and import script**
- Define CSV/JSON import format: `{ question_text, question_type, options[], correct_answer, difficulty, grade_level, subject_code, curriculum_code, topic_name, subtopic_name }`
- Write `/backend/scripts/import_questions.py`:
  - Reads CSV/JSON file
  - For each question: resolve `subtopic_id` by joining `curriculum_code → curricula`, `subject_code → subjects`, `grade_level → grades`, `topic_name → topics`, then `curriculum_topics`, then `subtopic_name → subtopics`
  - Populate denormalised columns: `topic_id`, `subject_id`, `grade_id`
  - Insert into `question_bank` with `source='BANK'`
  - Log stats: total, inserted, skipped, errors
- Idempotent — `canonical_form` uniqueness prevents duplicates

**Acceptance criteria:**
- [ ] Script imports all 7,000 questions without errors
- [ ] Re-running produces zero new inserts
- [ ] Every question has valid `subtopic_id`
- [ ] Unit test: 5 sample questions → correct DB records

---

### EPIC M1-2: Curriculum Graph & RAG Ingestion

**User Story:** As the system, I want to parse Cambridge curriculum PDFs into a structured graph with embeddings so questions can be accurately mapped to learning objectives.

#### Tasks

**M1-2-T1: Curriculum graph seeding**
- `/backend/scripts/seed_curriculum_graph.py`:
  - Seeds full v2 hierarchy for Cambridge Lower Secondary (Grades 6–8) + IGCSE (Grades 9–10)
  - Subjects seeded: MATH, SCI, ENG (Lower Secondary); MATH, BIO, CHEM, PHY, ENG, ENGL (IGCSE)
  - Note: SCI (Integrated Science) is Lower Secondary only. BIO, CHEM, PHY, ENGL are IGCSE only.
  - Source: manually authored JSON at `/backend/data/curriculum/cambridge_v1.json`
  - Inserts in dependency order: `curricula → subjects → grades → curriculum_subjects → topics → curriculum_topics → subtopics → subtopic_prerequisites`
  - Idempotent — upsert on unique constraints
  - **Must run before `ingest_curriculum.py`**

**Acceptance criteria:**
- [ ] JSON covers cambridge_lower (MATH/SCI/ENG × Grades 6–8) + igcse (MATH/BIO/CHEM/PHY/ENG/ENGL × Grades 9–10)
- [ ] SCI does not appear under igcse; BIO/CHEM/PHY/ENGL do not appear under cambridge_lower
- [ ] All subtopic_prerequisites correctly linked (193 subtopics total)
- [ ] Unit test: subtopic prerequisite traversal returns all upstream prerequisites
- [ ] Script idempotent — re-running produces zero new inserts

---

**M1-2-T2: Curriculum PDF ingestion script**
- `/backend/scripts/ingest_curriculum.py`:
  - Input: directory of Cambridge PDF files
  - Extract text using `pdfplumber`
  - Chunk: 500 tokens, 50 token overlap (`tiktoken`)
  - Resolve `subtopic_id` from seeded table (log warning + skip if unresolvable)
  - Insert `curriculum_chunks`
  - Generate embeddings via Google `text-embedding-004` (batch 100 chunks per call)
  - Store `subtopics.embedding` for each subtopic touched
  - Resumable — skips rows where `embedding IS NOT NULL`

**Acceptance criteria:**
- [ ] Processes 50-page Cambridge Math PDF without errors
- [ ] Chunks average 450–550 tokens
- [ ] Every `curriculum_chunk` has non-null `embedding`
- [ ] Every touched `subtopic` has non-null `embedding`
- [ ] Integration test: cosine similarity search on "quadratic equations" returns chunks with similarity > 0.7

---

### EPIC M1-3: Assessment Creation (Teacher — Tier 2)

**User Story:** As a teacher, I want to create a diagnostic assessment for my class so my students can take a structured assessment.

#### Tasks

**M1-3-T1: Assessment generation service**
- `/backend/app/services/assessment_service.py`:
  - `create_assessment(class_id, teacher_id, config: AssessmentConfig) → Assessment`
  - `AssessmentConfig`: `{ assessment_type, curriculum_topic_id: UUID | None, num_questions, question_types, difficulty_range }`
  - Sets `is_system_generated = FALSE` always (teacher-created = Tier 2)
  - Question selection: weighted random from `question_bank`
  - Fallback: LLM generation if bank insufficient
  - Populate `assessment_selected_questions` bridge

**M1-3-T2: Assessment API routes**

`POST /api/v1/assessments` (Teacher)
`GET /api/v1/assessments/{assessment_id}` (Teacher, SchoolAdmin)
`POST /api/v1/assessments/{assessment_id}/publish` (Teacher)
`GET /api/v1/classes/{class_id}/assessments` (Teacher, Student in class)

**Acceptance criteria:**
- [ ] Integration test: teacher creates 10-question Grade 9 Math assessment
- [ ] Integration test: published assessment visible to students
- [ ] Integration test: unpublished not visible to students
- [ ] Integration test: `is_system_generated` is always FALSE for teacher-created assessments
- [ ] Unit test: LLM fallback called when bank has insufficient questions

---

**M1-3-T3: Assessment creation UI (Teacher app)**
- Route: `/teacher/assessments/new`
- Step 1: Select class, subject, grade level
- Step 2: Select topics from checklist
- Step 3: Configure questions, types, difficulty
- Step 4: Preview questions — teacher can remove
- Step 5: Set deadline, publish

**Acceptance criteria:**
- [ ] E2E test: teacher creates 10-question Grade 9 Math diagnostic and publishes
- [ ] E2E test: question preview shown before publishing
- [ ] E2E test: removing a question reduces count

---

### EPIC M1-4: Student Diagnostic Flow (Both Tiers)

**User Story:** As a student, I want to take any diagnostic assessment (Tier 1 or Tier 2) in a focused, mobile-friendly interface.

#### Tasks

**M1-4-T1: Student attempt API**

`POST /api/v1/assessments/{assessment_id}/start` (Student)
- Creates `student_attempt` record
- Prevents duplicate (returns existing if in-progress)

`POST /api/v1/attempts/{attempt_id}/responses` (Student)
- Body: `{ question_id, answer_given, time_taken_ms }`
- Scores immediately (rule-based MCQ; queues LLM for short-answer)
- Returns: `{ scored: bool, next_question_available: bool }`

`POST /api/v1/attempts/{attempt_id}/submit` (Student)
- Marks attempt as COMPLETED
- Triggers async Celery task: `calculate_gap_states(attempt_id)`
- **NEW v2.1:** If `assessment.is_system_generated = TRUE`, also calls `check_and_update_onboarding_complete(student_id)` after gap states update
- Returns: `{ attempt_id, status: "completed", score_summary: { total, correct, pct } }`

`GET /api/v1/attempts/{attempt_id}/results` (Student — own; Teacher — any in class)

**Acceptance criteria:**
- [ ] Integration test: student starts and submits 10-question MCQ assessment
- [ ] Integration test: submitting Tier 1 attempt triggers `check_and_update_onboarding_complete`
- [ ] Integration test: submitting Tier 2 attempt does NOT trigger onboarding check
- [ ] Integration test: duplicate start returns existing attempt

---

**M1-4-T2: Answer scoring service**
- `/backend/app/services/scoring_service.py`:
  - `score_response(question, answer) → ScoringResult`
  - MCQ / True-False: exact match → `is_correct, score: 0|1, scored_by: "rule"`
  - Short answer: LLM via `LLMProvider.complete(task="answer_scoring")` → `score: 0.0–1.0, scored_by: "llm"`
  - LLM timeout 3s → queue retry, return `score: null`

**Acceptance criteria:**
- [ ] Unit test: MCQ correct → `{ is_correct: true, score: 1.0, scored_by: "rule" }`
- [ ] Unit test: short answer → LLM scoring
- [ ] Unit test: LLM timeout → `score: null` + queues retry
- [ ] Performance test: 40 concurrent MCQ submissions within 200ms

---

**M1-4-T3: Gap state calculation (Celery task)**
- `/backend/app/tasks/gap_tasks.py`:
  - `calculate_gap_states(attempt_id: UUID)` Celery task
  - Load all responses for attempt
  - For each response, get `subtopic_id` via `question_bank.subtopic_id`
  - Upsert `gap_states`:
    - `mastery_score = rolling average of last 3 attempt scores for that subtopic`
    - `confidence = function of attempt_count`
    - `last_assessed_at = now`
    - `attempt_count += 1`

**Acceptance criteria:**
- [ ] Unit test: first attempt, 3 questions same subtopic → mastery = mean of 3 scores
- [ ] Unit test: second attempt on same subtopic → rolling average (last 3 per attempt)
- [ ] Integration test: submit → gap_states updated within 5 seconds
- [ ] Unit test: subtopic with 0 answers → no gap_state row created

---

**M1-4-T4: Student assessment UI**
- Route: `/student/assessments` — lists active assessments (Tier 2 only — Tier 1 shown in onboarding)
- Route: `/student/assessments/{assessment_id}/take`:
  - Question card, MCQ options or text input
  - Progress bar: Q3 of 10
  - Timer displayed (not enforced)
  - Back/Next navigation, saves locally before submit
  - Submit confirmation modal
  - Score summary screen
- Mobile-first layout
- **Same UI used for Tier 1 in onboarding flow (M0-6-T4)**

**Acceptance criteria:**
- [ ] E2E test: student takes 10-question MCQ, submits, sees score summary
- [ ] E2E test: student refreshes mid-assessment — resumes from last answered
- [ ] E2E test: completed assessment shows "Completed" badge, cannot restart
- [ ] Responsive: correct at 375px and 768px

---

## MILESTONE 1 — Definition of Done
- [ ] 7,000 questions importable via script
- [ ] Cambridge curriculum PDFs ingestable with embeddings stored
- [ ] Tier 1 diagnostics created automatically on enrollment (M0)
- [ ] Student completes Tier 1 diagnostics via onboarding UI (M0-6-T4)
- [ ] Teacher can create and publish Tier 2 assessments
- [ ] Both Tier 1 and Tier 2 assessments score correctly and populate gap_states
- [ ] Onboarding completion correctly unlocks student dashboard
- [ ] All M1 tests pass

---

# MILESTONE 2: Gap Map & Teacher Dashboard
**Goal:** Teachers see a real-time colour-coded heatmap of class performance by curriculum subtopic. Students see their own gap profile.
**Exit criteria:** Teacher views class gap map for a completed assessment and can identify which subtopics to address.
**Estimated duration:** 2–3 weeks

---

### EPIC M2-1: Gap Map API

**User Story:** As a teacher, I want to see a heatmap of my class's mastery scores per curriculum subtopic.

#### Tasks

**M2-1-T1: Gap map aggregation service**
- `/backend/app/services/gap_service.py`:
  - `get_class_gap_map(class_id, subject_id, grade_id) → ClassGapMap`
  - Loads `gap_states` for all students, joined with `subtopics → curriculum_topics → topics`
  - Returns: `{ subtopic_id, topic_name, subtopic_name, student_scores: [{ student_id, mastery_score, confidence }], class_average, student_count }`
  - `get_student_gap_map(student_id, subject_id) → StudentGapMap`

**M2-1-T2: Gap map routes**

`GET /api/v1/classes/{class_id}/gap-map` (Teacher)
- Query params: `subject_id`, `grade_id`

`GET /api/v1/students/{student_id}/gap-map` (Student — own; Teacher — own class; Parent — own child)

**Acceptance criteria:**
- [ ] Integration test: 5 students with gap_states → correct averages per subtopic
- [ ] Integration test: nodes with no data excluded from response
- [ ] Integration test: teacher cannot get gap map for another class (403)
- [ ] Performance test: 40 students × 50 nodes → response < 500ms

---

**M2-1-T3: Gap Map heatmap UI (Teacher app)**
- Route: `/teacher/classes/{class_id}/gap-map`
- Subject + grade selector tabs
- Heatmap grid: rows = curriculum topics, columns = students
- Cell colour: Red (< 0.4), Amber (0.4–0.7), Green (> 0.7), Grey (not assessed)
- Hover tooltip: `{ student_name, mastery_score, last_assessed_date }`
- Class average row
- Sortable columns
- Click cell → side panel: student's full gap profile for that topic
- **NEW v2.1:** Side panel shows student's learning profile summary (dominant modality icon, top interests) — read only
- Export to CSV button

**Acceptance criteria:**
- [ ] E2E test: teacher views gap map → cells render with correct colours
- [ ] E2E test: hover tooltip shows correct data
- [ ] E2E test: click red cell → side panel opens with student gap detail + learning style icon
- [ ] Unit test: mastery=0.35 → red, 0.55 → amber, 0.85 → green
- [ ] Performance: renders 40 × 50 grid in < 2 seconds

---

**M2-1-T4: Student gap profile UI (Student app)**
- Route: `/student/my-progress`
- Subject tabs
- Visual: progress rings or bar chart per topic cluster
- Green = strong, amber = developing, red = needs work
- Each topic expandable to show subtopics
- "Suggested next steps" section (links to study plans — wired in M3)

**Acceptance criteria:**
- [ ] E2E test: student views progress after diagnostic → correct colours
- [ ] Unit test: topic expandable shows subtopics
- [ ] Accessibility: colour is not only indicator — text label also shown

---

## MILESTONE 2 — Definition of Done
- [ ] Teacher sees colour-coded gap map for their class
- [ ] Student sees their personal gap profile
- [ ] Gap map reflects latest assessment results in real-time
- [ ] Teacher gap map side panel shows student learning profile
- [ ] All M2 tests pass

---

# MILESTONE 3: Smart Study Plans
**Goal:** The system generates personalised study plans for identified gaps, using the student's learning profile to curate resources and contextualise quizzes.
**Exit criteria:** Teacher assigns a study plan to a student with a gap → student sees curated resources matched to their learning style + a quiz with personally relevant examples.
**Estimated duration:** 3–4 weeks

---

### EPIC M3-1: Content Curation Engine

**User Story:** As the system, I want to find the best 2–3 educational resources for each curriculum gap AND personalise them to the student's learning style.

#### Tasks

**M3-1-T1: Content source index (with learning profile weighting)**
- `/backend/app/ai/content_curator.py`:
  - `curate_resources(subtopic: Subtopic, student_id: UUID, school_id: UUID) → list[Resource]`
  - **NEW v2.1 signature:** accepts `student_id` to load learning profile
  - Sources (priority): YouTube Data API v3, Khan Academy topic API, static curated index JSON
  - YouTube query: `f"{subject_name} {subtopic_name} {curriculum_code} tutorial"`
  - Base alignment scoring: embed resource title+description → cosine similarity vs `subtopic.embedding` → filter > 0.72
  - **NEW v2.1 — Learning profile resource weighting:**
    - Load `student_learning_profiles` for student
    - Apply modality multipliers to base alignment score:
      - `modality_scores.visual > 0.6` → VIDEO resources get score × 1.3
      - `modality_scores.reading_writing > 0.6` → ARTICLE resources get score × 1.3
      - `modality_scores.kinesthetic > 0.6` → INTERACTIVE resources get score × 1.3
      - `modality_scores.auditory > 0.6` → VIDEO resources (with audio explanation) get score × 1.2
    - Multipliers are cumulative if student scores high on multiple modalities
  - Return top 3 resources sorted by final weighted score
  - Cache in Redis: key `content:{subtopic_id}:{student_id}`, TTL 24 hours
  - **Note:** If student has no learning profile (edge case), fall back to base alignment score only — do not error

**Acceptance criteria:**
- [ ] Unit test: student with visual=1.0 → VIDEO resources ranked above ARTICLE for same base score
- [ ] Unit test: student with reading_writing=1.0 → ARTICLE resources ranked above VIDEO
- [ ] Unit test: student with no learning profile → falls back gracefully, returns 3 resources
- [ ] Unit test: cache hit on second call — no API call made
- [ ] Unit test: resources with duration outside 3–15 min filtered out
- [ ] Integration test: full curation for 5 subtopics with learning profiles completes in < 10 seconds

---

**M3-1-T2: Quiz generation service (with interest injection)**
- `/backend/app/ai/quiz_generator.py`:
  - `generate_quiz(subtopic: Subtopic, student_mastery: float, student_id: UUID) → Quiz`
  - **NEW v2.1 signature:** accepts `student_id` to load learning profile
  - Prompt strategy: subtopic `learning_objectives` + 3 most relevant `curriculum_chunks` (pgvector cosine similarity)
  - LLM task: `"question_generation"` → Gemini 2.5 Flash
  - Output: 5 questions — 4 MCQ + 1 short answer, calibrated to `student_mastery`
  - **NEW v2.1 — Interest injection:**
    - Load `student_learning_profiles.interests` for student
    - If interests list is non-empty, take the top 2 interests and append to prompt:
      ```
      Personalisation context: Where possible, frame question scenarios using topics
      this student finds interesting: {interests[0]}, {interests[1]}.
      Do NOT force the interest if it doesn't fit the subtopic — academic accuracy is
      always more important than personalisation.
      ```
    - If student has no profile or empty interests → omit personalisation section from prompt
  - Validate output with Pydantic before storing

**Acceptance criteria:**
- [ ] Unit test: student with interests=["football","music"] → prompt contains "football" and "music"
- [ ] Unit test: student with empty interests → prompt does NOT contain personalisation section
- [ ] Unit test: student with no profile → quiz still generated without error
- [ ] Unit test: `student_mastery=0.2` → "foundational" difficulty in prompt
- [ ] Unit test: `student_mastery=0.8` → "application" difficulty in prompt
- [ ] Unit test: LLM invalid JSON → retry once → log error → raise exception
- [ ] Integration test: generate quiz for "Algebraic Fractions" → 5 valid questions returned

---

### EPIC M3-2: Study Plan Lifecycle

**User Story:** As a teacher, I want to assign a personalised study plan to a student for a specific gap.

#### Tasks

**M3-2-T1: Study plan service**
- `/backend/app/services/study_plan_service.py`:
  - `create_study_plan(student_id, subtopic_id, class_id, assigned_by) → StudyPlan`
  - **NEW v2.1:** Passes `student_id` to `curate_resources()` and `generate_quiz()` so both functions receive the learning profile
  - Stores in `study_plans`, `study_plan_resources`, `study_plan_quizzes`

**M3-2-T2: Study plan routes**

`POST /api/v1/classes/{class_id}/study-plans` (Teacher)
- Body: `{ student_ids: list[UUID] | "all", subtopic_id: UUID }`
- Creates plans for each student, queues as Celery task
- Returns: `{ status: "generating", task_ids: [...] }`

`GET /api/v1/study-plans/{plan_id}` (Student — own; Teacher — own class)
`GET /api/v1/students/{student_id}/study-plans` (Student — own; Teacher — own class; Parent — own child)

`POST /api/v1/study-plans/{plan_id}/quiz/submit` (Student)
- Body: `{ responses: [{ question_index, answer }] }`
- Scores quiz, updates `study_plan_quizzes.score`
- Triggers gap_state recalculation

**Acceptance criteria:**
- [ ] Integration test: teacher assigns plan to 5 students → 5 plans, each with 3 resources and 5-question quiz
- [ ] Integration test: resources reflect student's dominant modality (video for visual learners)
- [ ] Integration test: quiz prompt includes interests for students who have them
- [ ] Integration test: student submits quiz → gap_state updated
- [ ] Unit test: `create_study_plan` when curator returns 0 resources → plan created with warning

---

**M3-2-T3: Study plan UI (Student app)**
- Route: `/student/study-plans` — list, grouped by subject
- Plan card: subtopic name, 3 resource thumbnails, quiz status
- Route: `/student/study-plans/{plan_id}`:
  - Section 1: Resources (matched to your learning style — small badge "Matched to your style")
  - Section 2: Practice Quiz (after student marks resources as "watched")
  - After quiz: score + per-question explanation

**Acceptance criteria:**
- [ ] E2E test: student sees plan, watches resource, takes quiz, sees score
- [ ] E2E test: completed plan shows score on card
- [ ] Unit test: quiz UI shows MCQ options and text input for short answer

---

**M3-2-T4: Study plan assignment UI (Teacher app)**
- Route: `/teacher/classes/{class_id}/gap-map` → "Assign Study Plan" button from gap map cell
- Modal: confirm subtopic, select students (default: all with mastery < 0.6)
- "Generate Plans" → loading → success toast

**Acceptance criteria:**
- [ ] E2E test: teacher clicks "Assign Study Plan" → modal opens with correct subtopic
- [ ] E2E test: "Generate Plans" triggers generation → success toast
- [ ] Unit test: student selection defaults to mastery < 0.6

---

## MILESTONE 3 — Definition of Done
- [ ] Teacher can assign study plans from gap map
- [ ] Resources are personalised based on student's learning modality
- [ ] Quiz scenarios use student's personal interests where applicable
- [ ] Quiz submission updates gap state
- [ ] All M3 tests pass

---

# MILESTONE 4: Teacher Copilot (Lesson Planning)
**Goal:** Every Monday, each teacher receives an AI-generated weekly lesson plan based on their class's current gap map.
**Exit criteria:** Teacher receives lesson plan email, views it on dashboard, edits it, marks as used.
**Estimated duration:** 2–3 weeks

---

### EPIC M4-1: Lesson Plan Generation

#### Tasks

**M4-1-T1: Weekly lesson plan Celery beat task**
- `/backend/app/tasks/lesson_plan_tasks.py`:
  - `generate_weekly_lesson_plans()` — Celery beat, every Monday 06:00
  - For each active class with at least one completed assessment:
    1. Load class gap map
    2. Identify top 2 subtopics with lowest average mastery
    3. Cluster students: Group A (< 0.4), Group B (0.4–0.7), Group C (> 0.7)
    4. Build prompt with class context + gap summary + grouping + RAG chunks
    5. Call LLM (`task="lesson_plan"`, GPT-4.1, max 15 seconds)
    6. Store in `lesson_plans`
    7. Send notification email to teacher via Resend

**Acceptance criteria:**
- [ ] Unit test: identifies top 2 weakest subtopics correctly
- [ ] Unit test: student grouping — [0.2, 0.3, 0.55, 0.65, 0.9] → A:2, B:2, C:1
- [ ] Unit test: LLM timeout → retry once → log error → no email sent
- [ ] Integration test: beat trigger → plans stored for all active classes within 5 minutes
- [ ] Integration test: teacher receives email with lesson plan link

---

**M4-1-T2: Lesson plan schema and storage**
- Lesson plan JSON structure stored in `lesson_plans.generated_plan`:
```json
{
  "week_start": "2026-03-02",
  "focus_subtopic_ids": ["uuid1", "uuid2"],
  "class_summary": "60% of students struggle with algebraic fractions...",
  "student_groups": {
    "A": { "count": 8, "focus": "Foundational" },
    "B": { "count": 12, "focus": "Developing" },
    "C": { "count": 5, "focus": "Extension" }
  },
  "lesson_structure": {
    "starter_10min": "...",
    "main_activity_30min": { "group_A": "...", "group_B": "...", "group_C": "..." },
    "plenary_10min": "...",
    "homework": "..."
  },
  "teacher_notes": "..."
}
```

**Acceptance criteria:**
- [ ] Unit test: missing required field raises Pydantic validation error
- [ ] Integration test: `lesson_plans` row written with correct `class_id`, `week_start`, `teacher_id`

---

**M4-1-T3: Lesson plan API routes**

`GET /api/v1/classes/{class_id}/lesson-plans` (Teacher)
`GET /api/v1/lesson-plans/{plan_id}` (Teacher of that class)
`PATCH /api/v1/lesson-plans/{plan_id}` (Teacher) — stores `teacher_edits`
`POST /api/v1/lesson-plans/{plan_id}/regenerate` (Teacher)
`PATCH /api/v1/lesson-plans/{plan_id}/status` (Teacher) — body: `{ status: "used" | "archived" }`

**Acceptance criteria:**
- [ ] Integration test: teacher fetches this week's plan — gets correct JSON
- [ ] Integration test: teacher patches edits — stored in `teacher_edits` column
- [ ] Integration test: different class teacher cannot fetch this plan (403)

---

**M4-1-T4: Lesson plan UI (Teacher app)**
- Route: `/teacher/classes/{class_id}/lesson-plans`
- Current week's plan as primary card
- Plan view: gap summary, student groups (3 columns), lesson structure tabs, resources
- "Edit" → inline editing, save to `teacher_edits`
- "Regenerate" → confirmation modal → spinner → refresh
- "Mark as Used" button
- Notification badge in nav when new plan ready

**Acceptance criteria:**
- [ ] E2E test: teacher sees new lesson plan badge on Monday
- [ ] E2E test: teacher views 3 student group tabs with activities
- [ ] E2E test: teacher edits starter activity → saved → shows updated text
- [ ] E2E test: teacher clicks Regenerate → new plan loads

---

## MILESTONE 4 — Definition of Done
- [ ] Weekly lesson plans auto-generated every Monday
- [ ] Teacher receives email and sees plan in dashboard
- [ ] Teacher can edit and mark plans as used
- [ ] All M4 tests pass

---

# MILESTONE 5: Parent Portal
**Goal:** Parents receive weekly AI-generated progress narratives for their child and can view a simplified gap map.
**Exit criteria:** Parent logs in, sees child's narrative and gap summary.
**Estimated duration:** 2 weeks

---

### EPIC M5-1: Parent Narratives

#### Tasks

**M5-1-T1: Parent narrative generation task**
- `/backend/app/tasks/parent_tasks.py`:
  - `generate_parent_narratives()` — Celery beat, every Sunday 18:00
  - For each student with gap_state updated in last 7 days:
    1. Load student gap map
    2. Calculate week-over-week delta
    3. Identify top 2 improvements and top 2 areas needing work
    4. Build prompt: student name, grade, subject, gap summary, deltas
    5. Call LLM (Gemini Flash, 150-word limit)
    6. Store in `parent_report_snapshots`
    7. Send email to all parents linked via `parent_student`

**Acceptance criteria:**
- [ ] Unit test: narrative prompt contains student first name, grade, subject, top 2 gaps, top 2 improvements
- [ ] Unit test: delta calculation — mastery 0.3 → 0.65 = "improved significantly"
- [ ] Unit test: student with no parent linked → skip, no error
- [ ] Integration test: narrative stored in `parent_report_snapshots` with correct `student_id` and `week_start`
- [ ] Integration test: parent email sent via Resend mock

---

**M5-1-T2: Parent portal API**

`GET /api/v1/parent/children` (Parent)
`GET /api/v1/parent/children/{student_id}/reports` (Parent — own child)
`GET /api/v1/parent/children/{student_id}/gap-map` (Parent — own child)
- Simplified gap map: plain-language labels, no numeric scores

**Acceptance criteria:**
- [ ] Integration test: parent sees own child's reports only (403 for others)
- [ ] Integration test: gap map uses plain language labels ("Strong", "Developing", "Needs Work")

---

**M5-1-T3: Parent portal UI**
- Route: `/parent/dashboard` — child selector, latest narrative card
- Route: `/parent/children/{student_id}/progress`:
  - Simplified gap map: topic rows, traffic light circles
  - Weekly reports: accordion, click to expand narrative
- Mobile-first

**Acceptance criteria:**
- [ ] E2E test: parent logs in → sees child's name and latest narrative
- [ ] E2E test: parent clicks topic → sees green/amber/red with plain-language label
- [ ] E2E test: parent with 2 children can switch between them
- [ ] Unit test: traffic light renders correct colour for each mastery band

---

## MILESTONE 5 — Definition of Done
- [ ] Weekly parent reports auto-generated every Sunday
- [ ] Parents receive email with link to full report
- [ ] Parents can view simplified gap map
- [ ] All M5 tests pass

---

# MILESTONE 6: Analytics, Billing & Polish
**Goal:** School admin sees usage analytics; billing tiers enforced; platform ready for first live school deployment.
**Exit criteria:** First real school (Bali pilot) is live.
**Estimated duration:** 2–3 weeks

---

### EPIC M6-1: School Admin Analytics Dashboard

#### Tasks

**M6-1-T1: Analytics service and routes**
- `/backend/app/services/analytics_service.py`:
  - `get_school_analytics(school_id) → SchoolAnalytics`:
    - `total_students`, `active_students_last_7_days`
    - `assessments_completed`, `avg_class_mastery_by_subject`
    - `study_plans_assigned`, `study_plans_completed`
    - `lesson_plans_generated`, `lesson_plans_used`
    - **NEW v2.1:** `onboarding_completion_rate` — % of enrolled students who have completed both profile + Tier 1 diagnostics

`GET /api/v1/schools/{school_id}/analytics` (SchoolAdmin, KaihleAdmin)

**Acceptance criteria:**
- [ ] Integration test: school with 5 students, 2 assessments → correct counts
- [ ] Integration test: `onboarding_completion_rate` reflects actual profile + diagnostic status
- [ ] Performance test: analytics with 500 students returns in < 1 second

---

**M6-1-T2: Analytics UI (School Admin)**
- Route: `/admin/analytics`
- KPI cards: active students, assessments completed, avg mastery, onboarding completion rate
- Chart: mastery trends by subject over last 4 weeks (Recharts)
- Table: class-by-class breakdown

**Acceptance criteria:**
- [ ] E2E test: school admin sees correct student count
- [ ] Unit test: KPI card renders correct value

---

### EPIC M6-2: Billing Tier Enforcement

**M6-2-T1: Tier limit enforcement**
- `/backend/app/core/billing.py`:
  - `check_student_limit(school_id, current_count, tier) → bool`
  - `is_trial_expired(school: School) → bool`
  - Returns 402 Payment Required if limit exceeded or trial expired

| Tier | Max active students | Trial days |
|---|---|---|
| trial | 30 | 15 |
| starter | 100 | — |
| growth | 500 | — |
| scale | unlimited | — |

**Acceptance criteria:**
- [ ] Integration test: trial school at 30 students cannot enroll 31st (402)
- [ ] Integration test: trial past 15 days returns 402 on login
- [ ] Unit test: `is_trial_expired` with `created_at` 16 days ago → True

---

### EPIC M6-3: Production Readiness

**M6-3-T1: Rate limiting**
- `slowapi` rate limiter:
  - `/api/v1/auth/login`: 10 req/min per IP
  - `/api/v1/auth/magic-link`: 3 req/min per email
  - `/api/v1/attempts/*/responses`: 60 req/min per user
  - LLM-backed routes: 20 req/min per school

**M6-3-T2: Error handling**
- Global FastAPI exception handler
- Structured error response: `{ error_code, message, details }`
- Never expose stack traces to client

**M6-3-T3: Data backup**
- Enable Render managed PostgreSQL daily automated backups (7-day retention)
- Document restore procedure in `RUNBOOK.md`

**M6-3-T4: Seed data for pilot school**
- `seed_pilot_school.py`:
  - Creates first Bali pilot school record
  - Creates school admin user
  - Adopts Cambridge Lower Secondary (Grades 6–8) and IGCSE (Grades 9–10) for the pilot school
  - Subjects: MATH, SCI, ENG (Lower Secondary); MATH, BIO, CHEM, PHY, ENG, ENGL (IGCSE)
  - Note: curriculum graph must already be seeded by seed_curriculum_graph.py (M1-2-T1)
  - Imports matching questions from bank

**M6-3-T5: Pre-launch checklist**
- [ ] All environment variables set in Render production
- [ ] Custom domain + SSL configured
- [ ] `GET /health` returns 200 in production
- [ ] Email delivery tested (magic link, lesson plan, parent report)
- [ ] One full user journey tested manually: school admin → teacher → student (onboarding + diagnostic + study plan) → parent
- [ ] Celery beat running (lesson plans + parent reports)
- [ ] `RUNBOOK.md` documents: deploy procedure, DB backup/restore, common errors

---

## MILESTONE 6 — Definition of Done
- [ ] School admin sees analytics dashboard with onboarding completion rate
- [ ] Billing tier limits enforced
- [ ] Rate limiting active on all auth and LLM routes
- [ ] Production Render deployment live with first pilot school data
- [ ] All M6 tests pass
- [ ] Manual end-to-end journey verified in production

---

## Part 4: LLM Prompts Reference (v2.1)

All prompts stored in `/backend/app/ai/prompts/`. Each is a `.jinja2` template.

### Question Generation Prompt
```
System: You are an expert {{curriculum_code}} curriculum question writer
        for {{subject_name}} at Grade {{grade_level}}.
Generate exactly {{num_questions}} questions on the subtopic: {{subtopic_name}}.
Learning objectives: {{learning_objectives}}
Difficulty: {{difficulty_label}} (scale {{difficulty_min}}–{{difficulty_max}})

Return ONLY valid JSON — no preamble, no markdown:
{"questions": [{"question_text": "...", "type": "MCQ|SHORT_ANSWER|TRUE_FALSE",
  "options": [{"key":"A","text":"..."},...] or null,
  "correct_answer": "...", "explanation": "..."}]}

Curriculum context:
{{rag_context}}

{% if interests %}
Personalisation context: Where possible, frame question scenarios using topics
this student finds interesting: {{interests[0]}}, {{interests[1]}}.
Do NOT force the interest if it doesn't fit — academic accuracy is always priority.
{% endif %}
```

### Answer Scoring Prompt
```
System: You are a {{curriculum_code}} {{subject_name}} examiner.
        Score the student answer from 0.0 to 1.0.
        Return ONLY valid JSON — no preamble.

Question: {{question_text}}
Expected answer: {{correct_answer}}
Student answer: {{student_answer}}

{"score": 0.0-1.0, "justification": "one sentence"}
```

### Study Plan Quiz Generation Prompt
```
System: You are an educational content curator for {{curriculum_code}} {{subject_name}}.
        Generate a 5-question practice quiz.
        Student mastery: {{mastery_pct}}% on: {{subtopic_name}}.
        Calibration: {{difficulty_instruction}}

Learning objectives:
{{learning_objectives}}

Curriculum context:
{{rag_context}}

{% if interests %}
Personalisation: Frame scenarios using student interests where natural: {{interests|join(', ')}}.
{% endif %}

Return ONLY valid JSON:
{"questions": [{"question_text":"...", "type":"MCQ|SHORT_ANSWER",
  "options":[...],"correct_answer":"...","explanation":"..."}]}
```

### Lesson Plan Generation Prompt
```
System: You are an expert {{curriculum_code}} {{subject_name}} teacher
        planning a 50-minute lesson. Return ONLY valid JSON.

Class: Grade {{grade_level}}, {{total_students}} students.
Focus subtopics: {{focus_subtopics}}
Class gap summary: {{gap_summary}}

Groups:
- A ({{group_a_count}} students, mastery < 40%): foundational
- B ({{group_b_count}} students, mastery 40–70%): developing
- C ({{group_c_count}} students, mastery > 70%): extension

Curriculum context: {{rag_context}}

Return JSON:
{"week_start":"YYYY-MM-DD","class_summary":"...","lesson_structure":{
  "starter_10min":"...","main_activity_30min":{"group_A":"...","group_B":"...","group_C":"..."},
  "plenary_10min":"...","homework":"..."},"teacher_notes":"..."}
```

### Parent Narrative Prompt
```
System: You are a friendly school progress reporter.
        Write in warm, plain language. Maximum 150 words. No jargon.

Student: {{student_first_name}}, Grade {{grade_level}}
Subject: {{subject_name}}
This week:
- Showed improvement in: {{improvements}}
- Still working on: {{gaps}}
- Next steps: {{next_steps}}
```

---

## Part 5: Non-Functional Requirements

| Requirement | Target | How Enforced |
|---|---|---|
| API response time (non-LLM) | p95 < 300ms | Render metrics + pytest performance tests |
| API response time (LLM) | Per SLA table in §1.6 | Timeout enforcement in LLMProvider.complete() |
| Max class size | 40 students | Performance tests at 40-student load |
| Max schools (v1 infra) | 10 | Render plan sized for this |
| Uptime | 99% | Render automatic restarts |
| Language | English only | No i18n library required in v1 |
| Data isolation | Per-school (school_id filter) | Service layer filter + integration tests |
| Test coverage | ≥ 80% on service files | pytest-cov CI gate |
| Secret management | .env / Render secrets | Pre-commit secret scanner |

---

## Part 6: Environment Variables Reference

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

# LLM Providers
OPENAI_API_KEY=<key>
ANTHROPIC_API_KEY=<key>
YOUTUBE_DATA_API_KEY=<key>

# LLM Routing
LLM_QUESTION_GEN_PROVIDER=gemini
LLM_LESSON_PLAN_PROVIDER=openai
LLM_ANSWER_SCORING_PROVIDER=gemini

# Celery
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# Storage
AWS_ACCESS_KEY_ID=<key>
AWS_SECRET_ACCESS_KEY=<key>
AWS_S3_BUCKET=kaihle-assets
AWS_REGION=ap-southeast-1

# App
ENVIRONMENT=development|staging|production
LOG_LEVEL=INFO
SENTRY_DSN=<optional, add in M6>
```

---

## Part 7: Task Summary by Milestone

| Milestone | Duration | Key Deliverable |
|---|---|---|
| M0: Foundations | 3–4 weeks | Auth, DB, Docker, CI/CD, student onboarding flow, Tier 1 auto-diagnostic trigger |
| M1: Diagnostics | 3–4 weeks | Student completes Tier 1; teacher creates Tier 2; gap_states populated |
| M2: Gap Map | 2–3 weeks | Teacher heatmap (with learning style), student progress view |
| M3: Study Plans | 3–4 weeks | Personalised resources + interest-contextualised quiz per gap |
| M4: Teacher Copilot | 2–3 weeks | Weekly AI lesson plans |
| M5: Parent Portal | 2 weeks | Weekly parent narrative + simplified gap view |
| M6: Launch Polish | 2–3 weeks | Billing, analytics (with onboarding rate), production deployment |
| **Total** | **~20 weeks** | **First pilot school live** |

---

*Kaihle Product Plan v2.1 · Kramer (Technical Lead) · March 2026 · CONFIDENTIAL — FOR ENGINEERING USE*
*Supersedes v2.0. Key additions: Two-tier diagnostic model (§1.11), Student Learning Profile (§1.12, §2.12), Epic M0-6, updated M3-1-T1 and M3-1-T2.*
