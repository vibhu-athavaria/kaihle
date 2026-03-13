---
name: code-core
description: >
  Core implementation skill for Code mode. Use this when writing or
  modifying backend or frontend code. It helps you obey project
  governance, follow coding standards implied by the governance docs,
  implement the current task file, and produce tests that satisfy its
  acceptance criteria.
---

# Code Core – How to Implement

## When to use this skill

Use this skill whenever you are in Code mode and need to:
- Implement or modify backend services, routes, models, tasks, or scripts.
- Implement or modify frontend components, pages, or UI flows.
- Add or update tests to satisfy a task file’s acceptance criteria.
- Apply coding standards, git workflow, and CI rules while coding.

## Source of truth

Treat these as authoritative, in this order:

1. The current task file (`docs/tasks/MN/MN-E-TN*.md`) – defines exactly what to build and how it is tested.
2. `CONSTITUTION.md` – tech stack, repo structure, absolute rules (no deviations).
3. `AGENTS.md` – global engineering governance (MUST / MUST NOT).

If any of these conflict, follow the order above and explicitly call out the conflict.

## Mandatory first actions (before writing code)

Before writing or changing any code, you MUST:

1. Confirm you have the correct task file from the orchestrator.
2. Read the canonical schema file (for example `kaihle_v2_1_schema.sql`) and state the exact table and column names this task will touch.
3. Execute the git startup sequence in a shell (or equivalent commands in your environment):
   - `git checkout main`
   - `git pull origin main`
   - `git checkout -b <branch-name>`
4. Describe, in your own words:
   - Files you will create.
   - Files you will modify.
   - Function signatures and/or components you will implement.

Never work directly on `main`, never work from a stale local branch, and never commit code written before this sequence.

## Core coding behaviour

Always:
- Implement exactly what the task file (and any Architect design) specifies. If unclear, stop and ask for clarification.
- Keep route handlers thin:
  - Validate input → call a service method → return response.
  - No business logic, DB queries, or LLM calls directly in route handlers.
- Enforce multi-tenancy and auth:
  - For non‑curriculum tables, always filter by `school_id` in service queries.
  - Use the existing auth/role abstractions; do not roll your own.
- Use the LLM abstraction:
  - Call the central LLM provider/router abstraction, never call provider SDKs directly.
- Keep configuration external:
  - Read config from the central settings/config module and environment variables.
  - Missing required config MUST fail fast at startup, never silently default.
- For migrations:
  - Use the project’s migration tooling (e.g. Alembic autogenerate) and review the result.
  - Always include a downgrade path unless explicitly documented as irreversible.
- For logging:
  - Use structured logging at appropriate levels.
  - Never use `print` for production logging and never log secrets or sensitive PII.

Never:
- Introduce wildcard imports, implicit ORM loading that can cause N+1 queries, or undeclared cascades.
- Introduce nullable columns or enum changes without clear justification and tests.
- Bypass tests, linters, or CI gates just to "get it to pass".
- Use inline `# type: ignore` comments in production code. Instead, configure mypy in `mypy.ini`
  by adding a `[mypy-<module>.*]` section with `ignore_missing_imports = true` and/or `ignore_errors = true`.

## Tests and quality

You are responsible for implementing tests that make the task pass, based on the task file and any Architect test plan.

- Test philosophy:
  - Tests MUST assert behaviour and observable outcomes, not internal implementation details.
  - Use a consistent naming convention such as `test_what_when_condition_then_expected`.
- Coverage:
  - Backend service files MUST reach the project’s required coverage (for example ≥ 80%) before the task is considered done.
- Unit tests:
  - Cover happy paths, validation errors, edge cases, and error handling for each service method or function you add or change.
- Integration tests:
  - Use the real test database and boundary layers where feasible (no over‑mocking of the data layer).
  - For new persistent models, cover:
    - Creation and lifecycle.
    - All uniqueness and integrity constraints.
    - Cascades/relationships where defined.
    - Failure paths and validation errors.
- Mapping to acceptance criteria:
  - Every acceptance criterion in the task file MUST have at least one test that proves it.

If tests, linters, migrations, or security checks fail, you MUST:
- Stop, surface the exact failure, and fix it.
- Never disable or weaken checks to make CI green.

## Git workflow while coding

Follow the git rules from governance:

- Branch names MUST be of the form:
  - `MN-E-TNtype-short-description`
  - Example: `M1-4-T3feature-gap-state-calculation`
- Commits MUST use conventional commit format:
  - `feat(scope): description`
  - `fix(scope): description`
  - `chore(scope): description`
  - `migration(scope): description`
- Each commit should be focused; do not mix unrelated changes.

A task is NOT complete until:
- All acceptance criteria in the task file are met by tests.
- Required coverage on service files is achieved.
- `git status` is clean.
- New env vars are documented in `.env.example`.
- Branch is pushed and a PR is opened as per governance rules.

## Output format for this skill

When responding in Code mode using this skill:

1. **Task understanding**
   - Briefly restate what you are implementing and which files/tables it affects.

2. **Plan**
   - List files to create or modify.
   - List functions/components/routes to implement with their signatures.

3. **Implementation notes**
   - Any important details on multi-tenancy, LLM usage, migrations, or logging you will follow.

4. **Tests**
   - Enumerate the unit and integration tests you will add or update to satisfy the task’s acceptance criteria.

5. **Git and CI**
   - State the intended branch name and confirm that tests/linters/formatters must pass before completion.
