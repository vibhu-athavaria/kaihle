# M5 — Student Mini-Course
**Date:** 2026-05-14
**Status:** Ready for execution
**Milestone:** M5

---

## Overview

Deliver a personalised mini-course experience for students. When a student clicks a subtopic they get:
an interest-matched AI explanation, a curated YouTube video, 3 check questions, and an "Explain This"
live chat grounded to that subtopic. Teachers trigger generation per-topic, review generated content,
and see per-student course progress in the student detail page. A student feedback (👍👎) loop feeds
quality signals back to the ContentReviewPage and drives regeneration with teacher notes.

Also ships: Questionnaire v2 (7 scenario-based questions, direct single-select interest), and MVP
cleanup (hide My Progress sidebar/tab, hide Study Plans from student sidebar/class tabs).

---

## Architecture Decisions

- **Content is curriculum-level, not per-student.** `subtopic_content` rows are keyed by
  `(subtopic_id, interest_category_id)`. One approved explanation serves every student with that
  interest. Student-specific personalisation happens only in the "Explain This" SSE chat prompt.

- **Fallback chain for explanation delivery.** GET course endpoint tries: (1) approved row matching
  student's interest_category_id; (2) approved row with `interest_category_id IS NULL` (seed-generated
  generic); (3) returns `null` explanation with `content_status: "generating"` if nothing approved exists.

- **Teacher-triggered Celery task generates interest variants.** `POST /topics/{topicId}/generate-course`
  dispatches `generate_topic_mini_course` which loops all subtopics × 4 interest categories, upserts
  `subtopic_content` rows with `review_status="pending"`. Teacher reviews → approves → students see.

- **"Explain This" is SSE, synchronous, not persisted.** Chat history lives in React component state
  only. Each subtopic session starts fresh. No chat history table in v1.

- **Questionnaire v2 is config + service only.** No Alembic migration — just changes to
  `questionnaire_config.py` and `onboarding_service.py`. Old v1 profiles remain readable; new
  submissions store `questionnaire_version="v2"` and `interests` as a single canonical category key.

- **MVP UI cleanup is frontend-only.** No backend changes. Hide "My Progress" nav item in
  `StudentLayout`, remove `MyProgressTab` from `ClassPage`, remove Study Plans from student sidebar.

---

## Dependency Graph

```
main
  │
  ├── T1  migration/mini-course-schema        [MIGRATION — deploy before T2–T8]
  │         └── T2  backend/mini-course-service-and-route
  │                   ├── T3  frontend/student-mini-course-page
  │                   ├── T4  backend/teacher-generate-course-task
  │                   │         └── T5  frontend/teacher-generate-button
  │                   ├── T6  backend/content-feedback-service-and-route
  │                   │         └── T7  frontend/student-feedback-thumbs
  │                   │                   └── T8  frontend/teacher-content-quality-signals
  │                   └── T9  backend/teacher-student-course-progress-route
  │                             └── T10 frontend/teacher-student-mini-courses-tab
  │
  ├── T11 backend/explain-this-sse-route      [independent — no migration needed]
  │         └── T12 frontend/explain-this-drawer
  │
  └── T13 questionnaire-v2                    [independent — no migration needed]
  └── T14 mvp-ui-cleanup                      [independent — frontend-only]

Execution order:
  T1 → T2 → T3, T4, T6, T9 (parallel)
  T4 → T5
  T6 → T7 → T8
  T9 → T10
  T11 → T12  (can run in parallel with T1 track)
  T13         (standalone)
  T14         (standalone)

Conflict risk:
  T3 and T14 both touch ClassPage.tsx and StudentLayout — coordinate
  T8 and T5 both touch ContentReviewPage.tsx — T8 after T5 to avoid conflicts
```

---

## Phase 1 — Foundation

### T1 — DB Migration: mini-course schema
**Branch:** `main → M5-1-T1_migration/mini-course-schema`
**Executor:** Coding agent
**Size:** S

**What it does:** Creates two new tables and adds two counter columns to `subtopic_content`.

**New table: `subtopic_course_progress`**
```sql
student_id          UUID NOT NULL FK users.id CASCADE
subtopic_id         UUID NOT NULL FK subtopics.id CASCADE
school_id           UUID NOT NULL FK schools.id CASCADE
last_visited_at     TIMESTAMPTZ NOT NULL DEFAULT now()
explanation_accessed BOOLEAN NOT NULL DEFAULT false
video_accessed      BOOLEAN NOT NULL DEFAULT false
check_questions_score FLOAT NULL          -- null = not yet attempted
PRIMARY KEY (student_id, subtopic_id)
INDEX on (school_id, student_id)
```

**New table: `subtopic_content_feedback`**
```sql
id                  UUID PK
student_id          UUID NOT NULL FK users.id CASCADE
subtopic_content_id UUID NOT NULL FK subtopic_content.id CASCADE
school_id           UUID NOT NULL FK schools.id CASCADE
feedback_type       TEXT NOT NULL CHECK IN ('thumbs_up', 'thumbs_down')
comment             TEXT NULL
created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
UNIQUE (student_id, subtopic_content_id)   -- one feedback per student per content row
INDEX on (subtopic_content_id)
INDEX on (school_id)
```

**Columns added to `subtopic_content`:**
```sql
thumbs_up_count    INTEGER NOT NULL DEFAULT 0
thumbs_down_count  INTEGER NOT NULL DEFAULT 0
```

**New ORM models:**
- `backend/app/models/mini_course.py` — `SubtopicCourseProgress`, `SubtopicContentFeedback`

