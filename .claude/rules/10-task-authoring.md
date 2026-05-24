# Task File Authoring

## Before Writing Any Task File
- Check the repo first — confirm the gap is not already implemented.
- All decisions must be made before the task file is written.
- Verify every API endpoint against the live API — do not invent route paths.

## Task File Requirements
- Declare who the executor is: coding agent or a named human.
- Zero human-action steps if addressed to a coding agent.
- ID format must match the project's task numbering convention (check CONSTITUTION or task file).
- Must include TDD spec: exact test function names, file paths, mock setup, arrange-act-assert structure.

## Design Rules
- All business logic lives in the service layer. Route handlers are thin: validate → call service → return.
- Every write endpoint must enforce multi-tenancy. Cross-tenant access returns 403, not 404.
- Do not invent or alter API contracts without explicit approval and a CONSTITUTION update.

## Doubt Filing
If blocked by an architectural, design, or domain doubt:
- File a structured doubt document with: category, blocking status, options considered.
- Maximum one doubt per task. Analysis required before filing. Check CONSTITUTION for the doubt file path.
