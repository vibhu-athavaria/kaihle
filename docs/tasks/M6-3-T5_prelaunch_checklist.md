# M6-3-T5 — Pre-Launch Verification Checklist
**Milestone:** M6 · **Epic:** M6-3 · **Task:** T5
**Depends on:** Every prior task in every milestone — this is the final task of the project
**Blocks:** Nothing — this is the last task. Passing this checklist means the pilot is live.
**Estimated effort:** 4–8 hours (time is spent verifying, not coding)

---

## Context

This task has no application code. It is a verification task. Every item must be
checked and confirmed against the live production environment, not against staging.
Items are grouped into sections. Each item has an explicit verification method —
not just a description of what should be true.

Do not mark this task complete until every checkbox is ticked. If any item fails,
create a GitHub issue with the `launch-blocker` label and resolve it before proceeding.

---

## Section 1 — Infrastructure

- [ ] `GET https://api.kaihle.ai/health` returns `{"status": "ok", "db": "connected", "redis": "connected"}` — verify in a browser or via `curl`
- [ ] `GET https://api.kaihle.ai/ready` returns 200 — verify via `curl`
- [ ] Render PostgreSQL daily backups are enabled and at least one backup shows a "Completed" status in the Render dashboard
- [ ] Render environment variables are all set: verify by listing them in the Render dashboard and confirming no `_PLACEHOLDER_` or empty values exist
- [ ] Custom domain is configured and SSL certificate is valid — verify by navigating to the production frontend URL and checking the padlock icon
- [ ] Celery workers are running — verify by checking the Render service logs and confirming a heartbeat log line appears within the last 60 seconds
- [ ] Celery beat is running and the Monday lesson plan schedule is registered — run `celery -A app.tasks.celery_app inspect scheduled` and confirm `generate_weekly_lesson_plans` appears

---

## Section 2 — Authentication

- [ ] `POST /api/v1/auth/login` with valid credentials returns a JWT — test using a real teacher account created via the seed script
- [ ] `POST /api/v1/auth/magic-link` sends an email that arrives in the recipient's inbox within 2 minutes — test using a real email address
- [ ] Magic link email link opens the frontend and completes the password setup flow — follow the link and set a password
- [ ] `POST /api/v1/auth/refresh` with a valid refresh token returns a new access token — verify via API client (Postman or curl)
- [ ] Rate limiting is active on login: 11 requests in under a minute from the same IP returns a 429 — test via script or Postman runner

---

## Section 3 — Email Delivery

- [ ] Magic link email renders correctly on mobile (test via Gmail mobile app)
- [ ] Lesson plan notification email renders correctly — manually trigger `generate_weekly_lesson_plans` in a Celery worker shell and verify email arrives
- [ ] Parent narrative email renders correctly — manually trigger `generate_parent_narratives` and verify email arrives at a test parent address
- [ ] Resend API key is valid and email sending quota has not been exceeded — check the Resend dashboard

---

## Section 4 — Full End-to-End Journey

This is the most important section. Run the complete journey from school setup to
parent viewing a report. Use the pilot school accounts created by the seed script.

**School Admin setup (estimated time: 15 minutes)**

- [ ] School admin logs in via magic link, sets password, lands on the school admin dashboard
- [ ] School admin creates a Grade 8 class: "8A Mathematics", assigns a teacher
- [ ] School admin invites one test student via the invite user flow
- [ ] The student receives their invite email and can click the magic link

**Teacher setup (estimated time: 10 minutes)**

- [ ] Teacher logs in, sees the class "8A Mathematics" in their dashboard
- [ ] Teacher creates a Tier 2 TOPIC_SPECIFIC assessment for one Mathematics topic with 10 questions and publishes it
- [ ] The published assessment appears in the teacher's class assessment list with status ACTIVE

**Student onboarding and Tier 1 diagnostic (estimated time: 20 minutes)**

- [ ] Student logs in, is redirected to the learning profile questionnaire
- [ ] Student completes the 10-question questionnaire, profile is saved, student is redirected to the diagnostic hub
- [ ] Student sees the Tier 1 diagnostic cards for Mathematics
- [ ] Student completes the Mathematics Tier 1 diagnostic (20 questions), sees score summary
- [ ] After completing the diagnostic, student is redirected to the student dashboard (onboarding gate is lifted)
- [ ] In the database: `student_profiles.is_learning_profile_complete = TRUE`
- [ ] In the database: `class_enrollments.onboarding_diagnostic_status = 'COMPLETED'` for the Mathematics class
- [ ] In the database: `gap_states` rows exist for the student with non-null `mastery_score` values

**Student takes Tier 2 assessment (estimated time: 10 minutes)**

- [ ] Student sees the teacher's Tier 2 assessment in their class content page
- [ ] Student takes and submits the Tier 2 assessment, sees score summary
- [ ] Gap states are updated in the database after submission (verify by checking `last_assessed_at` timestamps)

**Teacher views gap map and assigns study plan (estimated time: 10 minutes)**

- [ ] Teacher navigates to the class gap map, sees coloured cells for the enrolled student
- [ ] Teacher clicks a red or amber cell, sees the student side panel with learning style
- [ ] Teacher assigns a study plan from the side panel, sees the "generating" confirmation

**Student works through study plan (estimated time: 10 minutes)**

- [ ] Student sees the assigned study plan in their study plans list
- [ ] Student marks at least one resource as done, takes the quiz, sees their score
- [ ] Gap state is updated after quiz submission

**Teacher views lesson plan (estimated time: 5 minutes)**

- [ ] Teacher dashboard shows a lesson plan (manually trigger the Celery task in the worker shell if Monday has not occurred yet)
- [ ] Teacher views the plan, edits one section, saves the edit
- [ ] Teacher marks the plan as Used

**Parent views reports (estimated time: 5 minutes)**

- [ ] A parent account is linked to the test student via the `parent_student` table (insert directly if no invite flow exists yet)
- [ ] Parent logs in, sees the student's name on their dashboard
- [ ] Parent views the child gap map — no numeric scores appear anywhere on the page
- [ ] Manually trigger `generate_parent_narratives` in a Celery worker shell
- [ ] Parent receives narrative email and can view the full report in the parent portal

---

## Section 5 — Performance and Monitoring

- [ ] `GET /api/v1/classes/{id}/gap-map` with 20 enrolled students responds in under 500ms — verify via browser network tab or `curl --write-out "%{time_total}"`
- [ ] `GET /health` does not appear in INFO-level logs (only DEBUG) — check Render log stream
- [ ] No unhandled exceptions appear in the Render logs during the end-to-end journey above
- [ ] Render metrics show CPU and memory within normal ranges (no spikes that would indicate an infinite loop or memory leak)

---

## Definition of Done for the Entire Project

If every checkbox above is ticked, the Bali pilot school is live and the project has
achieved its v1 exit criteria. Record the date and time of launch completion in
`docs/RUNBOOK.md` under a new "Launch Log" section.