**Acceptance criteria:**
- [ ] `alembic upgrade head` runs clean on a fresh DB with seed data
- [ ] `alembic downgrade -1` runs without error
- [ ] `subtopic_course_progress` has correct PK, FK constraints, and index
- [ ] `subtopic_content_feedback` has correct unique constraint on `(student_id, subtopic_content_id)`
- [ ] `subtopic_content.thumbs_up_count` and `thumbs_down_count` columns exist with default 0
- [ ] All existing `subtopic_content` rows have `thumbs_up_count = 0` after migration

**TDD spec:**

File: `backend/app/tests/unit/test_mini_course_models.py` (new)

```python
def test_subtopic_course_progress_when_created_then_defaults_are_false():
    # Arrange: SubtopicCourseProgress(student_id=..., subtopic_id=..., school_id=...)
    # Act: db.add + flush
    # Assert: explanation_accessed == False, video_accessed == False, check_questions_score is None

def test_subtopic_course_progress_primary_key_when_duplicate_then_raises_integrity_error():
    # Arrange: two rows with same (student_id, subtopic_id)
    # Act: db.add_all + flush
    # Assert: IntegrityError

def test_subtopic_content_feedback_when_duplicate_student_content_then_raises_integrity_error():
    # Arrange: two SubtopicContentFeedback rows with same (student_id, subtopic_content_id)
    # Act: db.add_all + flush
    # Assert: IntegrityError

def test_subtopic_content_thumbs_columns_when_migrated_then_default_zero():
    # Arrange: existing SubtopicContent row (seeded)
    # Act: query thumbs_up_count, thumbs_down_count
    # Assert: both == 0
```

**Files changed:**
```
backend/app/models/mini_course.py                         ← new
backend/app/models/__init__.py                            ← add imports
backend/alembic/versions/<generated>.py                   ← generated
backend/app/tests/unit/test_mini_course_models.py         ← new
```

---

### ✅ Checkpoint 1 — After T1
- [ ] `alembic upgrade head` passes in docker
- [ ] `alembic downgrade -1` passes
- [ ] Unit tests for new models pass
- **Human review before proceeding to T2**

---

## Phase 2 — Core Backend

### T2 — Backend: Mini-Course Service + Route
**Branch:** `T1 → M5-1-T2_feature/mini-course-service-and-route`
**Executor:** Coding agent
**Size:** M

**What it does:** Implements the student-facing GET course endpoint with fallback chain, and the
POST progress-mark endpoint.

**New service: `backend/app/services/mini_course_service.py`**

Key method: `get_course_for_student(subtopic_id, student_id, school_id, db)` →
`SubtopicCourseResponse`

Logic:
1. Load `StudentLearningProfile` for student → extract `interests[0]` as canonical interest key
2. Map interest key → `interest_category_id` via `interest_categories` table lookup
3. Query `subtopic_content` WHERE `subtopic_id=X AND content_type='explanation'
   AND review_status='approved' AND is_active=True`
   ORDER BY: interest_category_id match first, NULL last
   LIMIT 1
4. Query `subtopic_content` WHERE `content_type='video' AND review_status='approved' AND is_active=True`
5. Query `question_bank` WHERE `subtopic_id=X AND is_active=True` ORDER BY RANDOM() LIMIT 3
6. Query/upsert `subtopic_course_progress` row (set `last_visited_at=now()`)
7. Return `SubtopicCourseResponse`

Second method: `mark_progress(subtopic_id, student_id, school_id, db, explanation_accessed,
video_accessed)` → upsert `subtopic_course_progress`

**New route: `backend/app/api/v1/routes/student_content.py`** (file already exists — add to it)

```
GET  /api/v1/students/me/subtopics/{subtopicId}/course
POST /api/v1/students/me/subtopics/{subtopicId}/course/progress
```

**New Pydantic schemas in `backend/app/schemas/mini_course.py`:**
```python
class SubtopicCourseResponse(BaseModel):
    subtopic_id: UUID
    subtopic_name: str
    topic_name: str
    explanation: SubtopicExplanationItem | None   # None = not yet generated
    content_status: Literal["ready", "generating", "unavailable"]
    video: SubtopicVideoItem | None
    check_questions: list[CheckQuestion]           # 0–3 items
    progress: CourseProgressItem

class SubtopicExplanationItem(BaseModel):
    content_id: UUID
    explanation_text: str
    interest_matched: bool   # True if interest-specific, False if generic fallback

class SubtopicVideoItem(BaseModel):
    video_url: str
    thumbnail_url: str | None
    duration_seconds: int | None

class CheckQuestion(BaseModel):
    question_id: UUID
    question_text: str
    options: list[str]
    # correct_answer NOT returned — assessed server-side

class CourseProgressItem(BaseModel):
    explanation_accessed: bool
    video_accessed: bool
    check_questions_score: float | None
    last_visited_at: datetime | None
```

**Acceptance criteria:**
- [ ] GET returns 200 with explanation matching student interest if approved variant exists
- [ ] GET falls back to generic (interest_category_id IS NULL) when no interest variant approved
- [ ] GET returns `content_status: "unavailable"` and `explanation: null` when nothing approved
- [ ] GET returns max 3 questions from question_bank; returns 0 if none seeded
- [ ] GET returns video if approved; null if none
- [ ] POST progress updates `explanation_accessed` / `video_accessed` flags correctly
- [ ] POST is idempotent — repeated calls do not duplicate rows
- [ ] All endpoints return 403 if student attempts to access another student's course

**TDD spec:**

File: `backend/app/tests/unit/test_mini_course_service.py` (new)

