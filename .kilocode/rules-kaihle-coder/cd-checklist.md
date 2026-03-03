# Coder — Task Completion Checklist

A task is NOT done until every item below is checked.
Do not tell the orchestrator a task is complete until this entire list passes.

---

## Code Quality

- [ ] `ruff check backend/` — zero errors
- [ ] `mypy backend/app/` — zero errors
- [ ] No `print()` statements — structlog only
- [ ] No wildcard imports (`from x import *`)
- [ ] No hardcoded secrets, URLs, or magic strings

## Tests

- [ ] Every acceptance criterion in the task file has a corresponding test
- [ ] All tests follow naming: `test_<what>_when_<condition>_then_<expected>`
- [ ] `pytest --cov=app/services --cov-fail-under=90` passes
- [ ] Integration tests use a real test DB — not mocked
- [ ] Constraint and uniqueness tests exist for any new DB constraint

## Database

- [ ] No hand-written SQL in migration files — autogenerate only
- [ ] Migration includes a `downgrade()` path
- [ ] Migration committed together with model changes (not separately)
- [ ] Nullable columns have a comment explaining why NULL is valid

## Git

- [ ] `git status` is clean — no uncommitted or untracked files
- [ ] Branch name follows: `M{N}-{E}-T{N}_{type}/short-description`
- [ ] All new environment variables added to `.env.example`
- [ ] No debug code, commented-out blocks, or TODO markers in committed code

## Final

- [ ] Branch pushed to `origin`
- [ ] PR opened against `main` with title matching branch name and task ID
- [ ] PR description covers: what was built, decisions made, how to verify