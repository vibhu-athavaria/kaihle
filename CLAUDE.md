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

```bash
cd backend
uv pip install -e .
uvicorn app.main:app --reload

pytest app/tests/unit/ -v
pytest app/tests/integration/ -v
pytest app/tests/unit/path/to/test_file.py::test_function_name -v

ruff check --fix app/
ruff format app/
mypy app/

alembic revision --autogenerate -m "description"
alembic upgrade head
alembic downgrade -1
```

### Frontend (pnpm)

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
```

### Docker (full stack)

```bash
docker compose up -d
docker compose exec backend alembic upgrade head
docker compose exec backend python -m scripts.seed_curriculum_graph
docker compose exec backend python -m scripts.seed_test_data
docker compose down
docker compose down -v   # stop + wipe DB
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
