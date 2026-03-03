# M6-3-T3 — Data Backup & Recovery
**Task ID:** M6-3-T3
**Milestone:** M6 — Analytics, Billing & Launch Polish
**Epic:** M6-3 — Production Readiness
**Depends on:** Production Render environment set up (M6-3-T4 pilot seed)
**Blocks:** M6-3-T5 (pre-launch checklist)

---

## User Story

As the platform operator, I want automated daily database backups with a documented restore procedure so that we can recover from data loss or corruption within a known RTO (Recovery Time Objective).

---

## Context

Kaihle is deployed on Render.com with a managed PostgreSQL instance. Render provides built-in automated backups on paid plans. This task is about:
1. Enabling and verifying those backups are configured correctly
2. Writing and testing the restore procedure
3. Documenting everything in `RUNBOOK.md`

This is not a coding task — it is a configuration + documentation task. The output is verified backup configuration and a runbook that any team member can follow.

---

## Files to Create / Modify

```
RUNBOOK.md          CREATE at repo root — operational runbook
```

---

## Step 1: Enable Render PostgreSQL Backups

In the Render dashboard for the Kaihle PostgreSQL instance:

1. Navigate to the database → **Backups** tab
2. Confirm **Daily Backups** are enabled (available on Starter plan and above)
3. Set retention to **7 days**
4. Note the backup window time (Render default: between 02:00–06:00 UTC)
5. Take a screenshot of the backup configuration screen and store in `/docs/ops/backup_config_screenshot.png`

**Verify a backup exists:**
- After 24 hours from enabling, confirm at least one backup appears in the Render dashboard
- Note the backup timestamp and size

---

## Step 2: Test the Restore Procedure

Before launch, perform a full restore drill on the **staging** environment:

1. Identify the most recent backup in Render dashboard
2. Use Render's "Restore" feature to restore to a new staging database instance
3. Connect to the restored instance and verify:
   ```sql
   SELECT COUNT(*) FROM users;
   SELECT COUNT(*) FROM gap_states;
   SELECT extname FROM pg_extension WHERE extname = 'vector';
   SELECT version_num FROM alembic_version;
   ```
4. Confirm all counts match the source database
5. Confirm pgvector extension is present
6. Confirm Alembic version matches
7. Document time taken from "click Restore" to "verified data" — this is your RTO

---

## Step 3: Write RUNBOOK.md

Create `RUNBOOK.md` at the repository root. It must cover:

### Section 1: Deployment Procedure
```
1. Merge to `main` branch on GitHub
2. Render auto-deploys backend web service and Celery worker
3. Alembic migrations run automatically on deploy (add to Dockerfile CMD or Render pre-deploy command)
4. Verify: GET https://api.kaihle.ai/health returns 200
5. Verify: GET https://api.kaihle.ai/ready returns 200
```

### Section 2: Database Backup & Restore
```
Backup schedule: Daily, automated by Render, 02:00–06:00 UTC
Retention: 7 days
Location: Render dashboard → PostgreSQL → Backups tab

To restore:
1. Go to Render dashboard → PostgreSQL instance → Backups
2. Select the backup to restore from
3. Click "Restore" — choose "Restore to new database" for safety
4. Wait for restore to complete (~5–15 min depending on size)
5. Update DATABASE_URL environment variable in Render web service and Celery worker
6. Redeploy both services
7. Verify with health check and row count queries above
8. RTO target: < 30 minutes from incident declaration to verified restore
```

### Section 3: Common Errors & Fixes

| Error | Likely cause | Fix |
|---|---|---|
| `GET /health` returns `{"db": "disconnected"}` | DATABASE_URL wrong or DB restarting | Check Render DB status, verify env var |
| `GET /health` returns `{"redis": "disconnected"}` | Redis instance down or REDIS_URL wrong | Check Render Redis status |
| Celery tasks not processing | Worker crashed or not running | Restart Celery worker service in Render |
| `alembic.exc.LockError` on deploy | Previous migration didn't complete | Connect to DB, run `DELETE FROM alembic_version` if safe, re-run migration |
| Magic link emails not sending | RESEND_API_KEY wrong or domain not verified | Check Resend dashboard, verify sender domain |
| LLM calls timing out | Provider API key expired or rate limited | Check provider dashboards, rotate keys if needed |

### Section 4: Environment Variables Checklist
List every required env var (from `kaihle_product_plan_v2_1.md` Part 6) with:
- Where to find the value (which service dashboard)
- Which Render services need it (web, worker, or both)

### Section 5: Monitoring
```
Logs:    Render dashboard → Web Service → Logs (structured JSON)
Metrics: Render dashboard → Web Service → Metrics (CPU, memory, request count)
Alerts:  Set up Render email alerts for:
         - Service crash / restart
         - Deploy failure
         - Database storage > 80% full
```

---

## Acceptance Criteria

- [ ] Render PostgreSQL daily backups enabled and confirmed in dashboard
- [ ] At least one successful backup exists before launch
- [ ] Restore drill completed on staging — all row counts and extensions verified
- [ ] RTO documented (actual time measured during drill)
- [ ] `RUNBOOK.md` exists at repo root and covers all 5 sections
- [ ] `RUNBOOK.md` reviewed by at least one other team member
- [ ] Alembic migrations configured to run automatically on Render deploy (pre-deploy command)

---

## Output From This Task

- Render backup configuration active and verified
- `RUNBOOK.md` at repo root — operational reference for the entire team
- Documented RTO from restore drill
