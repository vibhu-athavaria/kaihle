# Retention Schedule (Proposed) and Production-Evaluation Rules

**Status:** DRAFT for decision by Vibhu and review by counsel. Engineering proposal, not legal advice.
**Prepared:** 2026-10-11 (task MLH-T19). Tagged **COUNSEL REVIEW** wherever a legal position is implied.

---

## Part A. Proposed retention schedule

**PROPOSED. Requires Vibhu / counsel decision. Nothing in this table is implemented.** No automatic deletion exists for any table today (GAPS G-1, G-2). Periods are deliberately left as `[PERIOD: TO BE DECIDED]`; this document does not invent them. The "recommended shape" column is the engineering view of how the rule should work, so the decision is about the number, not the design.

| Data class | Tables | Recommended shape | Period | Notes / risks |
|---|---|---|---|---|
| **Raw AI prompt and response text** | `llm_usage_events.prompt_text`, `.response_text` | **Bounded window.** After the window, set both columns to NULL and keep the row. Never keep forever. Purge job must be idempotent (a retried run leaves the same end state) and logged | `[PERIOD: TO BE DECIDED]` (shortest of any class; this is the largest store of child-written text) | Holds typed tutor questions, written answers, prior chat turns. No user id, so a deletion request for one child cannot find their rows by id; time-based deletion is the only practical control. Needs a migration if a "text purged at" marker is wanted |
| **AI call metadata** | `llm_usage_events` (all other columns) | Keep longer than the text, for cost reporting | `[PERIOD: TO BE DECIDED]` | Contains `school_id`, `correlation_id`, `error_detail` (up to 2000 chars, may echo content). Consider also nulling `error_detail` with the text |
| **Student chat history** | `mini_course_chat_messages` | Keep while the student is enrolled; delete on account removal or after a window | `[PERIOD: TO BE DECIDED]` | Currently all turns are kept; only the last 50 are shown |
| **Written answers to open questions** | `mini_course_quiz_responses` (`student_answer`, `ai_feedback`) | Keep while the learning record is needed; the free-text columns could be cleared sooner than the score | `[PERIOD: TO BE DECIDED]` | Score aggregate feeds progress and should outlive the text |
| **Assessment responses** | `student_responses.answer_given`, `student_attempts`, `student_attempt_subtopic_scores` | Tied to school's academic record needs | `[PERIOD: TO BE DECIDED]` | Counsel / school to say whether this is an education record the school must retain |
| **Mastery and progress** | `gap_states`, `subtopic_course_progress`, `student_lesson_packs` | While enrolled, then delete or anonymise | `[PERIOD: TO BE DECIDED]` | Derived data; document origin and failure mode if kept after source deletion |
| **Learning profile** | `student_learning_profiles` | Delete on account removal | `[PERIOD: TO BE DECIDED]` | Derived scores, no raw answers |
| **Accounts and identity** | `users`, `student_profiles`, `teacher_profiles`, `parent_student` | Active while employed / enrolled; then deactivate, then delete after a grace period | `[PERIOD: TO BE DECIDED]` | `users.school_id` is `ON DELETE SET NULL` and many child tables cascade from `users`; test cascade end to end before building deletion (GAPS G-2) |
| **Session and login tokens** | `auth_tokens` | Delete expired and used tokens | `[PERIOD: TO BE DECIDED]` | Hashes only; low risk but unbounded growth |
| **Feedback comments** | `subtopic_content_feedback.comment` | Same as chat | `[PERIOD: TO BE DECIDED]` | Free text from children |
| **Lesson plans** | `lesson_plans` (incl. `raw_llm_output`) | Teacher-owned; `raw_llm_output` is debug data and could be cleared early | `[PERIOD: TO BE DECIDED]` | Aggregates only, no per-student rows |
| **Removed study-plan data** | `study_plans`, `study_plan_resources`, `study_plan_quizzes` | **Delete.** The feature was removed 2026-05-21 | `[DECISION: TO BE MADE]` | Existing rows may hold student answers; deleting data is an explicit instruction Vibhu has not given, so this document only flags it (GAPS G-12) |
| **Parent report snapshots** | `parent_report_snapshots` | As accounts | `[PERIOD: TO BE DECIDED]` | No writer found in code; confirm whether rows exist |
| **Application logs** | stdout log pipeline | Bounded rolling window set at the hosting provider | `[PERIOD: TO BE DECIDED]`; confirm what the host actually does | Contain `user_id`, `school_id`, and some email addresses (GAPS G-8) |
| **Evaluation results** | `eval_runs`, `eval_results` (future, T18) | Metrics only, no text; keep long enough to show trends | `[PERIOD: TO BE DECIDED]` | See Part B rule 5 |
| **Backups and database exports** | Provider backups; `POST /api/v1/db-tools/export` output | Backups age out on the hosting provider's schedule; exports are copies and must be handled like the source | `[PERIOD: TO BE DECIDED]` | The export route is not disabled in production (GAPS G-10) |
| **Billing records** | `school_subscriptions`, `subscription_invoices`, `trial_extensions` | Business / tax record rules | `[PERIOD: TO BE DECIDED]` | **COUNSEL REVIEW** |

