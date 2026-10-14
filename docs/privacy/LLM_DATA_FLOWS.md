# Kaihle LLM Data Flows

**Status:** DRAFT for legal / DPO review. Engineering fact-gathering, not legal advice.
**Prepared:** 2026-10-11 (task MLH-T19). Line numbers were re-checked on this date and go stale.

This document says exactly what leaves Kaihle for an AI provider, per router task, and what is stored back. Anything implying a legal position is tagged **COUNSEL REVIEW**.

## 1. The one route out

Every LLM or embedding call goes through `backend/app/ai/providers/router.py` (LiteLLM). `complete()` is at line 185, `stream_sse()` at 291, `embed_batch()` at 388. Which provider and which model handle a task is decided only by environment variables (`TASK_MODEL_MAP`, lines 43-60; optional per-task `*_API_BASE`, lines 62-79). A task can be pointed at a self-hosted server. **The provider for each task is therefore a deployment choice, not a code fact**; see the deployer table in section 5.

The router sends the message list as given. It adds no student identifier. It does not mask or redact (a deliberate product position; see GAPS G-4).

One exception to "every call goes through the router": `backend/scripts/seed_subtopic_content.py` (docstring lines 13-16, `litellm.completion` at line 362) calls LiteLLM directly. It is an offline seed script that sends curriculum subtopic data only, no student data, but it bypasses CONSTITUTION Rule 4 (GAPS G-11).

## 2. What is stored back: `llm_usage_events`

For every call the router writes one row via `ai/usage_sink.py` (`record_usage`, lines 34-103), **only when `LLM_USAGE_TRACKING_ENABLED=true`** (default `false`, `.env.example`). The row holds the full **prompt and response text, raw** (`usage_sink.py:91-92`; `models/llm_usage.py:62-75`), token counts, cost, task, model, component, `correlation_id`, and a nullable `school_id` taken from the request's JWT (`core/middleware.py:49-55`). It holds **no student id**, but the text itself can identify a child (their question, a name they typed). Embedding calls store the joined input texts as `prompt_text` (`router.py:463`). On failure the exception text is stored too (`error_detail`, capped at 2000 characters, `usage_sink.py:88`), which can echo provider-side messages.

Read access: Kaihle administrator only (`api/v1/routes/platform.py:185-193`, `:241-245`). Deletion: **none exists** (GAPS G-1).

## 3. Per-task table

16 entries are in `TASK_MODEL_MAP` (the task brief said 15; the sixteenth is `eval_judge`). Each appears exactly once. "Child-written text" means words a student typed. "Student-derived data" means selected options or scores about a student that are not typed text.

