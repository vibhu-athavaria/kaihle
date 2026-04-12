# M3 — Smart Study Plans: Sequential Execution Plan

**Milestone:** 3 of 6  
**Duration:** 4–5 weeks  
**Preceded by:** M2 — Gap Map & Teacher Dashboard  
**Key architecture change:** Resources come from `subtopic_content` table (structured SQL), NOT pgvector/curriculum_chunks

---

## Dependency Graph

```
M3-0-T1 (subtopic_content table + seed pipeline)
  ↓ [migration must be deployed before M3-0 children]
  ├── M3-0-T2a (KaihleAdmin video review UI) ─┐
  ├── M3-0-T2b (teacher explanation review UI)─┤ [parallel]
  └── M3-0-T3  (stale link Celery job) ───────┘
  
All M3-0 complete → M3-1 can begin
  ├── M3-1-T1 (content curator) ──┐
  └── M3-1-T2 (quiz generator) ──┴─ [parallel]
        ↓
        M3-1-T3 (quiz quality validation)
              ↓
        M3-2-T1 (study plan service)
              ↓
        M3-2-T2 (study plan routes) [replace stubs]
              ↓
         ┌────┴────┐
         ↓         ↓
    M3-2-T3   M3-2-T4
  (student)  (teacher)
```

---

## PHASE 0 — Router Task Extension

**Purpose:** Add missing LLM task entries required by M3 tasks.

**Files to Modify:**
- `backend/app/ai/providers/router.py` — add `question_generation` and `student_pack` to TASK_MODEL_MAP and TASK_API_BASE_MAP
- `backend/app/core/config.py` — add `llm_question_generation_model`, `llm_question_generation_api_base`, `llm_student_pack_model`, `llm_student_pack_api_base` env vars

**Steps:**
1. Edit `router.py` to add the two new task entries
2. Edit `config.py` to add the four new settings attributes
3. Run `ruff check backend/app/ai/providers/router.py && mypy backend/app/ai/providers/router.py`

**Acceptance Criteria:**
- `router.complete("question_generation", ...)` calls the correct model
- `router.complete("student_pack", ...)` calls the correct model
- No other files modified

---

## PHASE 1 — M3-0-T1: Content Infrastructure (Foundation)

**MUST complete before all other M3 tasks.**

### Step 1.1 — Alembic Migration

**Generate migration:**
```bash
cd backend && alembic revision --autogenerate -m "add_subtopic_content_and_student_lesson_packs"
```

**Verify the generated migration creates:**

`subtopic_content` table (NO `school_id` — curriculum layer):
```sql
CREATE TABLE subtopic_content (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subtopic_id UUID NOT NULL REFERENCES subtopics(id) ON DELETE CASCADE UNIQUE,
    llm_explanation TEXT,
    llm_generated_at TIMESTAMPTZ,
    approved_explanation TEXT,
    explanation_review_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    explanation_reviewed_by UUID REFERENCES users(id) ON DELETE SET NULL,
    explanation_reviewed_at TIMESTAMPTZ,
    videos JSONB NOT NULL DEFAULT '[]',
    audience VARCHAR(20) NOT NULL DEFAULT 'both',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_subtopic_content_subtopic ON subtopic_content (subtopic_id);
CREATE INDEX idx_subtopic_content_explanation_status ON subtopic_content (explanation_review_status);
```

`student_lesson_packs` table (HAS `school_id` — student data):
```sql
CREATE TABLE student_lesson_packs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    lesson_plan_id UUID NOT NULL REFERENCES lesson_plans(id) ON DELETE CASCADE,
    subtopic_id UUID NOT NULL REFERENCES subtopics(id) ON DELETE CASCADE,
    learning_style VARCHAR(30) NOT NULL,
    interest_category VARCHAR(50),
    what_you_will_learn TEXT NOT NULL,
    real_life_intro TEXT NOT NULL,
    explanation TEXT NOT NULL,
    content_sequence VARCHAR(20) NOT NULL DEFAULT 'video_first',
    video_url TEXT,
    video_title TEXT,
    pre_quiz_question_ids UUID[] NOT NULL DEFAULT '{}',
    post_quiz_question_ids UUID[] NOT NULL DEFAULT '{}',
    post_quiz_score FLOAT,
    post_quiz_completed_at TIMESTAMPTZ,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ai_model VARCHAR(100),
    UNIQUE(student_id, lesson_plan_id, learning_style, interest_category),
    CONSTRAINT chk_slp_content_sequence CHECK (content_sequence IN ('video_first', 'text_first')),
    CONSTRAINT chk_slp_post_score CHECK (post_quiz_score IS NULL OR post_quiz_score BETWEEN 0.0 AND 1.0)
);
CREATE INDEX idx_slp_student ON student_lesson_packs (student_id);
CREATE INDEX idx_slp_lesson_plan ON student_lesson_packs (lesson_plan_id);
```

