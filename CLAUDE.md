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
that removes postgres_data without explicit written confirmation from Vibhu.<!-- BEGIN BYTEROVER RULES -->

# Workflow Instruction

You are a coding agent focused on one codebase. Use the brv CLI to manage working context.

## Core Rules

- **Start from memory.** First retrieve relevant context with `brv query`, then read only the code that's still necessary.
- **Keep a local context tree.** The context tree is your local memory store—update it with `brv curate` when you learn something valuable.

## When to Query

Use `brv query` **before** starting any code task that requires understanding the codebase:
- Writing, editing, or modifying code
- Understanding how something works
- Debugging or troubleshooting issues
- Making architectural decisions

## When to Curate

Use `brv curate` **after** you learn or create something valuable:
- Wrote or modified code
- Discovered how something works
- Made architectural/design decisions
- Found a bug root cause or fix pattern

After curating, use `brv curate view <logId>` to verify what was stored (logId printed on completion).

## Execution Mode: wait by default

Default is `brv curate "..."` (no flag) — **wait for it to finish** before continuing. Any follow-up (query, search, read, or a later curate that builds on this one) may depend on the curated data being live.

Use `--detach` only when BOTH are true:
1. No remaining step in this turn reads/queries/references this data, AND no later curate in this turn builds on it.
2. User explicitly said not to wait — addressed to the agent, e.g. "don't wait", "don't block on this", "fire and forget", "move on without waiting". Excludes "run in background" / "run async" (agent self-narrates these).

If user phrasing is ambiguous → wait. If either condition is uncertain → wait.

Size/duration is NOT a reason to `--detach`. "Looks like the last step" is NOT a reason — it's a guess.

After `--detach`, report "queued" (not "saved") and save the `logId`. Before any later read of that data, run `brv curate view <logId>` and wait for `status: completed`. Detach errors are silent.

## Context Tree Guideline

Good context is:
- **Specific** ("Use React Query for data fetching in web modules")
- **Actionable** (clear instruction a future agent/dev can apply)
- **Contextual** (mention module/service, constraints, links to source)
- **Sourced** (include file + lines or commit when possible)

---
# ByteRover CLI Command Reference

## Available Commands

- `brv curate` - Curate context to the context tree. **Blocking default — wait for it to finish before continuing** (returns `logId` on completion).
- `brv curate <ctx> --detach` - Queue curate and return `logId` immediately. Use ONLY when BOTH (a) no remaining step in this turn reads this data or builds on it, AND (b) user explicitly said not to wait ("don't wait", "fire and forget"). See Workflow.
- `brv curate view` - List curate history (last 10 entries by default)
- `brv curate view <logId>` - Full detail for a specific entry: all files and operations performed (logId returned by `brv curate`)
- `brv curate view --detail` - List entries with their file operations visible (no logId needed)
- `brv query` - Query and retrieve information from the context tree
- `brv status` - Show CLI status and project information

Run `brv query --help` for query instruction and `brv curate --help` / `brv curate view --help` for curation options.

---
Generated by ByteRover CLI for Claude Code
<!-- END BYTEROVER RULES -->