| # | Task | Call site(s) | What reaches the provider | Child-written free text? | Mode | Where the response goes |
|---|---|---|---|---|---|---|
| 1 | `gap_classification` | **None.** Mapped at `router.py:44` and configured at `core/config.py:67`; no caller found | Nothing today | No | Dead | n/a |
| 2 | `study_plan` | **None.** `router.py:45`; no caller found. Feature removed 2026-05-21 | Nothing today | No | Dead | n/a |
| 3 | `lesson_plan` | `tasks/lesson_plan_tasks.py:269-270` (retry `:301-302`), prompt built at `:246-247` from `ai/prompts/lesson_plan.jinja2`; also Kaihle-admin smoke test `api/v1/routes/smoke_tests.py:323-324, :358-359` | Class name (teacher-written, template line 4), subject, grade, duration, selected subtopic names and objectives, **school city and country** (template lines 18-20), student **count**, **class-average** modality percentages and top-5 interest keys (template lines 35-36). **No student names, ids or individual rows** | **No.** Aggregate student-derived data only | Background (Celery), teacher-triggered | `lesson_plans.generated_plan` and `raw_llm_output` (`models/lesson_plan.py:61,79`); teacher sees it; an email is sent to the teacher on completion or failure (`lesson_plan_tasks.py:57-90`) |
| 4 | `question_generation` | `scripts/generate_gap_questions.py:1067-1068` | Curriculum subtopic name, learning objectives, subject, grade; fixed system prompt | No | Batch, offline script | `question_bank` rows (after review) |
| 5 | `quiz_generation` | `ai/quiz_generator.py:421-422`. Callers: `tasks/study_plan_tasks.py:363` (removed feature, dead path) and Kaihle-admin smoke test `smoke_tests.py:432` | Subject, subtopic name and objectives, approved explanation text, a **mastery percentage** (`quiz_generator.py:46`, `:250`), difficulty label, up to two student interest keys filtered to the subject (`:245`, template lines 55-57) | No. Student-derived data only (mastery %, interest keys). Only reachable today through the admin smoke test, which can name a real `student_id` (`smoke_tests.py:429-435`) | Interactive (admin test); dead otherwise | Returned to caller; study-plan storage is dead code |
| 6 | `lo_matching` | `services/lo_review_service.py:857` (`adjudicate_question`, templates `lo_matching_question.jinja2`) and `scripts/map_questions_to_lo.py:167` (`lo_matching.jinja2`) | Old and candidate learning objectives, subject, grade, question text and options from the question bank | No | Kaihle-admin review action and offline script | Parsed choice stored in review items; not stored as text |
| 7 | `question_quality` | `scripts/validate_and_fix_questions.py:698-699` | Batches of question-bank questions (text, options, answers, explanations) plus subtopic context | No | Batch, offline script | Validation results and corrected questions in the question bank |
| 8 | `student_pack` | **None.** `router.py:51`; config `core/config.py:107`; no caller found (the `StudentLessonPack` model exists but generates nothing via the router) | Nothing today | No | Dead | n/a |
| 9 | `embeddings` | `router.py:388` (`embed_batch`) via `ai/similarity.py:76`; callers `services/lo_review_service.py:589` (the **Kaihle admin's typed search text**), `:709` (question-bank text), and curriculum scripts (`scripts/create_learning_objectives.py:283`, `scripts/map_questions_to_lo.py:237`) | Objective names and question text; one admin-typed search string | No | Admin action / batch | Vectors in the learning-objective tables (pgvector columns); input text copied to `llm_usage_events.prompt_text` |
| 10 | `concept_guide` | `services/concept_guide_service.py:173-174` (explanation; route `students.py:191`) and `:244-245` (follow-up on an MCQ answer; route `students.py:250`); admin smoke test `smoke_tests.py:180-181` | Subtopic name, description, objective, keywords; student's dominant modality label, **up to two interest keys, work-style flags** (`concept_guide.jinja2:4-7`); **the student's optional typed question** (`concept_guide.jinja2:17`, request limit 500 chars, `schemas/students.py:86`). The follow-up call sends the question, options and a one-letter answer supplied by the client (`schemas/students.py:105-112`; `student_answer` max 10 chars) | **Yes, conditionally** (the optional question). The one-letter MCQ answer is not free text, but the client-supplied `question`/`options` strings are unconstrained | Interactive | Returned to the student. Not saved in any domain table; only in `llm_usage_events` |
| 11 | `explain_this` | `services/concept_guide_service.py:383-384` (route `students.py:374`) and `:479-480` (persistent chat, route `students.py:437`) | System prompt (`explain_this.jinja2`: subtopic, topic, subject, grade, modality label, one interest category). **The student's question** as the user message, and for chat **up to 10 prior turns of the student's own and the AI's earlier messages** (`students.py:480`, `concept_guide_service.py:473-476`). Limit 500 chars per question (`schemas/mini_course.py:158`) | **Yes**, always | Interactive (streamed) | Streamed to the student; chat route also **saves both sides in `mini_course_chat_messages`** (`students.py:469`, `:531`) |
| 12 | `mini_course_explanation` | `services/mini_course_generation_service.py:591-592` (explanation), **`:493-494` (also used for quiz questions, template `mini_course_quiz.jinja2`)**, `tasks/content_tasks.py:74-75` | Subtopic, topic, subject, grade, one of a fixed set of interest-category names, and (content_tasks) the approved base explanation text | **No.** Nothing per-student is sent; the interest category is a fixed catalogue value, not a student's own entry | Background (Celery) / teacher or admin action | `subtopic_content` (pending review, then approved) |
| 13 | `content_seed` | `tasks/teacher_content_tasks.py:223-224` (quiz) and `:248-249` (explanation); `api/v1/routes/subtopic_content.py:949-950` (Kaihle-admin quiz generation). Offline seed script uses direct LiteLLM (section 1) | Subtopic name, subject, grade, objective (prompt strings at `teacher_content_tasks.py:36,64`) | No | Background (Celery) / admin action | `subtopic_content` |
| 14 | `transfer_question` | `services/mini_course_service.py:884-885`; prompt `transfer_question.jinja2` | Subtopic name, objective, keywords, the student's **dominant modality label and top two interest keys** (`:874-881`; template lines 20-22) | **No typed text.** Student-derived profile data only | Interactive | Returned to the student; the question text is later stored in `mini_course_quiz_responses.question_text` (`mini_course_service.py:959-968`) |
| 15 | `grade_open_answer` | `services/mini_course_service.py:152-157` (`request_grade_completion`), prompt at `:116-123`, used at `:931-939`; template `grade_open_answer.jinja2` | Subtopic name, objective, the question, and **the student's written answer** (template line 15; request limit 1000 chars, `schemas/mini_course.py:170`) | **Yes**, always | Interactive | Grade + feedback returned; stored as `mini_course_quiz_responses` (`student_answer`, `ai_grade`, `ai_feedback`, `mini_course_service.py:959-968`) |
| 16 | `eval_judge` | `backend/evals/judge.py:58-59`, offline evaluation harness only (not called by the app) | Today: synthetic evaluation datasets. After task T18: scrubbed samples of production prompt/response text (see `RETENTION_AND_EVALUATION.md`) | Not today. **Yes after T18**, for sampled student-text tasks, after scrubbing | Offline / scheduled | Judge output; only pass/fail metrics are meant to be kept (T18 D9) |

## 4. Check against T18's `contains_student_text` list

T18 (decision D5) will list: `grade_open_answer`, `explain_this`, `concept_guide`, `transfer_question`, `mini_course_explanation`, `lesson_plan`. Verified against the call sites above:

| Task | In T18 list | Verified finding | Verdict |
|---|---|---|---|
| `grade_open_answer` | yes | Always carries the student's written answer | **Agrees** |
| `explain_this` | yes | Always carries the student's question and prior chat turns | **Agrees** |
| `concept_guide` | yes | Carries the student's typed question when provided; otherwise only profile-derived flags | **Agrees** (conditional on the field) |
| `transfer_question` | yes | **No typed text.** Carries student-derived profile data (modality label, two interest keys) | **Disagrees on "text"**; agrees if the flag means "student data". Recommend keeping it flagged and renaming the concept to "student data" |
| `mini_course_explanation` | yes | **No student text and no per-student data.** Only subtopic and a fixed interest-category name. Also used for quiz generation | **Disagrees.** Safe to treat as no-student-data |
| `lesson_plan` | yes | **No student text.** Class-level averages, counts, school city/country, teacher-written class name | **Disagrees on "text"**; carries aggregate student-derived data and location. Recommend keeping it flagged because location plus class size could single out a micro-school |

Not on the T18 list but worth stating: `quiz_generation` sends a student's mastery percentage and interest keys, but is only reachable from a Kaihle-admin test route today.

No other task carries child-written text. The `embeddings` task only ever embeds admin text and question-bank text.

**Recommended change to T18 (for Vibhu to decide, not made here):** split the flag in two, `contains_student_text` (grade_open_answer, explain_this, concept_guide) and `contains_student_data` (adds transfer_question, lesson_plan, quiz_generation), and require the acknowledgement in D5 for either. `mini_course_explanation` should not carry either flag.

## 5. Subprocessors and other recipients

Providers are not named here: they depend on how each deployment sets its environment. **TO BE COMPLETED BY DEPLOYER.** COUNSEL REVIEW for each row: processor role, contract terms, retention and training-use terms, cross-border transfer basis.

| Kind | Evidence in code | Data it receives | Provider name | Region(s) | Terms / DPA link | Retention at provider | Used for provider-side training? |
|---|---|---|---|---|---|---|---|
| LLM provider(s), configurable per task | `router.py:43-79`; provider key variables bridged at `router.py:29-36`; `.env.example` | See section 3 | TO BE COMPLETED BY DEPLOYER | TO BE COMPLETED BY DEPLOYER | TO BE COMPLETED BY DEPLOYER | TO BE COMPLETED BY DEPLOYER | TO BE COMPLETED BY DEPLOYER |
| Embedding provider (may be the same) | `router.py:388-466` | Objective and question text, admin search text | TO BE COMPLETED BY DEPLOYER | TO BE COMPLETED BY DEPLOYER | TO BE COMPLETED BY DEPLOYER | TO BE COMPLETED BY DEPLOYER | TO BE COMPLETED BY DEPLOYER |
| Evaluation judge provider (must differ from the provider whose output is judged, T18 D4) | `evals/judge.py`; `LLM_EVAL_JUDGE_MODEL` in `.env.example` | Today: synthetic data. After T18: scrubbed samples | TO BE COMPLETED BY DEPLOYER | TO BE COMPLETED BY DEPLOYER | TO BE COMPLETED BY DEPLOYER | TO BE COMPLETED BY DEPLOYER | TO BE COMPLETED BY DEPLOYER |
| Transactional email delivery API | `services/email_service.py` (hosted email API client, API key from settings); other direct sends in `tasks/*.py` | Recipient address, first name, subject, body (login links, reset links, **temporary passwords**, lesson-plan notices) | TO BE COMPLETED BY DEPLOYER | TO BE COMPLETED BY DEPLOYER | TO BE COMPLETED BY DEPLOYER | TO BE COMPLETED BY DEPLOYER | n/a |
| Video search API | `services/youtube_service.py:54-100`: YouTube Data API search for educational videos, queries built from subtopic names | Subtopic/subject search text and the deployer's API key. No student data | YouTube Data API (fixed by the code) | n/a (API call from the server) | TO BE COMPLETED BY DEPLOYER | n/a | n/a |
| Video embeds in the student app | `frontend/apps/student/src/pages/mini-course/MiniCoursePage.tsx:155` embeds `youtube.com` players | Student browser contacts the video host; IP address, cookies per host policy | YouTube (fixed by the code) | n/a | **COUNSEL REVIEW** (children's use; consider privacy-enhanced embed) | n/a | n/a |
| Web-font host | `frontend/apps/*/src/index.css` lines 1-2 import a third-party font stylesheet | Visitor IP address and browser headers | Google Fonts (fixed by the code) | n/a | **COUNSEL REVIEW** | n/a | n/a |
| Hosting / database / cache | CONSTITUTION section 2: Render.com, PostgreSQL, Redis | All data in `DATA_INVENTORY.md` | Render.com (per CONSTITUTION; confirm for the actual deployment) | TO BE COMPLETED BY DEPLOYER | TO BE COMPLETED BY DEPLOYER | TO BE COMPLETED BY DEPLOYER | n/a |
| Object storage | CONSTITUTION section 2 lists AWS S3; `core/config.py:24` has bucket/region settings (`.env.example` default region `ap-southeast-1`) | **No code that reads or writes S3 was found** | AWS S3 per CONSTITUTION (confirm whether used) | TO BE COMPLETED BY DEPLOYER | TO BE COMPLETED BY DEPLOYER | TO BE COMPLETED BY DEPLOYER | n/a |
| Evaluation telemetry | `.env.example` sets `DEEPEVAL_TELEMETRY_OPT_OUT=YES`; the harness forces it | Would send harness data to the DeepEval vendor if enabled | DeepEval (opted out by default) | n/a | Confirm the opt-out is also set wherever production evaluation runs | n/a | n/a |

No analytics, error-reporting or advertising SDK was found in the backend or frontend (search of `backend/app`, `frontend/apps`, `frontend/packages` and `package.json` files). `frontend/packages/ui/src/components/ErrorBoundary.tsx:29` only mentions error-reporting services in a comment.

## 6. Cross-border transfer note

Pilot schools are in Southeast Asia (CONSTITUTION section 1). The hosting region, every provider's processing region, and the legal basis for any transfer are unknown to the code. **COUNSEL REVIEW**: transfer mechanisms per country, any local-storage obligations for children's data, and whether schools must be told provider regions.
