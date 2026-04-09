# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## What Is Kaihle?

Kaihle is an AI-powered learning diagnostics platform for international schools (Cambridge, IB curricula). It identifies student knowledge gaps, generates personalised study plans, and gives teachers, school admins, and parents real-time visibility into student progress.

**Authoritative references — read before any significant work:**
- `docs/CONSTITUTION.md` — schema, architecture rules, enums, frozen API contracts
- `docs/design/DESIGN_SYSTEM.md` — component rules, layout variants, colour tokens

@docs/CONSTITUTION.md
@docs/design/DESIGN_SYSTEM.md

---

## Commands

### Backend (Python)

```bash
cd backend

# Install deps
uv pip install -e .

# Dev server
uvicorn app.main:app --reload

# Tests
pytest app/tests/unit/ -v
pytest app/tests/integration/ -v
pytest app/tests/unit/path/to/test_file.py::test_function_name -v  # single test

# Lint / format / typecheck
ruff check --fix app/
ruff format app/
mypy app/

# Migrations
alembic revision --autogenerate -m "description"  # generate — never hand-write SQL
alembic upgrade head
alembic downgrade -1
```

### Frontend (Node / pnpm)

```bash
cd frontend

pnpm install

# Run individual apps
pnpm dev:teacher        # port 3001
pnpm dev:student        # port 3002
pnpm dev:parent         # port 3003
pnpm dev:school-admin   # port 3004
pnpm dev:kaihle-admin   # port 3005

# Run all
pnpm dev

# Build / lint / test / typecheck (all apps)
pnpm build
pnpm lint
pnpm test
pnpm typecheck
```

### Docker (full stack)

```bash
docker compose up -d
docker compose exec backend alembic upgrade head
docker compose exec backend python -m scripts.seed_curriculum_graph
docker compose exec backend python -m scripts.seed_test_data
docker compose down       # stop
docker compose down -v    # stop + wipe volumes (DB reset)
```

---

## Architecture

### Backend — FastAPI (Python 3.12)

- **`app/api/v1/routes/`** — thin route handlers only. Validate input, call a service, return response. Zero business logic here.
- **`app/services/`** — ALL business logic lives here. 90%+ test coverage required.
- **`app/models/`** — SQLAlchemy 2.x async ORM models (one file per domain).
- **`app/schemas/`** — Pydantic v2 request/response schemas.
- **`app/core/`** — `config.py` (env vars), `security.py`, `database.py`, `redis.py`.
- **`app/ai/providers/router.py`** — the **only** file in `providers/`. LiteLLM handles all provider adaption; no separate `openai.py` / `gemini.py` files exist or should be created.
- **`app/ai/prompts/`** — Jinja2 templates for LLM prompts.
- **`app/tasks/`** — Celery tasks (onboarding, lesson_plan, gap, parent).
- **`scripts/`** — Seed scripts (`seed_curriculum_graph.py`, `seed_test_data.py`).

### Frontend — React 18 + Vite + TypeScript (monorepo)

Five completely isolated apps, one per role:

| App | Port | Role |
|---|---|---|
| `apps/teacher` | 3001 | TEACHER |
| `apps/student` | 3002 | STUDENT |
| `apps/parent` | 3003 | PARENT |
| `apps/school-admin` | 3004 | SCHOOL_ADMIN |
| `apps/kaihle-admin` | 3005 | KAIHLE_ADMIN |

**App isolation is critical** — zero cross-role code inside any `apps/` directory. Shared code belongs only in `packages/`:

| Package | Purpose |
|---|---|
| `@kaihle/ui` | Shared Tailwind components (PasswordSetupForm, LoginForm, layouts, Modal) |
| `@kaihle/auth` | Token store, `useAuth`, `PrivateRoute`, `OnboardingRoute`, `PasswordSetupRoute` |
| `@kaihle/types` | Shared TypeScript interfaces + `getMasteryStyle()` |
| `@kaihle/api-client` | Axios instance + typed API hooks |

### Database — PostgreSQL 16 + pgvector

- **Curriculum tables** (`curricula`, `subjects`, `grades`, `topics`, `subtopics`) — school-agnostic, no `school_id`.
- **All other tables** — must have `school_id`; all service queries filter by it (except `KAIHLE_ADMIN`).
- `kaihle_v2_1_schema.sql` is the single source of truth for schema. If it conflicts with a task file, the SQL wins.

### LLM Routing

All LLM calls go through `app/ai/providers/router.py` via `litellm.acompletion()`. Feature code never imports provider SDKs directly.

| Task | Default model |
|---|---|
| `gap_classification` | `gemini/gemini-2.5-flash` |
| `study_plan` | `gpt-4.1-mini` |
| `lesson_plan` | `openrouter/anthropic/claude-sonnet-4-6` |
| `student_pack` | `gemini/gemini-2.5-pro` |