```python
def test_get_course_when_interest_matched_explanation_exists_then_returns_matched():
    # Arrange: SubtopicContent with interest_category_id matching student's interest
    # Act: get_course_for_student(...)
    # Assert: response.explanation.interest_matched == True

def test_get_course_when_no_interest_match_then_falls_back_to_generic():
    # Arrange: only SubtopicContent with interest_category_id=None (generic)
    # Act: get_course_for_student(...)
    # Assert: response.explanation.interest_matched == False, explanation not None

def test_get_course_when_no_approved_explanation_then_returns_unavailable_status():
    # Arrange: SubtopicContent with review_status='pending'
    # Act: get_course_for_student(...)
    # Assert: response.content_status == 'unavailable', response.explanation is None

def test_get_course_when_question_bank_has_5_questions_then_returns_3():
    # Arrange: 5 active questions in question_bank for subtopic
    # Act: get_course_for_student(...)
    # Assert: len(response.check_questions) == 3

def test_mark_progress_when_called_twice_then_does_not_duplicate_row():
    # Arrange: existing SubtopicCourseProgress row
    # Act: mark_progress called twice with explanation_accessed=True
    # Assert: SELECT COUNT(*) == 1, explanation_accessed == True

def test_get_course_when_cross_student_access_then_raises_403():
    # Arrange: two different student_ids, course fetched with wrong student_id
    # Act: route call with mismatched auth
    # Assert: HTTPException status_code=403
```

File: `backend/app/tests/integration/test_mini_course_route.py` (new)

```python
def test_get_course_route_when_authenticated_student_then_returns_200():
def test_get_course_route_when_unauthenticated_then_returns_401():
def test_post_progress_route_when_valid_payload_then_updates_db():
```

**Files changed:**
```
backend/app/services/mini_course_service.py                ← new
backend/app/schemas/mini_course.py                         ← new
backend/app/api/v1/routes/student_content.py               ← extend
backend/app/api/v1/__init__.py                             ← register new schemas if needed
backend/app/tests/unit/test_mini_course_service.py         ← new
backend/app/tests/integration/test_mini_course_route.py    ← new
```

---

### T4 — Backend: Teacher Generate-Course Celery Task + Route
**Branch:** `T2 → M5-1-T4_feature/teacher-generate-course-task`
**Executor:** Coding agent
**Size:** M

**What it does:** Teacher-triggered endpoint dispatches a Celery task that generates 4
interest-variant explanations (one per interest category) for all subtopics in a topic.
Uses existing router.py for LLM calls (task: `mini_course_explanation`).

**New Celery task: `backend/app/tasks/mini_course_tasks.py`**

```python
@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def generate_topic_mini_course(self, topic_id: str, teacher_id: str, school_id: str):
    """Generate 4 interest-variant explanations for each subtopic in a topic.
    
    Guards: exits with WARNING log if topic has no subtopics (Rule 17).
    Emits CRITICAL log on final retry exhaustion (Rule 18).
    """
```

LLM prompt (Jinja2 template at `backend/app/ai/prompts/mini_course_explanation.jinja2`):
```
Generate a clear explanation of "{{ subtopic_name }}" for a Grade {{ grade_level }} student
studying {{ subject_name }}.

The student is interested in {{ interest_category_name }}. Frame your explanation using
examples and analogies from {{ interest_category_name }} where natural — do not force it
if it doesn't fit.

Requirements:
- 120–200 words
- Plain language, no jargon without definition
- One concrete worked example
- End with one sentence connecting this concept to what comes next

Respond with ONLY valid JSON: {"explanation_text": "..."}
```

**Env var routing:** Add `LLM_MINI_COURSE_MODEL` (default: same as `gap_classification` — Gemini Flash).
Add to `backend/app/core/config.py` and router.py task table.

**New route in `backend/app/api/v1/routes/class_topics.py`** (already exists — add one endpoint):
```
POST /api/v1/topics/{topicId}/generate-course
  → validates teacher owns a class containing this topic
  → dispatches generate_topic_mini_course.delay(topic_id, teacher_id, school_id)
  → returns { "status": "generating", "subtopic_count": N }
```

**Acceptance criteria:**
- [ ] POST 200 dispatches Celery task and returns `{ status: "generating", subtopic_count: N }`
- [ ] POST 404 if topic does not belong to any class the teacher teaches
- [ ] Celery task creates one `subtopic_content` row per `(subtopic, interest_category)` combination
  with `review_status="pending"` and `content_type="explanation"`
- [ ] Task exits with WARNING log (no exception) if topic has 0 subtopics
- [ ] Task emits CRITICAL log with `exc_info=True` on final retry exhaustion
- [ ] Task is idempotent — re-dispatching does not create duplicate rows (upsert on conflict)
- [ ] LLM model is driven entirely by `LLM_MINI_COURSE_MODEL` env var

**TDD spec:**

File: `backend/app/tests/unit/test_mini_course_tasks.py` (new)

```python
def test_generate_topic_mini_course_when_topic_has_subtopics_then_creates_pending_content():
    # Arrange: topic with 3 subtopics, 4 interest categories
    # Act: generate_topic_mini_course(topic_id, teacher_id, school_id) with mocked LLM
    # Assert: 12 SubtopicContent rows created with review_status='pending'

def test_generate_topic_mini_course_when_topic_has_no_subtopics_then_logs_warning_and_exits():
    # Arrange: topic with 0 subtopics
    # Act: call task
    # Assert: no DB rows created, WARNING logged

def test_generate_topic_mini_course_when_idempotent_then_no_duplicate_rows():
    # Arrange: run task once, then again for same topic
    # Act: call task twice
    # Assert: row count unchanged after second run

def test_generate_topic_mini_course_when_llm_fails_all_retries_then_logs_critical():
    # Arrange: LLM mock raises exception on every call
    # Act: call task with mock Celery retry chain
    # Assert: CRITICAL log emitted with exc_info
```

File: `backend/app/tests/integration/test_teacher_generate_course_route.py` (new)

```python
def test_post_generate_course_when_teacher_owns_topic_then_returns_200():
def test_post_generate_course_when_topic_not_in_teachers_class_then_returns_404():
```