**Deprecate curriculum_chunks** (separate migration or same one):
```python
op.execute("""
    COMMENT ON TABLE curriculum_chunks IS
    'DEPRECATED in v1. PDF ingestion was abandoned.
     Table is not populated in v1.
     See subtopic_content table for the replacement architecture.
     Do not write to this table. Safe to query (always returns 0 rows).';
""")
```

### Step 1.2 — SQLAlchemy Model

**Create:** `backend/app/models/subtopic_content.py`

```python
from __future__ import annotations
from uuid import uuid4
from sqlalchemy import Column, String, Text, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base


class SubtopicContent(Base):
    __tablename__ = "subtopic_content"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    subtopic_id = Column(
        UUID(as_uuid=True),
        ForeignKey("subtopics.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # LLM-generated explanation (raw)
    llm_explanation = Column(Text, nullable=True)
    llm_generated_at = Column(DateTime(timezone=True), nullable=True)

    # Teacher-reviewed explanation
    approved_explanation = Column(Text, nullable=True)
    explanation_review_status = Column(String(20), nullable=False, default="pending")
    explanation_reviewed_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    explanation_reviewed_at = Column(DateTime(timezone=True), nullable=True)

    # Video candidates array
    videos = Column(JSONB, nullable=False, default=list)

    # Metadata
    audience = Column(String(20), nullable=False, default="both")

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    subtopic = relationship("Subtopic", back_populates="content")

    def get_approved_videos(self) -> list[dict]:
        return [v for v in (self.videos or []) if v.get("status") == "approved"]

    def get_display_explanation(self) -> str | None:
        return self.approved_explanation or self.llm_explanation
```

**Modify:** `backend/app/models/__init__.py` — add `SubtopicContent` to imports and `__all__`

### Step 1.3 — Pydantic Schemas

**Create:** `backend/app/schemas/subtopic_content.py`

Schemas required: `VideoEntry`, `SubtopicContentReviewResponse`, `ReviewQueueItem`, `ReviewQueueResponse`, `VideoStatusUpdateRequest`, `ManualVideoAddRequest`, `ExplanationQueueItem`, `ExplanationQueueResponse`, `ExplanationApprovalRequest`

### Step 1.4 — Seed Script

**Create:** `backend/scripts/seed_subtopic_content.py`

**Usage:**
```
python -m scripts.seed_subtopic_content [--dry-run] [--subject MATH] [--limit 10] [--skip-videos] [--skip-llm]
```

**Script logic:**
1. Load all active subtopics (joined with CurriculumTopic, Subject, Grade)
2. For each subtopic without `subtopic_content` row:
   - Generate LLM explanation via `litellm.acompletion()` (model: gemini/gemini-2.5-pro)
   - Search YouTube Data API v3 for top 3 videos by view count
   - Upsert to DB
3. Idempotent — skip subtopics that already have content

**YouTube API details:**
- Search query: `f"{subject_name} {subtopic.name} {curriculum_code} tutorial"`
- Filter: `videoDuration=medium`, `videoDefinition=high`, `relevanceLanguage=en`
- Score by `view_count`, take top 3
- Each video entry: `{url, title, channel, view_count, status: "pending", last_checked_at}`

### Step 1.5 — Unit Tests

**Create:** `backend/tests/unit/test_subtopic_content_seed.py`

