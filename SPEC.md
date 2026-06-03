# SPEC: Assessment Preview, Edit & Question Management

**Version:** 1.1 · June 2026  
**Status:** DRAFT — awaiting confirmation before implementation  
**Author:** Claude Code (Sonnet 4.6) + Vibhu  
**Applies to:** `backend/app/` + `frontend/apps/teacher/` + `frontend/apps/kaihle-admin/`

---

## 1. Objective

Give teachers full post-creation control over their assessments: preview questions with correct answers, edit assessment details, manage the question pool (add/edit-suggest/replace), and archive assessments (including Tier 1 diagnostics). Teacher-added questions are immediately usable in the assessment and flagged to KaihleAdmin for promotion to the shared question bank.

**Target users:**
- **Teacher** — creates and manages assessments for their classes
- **KaihleAdmin** — reviews teacher-submitted questions and edit suggestions for promotion to the shared bank

---

## 2. Feature Areas

### 2.1 Assessment Preview (post-creation)

A teacher can view the full question pool of any assessment they own at any time — DRAFT, ACTIVE, or CLOSED. The preview shows:
- All questions with **correct answers** visible (teacher-only)
- Questions grouped by **topic → subtopic**
- Per-question: difficulty level badge, question type, option count
- Pool stats: total questions, per-attempt count, difficulty distribution histogram

**API:** `GET /assessments/{id}/preview` (TEACHER only, must own assessment)  
Returns: questions with `correct_answer_key` included, grouped by topic/subtopic.

---

### 2.2 Edit Assessment Details

A teacher can edit any field of an assessment they own. Fields are split into **safe** and **risky** categories based on impact on existing attempts.

#### Safe fields (always editable — no warning)
| Field | Notes |
|---|---|
| `title` | Purely cosmetic |
| `instructions` | Purely cosmetic |
| `deadline` | Only affects whether new attempts can start |

#### Risky fields (editable with warning when attempts exist)
| Field | Risk | What breaks |
|---|---|---|
| `question_count` | MEDIUM | IN_PROGRESS students may get a different question subset on reload. Their partial responses remain valid but the set they see shifts. |
| `time_limit_minutes` | MEDIUM | IN_PROGRESS timers are running on old limit. Frontend reload picks up new limit. Retroactively changes `timed_out` flag on COMPLETED attempts. |
| `questions_per_topic` | MEDIUM | Does not change the pre-selected pool; affects how many questions future attempts see from each topic. |
| `minimum_difficulty` / `maximum_difficulty` | LOW | Does not change pre-selected pool (pool is already fixed in `assessment_selected_questions`). Metadata only. |

**Rules:**
- Backend always accepts the edit; it is the frontend's responsibility to display the warning.
- Warning is shown when `attempt_count > 0` and a risky field is being changed.
- Warning copy: *"X students have already started or completed this assessment. Changing [field] may affect their experience."*

**API:** `PATCH /assessments/{id}` (TEACHER, must own assessment)  
Body: any subset of `{title, instructions, deadline, question_count, time_limit_minutes, questions_per_topic, minimum_difficulty, maximum_difficulty}`  
Returns: updated `AssessmentResponse`  
Constraint: CLOSED assessments — only `title` and `instructions` are editable.

---

### 2.3 Add Question

A teacher can write a new question and add it directly to their assessment's question pool. The question is:
1. Inserted into `question_bank` with `source='teacher'`, `school_id` set to the teacher's school, `review_status='PENDING_REVIEW'`
2. Immediately linked to the assessment via a new `assessment_selected_questions` row (order_index = current max + 1)
3. Immediately available to students in the assessment
4. A `question_review_items` row (type=`TEACHER_QUESTION`) is created for KaihleAdmin review

**KaihleAdmin promotion flow:**
- KaihleAdmin sees pending teacher questions in the unified review queue
- **Approve:** `school_id` set to NULL, `review_status='APPROVED'` — question becomes globally available to all schools
- **Reject:** `is_active` set to FALSE, `review_status='REJECTED'` — removed from future question sampling; historical assessment responses are preserved
- **Edit then Approve:** KaihleAdmin can edit `question_text`, `options`, `correct_answer`, `explanation` before approving

