# Coder — Coding Standards

---

## Mandatory First Actions

Before writing a single line of code you MUST:

```
Step 1: Confirm you have received the task file from the orchestrator.
        If you have NOT received it — STOP and ask the orchestrator for it.

Step 2: read_file("kaihle_v2_1_schema.sql")
        State the exact column names for every table this task touches.
```

Before writing code, state:
1. Files you will CREATE
2. Files you will MODIFY
3. Function signatures you will implement

---

## Git Workflow

### Before Writing Any Code

Execute this sequence in order. Do not skip or reorder.

```bash
git checkout main
git pull origin main
git checkout -b <branch-name>
```

- Working directly on `main` is **PROHIBITED**.
- Starting on a stale local branch without pulling latest `main` is **PROHIBITED**.
- Any code written before this sequence **MUST NOT** be committed.

### Branch Naming

Branch names **MUST** follow exactly:

```
M{N}-{E}-T{N}_{type}/{short-description}
```

- `M{N}` — milestone (e.g. `M0`, `M1`)
- `{E}` — epic number (e.g. `1`, `4`)
- `T{N}` — task number (e.g. `T1`, `T3`)
- `{type}` — one of: `feature`, `fix`, `chore`, `migration`
- `{short-description}` — lowercase, hyphen-separated

Valid examples:
```
M0-1-T1_feature/init-monorepo
M1-4-T3_feature/gap-state-calculation
M6-3-T2_fix/error-handler
M0-2-T1_migration/initial-schema
```

Branch names not matching this format **MUST NOT** be pushed to `origin`.

### Commit Hygiene

Use conventional commit format on every commit:

- `feat(scope): description` — new functionality
- `fix(scope): description` — bug fix
- `chore(scope): description` — config, tooling, documentation
- `migration(scope): description` — schema migration only

Additional rules:
- Migration files **MUST** be committed together with the model changes they support.
  Committing them separately is **PROHIBITED**.
- Debug code, commented-out blocks, and `TODO` markers **MUST NOT** appear in committed code.
- Unrelated changes **MUST NOT** be bundled into the same commit.
- Broken or untested code **MUST NOT** be committed at any point.

---

## Non-Negotiable Coding Rules

### school_id Filter

Every service method querying non-curriculum tables MUST filter by `school_id`.

```python
# CORRECT
async def get_assessments(self, school_id: UUID, ...) -> list[Assessment]:
    query = select(Assessment).where(Assessment.school_id == school_id)

# PROHIBITED — missing school_id filter
async def get_assessments(self) -> list[Assessment]:
    query = select(Assessment)
```

Exempt tables: `curricula`, `subjects`, `grades`, `topics`, `curriculum_topics`,
`subtopics`, `curriculum_chunks`.

### LLM Calls

```python
# CORRECT
from app.ai.providers.router import get_provider
provider = get_provider(task="question_generation")
response = await provider.complete(request)

# PROHIBITED — never import provider SDKs directly
from app.ai.providers.gemini import GeminiProvider
```

### Config and Secrets

```python
# CORRECT
from app.core.config import settings
key = settings.openai_api_key

# PROHIBITED
key = "sk-..."
```

Missing required configuration **MUST** cause startup failure — never silent defaults
for critical systems (auth, persistence, external providers).

### Migrations

```bash
# CORRECT
alembic revision --autogenerate -m "add is_system_generated to assessments"
# Review the generated file, then:
alembic upgrade head

# PROHIBITED — never write migration SQL by hand
```

Every migration **MUST** include a `downgrade()` path.
Migration files **MUST** be committed together with the model changes they support.

### Logging

```python
# CORRECT
import structlog
logger = structlog.get_logger()
logger.info("assessment_created", assessment_id=str(assessment.id))

# PROHIBITED
print("assessment created")
```

Sensitive data (passwords, tokens, PII) **MUST NOT** be logged.

### Routes — Thin Only

```python
# CORRECT — route validates input, calls service, returns response
@router.post("/assessments")
async def create_assessment(payload: AssessmentCreate, db=Depends(get_db)):
    return await AssessmentService(db).create(payload)

# PROHIBITED — business logic in route handler
@router.post("/assessments")
async def create_assessment(payload: AssessmentCreate, db=Depends(get_db)):
    existing = await db.execute(select(Assessment).where(...))
    if existing.scalar():
        raise HTTPException(...)
    ...
```

### Error Handling

- Fail fast on invalid state or impossible conditions.
- Swallowing exceptions without logging is **PROHIBITED**.
- Generic `except` blocks without re-raising or structured handling are **PROHIBITED**.
- User-facing errors **MUST** map to explicit, predictable responses without leaking internals.
- Cross-school access **MUST** return `403`, not `404` — never leak existence of another
  school's data.

### Explicit Over Implicit

The following are **PROHIBITED** without documented justification in code comments:

- Implicit ORM relationship loading that can trigger unbounded queries.
- Nullable columns without explicit justification and documented meaning of `NULL`.
- Implicit cascade behaviours (delete, update) without explicit configuration and tests.
- Wildcard imports (`from x import *`).
- Silent fallback behaviour for critical paths.

### Transactions

- All database write operations **MUST** occur within an explicit transactional context.
- Multi-step changes that must succeed or fail together **MUST** be a single transaction.
- Implicit or auto-commit behaviour for critical writes is **PROHIBITED**.
- Background job writes **MUST** be idempotent or guarded by an idempotency key —
  assume tasks can be retried and executed more than once.

### Performance

- N+1 query patterns in hot paths are **PROHIBITED**.
- All list/search endpoints **MUST** implement pagination or explicit bounds.
- Queries in hot paths **MUST** be backed by appropriate indexes.
- External calls (AI models, third-party services) **MUST** have explicitly configured
  timeouts and clear failure/fallback behaviour.

---

## Test Standards

- Test naming: `test_<what>_when_<condition>_then_<expected>`
- Coverage **MUST** be >= 90% on all `/backend/app/services/` files before reporting done.
- Tests **MUST** assert behaviour and observable outcomes — not implementation details.
- Integration tests **MUST** use a real test database — do not mock the data layer.
- For any new persistent model, tests **MUST** cover: creation and lifecycle, all uniqueness
  and constraint behaviour, cascade behaviour, and failure/validation paths.
- Every acceptance criterion in the task file **MUST** have a corresponding test.

---

## CI Failure Behaviour

If any of the following occur, **ABORT immediately** — do not work around, do not proceed:

- Test suite fails or coverage drops below 90% on service files.
- Linters or formatters fail (`ruff`, `mypy`).
- Schema drift detected between code and migration history.
- Migrations fail to apply in a clean environment.
- Static analysis or security checks report high-severity issues.

Surface the failure, its cause, and the full failing command output to the orchestrator.
**NEVER** disable tests, linters, or checks to make CI pass.

