# M6 Brief — Analytics, Billing & Launch Polish
**Milestone:** 6 of 6
**Estimated duration:** 2–3 weeks
**Previous milestone:** M5 — Parent Portal

> Load this brief alongside CONSTITUTION.md when working on any M6 task.
> Load the specific task file for the task you are implementing.

---

## Goal

School admin sees usage analytics. Billing tier limits are enforced. Rate limiting and error handling are production-grade. First real school (Bali pilot) is live on Render.

## Exit Criteria

- First real school (Bali pilot) is live in production on Render.com
- School admin sees analytics dashboard including onboarding completion rate
- Billing limits enforced (trial limits, tier limits)
- Rate limiting active on all auth and LLM routes

---

## What This Milestone Delivers

- School admin analytics service + API + UI
- Billing tier enforcement (student limits, trial expiry)
- Rate limiting (slowapi + Redis)
- Global error handling
- Data backup configuration
- Pilot school seed script
- Pre-launch checklist verification

---

## Tasks in This Milestone

| Task ID | File | Description |
|---|---|---|
| M6-1-T1 | `M6/M6-1-T1_analytics_service_routes.md` | Analytics service + API endpoint |
| M6-1-T2 | `M6/M6-1-T2_analytics_ui.md` | School admin analytics dashboard UI |
| M6-2-T1 | `M6/M6-2-T1_billing_tier_enforcement.md` | Billing limits + trial expiry enforcement |
| M6-3-T1 | `M6/M6-3-T1_rate_limiting.md` | slowapi rate limiting on key routes |
| M6-3-T2 | `M6/M6-3-T2_error_handling.md` | Global error handler + structured error responses |
| M6-3-T3 | `M6/M6-3-T3_data_backup.md` | Render PostgreSQL automated backups + RUNBOOK |
| M6-3-T4 | `M6/M6-3-T4_pilot_seed_script.md` | Seed script for Bali pilot school |
| M6-3-T5 | `M6/M6-3-T5_prelaunch_checklist.md` | Pre-launch verification checklist |

---

## Task Execution Order

```
M6-1-T1 (analytics service) ← start here
  → M6-1-T2 (analytics UI) ← needs routes
M6-2-T1 (billing) ← parallel with analytics
M6-3-T1 (rate limiting) ← parallel
M6-3-T2 (error handling) ← parallel
M6-3-T3 (backup) ← parallel
M6-3-T4 (pilot seed) ← needs all prior tasks complete
  → M6-3-T5 (pre-launch checklist) ← last task of the entire project
```

---

## Definition of Done

- [ ] School admin analytics dashboard shows correct counts + onboarding completion rate
- [ ] Billing tier limits enforced at service layer (402 on breach)
- [ ] Trial expiry enforced (402 on login after 15 days)
- [ ] Rate limiting active on auth + LLM routes
- [ ] Global error handler returns structured JSON (never stack traces to client)
- [ ] Render PostgreSQL daily backups enabled, restore procedure documented
- [ ] Pilot school seed script runs cleanly
- [ ] Pre-launch checklist fully verified in production
- [ ] All M6 tests pass
- [ ] Manual end-to-end journey verified: school admin → teacher → student (onboarding + diagnostic + study plan) → parent

---

## Key Tables Used in This Milestone

`schools`, `school_subscriptions`, `subscription_plans`, `subscription_invoices`, `trial_extensions`, `users`, `student_profiles`, `gap_states`, `assessments`, `student_attempts`, `study_plans`, `lesson_plans`, `parent_report_snapshots`, `student_learning_profiles`

Full schema: `kaihle_v2_1_schema.sql`

---

## Analytics Metrics to Expose (M6-1-T1)

```python
SchoolAnalytics:
  total_students              # COUNT active users with role=STUDENT
  active_students_last_7_days # students with gap_state updated in last 7 days
  assessments_completed       # COUNT student_attempts WHERE status=COMPLETED
  avg_class_mastery_by_subject  # AVG(mastery_score) per subject
  study_plans_assigned        # COUNT study_plans
  study_plans_completed       # COUNT study_plans WHERE status=COMPLETED
  lesson_plans_generated      # COUNT lesson_plans
  lesson_plans_used           # COUNT lesson_plans WHERE status=USED
  onboarding_completion_rate  # % students WHERE onboarding_diagnostic_status=COMPLETED
                              #   AND learning_profile completed_at IS NOT NULL
```

---

## Billing Tier Limits (M6-2-T1)

| Tier | Max active students | Trial days |
|---|---|---|
| TRIAL | 30 | 15 |
| STARTER | 100 | — |
| GROWTH | 500 | — |
| SCALE | unlimited | — |

- Check happens in `billing.check_student_limit()` — called before every `class_enrollments` INSERT
- Trial expiry check `billing.is_trial_expired()` — called on every login for TRIAL schools
- Both return HTTP 402 Payment Required with `{ error_code, message, upgrade_url }` body

---

## Rate Limits (M6-3-T1)

| Route | Limit |
|---|---|
| `POST /api/v1/auth/login` | 10 req/min per IP |
| `POST /api/v1/auth/magic-link` | 3 req/min per email |
| `POST /api/v1/attempts/*/responses` | 60 req/min per user |
| Any LLM-backed route | 20 req/min per school |

---

## Pre-Launch Checklist (M6-3-T5)

- [ ] All environment variables set in Render production secrets
- [ ] Custom domain + SSL configured and verified
- [ ] `GET /health` returns 200 in production
- [ ] Email delivery tested: magic link, lesson plan notification, parent report
- [ ] Full manual journey: school admin → teacher → student (onboarding + Tier 1 diagnostic + study plan) → parent portal
- [ ] Celery beat running (lesson plans Monday + parent reports Sunday)
- [ ] `RUNBOOK.md` documents: deploy procedure, DB backup/restore, common errors and fixes

---

## What M5 Delivered (Available to Use)

- All product features complete and tested
- `parent_report_snapshots` populated
- Celery beat operational for both lesson plans (M4) and parent reports (M5)
- Full stack running in staging environment on Render

## This Is The Final Milestone

There is no M7. After M6-3-T5 is complete and the pre-launch checklist is fully verified, the project is live.
