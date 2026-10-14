# Kaihle Data Inventory

**Status:** DRAFT for legal / DPO review. Engineering fact-gathering, not legal advice.
**Prepared:** 2026-10-11 (task MLH-T19). Re-verify line numbers before relying on them; they go stale.
**Scope:** every table in the ORM (`backend/app/models/*.py`) that can hold personal data, checked against the schema source of truth `docs/kaihle_v2_1_schema.sql` (header says v2.2).

Every statement that implies a legal position is tagged **COUNSEL REVIEW**. Nothing here says Kaihle meets any law; that is for counsel to confirm.

## 1. How this was verified

1. All ORM tables were loaded from `app.models` (`Base.metadata`) and compared, column by column, with the `CREATE TABLE` blocks in `docs/kaihle_v2_1_schema.sql`.
2. Result: 54 ORM tables, 51 `CREATE TABLE` statements in the SQL file (the 51st is `alembic_version`).
3. The conflicts found are listed in section 5 and again in `GAPS.md` (G-14). Where ORM and SQL disagree, the SQL is the source of truth by CONSTITUTION Rule 8, so the ORM/migration side is the one that needs reconciling; **no guess was made about which is right for the live database**.

## 2. Classification key

| Code | Meaning |
|---|---|
| ID | Direct identifier (name, email, username, contact details) |
| CHILD-TEXT | Free text written by a student (aged 11-18) |
| PROFILE | Derived or selected learning-profile data about a student (modality scores, interests, work style) |
| RECORD | Academic performance or progress record about a student |
| STAFF-TEXT | Free text or content written by a teacher or administrator |
| OPS | Operational metadata (logs, tokens, correlation ids, cost) |
| ORG | School / billing / contract data (not about a child) |

## 3. Tables that hold personal data

"Seen by" is limited to what the code was checked to do. Role access beyond what is cited here must be confirmed against the route layer by whoever finalises the policy. Cross-school access returns 403 (CONSTITUTION section 7); every non-curriculum read is intended to filter by `school_id`.

