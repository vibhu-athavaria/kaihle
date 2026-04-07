# Task File Authoring

## Before Writing Any Task File
- Check the repo first — confirm the gap is not already implemented.
- All decisions must be made before the task file is written.
- Verify every API endpoint against the live API — do not invent route paths.

## Task File Requirements
- Declare `Executor: Coding agent` or `Executor: Human (name)`.
- Zero human-action steps if addressed to a coding agent.
- ID format: `M{N}-{E}-T{N}` with a matching branch name.
- Must include TDD spec (Rule 20): exact test function names, file paths, mock setup, arrange-act-assert structure.

## Design Rules
- ALL business logic lives in `/services/`. Route handlers are thin: validate → call service → return.
- Every non-curriculum table MUST have `school_id`. All service methods MUST filter by `school_id`.
- Cross-school access returns 403, not 404.
- All LLM calls MUST go through `app.ai.providers.router.get_provider(task=...)`. No direct SDK imports.
- API contracts finalized in M0-10 are frozen. Do not alter without explicit approval and CONSTITUTION.md update.

## Doubt Filing
If blocked by an architectural, design, or curriculum doubt:
- File `docs/doubts/DOUBT-{timestamp}.md` with: persona routing, category, blocking status, options considered.
- Maximum one doubt per task. Analysis required before filing.