**Files changed:**
```
backend/app/tasks/mini_course_tasks.py                          ← new
backend/app/ai/prompts/mini_course_explanation.jinja2           ← new
backend/app/ai/providers/router.py                             ← add mini_course_explanation task
backend/app/core/config.py                                     ← add LLM_MINI_COURSE_MODEL
backend/app/api/v1/routes/class_topics.py                      ← add generate-course endpoint
backend/app/tests/unit/test_mini_course_tasks.py               ← new
backend/app/tests/integration/test_teacher_generate_course_route.py ← new
```

---

### T6 — Backend: Content Feedback Service + Route
**Branch:** `T2 → M5-1-T6_feature/content-feedback-service-and-route`
**Executor:** Coding agent
**Size:** S

**What it does:** Student submits thumbs up/down on an explanation. Counter columns on
`subtopic_content` are updated atomically. Teacher note field added to existing reject endpoint.

**New service method in `mini_course_service.py`:**
`submit_feedback(student_id, school_id, subtopic_content_id, feedback_type, comment, db)`

Logic:
1. Verify `subtopic_content` row exists and `review_status='approved'`
2. Upsert `subtopic_content_feedback` (unique on student + content — one feedback per student)
3. If this is a new row: atomically increment `thumbs_up_count` or `thumbs_down_count` on
   `subtopic_content` using `UPDATE ... SET thumbs_up_count = thumbs_up_count + 1`
4. If row existed and feedback_type changed: decrement old counter, increment new counter

**New route in `student_content.py`:**
```
POST /api/v1/students/me/subtopic-content/{contentId}/feedback
Body: { feedback_type: "thumbs_up" | "thumbs_down", comment?: string (max 140 chars) }
```

**Extend existing reject endpoint** in `teacher_content_review.py`:
```
PATCH /api/v1/teacher/content-review/{id}
Body: { status: "REJECTED", teacher_note?: string }
```
Store `teacher_note` in a new nullable column `rejection_teacher_note TEXT` on `subtopic_content`.
Add this column in T1 migration (retroactively note: add `rejection_teacher_note TEXT NULL` to T1).

**Acceptance criteria:**
- [ ] POST feedback 201 on first submission; 200 on update (changed from up to down)
- [ ] `thumbs_up_count` / `thumbs_down_count` incremented atomically — no race condition
- [ ] Counter adjusts correctly when student changes vote (decrement old, increment new)
- [ ] Comment over 140 chars returns 422
- [ ] PATCH reject with `teacher_note` stores note in `subtopic_content.rejection_teacher_note`
- [ ] Student cannot submit feedback on non-approved content (403)

**TDD spec:**

File: `backend/app/tests/unit/test_content_feedback_service.py` (new)

```python
def test_submit_feedback_when_first_thumbs_up_then_increments_thumbs_up_count():
def test_submit_feedback_when_changed_from_up_to_down_then_adjusts_both_counters():
def test_submit_feedback_when_comment_over_140_chars_then_raises_validation_error():
def test_submit_feedback_when_content_not_approved_then_raises_403():
def test_submit_feedback_when_idempotent_same_vote_then_count_not_incremented_twice():
```

**Files changed:**
```
backend/app/services/mini_course_service.py        ← add submit_feedback method
backend/app/api/v1/routes/student_content.py       ← add feedback endpoint
backend/app/api/v1/routes/teacher_content_review.py ← extend reject with teacher_note
backend/app/schemas/mini_course.py                 ← add FeedbackRequest schema
backend/app/tests/unit/test_content_feedback_service.py ← new
```

---

### T9 — Backend: Teacher Fetches Student Course Progress
**Branch:** `T2 → M5-1-T9_feature/teacher-student-course-progress-route`
**Executor:** Coding agent
**Size:** S

**What it does:** New route returning per-subtopic mini-course progress for a specific student,
for display in the teacher's student detail page.

**New service method in `mini_course_service.py`:**
`get_student_course_progress(teacher_id, student_id, school_id, db)` →
`list[SubtopicProgressSummary]`

Logic: JOIN `subtopic_course_progress` with `subtopics`, `topics`, `subjects`. Filter by
`school_id`. Verify teacher teaches a class the student is enrolled in (403 otherwise).

**New route in `students.py`:**
```
GET /api/v1/students/{studentId}/subtopics/course-progress
```

Response: grouped by subject → topic → subtopic with `explanation_accessed`, `video_accessed`,
`check_questions_score`, `last_visited_at` per subtopic.

**Acceptance criteria:**
- [ ] Returns 200 with per-subtopic progress grouped by subject/topic
- [ ] Returns only subtopics the student has visited (empty list is valid)
- [ ] Returns 403 if teacher does not teach the student
- [ ] Returns 403 if `school_id` mismatch

**TDD spec:**

File: `backend/app/tests/unit/test_teacher_course_progress_service.py` (new)

```python
def test_get_student_course_progress_when_student_visited_subtopics_then_returns_grouped_data():
def test_get_student_course_progress_when_teacher_not_teaching_student_then_raises_403():
def test_get_student_course_progress_when_no_progress_rows_then_returns_empty_list():
```

**Files changed:**
```
backend/app/services/mini_course_service.py       ← add get_student_course_progress
backend/app/api/v1/routes/students.py             ← add course-progress endpoint
backend/app/schemas/mini_course.py                ← add SubtopicProgressSummary schemas
backend/app/tests/unit/test_teacher_course_progress_service.py ← new
```

---

### T11 — Backend: "Explain This" SSE Route
**Branch:** `main → M5-1-T11_feature/explain-this-sse-route`  *(independent of T1 track)*
**Executor:** Coding agent
**Size:** S