| Table (ORM : SQL) | Personal data held | Class | Purpose | Seen by (verified / stated) |
|---|---|---|---|---|
| `users` (`models/user.py:56` : SQL 670) | `first_name`, `last_name`, `email` (nullable, unique), `username` (nullable, unique), `hashed_password` (bcrypt, `core/security.py:16`), `role`, `school_id`, `is_active`, `last_login_at`, `must_change_password`, `permissions` (JSONB) | ID | Accounts, login, role-based access | The user; their school admin; Kaihle admin. School-admin scope per CONSTITUTION |
| `student_profiles` (`user.py:96` : 747) | `user_id`, `grade_id`, `age` (integer, nullable), `is_learning_profile_complete` | ID/RECORD | Grade placement and onboarding gate (Rule 11). No date of birth is stored; only `age` | Student; teachers of the student; school admin |
| `teacher_profiles` (`user.py:122` : 777) | `qualifications` (JSONB), `experience_years`, `bio`, `hire_date` | ID/STAFF-TEXT | Teacher profile | Teacher; school admin |
| `parent_student` (`user.py:140` : 731) | parent-to-child link (`parent_id`, `student_id`) | ID | Lets a parent see their child | Parent; school admin |
| `auth_tokens` (`user.py:165` : 708) | `user_id`, `token_hash` (hash, not the token), `type` (magic link, refresh, password reset, impersonation), `expires_at`, `used_at` | OPS | Login and session security | Backend only |
| `student_learning_profiles` (`models/onboarding.py:25` : 796) | `modality_scores`, `work_style`, `interests` (array of selected keys), `questionnaire_version`, `completed_at`, `school_id` | PROFILE | Personalises explanations, quizzes, tutor chat. **Raw questionnaire answers are not stored**; only the scores/keys derived from them (`services/onboarding_service.py:132-140`) | Student; **sent to the LLM provider** (see `LLM_DATA_FLOWS.md`); class aggregates reach teachers' lesson plans |
| `schools` (`models/school.py:104` : 613) | `name`, `slug`, `address`, `city`, `country`, `contact_email`, `contact_phone`, `website`, `logo_url`, `timezone`, `status` | ORG | Tenant record. City and country are sent to the LLM provider in lesson-plan prompts (`ai/prompts/lesson_plan.jinja2`) | School admin; Kaihle admin |
| `classes` (`school.py:64` : 857) | `name`, `academic_year`, `teacher_id`, `school_id` | ORG | Class definition. `name` is teacher-written and is sent in lesson-plan prompts | Teacher; school admin |
| `class_enrollments` (`school.py:21` : 883) | `student_id`, `class_id`, `enrolled_at`, `is_active`, `onboarding_diagnostic_status` | RECORD | Roster | Teacher; school admin |
| `class_topics` (`class_topic.py:21` : 912) | class-to-topic coverage | ORG | Not personal on its own | Teacher |
| `assessments` (`assessment.py:74` : 939) | `title`, `instructions`, `created_by`, `school_id`, `class_id`, deadlines | STAFF-TEXT | Teacher-created assessments | Teacher; students in the class |
| `student_attempts` (`assessment.py:188` : 1030) | `student_id`, `overall_score`, `time_taken_seconds`, `started_at`, `completed_at`, status | RECORD | Attempt record. No `school_id` column (see GAPS G-13) | Student; teacher; parent view per product design |
| `student_responses` (`assessment.py:230` : 1064) | `answer_given` (TEXT, may be free text), `is_correct`, `score`, `ai_feedback`, `hints_used`, `time_taken_ms` | CHILD-TEXT/RECORD | The student's answers. No `school_id` column. No call that sends `answer_given` to an LLM was found (the assessment grading path is deterministic) | Student; teacher |
| `student_attempt_subtopic_scores` (`assessment.py:276` : 1310) | per-subtopic score and counts | RECORD | Mastery inputs | Student; teacher |
| `gap_states` (`models/gap.py:23` : 1098) | `student_id`, `subtopic_id`, `class_id`, `mastery_score`, `confidence`, attempt counts, `needs_review` | RECORD | Mastery tracking | Student; teacher; parent per product design |
| `mastery_priors` (`gap.py:77` : 1139) | population statistics per subtopic (alpha/beta) | OPS | Aggregate; not individual | Backend |
| `mini_course_chat_messages` (`models/mini_course.py:180`; **not in SQL**) | `student_id`, `subtopic_id`, `school_id`, `role` (`student`/`ai`), `content` (TEXT, raw), `created_at` | **CHILD-TEXT** | Persistent AI-tutor chat history. Student messages are saved before streaming (`api/v1/routes/students.py:469`); AI reply saved after (`:531`). All turns retained; only last 50 returned (`services/mini_course_service.py:785-795`) | Read paths found in code: the student only. Visible to anyone with DB access and, via LLM Logs, to Kaihle admin (prompt contains the same text) |
| `mini_course_quiz_responses` (`mini_course.py:237`; **not in SQL**) | `question_text`, `student_answer` (TEXT; free text for `open_ended`, option key for `mcq`), `ai_grade`, `ai_feedback`, `score`, `school_id` | **CHILD-TEXT** | Open-answer transfer questions and MCQs, AI-graded (`mini_course_service.py:959-968`) | Student (`mini_course_service.py:662-668`); aggregate score feeds progress |
| `subtopic_course_progress` (`mini_course.py:34` : 1457) | `student_id`, `school_id`, `last_visited_at`, flags, `check_questions_score` | RECORD | Progress | Student; teacher |
| `subtopic_content_feedback` (`mini_course.py:85` : 1480) | `student_id`, `feedback_type` (thumbs), **`comment` (TEXT, nullable)** | CHILD-TEXT | Student feedback on AI content | Teacher / Kaihle admin (review flow) |
| `mini_course_student_overrides` (`mini_course.py:132` : 234) | teacher-chosen interest category for a student | PROFILE | Teacher override | Teacher |
| `student_lesson_packs` (`models/student_lesson_pack.py:43` : 1268) | `student_id`, `title`, `mastery_score`, lifecycle timestamps | RECORD | Assigned content packs | Student; teacher |
| `lesson_plans` (`models/lesson_plan.py:45` : 1590) | `class_context_snapshot` (class aggregates: modality distribution, top interests, student count), `generated_plan`, `teacher_edits`, **`raw_llm_output` (TEXT)**, `failure_reason`; no `school_id` column (via `class_id`) | STAFF-TEXT/PROFILE (aggregate) | Teacher lesson plans | Teacher; school admin |
| `study_plans`, `study_plan_resources`, `study_plan_quizzes` (`models/study_plan.py:37/90/127` : 1505/1532/1560) | per-student plan, `student_answers` (JSONB), quiz `score` | RECORD | **Feature removed from the product 2026-05-21; tables and code remain.** Existing rows may still hold student answers (GAPS G-12) | Not surfaced in current product |
| `parent_report_snapshots` (`models/parent.py:20` : 1637) | weekly `narrative` (TEXT), `gap_summary`, `improvements`, `needs_work`, `email_sent_at`; no `school_id` column | RECORD | Parent weekly report. **No code writing to this table was found** (`grep` of `app/` outside models returns none); verify whether rows exist | Parent |
| `subtopic_content` (`models/subtopic_content.py:56` : 1183) | explanation text, quizzes, videos; `teacher_explanation` and its author id; `school_id` (school scope) | STAFF-TEXT | Curriculum and school content. Not about children | Students (approved); teachers; Kaihle admin |
| `subtopic_explanation_suggestions` (`models/subtopic_explanation_suggestion.py:22`; **not in SQL**) | `suggested_by_id` (teacher), `original_text`, `suggested_text`, `admin_note` | STAFF-TEXT | Teacher suggestions to Kaihle admin | Kaihle admin |
| `question_review_items` (`assessment.py:358` : 1351) | `submitted_by`, suggested question/answer/explanation, `reason` (TEXT), `admin_note`, `school_id` | STAFF-TEXT | Teacher question submissions | Kaihle admin |
| `question_bank` (`models/curriculum.py:403` : 534) | question content; `submitted_by` and `school_id` for teacher-submitted items | STAFF-TEXT | Question bank | Per assessment use |
| `lo_review_items` (`curriculum.py:500` : 1401) | curriculum remap review items | OPS | Not personal | Kaihle admin |
| `school_subscriptions`, `subscription_invoices`, `trial_extensions` (`models/billing.py:95/146/186` : 1704/1734/1766) | student counts, amounts, payment status; `trial_extensions` holds the granting Kaihle admin's user id | ORG | Billing. No payment-card data is stored in these models | School admin; Kaihle admin |
| **`llm_usage_events`** (`models/llm_usage.py:38` : SQL 1931) | `task`, `model`, `component`, `run_id`, token counts, `latency_ms`, `estimated_cost_usd`, `succeeded`, `error_type`, `error_detail` (<= 2000 chars, `ai/usage_sink.py:88`), `correlation_id`, `school_id` (nullable), `created_at`, and **raw `prompt_text` and `response_text`** (TEXT, no masking or truncation, product decision 2026-09-09, `llm_usage.py:62-75`). **No user/student id column** | **CHILD-TEXT, PROFILE, OPS** | Cost reporting and the Kaihle-admin "LLM Logs" viewer | Kaihle admin only: `GET /api/v1/platform/llm-logs` and `/{id}` use `require_role(KAIHLE_ADMIN)` (`api/v1/routes/platform.py:185-193`, `:241-245`). Written only when `LLM_USAGE_TRACKING_ENABLED=true` (default false). **Nothing deletes these rows** |

