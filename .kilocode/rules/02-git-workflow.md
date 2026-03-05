# Git Workflow — AGENTS.md Compliant

## Branch Format (non-negotiable)
M{N}-{E}-T{N}_{type}/{short-description}

## Real M1 Examples
M1-1-T1_feature/question-bank-import
M1-2-T1_feature/curriculum-graph-seeding
M1-2-T2_feature/curriculum-pdf-ingestion
M1-3-T1_feature/assessment-generation-service
M1-3-T2_feature/assessment-api-routes
M1-4-T2_feature/answer-scoring-service
M1-4-T3_migration/gap-state-calculation    ← migration type if schema change

## Task Start (run in this exact order, no exceptions)
git checkout main
git pull origin main
git checkout -b M{N}-{E}-T{N}_{type}/{short-description}

## Pre-Push Gate (ALL must pass — no push until they do)
docker compose up -d
pytest --cov=app --cov-fail-under=90 --cov-report=term-missing
ruff check . && ruff format --check .
alembic check

## Commit Format
feat(M{N}-{E}-T{N}): {what was built}
fix(M{N}-{E}-T{N}): {what was fixed}
migration(M{N}-{E}-T{N}): {schema change description}

## Migration Rule
Migration file MUST be in the SAME commit as the model changes it supports.

## PR Requirements (from AGENTS.md — task is NOT done without these)
Title:   Branch name exactly
Body:
  ## What was built
  ## Decisions made
  ## How to verify (exact commands)
  ## New env vars added to .env.example: [list or "none"]

## Post-Push
Run: bash scripts/sourcery_loop.sh {PR_NUMBER}
Wait for exit code:
  0 → task complete, report COMPLETE to orchestrator
  1 → max iterations or hard failure, report BLOCKED
  2 → never returned to you directly (script handles the loop internally)