**What it does:** Streaming LLM endpoint grounded to a single subtopic. Student sends a question;
response streams back as Server-Sent Events. No DB writes. Uses `student_learning_profiles` for
modality + interest context.

**New service: `backend/app/services/concept_guide_service.py`** already exists — add method
`explain_subtopic_question(subtopic_id, student_id, school_id, question, db, redis)` → async generator
yielding SSE chunks.

System prompt template: `backend/app/ai/prompts/explain_this.jinja2`
```
You are a patient tutor helping a student understand one specific topic:
"{{ subtopic_name }}" (part of {{ topic_name }}, {{ subject_name }}, Grade {{ grade_level }}).

The student is {{ grade_level | student_age_range }} years old.
They learn best through {{ dominant_modality }} explanations.
They are interested in {{ interest_category }}.

RULES:
- Only answer questions about {{ subtopic_name }}. If asked about anything else, redirect:
  "That's a great question for another time — let's focus on {{ subtopic_name }} for now."
- Keep answers under 150 words unless the student asks for more detail.
- Use one concrete example tied to {{ interest_category }} when explaining.
- Never give direct answers to exam-style questions — guide with a follow-up question instead.
```

**New route in `student_content.py`:**
```
POST /api/v1/students/me/subtopics/{subtopicId}/explain
Body: { question: string (max 500 chars) }
Response: text/event-stream (SSE)
```

**Env var:** `LLM_EXPLAIN_THIS_MODEL` — add to config.py and router.py.

**Acceptance criteria:**
- [ ] POST returns `Content-Type: text/event-stream`
- [ ] Streaming response delivers tokens incrementally
- [ ] System prompt includes subtopic name, topic name, subject, grade, student modality + interest
- [ ] Question over 500 chars returns 422 before streaming
- [ ] Returns 404 if subtopic_id does not exist
- [ ] LLM model driven by `LLM_EXPLAIN_THIS_MODEL` env var

**TDD spec:**

File: `backend/app/tests/unit/test_explain_this_service.py` (new)

```python
def test_explain_subtopic_question_when_valid_question_then_yields_sse_chunks():
    # Arrange: mock router.py to yield chunks; valid subtopic + student
    # Act: consume async generator
    # Assert: yields at least one chunk containing text

def test_explain_subtopic_question_when_question_over_500_chars_then_raises_validation_error():
    # Arrange: 501-char question string
    # Act: call service
    # Assert: ValidationError raised before LLM call

def test_explain_subtopic_question_when_subtopic_not_found_then_raises_404():
    # Arrange: non-existent subtopic_id
    # Act: call service
    # Assert: HTTPException 404
```

**Files changed:**
```
backend/app/services/concept_guide_service.py        ← add explain_subtopic_question
backend/app/ai/prompts/explain_this.jinja2           ← new
backend/app/ai/providers/router.py                   ← add explain_this task
backend/app/core/config.py                           ← add LLM_EXPLAIN_THIS_MODEL
backend/app/api/v1/routes/student_content.py         ← add /explain SSE endpoint
backend/app/tests/unit/test_explain_this_service.py  ← new
```

---

### ✅ Checkpoint 2 — After T2, T4, T6, T9, T11
- [ ] All backend unit tests pass: `uv run pytest app/tests/unit/ -v`
- [ ] All integration tests pass: `uv run pytest app/tests/integration/ -v`
- [ ] Service coverage ≥ 90% on all new service files
- [ ] `ruff check app/ && mypy app/` clean
- [ ] GET /students/me/subtopics/{id}/course returns data in Postman/httpie
- [ ] POST /students/me/subtopics/{id}/explain streams in curl
- **Human review before frontend work begins**

---

## Phase 3 — Frontend

### T3 — Frontend: Student Mini-Course Page
**Branch:** `T2 → M5-1-T3_feature/student-mini-course-page`
**Executor:** Coding agent
**Size:** M

**What it does:** New page at `/student/topics/:topicId/subtopics/:subtopicId/course`
(accessible from `ClassTopicsPage` — clicking a subtopic card opens this page). Displays
explanation card, video card, check questions, and the "Explain This" button that opens a drawer.

**New hook:** `frontend/apps/student/src/hooks/useSubtopicCourse.ts`
— React Query `useQuery` calling `GET /students/me/subtopics/{id}/course`

**New page:** `frontend/apps/student/src/pages/topics/SubtopicCoursePage.tsx`

Layout:
```
[Back to topics]
[SubtopicCourseHeader] — subtopic name, topic name, progress chip
[ExplanationCard]       — explanation text, interest_matched badge, 👍👎 buttons (T7)
[VideoCard]             — YouTube embed or "Video coming soon" placeholder
[CheckQuestionsCard]    — 3 MCQ cards, inline answer reveal, score tracking
```

**Loading states (Rule 22):**
- Page skeleton (3 stacked skeleton cards) while `useQuery` loading
- "Video coming soon" placeholder when video is null
- "Content being generated — check back soon" empty state when `content_status: "unavailable"`

**Design tokens (Student role — §5.4):**
- Page bg: `role-student-bg`
- Cards: `bg-white border border-role-student-border rounded-xl p-5`
- Back button: `text-brand-primary text-sm font-semibold`
- Interest matched badge: `bg-brand-green-light text-brand-primary text-xs font-bold rounded-full px-3 py-1`
- Check questions correct: `bg-brand-green-light border border-brand-green`
- Check questions wrong: `bg-red-50 border border-red-300`

**Route added to student app router.**

**Subtopic cards in `ClassTopicsPage.tsx`** — add click handler routing to `SubtopicCoursePage`.