Curriculum-only tables (`curricula`, `subjects`, `grades`, `topics`, `curriculum_*`, `subtopics`, `learning_objectives`, `interest_categories`, `curriculum_chunks`, etc.) hold no personal data and are school-agnostic by design (Rule 2).

## 4. Other places personal data can sit (outside the tables)

| Location | What | Evidence |
|---|---|---|
| Application logs (stdout JSON) | Request log lines carry `user_id` (an opaque uuid), `school_id`, path, status (`core/middleware.py:73-81`). **Email addresses are also logged**: `logger.info("email_sent", to=to, ...)` (`services/email_service.py:48`) and `teacher_email` (`tasks/mini_course_tasks.py:59`). Student ids appear in many log lines (e.g. `concept_guide_service.py:166`). | Rule 02-security says PII must not be logged. See GAPS G-8 |
| Outbound email | Recipient address, first name, and for school-created accounts a **temporary password in the email body** (`services/user_service.py:457-465`, template `emails/welcome_credentials.html.jinja2:30`) | See GAPS G-9 |
| Redis (Celery broker/results) | Task arguments, such as subtopic ids and class ids, for the duration of the task. Contents were not audited | Not verified; GAPS G-15 |
| Database export tool | `POST /api/v1/db-tools/export` (`api/v1/routes/db_tools.py:211`) dumps every table, including `users` and `llm_usage_events`, as SQL for Kaihle admin. The import side is blocked in production (`:302`); **the export side is not** | GAPS G-10 |
| Impersonation | Kaihle admin can mint a short-lived session as another user (`AuthTokenType.IMPERSONATION`, `models/user.py:50`; config in `.env.example` lines on `IMPERSONATION_*`) | Needs a policy line (audit trail not verified) |
| Browser | The frontend apps load web fonts from a third-party font host (`frontend/apps/*/src/index.css`, line 1-2), so a visitor's IP address is sent to that host. Student mini-course pages embed YouTube (`frontend/apps/student/src/pages/mini-course/MiniCoursePage.tsx:155`), which can set its own cookies | **COUNSEL REVIEW** (cookie / tracking notice). No analytics SDK was found in the repo |
| S3 | `AWS_S3_BUCKET` and `AWS_REGION` exist in config (`core/config.py:24`) but **no code that reads or writes S3 was found** | Treat S3 as "configured, not used by current code" and confirm with deployment |

