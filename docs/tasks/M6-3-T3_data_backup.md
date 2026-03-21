# M6-3-T3 — Data Backup Configuration + RUNBOOK
**Milestone:** M6 · **Epic:** M6-3 · **Task:** T3
**Depends on:** Production Render deployment exists
**Parallel with:** M6-3-T1, M6-3-T2
**Estimated effort:** 2 hours

---

## Context

This task has no application code. It is a configuration and documentation task.
Render.com provides automated PostgreSQL backups at the infrastructure level. This
task enables them, verifies they work, and creates the RUNBOOK document that any
operator can follow without needing to understand the codebase.

---

## Deliverables

### 1. Enable Render PostgreSQL Backups

In the Render dashboard, navigate to the PostgreSQL service. Under "Backups," enable
daily automated backups. Set the retention period to 7 days (appropriate for a pilot
school with low data volume). Verify that at least one successful backup exists before
marking this task complete.

### 2. Test the Restore Procedure

Create a throwaway Render PostgreSQL service. Restore the most recent backup to it.
Connect to the restored database using `psql` and verify that key tables exist and
contain the expected row counts. Delete the throwaway service after verification.
Document the exact steps taken in RUNBOOK.md.

### 3. Create `docs/RUNBOOK.md`

The RUNBOOK must be written so that a technically competent person with no knowledge
of Kaihle can follow it to perform operational tasks. Every procedure must be a
numbered list of exact commands or UI steps — no "you know what to do" hand-waving.

Sections required:

**Deployment procedure.** How to deploy a new version: push to `main` → CI runs →
CI passes → Render auto-deploys via the `workflow_run` trigger. How to force a
rollback: find the previous successful deployment in Render's deploy history, click
"Rollback to this deploy."

**Database backup and restore.** Where backups are stored (Render dashboard). How to
initiate a manual backup. The exact steps to restore to a new database (tested above).
How to point the application at the restored database (update `DATABASE_URL` in Render
environment variables).

**Running database migrations.** How to trigger an Alembic migration on the production
database. The recommended approach is a one-off Render job that runs `alembic upgrade head`.

**Common errors and fixes.** At minimum: (a) Celery workers stopped processing — how
to restart them in Render. (b) Redis connection refused — how to diagnose and restart.
(c) LLM call failures at high rate — how to check the LiteLLM logs and switch the
provider env var to a fallback.

**Emergency contacts.** Placeholder for school admin contact, hosting account owner,
and LLM provider account info.

---

## Acceptance Criteria

- Render daily backups are enabled and at least one successful backup appears in the
  dashboard
- The restore procedure has been tested end-to-end against a throwaway database
- `docs/RUNBOOK.md` exists in the repository and covers all five sections above
- Every procedure in the RUNBOOK has been verified to work by following it exactly
  (no assumed knowledge)
