# AGENTS.md

Instruction file for Kilo/Claude Code sessions. Start with `CLAUDE.md` (project overview, commands, tech stack), then `docs/CONSTITUTION.md` (absolute rules, architecture). This file covers operational gotchas those docs don't.

## Operational Gotchas

### Docker & Data Safety
- **NEVER run `docker compose down -v`** or any command that destroys `postgres_data` without explicit written confirmation from Vibhu. Use `make down` instead.
- Docker Compose must be running before any local backend/frontend dev — Postgres (port 5433) and Redis are dependencies.
- After `docker compose up -d`, always run `alembic upgrade head` before doing anything.

### Pre-Commit Hooks (what runs on `git commit`)
Backend: ruff, ruff-format, mypy, pytest unit (≥80% coverage on services)
Frontend: prettier, tsc (per-app), jest (per-app)
- **Jest hook often times out at 120s** — retry with `--timeout 180000` or let it re-run.
- **Prettier auto-fix**: `cd frontend && pnpm -w exec prettier --write <file>` (NOT plain `prettier --write`).

### Package Management
- Backend: uses `uv` (NOT pip). Commands: `uv sync --all-extras`, `uv run pytest`, `uv run mypy app/`.
- Frontend: pnpm workspace monorepo. Install from `frontend/`. Per-app commands use `pnpm --filter "@kaihle/<app>" <cmd>`.

### Running Checks Before Commit
```bash
# Backend (from backend/)
uv run ruff check --fix app/ && uv run ruff format app/ && uv run mypy app/ && uv run pytest app/tests/unit/ -v

# Frontend per-app typecheck (from the app dir, e.g. frontend/apps/school-admin)
npx tsc --noEmit

# Frontend per-app tests
pnpm --filter "@kaihle/school-admin" exec jest --verbose
```

## Architecture Reminders

### Route → Service Pattern
Routes in `backend/app/api/v1/routes/` are thin — validate input, call a service, return response. ALL business logic lives in `backend/app/services/`. Do not add logic to route handlers.

### Five Frontend Apps — Zero Cross-Role Code
Each `frontend/apps/<role>/` serves exactly one role. Shared code belongs in `frontend/packages/`. School Admin pages MUST NOT live in `apps/teacher/`.

## Key Reference Files
| Purpose | File |
|---|---|
| Project overview, commands, tech stack | `CLAUDE.md` |
| Absolute rules, architecture | `docs/CONSTITUTION.md` |
| Design tokens, loading states, modals, accessibility | `docs/design/DESIGN_SYSTEM.md` |
| Canonical DB schema (source of truth) | `docs/kaihle_v2_1_schema.sql` |
| Personal workflow (tasks, PRs, branches) | `CLAUDE.local.md` |
| Agent rules (testing, git, security) | `.claude/rules/` |
| Render setup checklist | `README.md` §Render |

## Non-Obvious Conventions
- **No pgvector embeddings in v1** — `subtopic_content` table (structured SQL) replaces cosine similarity. Do not add embedding calls.
- **Questions come from `question_bank` table**, NOT LLM generation. MCQ scoring is deterministic string comparison.
- **Test naming**: `test_<what>_when_<condition>_then_<expected>` (CONSTITUTION.md Rule 7).
- **Never write migration SQL by hand** — use `alembic revision --autogenerate`.
- **API contracts are frozen** once published. Breaking changes require `/api/v2/` + ADR.
- **`# type: ignore` is prohibited** in production code — resolve via `mypy.ini`.
- **No additional UI kits** (MUI, Chakra, shadcn, etc.) without a documented ADR.
- **`getMasteryStyle(score)`** from `packages/types/src/mastery.ts` — never inline mastery color logic.