**API (Teacher):**
- `POST /assessments/{id}/questions` — create and add question
- Body: `{subtopic_id, question_text, question_type, options, correct_answer, difficulty_level, explanation?}`

**Subtopic scope:** The teacher picks a subtopic from within the class's subject+grade. Frontend shows a filtered subtopic picker.

---

### 2.4 Edit Question Suggestion

A teacher can suggest an edit to any existing question in their assessment's pool. They cannot edit `question_bank` directly — only suggest. The suggestion is:
1. Saved as a `question_review_items` row (type=`EDIT_SUGGESTION`) in the unified review table
2. Email notification sent to KaihleAdmin
3. KaihleAdmin can approve (updates `question_bank`), reject (marks suggestion closed), or edit then approve

**Teacher can suggest changes to:** `question_text`, `options`, `correct_answer`, `explanation`, `difficulty_level`

**API (Teacher):**
- `POST /assessments/{id}/questions/{question_id}/suggest-edit`
- Body: `{suggested_question_text?, suggested_options?, suggested_correct_answer?, suggested_explanation?, suggested_difficulty_level?, reason}`

**Unified KaihleAdmin review API (handles both TEACHER_QUESTION and EDIT_SUGGESTION types):**
- `GET /question-review-items` — list all pending items (filter by `?item_type=`)
- `POST /question-review-items/{id}/approve` — for TEACHER_QUESTION: promotes to global bank; for EDIT_SUGGESTION: applies suggested fields to `question_bank`
- `POST /question-review-items/{id}/reject` — closes with optional `admin_note`
- `PATCH /question-review-items/{id}` — KaihleAdmin edits the item (either the question itself for TEACHER_QUESTION, or the suggested fields for EDIT_SUGGESTION) before approving

**Email:** Sent via `email_service` using `resend`. Goes to all KaihleAdmin users.
- TEACHER_QUESTION: *"New question submitted by [Teacher Name] for review — [Assessment Title]"*
- EDIT_SUGGESTION: *"New question edit suggestion from [Teacher Name] — [Assessment Title]"*

---

### 2.5 Replace Question

A teacher can swap a question in the pool for a different one from the shared question bank, scoped to the same subject/grade as the assessment's class.

**Replacement candidates must:**
- Belong to the same `curriculum_topic_id` as the question being replaced (teacher sees this as same topic/subtopic)
- Match the class's `subject_id` and `grade_id`
- Be `is_active = TRUE`
- **Not** already be in the assessment's pool
- Optionally filtered by the teacher: same difficulty level, same question type

**Break analysis — replacement when attempts exist:**

| Scenario | Risk | What breaks |
|---|---|---|
| No attempts exist | NONE | Safe |
| Attempts exist, no student has answered the old question | LOW | Safe — old question wasn't seen yet |
| IN_PROGRESS attempts, student has answered old question | HIGH | `submit_response` will fail with `QuestionNotInAssessmentError` if they try to re-answer. Their existing `StudentResponse` row becomes orphaned (no ASQ bridge) but the score denominator is unaffected (score calculated at submit from `len(all_responses)`). |
| COMPLETED attempts with response for old question | MEDIUM | The `StudentResponse` row remains (score was already stored). `get_attempt_detail` won't show this question (it uses an ASQ JOIN). The orphaned response is invisible but does not corrupt the stored score. |

**Frontend responsibility:** Show warning if ANY attempt has a response for the question being replaced. The teacher can still proceed — it's a choice, not a hard block.

**API:**
- `GET /assessments/{id}/questions/{question_id}/replacements` — return candidate questions from the bank (with optional `?difficulty_level=&question_type=` filters)
- `POST /assessments/{id}/questions/{question_id}/replace` — body: `{replacement_question_id}`