**Acceptance criteria:**
- [ ] Explanation card renders markdown explanation text correctly
- [ ] Video card embeds YouTube iframe when video URL exists
- [ ] 3 check questions render; selecting an answer reveals correct/incorrect inline
- [ ] Skeleton shown on initial load, not a spinner (Rule 22)
- [ ] "Content being generated" empty state shown when `content_status: "unavailable"`
- [ ] Progress is marked when explanation card is viewed (POST course/progress called)
- [ ] All interactive elements have `focus-visible:ring-2` focus ring (Rule §9)
- [ ] Page is navigable from subtopic cards in ClassTopicsPage

**Files changed:**
```
frontend/apps/student/src/hooks/useSubtopicCourse.ts          ← new
frontend/apps/student/src/hooks/useMarkCourseProgress.ts      ← new
frontend/apps/student/src/pages/topics/SubtopicCoursePage.tsx ← new
frontend/apps/student/src/pages/classes/ClassTopicsPage.tsx   ← add subtopic click nav
frontend/apps/student/src/App.tsx (or router file)            ← add route
```

---

### T5 — Frontend: Teacher Generate-Course Button
**Branch:** `T4 → M5-1-T5_feature/teacher-generate-button`
**Executor:** Coding agent
**Size:** S

**What it does:** Adds a "Generate mini-course" button to the teacher's topic detail or class
topics view. On click: shows loading state, POSTs to generate-course endpoint, shows
"Generating..." pulsing badge (Rule 22 — background generation).

**Where the button lives:** `frontend/apps/teacher/src/pages/classes/ClassDetailPage.tsx`
— in the topics list, each topic row gets a "Generate mini-course" button.

**New hook:** `frontend/apps/teacher/src/hooks/useGenerateMiniCourse.ts`
— React Query `useMutation` calling `POST /topics/{topicId}/generate-course`

**States:**
- Default: `bg-brand-gold text-white rounded-full` button
- After click: pulsing badge `Generating...` (replace button until status confirmed)
- On error: toast notification "Generation failed — please try again"

**Acceptance criteria:**
- [ ] Button present on each topic row in teacher's class detail
- [ ] Click triggers POST and shows pulsing "Generating..." badge (Rule 22)
- [ ] Button disabled and non-interactive while generating
- [ ] Error state shown on failure (no silent failure)

**Files changed:**
```
frontend/apps/teacher/src/hooks/useGenerateMiniCourse.ts       ← new
frontend/apps/teacher/src/pages/classes/ClassDetailPage.tsx    ← add generate button per topic
```

---

### T7 — Frontend: Student Feedback Thumbs
**Branch:** `T6 → M5-1-T7_feature/student-feedback-thumbs`
**Executor:** Coding agent
**Size:** S

**What it does:** Adds 👍👎 feedback buttons to the `ExplanationCard` in `SubtopicCoursePage`.
On tap: optimistic UI update, POST to feedback endpoint, optional comment input revealed on 👎.

**New hook:** `frontend/apps/student/src/hooks/useContentFeedback.ts`

**ExplanationCard footer:**
```
Was this explanation helpful?   [👍 Helpful]  [👎 Not helpful]
```
After 👎 tap: small text input appears — "What was confusing? (optional, 140 chars max)"
After submission: buttons replaced with "Thanks for your feedback" text.

**Acceptance criteria:**
- [ ] 👍/👎 buttons visible at bottom of explanation card
- [ ] Tapping 👎 reveals optional comment input (max 140 chars enforced)
- [ ] POST sent on tap; optimistic state shows immediately
- [ ] After submission: buttons replaced with confirmation text
- [ ] If student already submitted feedback (page reload), buttons show previous selection

**Files changed:**
```
frontend/apps/student/src/hooks/useContentFeedback.ts           ← new
frontend/apps/student/src/pages/topics/SubtopicCoursePage.tsx   ← add thumbs to ExplanationCard
```

---

### T8 — Frontend: Teacher Content Quality Signals
**Branch:** `T7 → M5-1-T8_feature/teacher-content-quality-signals`
**Executor:** Coding agent
**Size:** S

**What it does:** Extends `ContentReviewPage.tsx` with quality badges and student feedback
comments. Extends the reject modal with a `teacher_note` field.

**Changes to `ContentReviewPage.tsx`:**
- Add "Quality" column to the table: 🟢 High (>80% 👍) · 🟡 Mixed (50–80%) · 🔴 Low (<50% or ≥3 👎)
- Clicking a row shows: explanation text + student feedback list (anonymised "Student 1", "Student 2")
- Reject modal: add optional `teacher_note` textarea (placeholder: "What should be improved?")

**Quality badge component** (new reusable in packages/ui or inline):
```tsx
// Green/amber/red pill based on thumbs_up_count / (thumbs_up_count + thumbs_down_count)
```

**Acceptance criteria:**
- [ ] Quality badge displayed per content row in ContentReviewPage
- [ ] Clicking a content row shows student feedback comments (anonymised)
- [ ] Reject modal has optional teacher_note field
- [ ] teacher_note sent in PATCH payload on rejection
- [ ] Quality badge uses correct color thresholds (>80% green, 50–80% amber, <50% red)
- [ ] Rows with no feedback show "No feedback yet" instead of a badge

**Files changed:**
```
frontend/apps/teacher/src/pages/content-review/ContentReviewPage.tsx ← extend
frontend/apps/teacher/src/hooks/useTeacherExplanationReview.ts       ← extend with feedback data
```

---

### T10 — Frontend: Teacher Student Mini-Courses Tab
**Branch:** `T9 → M5-1-T10_feature/teacher-student-mini-courses-tab`
**Executor:** Coding agent
**Size:** S

**What it does:** New "Mini-Courses" tab in `StudentProfilePage.tsx` showing per-subtopic
course access data.

**New hook:** `frontend/apps/teacher/src/hooks/useStudentCourseProgress.ts`

