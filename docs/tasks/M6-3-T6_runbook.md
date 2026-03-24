# M6-3-T6 — Operations Runbook
**Milestone:** M6 — Analytics, Billing & Launch Polish
**Epic:** M6-3 — Production Hardening
**Task ID:** M6-3-T6
**Depends on:** M6-3-T3 (backup procedures), M6-3-T4 (pilot seed script), all prior M6 tasks
**Blocks:** M6-3-T5 (pre-launch checklist requires RUNBOOK.md to exist)
**Estimated effort:** 3–4 hours (Kramer writes, Vidhya reviews onboarding section, Pixel reviews UI section)
**Output:** `docs/RUNBOOK.md`

> **Why this task is separate from M6-3-T3:**
> M6-3-T3 covers backup/restore only. A complete runbook for a live pilot school needs
> six additional sections beyond backup: deploy procedure, rollback, Celery beat health,
> new school onboarding, common errors, and UI troubleshooting. Without this, Vibhu is
> the only person who can operate the platform — a single point of failure.

---

## Vidhya — Review Scope

Vidhya reviews the "New School Onboarding" section to verify:
- The school setup sequence matches the intended pedagogical rollout
- The teacher setup instructions are realistic for Cambridge/IB teachers
- The student onboarding success criteria match what a real student would experience

---

## Pixel — Review Scope

Pixel reviews the "UI Troubleshooting" section to verify:
- Browser compatibility notes are accurate
- Common UI issues and their solutions reference the correct component/design system decisions
- The instructions are clear enough for a non-technical school admin to follow

---

## Kramer — RUNBOOK Content

The runbook is a single Markdown file at `docs/RUNBOOK.md`. It is operational
documentation — written for Vibhu and future team members, not for students or
teachers. Tone: direct, step-by-step, no preamble.

---

## Full `docs/RUNBOOK.md` Content

```markdown
# Kaihle Operations Runbook
**Version:** 1.0
**Last updated:** [Date]
**Platform:** Render.com (production), GitHub (source), Resend (email)
**Emergency contact:** [Vibhu Athavaria — contact info]

---

## Table of Contents

1. [Deploy Procedure](#1-deploy-procedure)
2. [Rollback a Bad Deploy](#2-rollback-a-bad-deploy)
3. [Database Backup and Restore](#3-database-backup-and-restore)
4. [Celery Beat Health Check](#4-celery-beat-health-check)
5. [New School Onboarding](#5-new-school-onboarding)
6. [Common Errors and Fixes](#6-common-errors-and-fixes)
7. [UI Troubleshooting](#7-ui-troubleshooting)
8. [Environment Variables Reference](#8-environment-variables-reference)

---

## 1. Deploy Procedure

### Normal deploy (CI-triggered)

1. Push to `main` branch or merge a PR to `main`
2. GitHub Actions CI runs: ruff, mypy, pytest, Playwright E2E
3. If CI passes, `deploy.yml` workflow triggers automatically
4. Render deploys backend service first (health check at `/ready`)
5. Render deploys each frontend static site (teacher, student, parent, school-admin, kaihle-admin)
6. Verify deploy: `GET https://api.kaihle.com/ready` returns `{ status: "ok" }`

**Expected total deploy time:** 4–8 minutes

### Manual deploy (emergency)

If CI is broken but a hotfix must ship:
1. Log in to Render.com dashboard
2. Navigate to the affected service (backend or specific frontend)
3. Click "Manual Deploy" → "Deploy latest commit"
4. Monitor logs in real-time on Render dashboard

**Do not push directly to `main` without CI unless it is a production emergency.**

### Post-deploy verification

After every deploy, verify:
```bash
curl https://api.kaihle.com/health
# Expected: { "status": "ok", "db": "connected", "redis": "connected" }

curl https://api.kaihle.com/ready
# Expected: { "status": "ready" }
```

If `/health` returns `"db": "error"`, the database connection is down.
If `/health` returns `"redis": "error"`, Redis is down (Celery tasks will fail).

---

## 2. Rollback a Bad Deploy

### Identify the bad deploy

Signs of a bad deploy:
- `/health` endpoint returning 500 or unhealthy services
- Frontend apps returning blank screens or 404
- Users reporting they cannot log in (auth regression)

### Rollback steps