**Removes** old `assessment_selected_questions` row, inserts new one at same `order_index`.

---

### 2.6 Remove Question from Pool

A teacher can remove a question from the pool (without replacement).

**Same break analysis as Replace (§2.5) applies.** Show warning if any attempt has a response for the question.

**`question_count` auto-adjustment:** When a question is removed, `assessment.question_count` is decremented by 1 if `question_count > 0`. If `question_count` would drop below 1, the removal is blocked.

**API:**
- `DELETE /assessments/{id}/questions/{question_id}` — remove from pool

---

### 2.7 Archive (= Close) Assessment + Tier 1 Replacement

"Archive" is the existing `CLOSED` transition with one new business rule for Tier 1:

**Existing behaviour (unchanged):**
- `POST /assessments/{id}/close` transitions ACTIVE → CLOSED
- No new attempts accepted on CLOSED assessments

**New rule — Tier 1 Diagnostic:**
- `design_tier1_diagnostic` currently blocks replacement if the existing diagnostic is not DRAFT
- **Change:** Allow replacement if the existing diagnostic is DRAFT **or CLOSED**
- ACTIVE Tier 1 still cannot be replaced (must close it first)
- This unblocks the teacher workflow: Close Tier 1 → design new Tier 1

**No new status, no new endpoint.** Only a 1-line change in `design_tier1_diagnostic`:
```python
# Before
if existing.status != AssessmentStatus.DRAFT:
    raise ValueError(...)
# After
if existing.status not in (AssessmentStatus.DRAFT, AssessmentStatus.CLOSED):
    raise ValueError(...)
```

---

## 3. Data Model Changes

### 3.1 `question_bank` — new columns (migration required)

```sql
ALTER TABLE question_bank
  ADD COLUMN school_id         UUID         REFERENCES schools(id) ON DELETE RESTRICT,
  ADD COLUMN submitted_by      UUID         REFERENCES users(id)   ON DELETE SET NULL,
  ADD COLUMN review_status     VARCHAR(20)  DEFAULT NULL;

-- Widen source CHECK to include 'teacher'
ALTER TABLE question_bank DROP CONSTRAINT chk_qb_source;
ALTER TABLE question_bank ADD CONSTRAINT chk_qb_source
  CHECK (source IN ('bank', 'llm', 'teacher'));

ALTER TABLE question_bank ADD CONSTRAINT chk_qb_review_status
  CHECK (review_status IS NULL OR review_status IN ('PENDING_REVIEW', 'APPROVED', 'REJECTED'));
```

**Invariant:** `school_id IS NOT NULL` ↔ `source = 'teacher'`. Enforced at service layer.  
**Index:** `CREATE INDEX idx_qb_school ON question_bank (school_id) WHERE school_id IS NOT NULL;`  
**CONSTITUTION Rule 2:** `school_id` IS nullable here by design — existing bank/llm questions are school-agnostic. Teacher questions always have school_id set.

### 3.2 New table: `question_review_items`

Unified review queue for both teacher-submitted questions and teacher edit suggestions.