Tests:
- `test_seed_when_subtopic_has_no_content_then_row_created`
- `test_seed_when_subtopic_already_has_explanation_then_not_overwritten`
- `test_seed_when_subtopic_already_has_videos_then_not_overwritten`
- `test_seed_when_youtube_fails_then_warning_logged_and_continues`
- `test_seed_when_llm_fails_then_warning_logged_and_continues`
- `test_seed_dry_run_when_called_then_no_db_writes`
- `test_get_approved_videos_when_all_pending_then_returns_empty`
- `test_get_approved_videos_when_one_approved_then_returns_one`
- `test_get_display_explanation_when_no_approved_then_returns_llm`
- `test_get_display_explanation_when_approved_exists_then_returns_approved`

**Create:** `backend/tests/integration/test_subtopic_content_pipeline.py`

### Step 1.6 — Run Migration and Seed

```bash
alembic upgrade head
python -m scripts.seed_subtopic_content
```

**Validation:**
- `subtopic_content` table has rows for all active subtopics
- Each row has `llm_explanation IS NOT NULL`
- Each row has at least 1 video entry with `status = 'pending'`

### Step 1.7 — `get_interest_category()` function

**Add to:** `backend/app/core/questionnaire_config.py`

```python
def get_interest_category(student_interests: list[str]) -> str | None:
    """
    Maps a student's raw interest list to one of the 4 canonical interest categories.
    Returns the first matching category for the first matching interest.
    Returns None if no interest matches a known category.
    """
    CATEGORY_MAP = {
        'sports_movement': {'sports', 'football', 'basketball', 'swimming', 'running', 'dance', 'athletics', 'cricket'},
        'tech_gaming': {'gaming', 'technology', 'coding', 'programming', 'robots', 'computers', 'apps'},
        'nature_animals': {'animals', 'nature', 'wildlife', 'environment', 'plants', 'ecology'},
        'arts_culture': {'music', 'art', 'drawing', 'films', 'movies', 'stories', 'design', 'culture', 'cooking'},
    }
    for interest in student_interests:
        for category, keywords in CATEGORY_MAP.items():
            if interest.lower() in keywords:
                return category
    return None
```

---

## PHASE 2 — M3-0-T2a: KaihleAdmin Video Review UI

**Depends on:** M3-0-T1 (migration deployed, table seeded)

### Step 2.1 — Backend API Routes

**Create:** `backend/app/api/v1/routes/subtopic_content.py`

Endpoints (KAIHLE_ADMIN only):
- `GET /subtopic-content/review-queue` — paginated list of subtopics with pending video reviews
- `GET /subtopic-content/{subtopic_id}` — full subtopic_content row
- `PATCH /subtopic-content/{subtopic_id}/videos/{video_index}` — update video status
- `POST /subtopic-content/{subtopic_id}/videos` — add manual video

**Register in `main.py`** with prefix `/api/v1`

### Step 2.2 — Unit Tests

**Create:** `backend/tests/unit/test_subtopic_content_routes.py`

Tests: `test_review_queue_when_kaihle_admin_then_returns_queue`, `test_review_queue_when_teacher_role_then_403`, `test_update_video_status_when_valid_index_then_status_updated`, `test_update_video_status_when_invalid_index_then_404`, `test_add_manual_video_when_valid_then_appended_to_array`, etc.

### Step 2.3 — Frontend: Video Review Queue Page

**Create:** `frontend/apps/kaihle-admin/src/pages/content/VideoReviewQueue.tsx`

Route: `/kaihle-admin/content/videos`

Features:
- Table of subtopics with pending video counts
- Filters: Subject dropdown, Grade dropdown, Status filter
- Badge on sidebar showing pending count
- Click row → navigate to detail page

**Follow DESIGN_SYSTEM.md §5.1 (Kaihle Admin):** Inter font, surgical slate palette, green action buttons, left sidebar layout.

### Step 2.4 — Frontend: Video Review Detail Page

**Create:** `frontend/apps/kaihle-admin/src/pages/content/VideoReviewDetail.tsx`

Route: `/kaihle-admin/content/videos/:subtopicId`

Features:
- Up to 3 video cards per subtopic
- YouTube embed with proper `sandbox`, `title`, `aria-label` attributes
- Approve/Reject buttons per video
- Add manual video modal

### Step 2.5 — Frontend: Video Review Card Component

**Create:** `frontend/apps/kaihle-admin/src/components/content/VideoReviewCard.tsx`