1. Log in to Render.com
2. Navigate to the service that needs rollback
3. In "Events" tab, find the last known good deploy (by commit SHA)
4. Click "Rollback to this deploy"
5. Confirm rollback — Render redeploys from the previous commit

**Rollback does NOT roll back database migrations.** If the bad deploy included a
migration, rollback may leave the DB in an incompatible state. Check:
- Was there an Alembic migration in the bad deploy? (`git diff [old-sha] [new-sha] -- alembic/`)
- If yes: the rollback will revert the code but NOT the migration
- Solution: write a reverse migration (`alembic downgrade -1`) before rolling back

### After rollback

1. Verify `/health` returns healthy
2. Test login with a test account
3. Create a GitHub issue describing what broke and why
4. Label it `deploy-regression` and assign to yourself

---

## 3. Database Backup and Restore

See M6-3-T3 for the automated backup setup. This section covers manual operations.

### Check backup status

Render.com PostgreSQL backups are configured in the Render dashboard.
To verify backups are running:
1. Log in to Render dashboard
2. Navigate to the PostgreSQL service
3. Check "Backups" tab — should show daily backups for the last 7 days

### Manual backup (before risky operations)

Before running any migration or bulk data operation:
```bash
# From your local machine with DATABASE_URL set
pg_dump $DATABASE_URL --format=custom --no-acl --no-owner \
  -f backups/kaihle_manual_$(date +%Y%m%d_%H%M%S).dump
```

### Restore from backup

```bash
# DANGER: This replaces all production data
# Only do this after exhausting all other options
# Notify all active users first

# 1. Stop the backend service (Render: manual → Suspend)
# 2. Restore the dump
pg_restore --clean --if-exists --no-acl --no-owner \
  -d $DATABASE_URL backups/kaihle_manual_TIMESTAMP.dump
# 3. Run migrations to bring schema up to date
alembic upgrade head
# 4. Restart the backend service
```

---

## 4. Celery Beat Health Check

Kaihle has two scheduled tasks:
- Monday 06:00 (WIB): `generate_weekly_lesson_plans`
- Sunday 18:00 (WIB): `generate_parent_narratives`

### Verify a task fired

After the expected time has passed:

```bash
# Check Celery logs on Render
# In Render dashboard → Celery worker service → Logs
# Search for "lesson_plans_generation_complete" or "parent_narratives_generation_complete"

# OR: check the database directly
psql $DATABASE_URL -c "
  SELECT COUNT(*), MAX(created_at)
  FROM lesson_plans
  WHERE created_at > NOW() - INTERVAL '1 hour';
"
```

### Manually trigger a task (for testing)

```bash
# From a machine with the backend running or via Render shell:
python -c "
from app.tasks.celery_app import celery_app
celery_app.send_task('tasks.generate_weekly_lesson_plans')
"
```

### If a task didn't fire

1. Check if Celery beat worker is running (Render → Celery service → Status must be "Running")
2. Check timezone: tasks are scheduled in UTC. Monday 06:00 WIB = Sunday 23:00 UTC.
   Verify `celery_app.py` uses the correct crontab times.
3. Check if Redis is healthy: `GET https://api.kaihle.com/health` → `redis: "connected"`
4. If Redis was restarted (e.g., Render free tier restart), Celery beat may need a manual restart:
   Render → Celery service → "Manual Restart"

---

## 5. New School Onboarding

*Reviewed by Vidhya — matches intended pedagogical rollout.*

### Prerequisites (before creating any accounts)

1. Cambridge curriculum seed must be run: `python scripts/seed_curriculum_graph.py`
2. Question bank must be imported: `python scripts/import_questions.py --file data/questions/batch_01.csv`
3. Verify: `GET /api/v1/curricula` returns 2 curricula (Cambridge Lower Secondary + IGCSE)
4. Verify: `GET /api/v1/subjects` returns 7 subjects

### Step 1: Create the school (KaihleAdmin UI or API)

Using the Kaihle Admin UI at `https://kaihle-admin.kaihle.com`:
1. Navigate to Schools → `[+ Add school]`
2. Fill: School name, country, city, timezone, admin first name, admin last name, admin email
3. Submit → magic link sent to school admin email

**OR via API:**
```bash
curl -X POST https://api.kaihle.com/api/v1/schools \
  -H "Authorization: Bearer $KAIHLE_ADMIN_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Bali International School",
    "country": "Indonesia",
    "city": "Denpasar",
    "timezone": "Asia/Makassar"
  }'
```

