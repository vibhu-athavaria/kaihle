# Git Workflow

## Starting Any Task
Execute in order before writing any code:
```bash
git checkout main
git pull origin main
git checkout -b <branch-name>
```
Working directly on `main` is PROHIBITED. Code written before this sequence MUST NOT be committed.

## Branch Naming
Format: `M{N}-{E}-T{N}_{type}/{short-description}`
- `{type}` = `feature` | `fix` | `chore` | `migration`
- `{short-description}` = lowercase, hyphen-separated

Examples: `M0-1-T1_feature/init-monorepo`, `M0-2-T1_migration/initial-schema`

Branch MUST match the task file being implemented. Non-conforming branches MUST NOT be pushed.

## Commit Format
- `feat(scope): description`
- `fix(scope): description`
- `chore(scope): description`
- `migration(scope): description`

Migration files MUST be committed together with their model changes — never separately.
Debug code, commented-out blocks, and `TODO` markers MUST NOT appear in committed production code.
Broken or untested code MUST NOT be committed.

## Task Completion — NOT done until ALL true
1. All acceptance criteria in the task file are met — not self-assessed.
2. Test coverage >= 90% on service files — enforced by test runner.
3. `git status` is clean.
4. New environment variables documented in `.env.example`.
5. Branch pushed to origin.
6. PR open against `main` with: title matching branch/task ID, description covering what was built, decisions made, and how to verify.

Merging directly to `main` without a PR is PROHIBITED.