**Create:** `frontend/apps/kaihle-admin/src/components/content/VideoStatusBadge.tsx`

### Step 2.6 — React Query Hooks

**Create:** `frontend/apps/kaihle-admin/src/hooks/useSubtopicContent.ts`

`useVideoReviewQueue(filters)`, `useSubtopicContentDetail(subtopicId)`, `useUpdateVideoStatus()`, `useAddManualVideo()`

### Step 2.7 — Sidebar Navigation

**Modify:** KaihleAdmin sidebar — add CONTENT section with "Video Library" nav item with badge

### Step 2.8 — Playwright Tests

**Create:** `frontend/apps/kaihle-admin/src/tests/video-review.spec.ts`

---

## PHASE 3 — M3-0-T2b: Teacher Explanation Review UI

**Depends on:** M3-0-T1 (migration deployed, table seeded)

### Step 3.1 — Backend: Teacher-Scoped Explanation Endpoints

**Add to:** `backend/app/api/v1/routes/subtopic_content.py`

Endpoints (TEACHER only, scoped to teacher's classes):
- `GET /subtopic-content/explanation-queue` — subtopics with pending explanations for teacher's classes
- `GET /subtopic-content/{subtopic_id}/explanation` — explanation for one subtopic
- `PATCH /subtopic-content/{subtopic_id}/explanation` — approve/reject explanation

### Step 3.2 — Unit Tests

**Create:** `backend/tests/unit/test_explanation_review.py`

Tests: `test_explanation_queue_when_teacher_then_scoped_to_their_classes`, `test_approve_explanation_when_valid_then_stores_approved_text`, etc.

### Step 3.3 — Frontend: Explanation Review Queue Page

**Create:** `frontend/apps/teacher/src/pages/content/ExplanationReviewQueue.tsx`

Route: `/teacher/content/explanations`

**Follow DESIGN_SYSTEM.md §5.3 (Teacher):** Fraunces headings, Nunito body, GOLD action buttons. Green = mastery only.

### Step 3.4 — Frontend: Explanation Editor Component

**Create:** `frontend/apps/teacher/src/components/content/ExplanationEditor.tsx`

Features:
- Editable textarea with word counter (max 200 words)
- Interest example block (distinct styled callout, separate approve action)
- Focus management on edit mode activation (WCAG 2.1)
- Approve (gold button), Reject (outlined danger), Cancel buttons

### Step 3.5 — Frontend: Gap Map Side Panel Integration

**Modify:** `frontend/apps/teacher/src/components/gap-map/GapMapSidePanel.tsx`

Add "Review Explanation" section linking to explanation editor for pending subtopics.

### Step 3.6 — React Query Hooks

**Create:** `frontend/apps/teacher/src/hooks/useSubtopicContent.ts`

### Step 3.7 — Sidebar Navigation

**Modify:** Teacher sidebar — add CONTENT section with "Lesson Explanations" nav item with badge

---

## PHASE 4 — M3-0-T3: Stale Link Celery Job

**Depends on:** M3-0-T1 (migration deployed, table populated)

### Step 4.1 — Celery Task

**Create:** `backend/app/tasks/content_maintenance_tasks.py`

```python
@shared_task(name="tasks.check_stale_video_links", max_retries=0, ignore_result=True)
def check_stale_video_links() -> None:
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_run_stale_check())
    finally:
        loop.close()
```

**Job logic:**
- Query all `subtopic_content` rows with videos
- For each video with status `pending` or `approved`:
  - Skip if `last_checked_at` < 7 days ago
  - Skip if status is `rejected` or `stale`
  - Perform HEAD request (fallback to GET on 405)
  - If 404 or 403 → mark as `stale`
  - Update `last_checked_at`
- Cap at 500 URLs per run
- 0.5s delay between requests

### Step 4.2 — Beat Schedule

**Modify:** `backend/app/tasks/celery_app.py`

Add:
```python
"check-stale-video-links": {
    "task": "tasks.check_stale_video_links",
    "schedule": crontab(hour=2, minute=0),  # daily at 02:00
}
```

### Step 4.3 — Unit Tests

**Create:** `backend/tests/unit/test_stale_link_job.py`

Tests: `test_check_url_when_404_then_returns_true`, `test_check_url_when_200_then_returns_false`, `test_check_url_when_405_then_falls_back_to_get_and_returns_false`, `test_stale_check_when_video_checked_recently_then_skipped`, `test_stale_check_when_cap_reached_then_stops_at_max_urls`, etc.

---

## PHASE 5 — M3-1-T1: Content Curator

**Depends on:** M3-0-T1 (subtopic_content table with approved videos)

### Step 5.1 — Content Curator Service

**Create:** `backend/app/ai/content_curator.py`

```python
async def curate_resources(
    subtopic: Subtopic,
    student_id: UUID,
    school_id: UUID,
    db: AsyncSession,
    redis: Redis,
) -> list[Resource]:
```

**Logic:**
1. Check Redis cache: `content:{subtopic_id}:{student_id}`
2. Load `StudentLearningProfile` for student
3. Load `SubtopicContent` for subtopic
4. Get approved videos via `get_approved_videos()`
5. Apply modality weighting:
   - Visual > 0.6: multiplier × 1.3
   - Auditory > 0.6: multiplier × 1.2 (cumulative)
6. Sort by `final_score` descending
7. Return top 3 as `Resource` objects
8. Cache in Redis for 24h

### Step 5.2 — Resource Dataclass

```python
@dataclass
class Resource:
    url: str
    title: str
    description: str
    resource_type: ResourceType  # VIDEO | ARTICLE | INTERACTIVE
    duration_seconds: int | None
    source: str  # "youtube" | "khan_academy" | "static"
    thumbnail_url: str | None
    base_score: float
    final_score: float
```

### Step 5.3 — Unit Tests

**Create:** `backend/tests/unit/test_content_curator.py`

Tests: `test_curate_when_visual_profile_then_multiplier_applied`, `test_curate_when_no_subtopic_content_row_then_empty_list_and_warning`, `test_curate_when_cached_then_no_db_call`, etc.

### Step 5.4 — Integration Tests

**Create:** `backend/tests/integration/test_curation_integration.py`

---

## PHASE 6 — M3-1-T2: Quiz Generator

**Depends on:** M3-0-T1 (subtopic_content table)

### Step 6.1 — Quiz Generator Service

**Create:** `backend/app/ai/quiz_generator.py`

```python
async def generate_quiz(
    subtopic: Subtopic,
    student_mastery: float,
    student_id: UUID,
    db: AsyncSession,
) -> GeneratedQuiz:
```

**Logic:**
1. Load `SubtopicContent` → get `approved_explanation` (or fallback to `subtopic.learning_objective`)
2. Load `StudentLearningProfile` → get interests
3. Filter interests via `get_compatible_interests(subject_code, interests)` from `questionnaire_config.py`
4. Determine difficulty label based on mastery score
5. Build prompt using Jinja2 template `study_plan_quiz.jinja2`
6. Call `router.complete(task="question_generation", messages=...)`
7. Parse JSON response
8. Validate: exactly 5 MCQ questions, each with exactly 4 options
9. Retry once on invalid JSON or timeout
10. Return `GeneratedQuiz`

**Hard timeout:** 8 seconds. On timeout → retry once → raise `QuizGenerationError`.

### Step 6.2 — Jinja2 Prompt Template

**Create:** `backend/app/ai/prompts/study_plan_quiz.jinja2`

```jinja2
System: You are an educational content creator for {{ curriculum_code }} {{ subject_name }}.
        Generate a practice quiz. Return ONLY valid JSON — no preamble, no markdown fences.

Student mastery: {{ mastery_pct }}% on: {{ subtopic_name }}.
Difficulty calibration: {{ difficulty_label }}.

Learning objectives:
{{ learning_objectives }}

Subtopic explanation (use this to anchor questions to what was taught):
{{ subtopic_context }}

{% if top_2_interests %}
Personalisation: Where it fits naturally, frame question scenarios using topics this
student finds interesting: {{ top_2_interests | join(', ') }}.
Do NOT force the interest — academic accuracy is always the priority.
Only use if the scenario genuinely fits the subtopic.
{% endif %}

Generate exactly 5 MCQ questions.
Each MCQ must have exactly 4 options (A, B, C, D).
All questions must be MCQ — no short answer, no true/false.
```

### Step 6.3 — Unit Tests

**Create:** `backend/tests/unit/test_quiz_generator.py`

Tests: `test_generate_quiz_when_interests_present_then_prompt_includes_interests`, `test_generate_quiz_when_mastery_low_then_prompt_has_foundational`, `test_generated_quiz_has_5_mcq_no_short_answer`, etc.

### Step 6.4 — Integration Tests

**Create:** `backend/tests/integration/test_quiz_generation.py`

---

## PHASE 7 — M3-1-T3: Quiz Quality Validation

**Depends on:** M3-1-T2 (quiz generator exists)

### Step 7.1 — Quiz Validator Service

**Create:** `backend/app/services/quiz_validator.py`

```python
class QuizValidator:
    SIMILARITY_THRESHOLD = 0.55
    MAX_QUESTION_TOKENS = 120

    async def validate_question(self, question_text, subtopic_id, grade_level) -> tuple[bool, str]:
        # Gate 1: Semantic similarity using pgvector
        # Uses embed_text() + cosine similarity
        # Skip if subtopic has no embedding (pass-through)
        # Gate 2: Word count > 120 → reject
        return (is_valid, rejection_reason)

    async def validate_batch(self, questions, subtopic_id, grade_level) -> list[dict]:
```

### Step 7.2 — Integrate into QuizGenerator

**Modify:** `backend/app/ai/quiz_generator.py`

After LLM response parsing:
```python
validator = QuizValidator(self.db)
valid_questions = await validator.validate_batch(raw_questions, subtopic_id, grade_level)

if len(valid_questions) < 5:
    # Retry once with needed + 2 questions
    retry_questions = await self._call_llm(...)
    retry_valid = await validator.validate_batch(retry_questions, ...)
    valid_questions.extend(retry_valid)

if len(valid_questions) < 3:
    raise QuizGenerationError("Insufficient valid questions after retry")
```

### Step 7.3 — Unit Tests

**Create:** `backend/tests/unit/test_quiz_validator.py`

Tests: `test_validate_question_when_high_similarity_then_passes`, `test_validate_question_when_too_long_then_rejected`, etc.

---

## PHASE 8 — M3-2-T1: Study Plan Service

**Depends on:** M3-1-T1 (content curator), M3-1-T2 (quiz generator)

### Step 8.1 — Study Plan Service

**Create:** `backend/app/services/study_plan_service.py`

**Service: `create_study_plan(config: StudyPlanCreate) → StudyPlanResponse`**
1. Create `StudyPlan` row with `status=GENERATING`
2. Queue Celery task `generate_study_plan_content.delay(str(plan.id))`
3. Return immediately with `status=GENERATING`

**Service: `create_bulk_study_plans(...)`**
- Loop over student_ids, call `create_study_plan` for each
- Return list of plans

**Service: `submit_quiz(plan_id, student_id, responses) → QuizResult`**
1. Load plan, validate ownership
2. Score each MCQ response
3. Calculate total score
4. Update `study_plan_quizzes.score`
5. Update plan status
6. Trigger `update_gap_state_from_quiz.delay(...)`
7. Return `QuizResult`

### Step 8.2 — Celery Task

**Create/Modify:** `backend/app/tasks/study_plan_tasks.py`

```python
@shared_task(bind=True, max_retries=2)
def generate_study_plan_content(self, plan_id: str):
    # 1. Curate resources via content_curator
    # 2. Generate quiz via quiz_generator
    # 3. Store resources in study_plan_resources
    # 4. Store quiz in study_plan_quizzes
    # 5. Update plan status to ACTIVE
```

### Step 8.3 — Unit Tests

**Create:** `backend/tests/unit/test_study_plan_service.py`

Tests: `test_create_study_plan_returns_generating_status_immediately`, `test_generate_task_when_complete_then_plan_status_active`, etc.

### Step 8.4 — Integration Tests

**Create:** `backend/tests/integration/test_study_plan_creation.py`

---

## PHASE 9 — M3-2-T2: Study Plan Routes (Stub Replacement)

**Depends on:** M3-2-T1 (study plan service exists)

### Step 9.1 — Replace Stub Bodies

**Modify:** `backend/app/api/v1/routes/study_plans.py`

**DO NOT change:** route decorators, paths, response_model, status_code, Depends

Replace ONLY function bodies for:
1. `assign_study_plans` → call `StudyPlanService.assign_plans`
2. `list_my_study_plans` → call `StudyPlanService.list_student_plans`
3. `list_student_study_plans` → role-based authorization + service call
4. `get_study_plan` → ownership check + service call
5. `mark_resource_watched` → verify ownership + DB write
6. `submit_study_plan_quiz` → call `StudyPlanService.submit_quiz`

### Step 9.2 — Integration Tests

**Create:** `backend/tests/integration/test_study_plan_routes.py`

Full test cases specified in task file:
- `test_assign_plans_when_teacher_owns_class_then_202_with_generating_plans`
- `test_assign_plans_when_teacher_does_not_own_class_then_403`
- `test_list_my_study_plans_when_student_has_plans_then_200_with_data`
- `test_get_plan_quiz_questions_never_include_correct_answer`
- `test_submit_quiz_when_4_correct_of_5_then_score_0_8_and_plan_completed`
- etc.

---

## PHASE 10 — M3-2-T3: Student Study Plan UI

**Depends on:** M3-2-T2 (routes return real data)

### Step 10.1 — Study Plan List Page

**Create:** `frontend/apps/student/src/pages/study-plans/StudyPlanListPage.tsx`

Route: `/student/study-plans`

Features:
- Group plans by subject
- Within subject: ACTIVE first, GENERATING, COMPLETED last
- `PlanStatusBadge` per plan
- GENERATING: animated pulse, "Your personalised plan is being prepared..."
- Empty state

### Step 10.2 — Study Plan Detail Page

**Create:** `frontend/apps/student/src/pages/study-plans/StudyPlanDetailPage.tsx`

Route: `/student/study-plans/:planId`

Features:
- Resources section with "✨ Matched to your style" badge
- Quiz section (locked until 1 resource watched — soft UX gate)
- ResourceCard components with watch/mark-done
- StudyPlanQuiz component

### Step 10.3 — Resource Card Component

**Create:** `frontend/apps/student/src/components/ResourceCard.tsx`

Features:
- Video type icon (📹), source, duration
- "Mark as done" checkbox with optimistic update
- Already-watched: green tint + "Done ✓"

### Step 10.4 — Study Plan Quiz Component

**Create:** `frontend/apps/student/src/components/StudyPlanQuiz.tsx`

Features:
- 5 questions (MCQ + SHORT_ANSWER) on single scrollable page
- MCQ: 2×2 option grid, single select
- SHORT_ANSWER: textarea, 300-char limit
- Submit disabled until all answered
- Results: score display with message, per-question correct/incorrect + explanation

### Step 10.5 — React Query Hooks

**Create:** `frontend/apps/student/src/hooks/useStudyPlanDetail.ts`
**Create:** `frontend/apps/student/src/hooks/useStudyPlanActions.ts`

### Step 10.6 — Navigation Integration

**Modify:** Student sidebar — "Study Plans" nav item
**Modify:** `/student/my-progress` — "Suggested Next Steps" section links to study plans

### Step 10.7 — Tests

**Create:** `frontend/apps/student/src/tests/study-plans.spec.ts` (Playwright E2E)
**Create:** `frontend/apps/student/src/tests/StudyPlanQuiz.test.tsx` (Jest)

---

## PHASE 11 — M3-2-T4: Teacher Assignment UI

**Depends on:** M3-2-T2 (routes return real data)

### Step 11.1 — Assign Study Plan Modal

**Create:** `frontend/apps/teacher/src/components/study-plans/AssignStudyPlanModal.tsx`

Features:
- Three radio options: "All below 70%", "This student only", "Custom selection"
- StudentSelectionList for custom selection
- "Generate Plans →" gold button
- Success toast, inline error handling

### Step 11.2 — Student Selection List

**Create:** `frontend/apps/teacher/src/components/study-plans/StudentSelectionList.tsx`

### Step 11.3 — React Query Hook

**Create:** `frontend/apps/teacher/src/hooks/useAssignStudyPlan.ts`

### Step 11.4 — Gap Map Side Panel Wiring

**Modify:** `frontend/apps/teacher/src/components/study-plans/StudentSidePanel.tsx`

Replace stub toast with real `AssignStudyPlanModal`:
- Button disabled when `mastery_score >= 0.7`
- Modal opens with classId, subtopicId, studentScores

### Step 11.5 — Tests

**Add to:** `frontend/apps/teacher/src/tests/gap-map.spec.ts`

Tests: `test_assign_button_when_red_cell_then_enabled`, `test_assign_modal_default_option_is_all_below_threshold`, etc.

---

## Exit Criteria Summary

| Criterion | Validated By |
|-----------|-------------|
| `subtopic_content` table seeded for all active subtopics | M3-0-T1: seed script ran successfully |
| At least one video per subtopic approved by KaihleAdmin | M3-0-T2a: UI approved |
| Teacher explanation review UI operational | M3-0-T2b: UI approved |
| Nightly stale link job registered | M3-0-T3: Celery beat schedule confirmed |
| Teacher assigns study plan → student sees curated video | M3-2-T4 → M3-2-T3 E2E test |
| Resources personalised by learning modality | M3-1-T1: content curator unit tests |
| Quiz uses student interests in scenarios | M3-1-T2: quiz generator unit tests |
| Quiz submission updates gap_states | M3-2-T2: integration test |
| All M3 tests pass | Full test suite |

---

## Key Files Reference

### Backend Created Files
| File | Phase |
|------|-------|
| `backend/alembic/versions/XXX_add_subtopic_content_and_student_lesson_packs.py` | 1 |
| `backend/app/models/subtopic_content.py` | 1 |
| `backend/app/schemas/subtopic_content.py` | 1 |
| `backend/scripts/seed_subtopic_content.py` | 1 |
| `backend/app/api/v1/routes/subtopic_content.py` | 2, 3 |
| `backend/app/ai/content_curator.py` | 5 |
| `backend/app/ai/quiz_generator.py` | 6 |
| `backend/app/ai/prompts/study_plan_quiz.jinja2` | 6 |
| `backend/app/services/quiz_validator.py` | 7 |
| `backend/app/services/study_plan_service.py` | 8 |
| `backend/app/tasks/study_plan_tasks.py` | 8 |
| `backend/app/tasks/content_maintenance_tasks.py` | 4 |

### Frontend Created Files
| File | Phase |
|------|-------|
| `frontend/apps/kaihle-admin/src/pages/content/VideoReviewQueue.tsx` | 2 |
| `frontend/apps/kaihle-admin/src/pages/content/VideoReviewDetail.tsx` | 2 |
| `frontend/apps/kaihle-admin/src/components/content/VideoReviewCard.tsx` | 2 |
| `frontend/apps/kaihle-admin/src/components/content/VideoStatusBadge.tsx` | 2 |
| `frontend/apps/kaihle-admin/src/hooks/useSubtopicContent.ts` | 2 |
| `frontend/apps/teacher/src/pages/content/ExplanationReviewQueue.tsx` | 3 |
| `frontend/apps/teacher/src/components/content/ExplanationEditor.tsx` | 3 |
| `frontend/apps/teacher/src/hooks/useSubtopicContent.ts` | 3 |
| `frontend/apps/student/src/pages/study-plans/StudyPlanListPage.tsx` | 10 |
| `frontend/apps/student/src/pages/study-plans/StudyPlanDetailPage.tsx` | 10 |
| `frontend/apps/student/src/components/ResourceCard.tsx` | 10 |
| `frontend/apps/student/src/components/StudyPlanQuiz.tsx` | 10 |
| `frontend/apps/student/src/hooks/useStudyPlanDetail.ts` | 10 |
| `frontend/apps/student/src/hooks/useStudyPlanActions.ts` | 10 |
| `frontend/apps/teacher/src/components/study-plans/AssignStudyPlanModal.tsx` | 11 |
| `frontend/apps/teacher/src/components/study-plans/StudentSelectionList.tsx` | 11 |
| `frontend/apps/teacher/src/hooks/useAssignStudyPlan.ts` | 11 |

---

*Plan version 1.0 — Generated for M3 milestone*
*Key references: M3_brief.md, CONSTITUTION.md, CLAUDE.md, CLAUDE.local.md, DESIGN_SYSTEM.md*
