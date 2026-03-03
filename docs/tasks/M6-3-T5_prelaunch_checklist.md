# M6-3-T5 — Pre-Launch Checklist
**Task ID:** M6-3-T5
**Milestone:** M6 — Analytics, Billing & Launch Polish
**Epic:** M6-3 — Production Readiness
**Depends on:** ALL prior tasks across ALL milestones
**Blocks:** Nothing — this is the final task of the entire project

---

## User Story

As the platform operator, I want a complete verified checklist of every system, integration, and user journey that must work before handing credentials to the first real school — so I can launch with confidence and no surprises.

---

## Context

This is not a coding task. It is a structured verification exercise performed in the **production** Render environment after the pilot school seed (M6-3-T4) has been run. Every item must be checked by a human, not inferred. Items marked ❌ block launch and must be fixed before proceeding.

Assign one person to own this checklist end-to-end and sign off on it.

---

## The Checklist

### Section 1: Infrastructure

- [ ] `GET https://api.kaihle.ai/health` returns `200` with `{ "status": "ok", "db": "connected", "redis": "connected" }`
- [ ] `GET https://api.kaihle.ai/ready` returns `200`
- [ ] Custom domain `api.kaihle.ai` resolves with valid SSL certificate (green padlock)
- [ ] Frontend URLs (`app.kaihle.ai/student`, `/teacher`, `/parent`) load without console errors
- [ ] Render PostgreSQL daily backups enabled and at least one backup visible in dashboard
- [ ] Render Redis instance running and connected (verify via `/health`)
- [ ] Celery worker service running — confirm in Render dashboard (status: Live)
- [ ] All production environment variables set — cross-check against `kaihle_product_plan_v2_1.md` Part 6

---

### Section 2: Authentication

- [ ] School Admin can log in with email + password → lands on admin dashboard
- [ ] Magic link: School Admin requests magic link → email received within 60 seconds → clicking link logs in
- [ ] Expired magic link (wait 11 minutes) → login attempt returns 401
- [ ] Wrong password returns 401 (not 500)
- [ ] Token refresh: access token expires → Axios interceptor auto-refreshes → user stays logged in
- [ ] Logout invalidates refresh token → second logout attempt returns 401

---

### Section 3: Email Delivery

- [ ] Magic link email: received, sender shows `no-reply@kaihle.ai`, not marked as spam
- [ ] Teacher invite email: School Admin invites a teacher → teacher receives invite with magic link
- [ ] Lesson plan notification email: trigger a plan manually → teacher receives email with link
- [ ] Parent report email: trigger a report manually → parent receives email with child's narrative
- [ ] All emails render correctly on mobile (test via Gmail mobile app)

---

### Section 4: Full End-to-End Journey (Manual)

Run this complete flow in production with real users (or internal test accounts):

**Step 1 — School Admin setup:**
- [ ] School Admin logs in
- [ ] Creates a Grade 8 class: "8A Mathematics"
- [ ] Invites 1 teacher by email
- [ ] Invites 3 test students by email

**Step 2 — Teacher onboarding:**
- [ ] Teacher receives invite, logs in via magic link
- [ ] Teacher sees class "8A Mathematics" in their dashboard
- [ ] Teacher creates a Tier 2 TOPIC_SPECIFIC assessment for Algebra, 10 questions, publishes it

**Step 3 — Student onboarding (Tier 1):**
- [ ] Student 1 logs in → redirected to `/student/onboarding/profile`
- [ ] Student completes 10-question learning profile questionnaire → profile saved
- [ ] Student redirected to `/student/onboarding/diagnostics`
- [ ] Student sees Tier 1 diagnostic cards for each subject (Math, Science, English)
- [ ] Student completes Math Tier 1 diagnostic (20 questions) → score summary shown
- [ ] Student completes Science and English diagnostics
- [ ] After all 3 complete → redirected to `/student/dashboard` (no more onboarding gate)
- [ ] `student_profiles.onboarding_diagnostic_status` = `COMPLETED` in DB (verify)
- [ ] `gap_states` rows populated for Student 1 (verify row count > 0)

**Step 4 — Student takes Tier 2 assessment:**
- [ ] Student 1 sees teacher's Algebra assessment on dashboard
- [ ] Student takes it, submits → score summary shown
- [ ] `gap_states` updated with new mastery scores (verify in DB or gap map)

**Step 5 — Teacher views gap map:**
- [ ] Teacher opens class gap map for 8A Mathematics
- [ ] Cells render with correct Red/Amber/Green colours
- [ ] Teacher clicks a red cell → side panel opens with student name, learning style icon, interests
- [ ] Teacher assigns a study plan from the gap map → success toast
- [ ] Student 1 sees the study plan on their dashboard

**Step 6 — Student completes study plan:**
- [ ] Student opens study plan → sees 3 curated resources
- [ ] Student marks resources as watched
- [ ] Student takes the 5-question quiz → score shown
- [ ] `gap_states` updated after quiz submission (verify mastery_score changed)

**Step 7 — Teacher lesson plan:**
- [ ] Trigger `generate_weekly_lesson_plans` Celery task manually (or wait for Monday)
- [ ] Teacher sees lesson plan in dashboard with 3 student group tabs
- [ ] Teacher edits the starter activity → change saved
- [ ] Teacher marks plan as "Used"

**Step 8 — Parent portal:**
- [ ] Link Parent account to Student 1 via `parent_student` table
- [ ] Trigger `generate_parent_narratives` Celery task manually
- [ ] Parent logs in → sees child's name and weekly narrative
- [ ] Parent views simplified gap map (traffic lights, no scores)

---

### Section 5: Performance Spot-Check

- [ ] Gap map loads for a class with 10+ students in under 2 seconds
- [ ] Assessment with 20 MCQ questions — all scoring completes within 5 seconds of submit
- [ ] Study plan generation (resources + quiz) completes within 15 seconds
- [ ] No 500 errors in Render logs during the full E2E journey above

---

### Section 6: Security Spot-Check

- [ ] Student from School A cannot access School B's data (test with two test schools)
- [ ] Student cannot access `/student/dashboard` before completing onboarding (verify redirect)
- [ ] Teacher cannot access another teacher's class gap map (verify 403)
- [ ] Trigger an intentional 500 error → response body contains no traceback or file paths
- [ ] Rate limiting: 11 login attempts from same IP in 1 minute → 11th is rejected with 429

---

### Section 7: Billing

- [ ] Trial school at 30 students → attempting to enroll 31st returns 402
- [ ] Trial subscription `trial_end_date` set correctly to `created_at + 15 days` in DB

---

### Section 8: Sign-Off

Complete this section when ALL items above are checked ✅:

```
Pre-launch checklist completed by: _______________
Date: _______________
Production URL verified: _______________
Pilot school name: _______________
School Admin email delivered to client: YES / NO

Launch approved: YES / NO

Notes:
_____________________________________________
_____________________________________________
```

---

## Acceptance Criteria

- [ ] Every checkbox in Sections 1–7 is checked ✅ with no outstanding ❌ items
- [ ] Section 8 sign-off is completed and dated
- [ ] This checklist file is saved with checkboxes filled as a permanent record in `/docs/ops/launch_checklist_YYYYMMDD.md`
- [ ] Pilot school admin has received their login credentials via secure channel

---

## Output From This Task

- Production system verified as launch-ready
- Permanent record of launch verification saved in `/docs/ops/`
- Pilot school live and accessible to the school's admin

**🚀 This is the final task. After sign-off, Kaihle v1 is live.**