**New tab component:** `frontend/apps/teacher/src/components/students/MiniCoursesTab.tsx`

Layout (grouped by subject → topic):
```
[Subject: Mathematics]
  Topic: Algebra
    ├── Subtopic: Solving Linear Equations   [Accessed ✓]  [Video ✓]  [3/3 questions ✓]  3 days ago
    └── Subtopic: Quadratic Functions        [Accessed ✓]  [Video –]  [1/3 questions ⚠]  today

  Topic: Geometry
    └── Subtopic: Angles                     [Not accessed]
```

**Acceptance criteria:**
- [ ] "Mini-Courses" tab visible in StudentProfilePage
- [ ] Subtopics grouped correctly by subject and topic
- [ ] Access status, video status, question score, and last visited shown per row
- [ ] Rows with no progress shown as "Not accessed" (not hidden)
- [ ] Skeleton shown while data loads (Rule 22)
- [ ] Empty state shown if student has accessed no mini-courses

**Files changed:**
```
frontend/apps/teacher/src/hooks/useStudentCourseProgress.ts                ← new
frontend/apps/teacher/src/components/students/MiniCoursesTab.tsx           ← new
frontend/apps/teacher/src/pages/StudentProfilePage.tsx                     ← add tab
```

---

### T12 — Frontend: "Explain This" Drawer
**Branch:** `T11 → M5-1-T12_feature/explain-this-drawer`
**Executor:** Coding agent
**Size:** S

**What it does:** Adds the "Ask about this topic" button and slide-in drawer to `SubtopicCoursePage`.
Chat streams via SSE.

**New component:** `frontend/apps/student/src/components/ExplainThisDrawer.tsx`

- Fixed right drawer `w-[360px]`, `translate-x-full` → `translate-x-0` on open
- Topic grounding chip at top: subtopic name in `bg-brand-green-light text-brand-primary`
- Message list: student messages right-aligned, AI messages left-aligned
- Typing indicator: three animated dots while streaming
- Input: `Enter` to send, `Shift+Enter` for newline
- Streaming: fetch with `ReadableStream` consuming SSE chunks, appending to last AI message
- Focus trap when drawer open (Rule 21 — use `Modal` pattern or equivalent focus management)
- History kept in component state only — cleared on drawer close

**Button on SubtopicCoursePage:**
`bg-brand-primary text-white rounded-full` floating button bottom-right of explanation card.

**Acceptance criteria:**
- [ ] Drawer slides in from right on button click
- [ ] Topic grounding chip shows current subtopic name
- [ ] Student message appears immediately on send
- [ ] AI response streams token-by-token (no waiting for full response)
- [ ] Focus trapped in drawer while open (Tab cycles within drawer)
- [ ] Escape or X closes drawer and returns focus to trigger button
- [ ] Chat history cleared on close (fresh session per open)
- [ ] Empty state shown: "No questions yet — ask anything about {subtopic_name}!"

**Files changed:**
```
frontend/apps/student/src/components/ExplainThisDrawer.tsx       ← new
frontend/apps/student/src/pages/topics/SubtopicCoursePage.tsx    ← wire up drawer
```

---

## Phase 4 — Standalone Tasks

### T13 — Questionnaire v2
**Branch:** `main → M5-1-T13_feature/questionnaire-v2`
**Executor:** Coding agent
**Size:** S

**What it does:** Replaces the 10-question v1 questionnaire with a 7-question scenario-based v2.
No DB migration — config + service changes only.

**Changes to `backend/app/core/questionnaire_config.py`:**
- Replace `QUESTIONNAIRE_V1` with `QUESTIONNAIRE_V2` (7 questions)
- Q1–Q3: scenario-based modality (each answer maps to one modality)
- Q4–Q5: work rhythm (short_sessions, concept_first)
- Q6: direct interest category single-select (4 options mapping to canonical interest keys)
- Q7: challenge response (stored in work_style as `challenge_response` key)
- Bump `QUESTIONNAIRE_VERSION = "v2"`

**Question designs** (verbatim from design session):

| Q | Scenario text | Options → maps_to |
|---|---|---|
| Q1 | "Your teacher just introduced a concept you've never heard of. Which would help you most right now?" | Watch walkthrough→auditory · Written explanation→reading_writing · Practice problems→kinesthetic · Diagram→visual |
| Q2 | "You have to explain what you just learned to a friend. How do you naturally do it?" | Draw it→visual · Talk through→auditory · Write key points→reading_writing · Show worked example→kinesthetic |
| Q3 | "You're stuck on a problem. What's your first move?" | Re-read alone→reading_writing · Look for example→visual · Ask someone→auditory · Try different problem→kinesthetic |
| Q4 | "Which study setup feels most like you?" | Headphones+bursts→short_sessions=True+prefers_solo=True · Long desk session→short_sessions=False+prefers_solo=True · With friends→prefers_solo=False · Moving around→kinesthetic hint |
| Q5 | "When you start a new unit, what do you prefer?" | Big picture first→concept_first=True · Dive into examples→concept_first=False · Either works→concept_first=None (balanced) |
| Q6 | "If your lessons could use examples from one of these, which would feel most exciting?" | Sports & movement→sports_movement · Tech & gaming→tech_gaming · Nature & animals→nature_animals · Arts & culture→arts_culture |
| Q7 | "When something feels really hard, what do you usually do?" | Keep trying→persists · Take a break→paces · Ask for help→collaborative · Feel like giving up→avoidant |

**Changes to `onboarding_service.py`:**
- `_calculate_modality_scores()`: plurality vote across Q1, Q2, Q3 →
  `{ "dominant": "visual", "secondary": "kinesthetic" }` (stored in `modality_scores` JSONB)