```sql
CREATE TABLE question_review_items (
  id                         UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
  item_type                  VARCHAR(20)  NOT NULL,
  -- 'TEACHER_QUESTION': teacher added a new question (question_id → newly inserted question_bank row)
  -- 'EDIT_SUGGESTION':  teacher suggested changes to existing question
  question_id                UUID         NOT NULL REFERENCES question_bank(id) ON DELETE CASCADE,
  submitted_by               UUID         NOT NULL REFERENCES users(id)         ON DELETE CASCADE,
  school_id                  UUID         NOT NULL REFERENCES schools(id)       ON DELETE CASCADE,
  assessment_id              UUID         REFERENCES assessments(id)            ON DELETE SET NULL,
  -- suggested_* fields: NULL for TEACHER_QUESTION (question already in bank as-is)
  --                      populated for EDIT_SUGGESTION (proposed changes to apply on approve)
  suggested_question_text    TEXT,
  suggested_options          JSONB,
  suggested_correct_answer   TEXT,
  suggested_explanation      TEXT,
  suggested_difficulty_level FLOAT,
  reason                     TEXT,        -- required for EDIT_SUGGESTION, optional for TEACHER_QUESTION
  status                     VARCHAR(20)  NOT NULL DEFAULT 'PENDING',
  admin_note                 TEXT,
  resolved_by                UUID         REFERENCES users(id) ON DELETE SET NULL,
  created_at                 TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  resolved_at                TIMESTAMPTZ,
  CONSTRAINT chk_qri_item_type CHECK (item_type IN ('TEACHER_QUESTION', 'EDIT_SUGGESTION')),
  CONSTRAINT chk_qri_status    CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED'))
);

CREATE INDEX idx_qri_status    ON question_review_items (status) WHERE status = 'PENDING';
CREATE INDEX idx_qri_school    ON question_review_items (school_id);
CREATE INDEX idx_qri_item_type ON question_review_items (item_type);
```

**Invariant:** For `TEACHER_QUESTION` rows, `question_bank.review_status` mirrors `question_review_items.status`. Kept in sync by the service layer.

### 3.3 `kaihle_v2_1_schema.sql` — must be updated

Both new structures must be reflected in `kaihle_v2_1_schema.sql` as the single source of truth (CONSTITUTION Rule 8).

---

## 4. New Backend Services & Endpoints

### 4.1 `assessment_service.py` — additions

| Method | Description |
|---|---|
| `get_assessment_preview(assessment_id, school_id, teacher_id)` | Returns assessment + all questions WITH correct_answer (teacher-facing). |
| `update_assessment(assessment_id, school_id, teacher_id, body)` | PATCH fields. Returns (assessment, has_attempts: bool). |
| `add_question_to_assessment(assessment_id, school_id, teacher_id, body)` | Inserts into question_bank (source='teacher') + ASQ bridge + creates submission record. |
| `get_replacement_candidates(assessment_id, question_id, school_id, teacher_id, filters)` | Returns question_bank rows for same topic/subject/grade, not already in pool. |
| `replace_question(assessment_id, old_question_id, new_question_id, school_id, teacher_id)` | Swaps ASQ row. |
| `remove_question_from_pool(assessment_id, question_id, school_id, teacher_id)` | Removes ASQ row, decrements question_count. |
| `suggest_question_edit(assessment_id, question_id, school_id, teacher_id, body)` | Inserts question_edit_suggestions row, fires email task. |

### 4.2 New `question_review_service.py` (KaihleAdmin)

Handles both TEACHER_QUESTION and EDIT_SUGGESTION item types through a single service.

| Method | Description |
|---|---|
| `list_pending_items(item_type?, page, page_size)` | All PENDING items, optionally filtered by type. |
| `approve_item(item_id, admin_id, edits?)` | TEACHER_QUESTION: sets school_id=NULL, review_status='APPROVED'. EDIT_SUGGESTION: applies suggested (or admin-edited) fields to question_bank. Both set item status='APPROVED'. |
| `reject_item(item_id, admin_id, admin_note?)` | TEACHER_QUESTION: sets question_bank.is_active=FALSE, review_status='REJECTED'. EDIT_SUGGESTION: closes without touching question_bank. Both set item status='REJECTED'. |
| `edit_item(item_id, admin_id, body)` | Updates suggested_* fields on the review item before calling approve_item. |

### 4.3 Route additions

**`assessments.py`:**
```
GET    /assessments/{id}/preview                               — teacher preview with correct answers
PATCH  /assessments/{id}                                       — edit details
POST   /assessments/{id}/questions                             — add new question to pool
DELETE /assessments/{id}/questions/{question_id}               — remove from pool
GET    /assessments/{id}/questions/{question_id}/replacements  — replacement candidates
POST   /assessments/{id}/questions/{question_id}/replace       — swap question
POST   /assessments/{id}/questions/{question_id}/suggest-edit  — submit edit suggestion
```

