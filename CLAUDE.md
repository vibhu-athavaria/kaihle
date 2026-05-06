# CLAUDE.md

Guidance for Claude Code when working in this repository.

@docs/CONSTITUTION.md
@docs/design/DESIGN_SYSTEM.md
@CLAUDE.local.md
---

## What Is Kaihle?

AI-powered learning diagnostics platform for international schools (Cambridge, IB). See `docs/CONSTITUTION.md` for full project spec, tech stack, repo structure, rules, and architecture decisions.

---

## Commands

### Backend (Python)

Uses `uv` — NOT pip. Always prefix with `uv run` in a live environment.

```bash
cd backend
uv sync --all-extras
uvicorn app.main:app --reload

uv run pytest app/tests/unit/ -v
uv run pytest app/tests/integration/ -v
uv run pytest app/tests/unit/path/to/test_file.py::test_function_name -v

uv run ruff check --fix app/
uv run ruff format app/
uv run mypy app/

alembic revision --autogenerate -m "description"
alembic upgrade head
alembic downgrade -1
```

### Frontend (pnpm)

Install from `frontend/`. Per-app commands use `pnpm --filter`.

```bash
cd frontend
pnpm install

pnpm dev:teacher        # port 3001
pnpm dev:student        # port 3002
pnpm dev:parent         # port 3003
pnpm dev:school-admin   # port 3004
pnpm dev:kaihle-admin   # port 3005
pnpm dev                # all apps

pnpm build
pnpm lint
pnpm test
pnpm typecheck

# Per-app typecheck (run from the app directory, e.g. frontend/apps/school-admin)
npx tsc --noEmit

# Per-app tests
pnpm --filter "@kaihle/school-admin" exec jest --verbose

# Prettier fix (must use pnpm -w exec, NOT plain prettier)
cd frontend && pnpm -w exec prettier --write <file>
```

### Docker (full stack)

Postgres runs on port **5433** locally. Docker must be running before any backend/frontend dev.

```bash
docker compose up -d
docker compose exec backend alembic upgrade head   # always run after up
docker compose exec backend python -m scripts.seed_curriculum_graph
docker compose exec backend python -m scripts.seed_test_data
docker compose down       # safe — preserves postgres_data
# docker compose down -v  # NEVER without explicit confirmation from Vibhu
```

### Pre-Commit Hooks

On `git commit`, hooks run automatically:
- **Backend:** ruff, ruff-format, mypy, pytest unit (≥80% coverage on services)
- **Frontend:** prettier, tsc (per-app), jest (per-app)

Jest hook often times out at 120s — retry the commit or run `jest --testTimeout 180000` manually. Always run the full pre-commit check manually before committing:

```bash
# Backend (from backend/)
uv run ruff check --fix app/ && uv run ruff format app/ && uv run mypy app/ && uv run pytest app/tests/unit/ -v
```

---

## Key Source Paths

```
backend/app/api/v1/routes/    ← thin handlers only — delegate to services
backend/app/services/         ← ALL business logic
backend/app/ai/providers/router.py  ← only LLM file; LiteLLM, no provider SDKs
backend/app/ai/prompts/       ← .jinja2 prompt templates
frontend/packages/ui/         ← shared components, layouts, Modal
frontend/packages/auth/       ← tokenStore, useAuth, route guards
frontend/packages/types/      ← getMasteryStyle() + shared interfaces
```

---

## LLM Task Routing

All LLM calls go through `backend/app/ai/providers/router.py`. See `docs/CONSTITUTION.md §8` for the full task table and rules.

| Task | Model |
|---|---|
| `gap_classification` | `gemini/gemini-2.5-flash` |
| `study_plan` | `gpt-4.1-mini` |
| `lesson_plan` | `openrouter/anthropic/claude-sonnet-4-6` |
| `student_pack` | `gemini/gemini-2.5-pro` |

NEVER run docker compose down -v, docker volume rm, or any variant 
that removes postgres_data without explicit written confirmation from Vibhu.