## 5. ORM vs schema-file conflicts (do not guess; reconcile)

Found by the comparison described in section 1.

| # | Item | ORM | `kaihle_v2_1_schema.sql` |
|---|---|---|---|
| C1 | `mini_course_chat_messages`, `mini_course_quiz_responses`, `subtopic_explanation_suggestions`, `curriculum_migrations` | Exist (Alembic `f892502b0975` adds the chat and quiz tables) | **Absent** from the SQL file. The first two hold child-written text, so the file the policy would be read against is incomplete exactly where it matters |
| C2 | `llm_usage_events.prompt_text`, `.response_text` | Present (`llm_usage.py:74-75`) | **Absent** (SQL block ends at `school_id`, `created_at`) |
| C3 | `subtopic_content.school_id`, `.scope` | Present (`subtopic_content.py:65-74`) | Absent |
| C4 | `users.permissions` (JSONB) | Present (`user.py:90`) | Absent |
| C5 | `subtopics.tier`; `curriculum_subjects.created_at/updated_at`; `study_plan_resources.updated_at` | Present | Absent |

The comparison script also printed `REFERENCES` as a "SQL-only column" for `learning_objectives`, `question_bank`, `subtopic_objectives`, `subtopics`, `trial_extensions`. That is an artefact of the script's line parser reading multi-line column definitions, not a real conflict.

## 6. `school_id` coverage (relevant to the multi-tenancy statements in the policy)

ORM tables with no `school_id` column that nonetheless relate to students: `student_attempts`, `student_responses`, `student_attempt_subtopic_scores`, `gap_states`, `lesson_plans`, `parent_report_snapshots`, `study_plans` (+ children), `class_enrollments`, `parent_student`, `student_profiles`, `auth_tokens`. Tenancy for these is enforced through joins (e.g. to `classes` or `users`), which CONSTITUTION Rule 2 does not literally require to be a column but which the policy should not over-describe. **COUNSEL REVIEW** for any sentence claiming "each school's data is separated".