### Step 2: School admin sets up the school

The school admin receives a magic link. On first login:
1. Sets a password (PasswordSetupRoute)
2. Logs in to the school admin dashboard at `/school-admin/overview`
3. Creates classes: Go to Classes → `[Create class]`
   - Select grade (6–10), curriculum, subject, assign teacher
4. Invites teachers: Go to Users → `[Invite teacher]`
   - Teacher receives magic link, sets password, can now access teacher dashboard
5. Invites students: Go to Users → `[Invite student]`
   - Student receives magic link, sets password, completes learning profile questionnaire
   - On questionnaire completion: Tier 1 diagnostic auto-created via Celery
   - Student takes Tier 1 diagnostic → content unlocked

### Step 3: Verify onboarding success

```sql
-- All enrolled students should have submitted their learning profile
SELECT
  u.email,
  slp.completed_at IS NOT NULL AS profile_complete,
  ce.onboarding_diagnostic_status
FROM users u
JOIN class_enrollments ce ON ce.student_id = u.id
LEFT JOIN student_learning_profiles slp ON slp.student_id = u.id
WHERE u.school_id = '[SCHOOL_UUID]'
  AND u.role = 'STUDENT';
```

Expected: `profile_complete = true` and `onboarding_diagnostic_status = 'COMPLETED'`
for students who have completed onboarding.

### Step 4: Verify lesson plans will generate

The next Monday at 06:00 WIB, lesson plans auto-generate for all active classes with
at least one completed assessment. Before that:

1. Teacher creates and publishes a Tier 2 assessment: Teacher UI → Assessments → `[+ Create]`
2. Students take the assessment
3. Verify `gap_states` are populated: `SELECT COUNT(*) FROM gap_states WHERE school_id = '[SCHOOL_UUID]';`
4. If count > 0, lesson plans will generate on Monday

---

## 6. Common Errors and Fixes

### Error: `IntegrityError: unique constraint violation on (email, school_id)`

**Cause:** Attempting to register a user with an email already registered at that school.

**Fix:** Check if user exists: `SELECT * FROM users WHERE email = '[EMAIL]' AND school_id = '[SCHOOL_UUID]';`
If user exists but is inactive (`is_active = false`), reactivate: `UPDATE users SET is_active = true WHERE id = '[USER_UUID]';`
If user exists and is active, they should use the login flow, not registration.

---

### Error: `JWT decode error: signature verification failed`

**Cause:** The `JWT_SECRET_KEY` environment variable was rotated or changed.

**Impact:** ALL existing sessions are invalidated. All logged-in users are logged out.

**Fix:**
1. Verify the secret key in Render environment variables matches what was used to generate the tokens
2. If the secret was accidentally changed: revert to the original key
3. If the secret must be rotated: notify all users that they will need to log in again

---

### Error: LLM timeout in lesson plan generation

**Cause:** The LLM call to OpenRouter timed out (> 90 seconds).

**Symptom:** No lesson plans generated for a Monday. Check logs for `lesson_plan_generation_timeout`.

**Fix:**
1. Check OpenRouter status: `https://openrouter.ai/status`
2. If OpenRouter is down: lesson plans will not generate this week. Manual trigger next Monday.
3. If timeout is consistently happening: increase `LLM_LESSON_PLAN_TIMEOUT_S` in Render env vars
   from 90 to 120 (note: this increases cost per plan)
4. Alternatively: temporarily switch to a faster model by changing `LLM_LESSON_PLAN_MODEL`

---

### Error: `Redis connection refused`

**Cause:** Redis service is down or restarting (common on Render free tier).

**Impact:** Celery tasks cannot queue. Magic link emails may not send (depending on implementation).

**Fix:**
1. Check Redis service in Render dashboard → restart if needed
2. After Redis restarts, Celery workers may need a manual restart too (they lose connection)
3. Verify: `GET https://api.kaihle.com/health` → `redis: "connected"`

---

### Error: Student sees "Diagnostic locked" even after completing questionnaire

**Cause:** The `onboarding_diagnostic_status` in `class_enrollments` is still `PENDING`.
This can happen if the Celery task `create_class_diagnostic_task` failed silently.