**New `question_management.py` (KaihleAdmin — unified):**
```
GET    /question-review-items                  — list all pending items (?item_type= filter)
POST   /question-review-items/{id}/approve    — approve (promotes or applies edits)
POST   /question-review-items/{id}/reject     — reject with optional admin_note
PATCH  /question-review-items/{id}            — edit item before approving
```

---

## 5. Frontend Changes

### 5.1 Teacher app — new pages/components

| Component | Location | Purpose |
|---|---|---|
| `AssessmentPreviewPage` | `pages/assessments/AssessmentPreviewPage.tsx` | Full question list with correct answers, grouped by topic/subtopic, difficulty badges. Accessible from assessment list. |
| `EditAssessmentDetailsModal` | `components/assessments/EditAssessmentDetailsModal.tsx` | PATCH form for safe + risky fields. Shows warning banner when attempts exist and risky field is changed. |
| `AddQuestionModal` | `components/assessments/AddQuestionModal.tsx` | Form: subtopic picker (filtered to class subject/grade), question type, text, options, correct answer, difficulty. |
| `ReplaceQuestionDrawer` | `components/assessments/ReplaceQuestionDrawer.tsx` | Shows candidates from bank. Filter by difficulty/type. Shows warning if responses exist for old question. |
| `SuggestEditModal` | `components/assessments/SuggestEditModal.tsx` | Pre-filled with current question data. Teacher edits fields + adds reason. |
| `QuestionPoolPanel` | used inside `AssessmentPreviewPage` | Replaces flat list with topic-grouped accordion. Per-question: difficulty badge, remove button, replace button, suggest-edit button. |

### 5.2 KaihleAdmin app — new pages

| Component | Location | Purpose |
|---|---|---|
| `QuestionReviewPage` | `pages/questions/QuestionReviewPage.tsx` | Unified list of PENDING items (both TEACHER_QUESTION and EDIT_SUGGESTION). Toggle filter by type. Approve/reject/edit actions. |

### 5.3 Existing pages — additions

- `AssessmentListPage` and `AssessmentResultsPage`: add "Preview" button for assessments owned by current teacher
- `AllAssessmentsPage`: add "Archive" (= close) action for ACTIVE assessments

---

## 6. Testing Strategy

All tests follow naming: `test_<what>_when_<condition>_then_<expected>`

### 6.1 Unit tests (new service methods)

**`app/tests/unit/test_assessment_service.py` — new cases:**
```python
test_get_assessment_preview_when_teacher_owns_assessment_then_returns_questions_with_correct_answers
test_get_assessment_preview_when_teacher_does_not_own_assessment_then_raises_TeacherNotClassOwnerError
test_update_assessment_when_safe_fields_only_then_updates_without_warning
test_update_assessment_when_risky_field_changed_with_attempts_then_applies_change_and_flags_has_attempts_true
test_update_assessment_when_assessment_is_closed_then_only_cosmetic_fields_accepted
test_add_question_to_assessment_then_inserts_question_bank_row_with_source_teacher
test_add_question_to_assessment_then_creates_asq_bridge_row
test_add_question_to_assessment_then_question_count_incremented
test_get_replacement_candidates_when_filters_applied_then_excludes_existing_pool_questions
test_replace_question_when_no_responses_for_old_question_then_swaps_asq_row
test_replace_question_when_responses_exist_for_old_question_then_still_replaces_and_returns_warning_flag
test_remove_question_from_pool_when_no_responses_then_removes_asq_and_decrements_count
test_remove_question_from_pool_when_count_would_drop_to_zero_then_raises_ValueError
test_suggest_question_edit_then_creates_suggestion_row_and_fires_email_task
```

