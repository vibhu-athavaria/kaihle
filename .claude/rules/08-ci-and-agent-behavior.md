# CI Gates and Agent Failure Behavior

## Non-Negotiable CI Gates
A change MUST NOT be merged or considered complete if any of the following occur:
- Test suite fails or service coverage < 90%.
- Linters or formatters fail (ruff, mypy, eslint, prettier).
- Schema drift detected between models and migration history.
- Migrations fail to apply in a clean environment.
- Duplicate or conflicting model or migration files detected.
- Static analysis or security checks report high-severity issues without a documented waiver.

## Agent Behavior Under Failure
When any CI gate fails, the agent MUST:
- Abort immediately — no further implementation.
- Surface the failure, its cause, and the exact failing command output.
- NOT work around governance by disabling tests, linters, or checks.
- NOT proceed to the next task until the failure is resolved.