- `_calculate_work_style()`: Q4 → `short_sessions`, `prefers_solo`; Q5 → `concept_first`;
  Q7 → `challenge_response` key added to work_style dict
- `_extract_interests()`: Q6 is single-select → `interests = [selected_key]` (one item list)

**Frontend changes in `ProfileQuestionnaire.tsx`:**
- Fetch questionnaire v2 definition from backend (already dynamic via API)
- One question per screen (already implemented)
- Interest question (Q6): 4 large illustrated option cards, single-select
- Challenge response (Q7): 4 option cards

**Acceptance criteria:**
- [ ] `QUESTIONNAIRE_VERSION == "v2"` in config
- [ ] 7 questions returned from GET /onboarding/questionnaire
- [ ] `modality_scores` stored as `{ "dominant": "visual", "secondary": "kinesthetic" }`
- [ ] `interests` stored as single-item list e.g. `["sports_movement"]`
- [ ] `work_style` includes `challenge_response` key
- [ ] Existing v1 profiles (questionnaire_version="v1") still readable — no breakage
- [ ] `get_compatible_interests()` still works with single-item list

**TDD spec:**

File: `backend/app/tests/unit/test_questionnaire_v2.py` (new)

```python
def test_calculate_modality_scores_v2_when_q1_q2_q3_all_visual_then_dominant_is_visual():
def test_calculate_modality_scores_v2_when_split_votes_then_secondary_is_second_most():
def test_calculate_modality_scores_v2_when_three_way_tie_then_dominant_is_reading_writing():
def test_extract_interests_v2_when_single_select_then_returns_one_item_list():
def test_work_style_v2_when_q7_submitted_then_challenge_response_key_present():
def test_get_compatible_interests_when_single_item_list_then_still_returns_correct_subject_match():
```

**Files changed:**
```
backend/app/core/questionnaire_config.py                       ← replace v1 with v2
backend/app/services/onboarding_service.py                     ← update scoring logic
backend/app/tests/unit/test_questionnaire_v2.py                ← new
frontend/apps/student/src/pages/onboarding/ProfileQuestionnaire.tsx ← minor UX updates
```

---

### T14 — MVP UI Cleanup
**Branch:** `main → M5-1-T14_chore/mvp-ui-cleanup`
**Executor:** Coding agent
**Size:** XS

**What it does:** Frontend-only changes to hide "My Progress" from sidebar and class page,
and hide "Study Plans" from student sidebar and class page. No backend changes, no deletions.

**Changes:**
1. `frontend/packages/ui/src/layouts/StudentLayout.tsx`
   — Comment out or conditionally hide "My progress" nav item (keep code, add `hidden` class or `null` render)
2. `frontend/apps/student/src/pages/classes/ClassPage.tsx`
   — Remove `MyProgressTab` from the tab array; remove `StudyPlanTab` from the tab array
3. `frontend/apps/student/src/pages/classes/ClassPage.tsx`
   — Keep the default tab as "Topics"
4. `frontend/packages/ui/src/layouts/StudentLayout.tsx`
   — Comment out or hide "Study plans" nav item

**Acceptance criteria:**
- [ ] Student sidebar has no "My Progress" nav item
- [ ] Student sidebar has no "Study Plans" nav item
- [ ] Class page shows only "Topics" tab (no My Progress tab, no Study Plans tab)
- [ ] Navigating directly to `/student/my-progress` still works (route not removed)
- [ ] Study Plans backend routes unchanged — no backend files touched

**Files changed:**
```
frontend/packages/ui/src/layouts/StudentLayout.tsx     ← hide 2 nav items
frontend/apps/student/src/pages/classes/ClassPage.tsx  ← remove 2 tabs
```

---

## Final Checkpoint — Milestone Complete

- [ ] All 14 tasks complete with PRs open
- [ ] All backend unit tests pass with ≥ 90% service coverage
- [ ] All integration tests pass
- [ ] `ruff check && mypy` clean
- [ ] `pnpm typecheck` clean for student and teacher apps
- [ ] Mini-course page accessible from student class topics
- [ ] Teacher can trigger generation and see "Generating..." state
- [ ] Teacher sees quality signals in ContentReviewPage
- [ ] Teacher sees student progress in student detail Mini-Courses tab
- [ ] Explain This drawer streams responses correctly
- [ ] Questionnaire v2 serves 7 questions correctly
- [ ] My Progress and Study Plans hidden from student UI
- [ ] `.env.example` updated with `LLM_MINI_COURSE_MODEL`, `LLM_EXPLAIN_THIS_MODEL`

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| SSE streaming requires server config (nginx/render buffering) | High | Test on staging early; add `X-Accel-Buffering: no` header in T11 |
| LLM-generated explanations may be low quality in non-English contexts | Medium | Teacher review gate (`review_status=pending`) blocks student-visible delivery |
| T3 and T14 both touch ClassPage.tsx | Medium | T14 runs from main; T3 branches from T2. Merge T14 first, then rebase T3 onto it |
| Celery task generates 4 × N LLM calls per topic trigger | Low | Typical topic has 4–8 subtopics → 16–32 calls. At Gemini Flash pricing this is <$0.05 per topic |
| Student feedback counter race condition | Medium | Use atomic SQL UPDATE col = col + 1 (not read-modify-write) in T6 |

---

## Open Questions

1. Should the "Explain This" chat history be persisted server-side for teacher visibility in v1.5?
   Decision needed before T11/T12 implementation — current plan: no persistence in v1.
2. Should the teacher "Generate mini-course" button show how many subtopics exist before clicking?
   Nice-to-have — T5 can show `subtopic_count` from the API response.
3. `LLM_MINI_COURSE_MODEL` default — confirm with Vibhu: Gemini Flash (cost-efficient) or Claude Sonnet (quality)?