**COUNSEL REVIEW** for the whole table: statutory minimum and maximum periods per country, rules for children's data, and school record-keeping duties.

---

## Part B. Rules for using production output for evaluation (referenced by T18)

These rules are the privacy side of T18 (`T18-production-sampling-and-quality-view.md`). Decision numbers are T18's. If T18 changes, update this part in the same change.

**R1. Production text may be read and judged at runtime, but never written to disk outside the product database (T18 D1).**
Committed datasets, fixtures, CI artifacts, reports, git history and logs stay synthetic. Production text is read from `llm_usage_events`, scrubbed, sent to the judge, and discarded. It is never copied into a file, a result table, a log line, or a pull request. A change that would need to do so (for example exporting real items to a labelling sheet) needs its own decision (T18 lists this as follow-up T18b).

**R2. Scrub before judging, and fail closed (T18 D8).**
Emails, phone numbers (including regional formats), URLs, long digit runs, and known user and school names are replaced with fixed tokens before any text leaves for the judge. After scrubbing the same patterns are checked again; any remaining hit, or any error in scrubbing, means the row is **skipped and counted** and is never sent. The scrubber is a best-effort control. It cannot reliably catch free-text locations, relatives' names or circumstances that a child writes, and the product UI and policy say so (Policy draft section 7). **COUNSEL REVIEW** whether best-effort scrubbing is an acceptable control for children's free text, or whether student-text tasks should wait for a stronger control.

**R3. Per-task allowlist, empty by default, with an explicit acknowledgement (T18 D5).**
No task is evaluated until the Kaihle administrator enables it. Each task carries a `contains_student_text` flag in code. Enabling a flagged task requires a ticked acknowledgement, stored with who and when. Rollout order: tasks with no student text first; student-text tasks only after this policy is approved by counsel. The flag list needs review against what the code actually sends: see `LLM_DATA_FLOWS.md` section 4, which finds that `mini_course_explanation` carries no student data at all and that `transfer_question` and `lesson_plan` carry student-derived data but no typed text. Reasonable minimum: `grade_open_answer`, `explain_this`, `concept_guide` are the student-text tasks.

**R4. Results contain no text (T18 D9).**
Result tables hold only: run id, usage-event id, check name, kind, pass / fail / indeterminate, rubric hash and status, and a `school_id` copied from the event. The judge's free-text "evidence" is not stored, because it can quote the student. To investigate a failure the administrator opens the existing LLM Logs entry by id, which already has an access model.

**R5. Kaihle administrator only (T18 D10).**
Every evaluation endpoint and page requires `KAIHLE_ADMIN`, with the explicit role check from CONSTITUTION Rule 12. No teacher, school administrator or parent sees, reviews or labels any production item, and no teacher is asked to. Human labelling of real items, if ever needed, is done by the Kaihle administrator.

**R6. Judge-provider terms are reviewed before the first run.**
The judge model is set by environment and must be a different provider family from the model that produced the output (T18 D4; same-vendor rows are skipped). Before any production text goes to a judge provider, Kaihle records in the subprocessor table (`LLM_DATA_FLOWS.md` section 5) that provider's retention and training terms and region. **COUNSEL REVIEW** that those terms are acceptable for children's text. Telemetry opt-out for the evaluation framework must be set in any environment that runs production evaluation.

**R7. Budget and switches fail closed (T18 D2, D3).**
Budget defaults to zero and nothing runs until the administrator sets it. Evaluation refuses to run if usage tracking is off, because the cost rows that enforce the budget would not exist. Sampling is read-only, bounded (default 50 per task, maximum 200) and limited to a recent time window (T18 D11).

**R8. Evaluation does not extend retention.**
Production evaluation reads rows that already exist; it never makes the raw text live longer. When the retention window for `llm_usage_events` text is set (Part A), any evaluation run must tolerate rows whose text has been cleared (skip and count them).

**R9. Notice.**
The policy states plainly that a sample of real AI outputs is checked, by the Kaihle administrator only, after scrubbing, with results holding no text (Policy draft section 7). **COUNSEL REVIEW** whether a notice is enough or a new lawful basis / school consent is required. Do not enable student-text tasks until that review is done.

### Pre-flight checklist before enabling any student-text task

- [ ] Counsel has reviewed `PRIVACY_POLICY_DRAFT.md` and approved sections 5 and 7.
- [ ] A retention period for `llm_usage_events` text is decided and the purge job exists (or an explicit written waiver exists).
- [ ] Judge provider is named in the subprocessor table with terms recorded.
- [ ] Scrubber limits are shown in the admin UI.
- [ ] Administrator acknowledgement recorded in the settings store.
- [ ] First run is on a small sample and reviewed for leaked personal data by the administrator.