**`app/tests/unit/test_question_review_service.py`:**
```python
test_approve_item_when_teacher_question_no_edits_then_clears_school_id_and_sets_approved
test_approve_item_when_teacher_question_with_edits_then_applies_edits_before_promoting
test_reject_item_when_teacher_question_then_sets_is_active_false_and_review_status_rejected
test_approve_item_when_edit_suggestion_then_applies_suggested_fields_to_question_bank
test_approve_item_when_edit_suggestion_with_admin_edits_then_admin_version_applied
test_reject_item_when_edit_suggestion_then_question_bank_unchanged
test_reject_item_when_admin_note_provided_then_note_stored_on_review_item
test_edit_item_when_pending_then_updates_suggested_fields_without_applying
```

### 6.2 Integration tests

**`app/tests/integration/test_assessment_edit_flow.py`:**
```python
test_patch_assessment_title_when_active_with_attempts_then_200_and_title_updated
test_patch_assessment_question_count_when_in_progress_attempts_exist_then_200_and_has_attempts_true
test_add_question_via_api_then_appears_in_preview_endpoint
test_replace_question_via_api_then_old_question_not_in_pool
test_suggest_edit_via_api_then_suggestion_row_created_with_pending_status
```

### 6.3 Coverage requirement
≥ 90% on all new `/services/` files (CI enforced per CONSTITUTION Rule 6).

---

## 7. Break Analysis Summary

This table documents exactly what breaks when teachers edit assessments with active attempts. Frontend must surface the appropriate warning for each case.

| Action | No attempts | NOT_STARTED only | IN_PROGRESS exist | COMPLETED exist |
|---|---|---|---|---|
| Edit title/instructions/deadline | ✅ Safe | ✅ Safe | ✅ Safe | ✅ Safe |
| Edit question_count | ✅ Safe | ✅ Safe | ⚠️ Warn — student subset shifts on reload | ✅ Safe — score already stored |
| Edit time_limit_minutes | ✅ Safe | ✅ Safe | ⚠️ Warn — running timer affected on reload | ⚠️ Warn — timed_out flag retroactively changes |
| Add question to pool | ✅ Safe | ✅ Safe | ⚠️ Warn — subset may shift on reload | ✅ Safe |
| Remove question (no prior responses) | ✅ Safe | ✅ Safe | ✅ Safe | ✅ Safe |
| Remove question (responses exist) | — | — | ⚠️ Warn — orphaned response invisible in detail view | ⚠️ Warn — orphaned response invisible in detail view |
| Replace question (no prior responses) | ✅ Safe | ✅ Safe | ✅ Safe | ✅ Safe |
| Replace question (responses exist for old) | — | — | ⚠️ Warn — same as remove | ⚠️ Warn — same as remove |

**No hard blocks** — teacher is warned and can proceed. This matches the agreed behaviour (§2.2).

---

## 8. Absolute Rules (from CONSTITUTION)

- All new service code follows Rule 1: business logic in services, routes are thin.
- All new tables follow Rule 2: `school_id` on `question_edit_suggestions`. Exception documented for `question_bank.school_id` (nullable by design — existing rows are school-agnostic).
- All queries filter by `school_id` or have explicit KaihleAdmin bypass (Rule 3/12).
- No LLM calls in this feature (Rule 4 — not applicable).
- Test coverage ≥ 90% on services (Rule 6).
- Test naming: `test_<what>_when_<condition>_then_<expected>` (Rule 7).
- Schema change: `kaihle_v2_1_schema.sql` must be updated (Rule 8).
- Migrations autogenerated (Rule 9). `chk_qb_source` constraint widening requires explicit DROP + ADD in migration.
- All modals use `Modal` from `packages/ui` (Rule 21).
- Loading states: skeletons for page load, spinners for button actions (Rule 22).

---

## 9. Out of Scope (this spec)

- Bulk question import / CSV upload
- Question bank search/browse UI for KaihleAdmin
- Audit trail / history of edits to question_bank
- AI-assisted question generation for teachers
- KaihleAdmin email notification preferences / unsubscribe
- Tier 1 diagnostic wizard UI (separate feature)

---

*Confirm this spec before implementation begins.*