**Fix:**
```sql
-- Check the status
SELECT * FROM class_enrollments
WHERE student_id = '[STUDENT_UUID]'
  AND onboarding_diagnostic_status != 'COMPLETED';

-- If diagnostic exists but status is stuck, manually update
-- (Only do this if the student has submitted the attempt)
UPDATE class_enrollments
SET onboarding_diagnostic_status = 'COMPLETED'
WHERE student_id = '[STUDENT_UUID]'
  AND class_id = '[CLASS_UUID]';
```

---

## 7. UI Troubleshooting

*Reviewed by Pixel — instructions reflect actual component and design system decisions.*

### Teacher sees blank page after login

**Most likely cause:** The teacher has no classes assigned. The dashboard class grid
renders empty which may look like a blank page.

**Fix:** Verify in school admin UI: Users → [Teacher name] → should see assigned classes.
If no classes: Classes → [Create class] → assign this teacher.

### Student cannot see assessment (class locked icon)

**Cause:** Gate 2 — the student's Tier 1 diagnostic for that class is not yet COMPLETED.

**UI behaviour (correct):** Class card shows lock icon + "Complete diagnostic to unlock"
This is NOT a bug — it is the intended two-gate onboarding flow.

**Fix:** Student should navigate to the locked class and start the Tier 1 diagnostic.
If the diagnostic card is also missing: run the Celery task manually (see §4).

### App shows white screen (blank page)

**Cause:** A JavaScript runtime error occurred and there may not be an ErrorBoundary.

**Fix:**
1. Check browser console for JavaScript errors
2. Hard refresh (Ctrl+Shift+R / Cmd+Shift+R)
3. If the error persists, report with: browser type, URL, and console error message
4. Check Render backend logs for API errors that may have caused the issue

### Parent sees "Your first weekly update will appear here"

**Cause:** Either (a) the student hasn't completed their Tier 1 diagnostic yet, or
(b) the Sunday narrative generation task hasn't run yet.

**This is expected behaviour for new schools.** Narratives generate every Sunday at 18:00 WIB.
First narratives appear after the first Sunday following the student's diagnostic completion.

### Font renders as system-ui instead of Fraunces/Nunito

**Cause:** Google Fonts is blocked (rare in some corporate networks or browser extensions).

**Fix:** This is a font fallback — functionally the app still works, just looks different.
No action needed unless the school's network administrator is blocking Google Fonts globally
(unusual — advise them to allowlist `fonts.googleapis.com`).

---

## 8. Environment Variables Reference

See `docs/kaihle_product_plan.md` Part 6 for the full list. Critical variables:

| Variable | What it controls | How to find the value |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection | Render PostgreSQL service → Info tab |
| `JWT_SECRET_KEY` | Auth token signing | Generate: `openssl rand -hex 64` |
| `RESEND_API_KEY` | Email delivery | Resend dashboard → API Keys |
| `LLM_LESSON_PLAN_MODEL` | Lesson plan LLM | Default: `openrouter/anthropic/claude-sonnet-4-6` |
| `LLM_LESSON_PLAN_TIMEOUT_S` | Lesson plan timeout | Default: 90 |
| `OPENROUTER_API_KEY` | OpenRouter access | OpenRouter dashboard → Keys |
| `REDIS_URL` | Redis connection | Render Redis service → Info tab |

**Never commit any environment variable values to git.** Use `.env.example` for keys only.
```

---

## Acceptance Criteria

- [ ] `docs/RUNBOOK.md` exists at the correct path
- [ ] All 8 sections are present and complete
- [ ] §3 (backup/restore) is consistent with M6-3-T3 implementation
- [ ] §5 (school onboarding) reviewed and approved by Vidhya
- [ ] §7 (UI troubleshooting) reviewed and approved by Pixel
- [ ] SQL queries in §5 and §6 use the correct table and column names from `kaihle_v2_1_schema.sql`
- [ ] Environment variables in §8 match the actual env var names in `docs/kaihle_product_plan.md` Part 6
- [ ] M6-3-T5 pre-launch checklist includes: "RUNBOOK.md reviewed and complete" as a checklist item
- [ ] `docs/RUNBOOK.md` renders correctly as Markdown (no broken tables or code blocks)

---

## Do NOT Touch

- Any application code — this is documentation only
- Any existing task files — M6-3-T3 backup section is referenced, not replaced
