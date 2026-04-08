# M3-0-T1 — Subtopic Content Table, Migration & YouTube Seed Pipeline
**Milestone:** M3 — Smart Study Plans
**Epic:** M3-0 — Content Infrastructure (prerequisite to M3-1)
**Task:** T1
**Executor:** Coding agent
**Depends on:** M1-2-T1 (curriculum graph seeded — subtopics rows must exist), M0-2-T1 (Alembic infra)
**Blocks:** M3-0-T2a, M3-0-T2b, M3-0-T3, M3-1-T1, M3-1-T2, M4-1-T1

> **Run this task before any M3-1 or M4-1 tasks.**
> The `subtopic_content` table is the foundation every content-dependent feature builds on.
> No task may query `curriculum_chunks` for content — that table is deprecated.

---

## Context

PDF RAG ingestion was abandoned. `curriculum_chunks` is deprecated and will not be
populated. The replacement architecture is a single `subtopic_content` table that
stores:
- LLM-generated explanations per subtopic (reviewed by teachers)
- Approved YouTube video candidates per subtopic (reviewed by KaihleAdmin)

This task creates the table, seeds initial LLM explanations, and runs the YouTube
search pipeline to populate initial video candidates for KaihleAdmin review.

---

## User Story

As the system, I want a `subtopic_content` table per subtopic that holds
an LLM-generated explanation and a set of YouTube video candidates, so that
content curation, quiz generation, and lesson planning have a reliable, reviewed
content source that does not depend on external PDF files.

---

## Files to Create / Modify

```
CREATE  backend/alembic/versions/XXXX_add_subtopic_content_table.py
CREATE  backend/app/models/subtopic_content.py
CREATE  backend/app/schemas/subtopic_content.py
CREATE  backend/scripts/seed_subtopic_content.py
CREATE  backend/tests/unit/test_subtopic_content_seed.py
CREATE  backend/tests/integration/test_subtopic_content_pipeline.py

MODIFY  backend/app/models/__init__.py          ← add SubtopicContent import
MODIFY  backend/alembic/versions/XXXX_deprecate_curriculum_chunks.py ← new migration
```

---

## Part 1 — Database Migration

### New table: `subtopic_content`

> **CONSTITUTION Rule 2 note:** `subtopic_content` does NOT have `school_id`.
> It is a curriculum-layer table — school-agnostic by design, like `subtopics`,
> `curriculum_chunks`, and all other curriculum tables. One row per subtopic exists
> platform-wide; KaihleAdmin manages it globally. All other roles read it.
> This is consistent with the curriculum layer design principle in §1 of the schema.
> Any coding agent that adds `school_id` to this table is violating the schema design.

Generate via:
```bash
alembic revision --autogenerate -m "add_subtopic_content_table"
```

Then verify the generated migration matches this schema exactly:

```sql
CREATE TABLE subtopic_content (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subtopic_id UUID NOT NULL REFERENCES subtopics(id) ON DELETE CASCADE,
    UNIQUE(subtopic_id),

    -- LLM-generated explanation (raw, unreviewed)
    llm_explanation             TEXT,
    llm_generated_at            TIMESTAMPTZ,

    -- Teacher-reviewed explanation (approved canonical version)
    approved_explanation        TEXT,
    explanation_review_status   VARCHAR(20) NOT NULL DEFAULT 'pending',
    -- 'pending' | 'approved' | 'rejected'
    explanation_reviewed_by     UUID REFERENCES users(id) ON DELETE SET NULL,
    explanation_reviewed_at     TIMESTAMPTZ,

    -- Video candidates (KaihleAdmin-reviewed)
    -- JSONB array: [{url, title, channel, view_count, status, last_checked_at}]
    -- status per entry: 'pending' | 'approved' | 'rejected' | 'stale'
    videos                      JSONB NOT NULL DEFAULT '[]',

    -- Metadata
    audience                    VARCHAR(20) NOT NULL DEFAULT 'both',
    -- 'teacher' | 'student' | 'both'

    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_subtopic_content_subtopic ON subtopic_content (subtopic_id);
CREATE INDEX idx_subtopic_content_explanation_status
    ON subtopic_content (explanation_review_status);
```

### Add `student_lesson_packs` table (needed by M4-2-T1)

Include in the same migration or a follow-on:

```sql
CREATE TABLE student_lesson_packs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    school_id       UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    -- school_id: CONSTITUTION Rule 2 — every non-curriculum table requires school_id.
    -- student_lesson_packs is student data, not curriculum data. school_id is mandatory.
    lesson_plan_id  UUID NOT NULL REFERENCES lesson_plans(id) ON DELETE CASCADE,
    subtopic_id     UUID NOT NULL REFERENCES subtopics(id) ON DELETE CASCADE,
    learning_style  VARCHAR(30) NOT NULL,
    -- 'visual' | 'auditory' | 'kinesthetic' | 'reading_writing' | 'mixed'
    interest_category VARCHAR(50),
    -- null = generic | 'sports_movement' | 'tech_gaming' | 'nature_animals' | 'arts_culture'

    -- Generated pack content
    what_you_will_learn TEXT NOT NULL,      -- 1 plain-language sentence
    real_life_intro     TEXT NOT NULL,      -- max 100 words, interest-matched
    explanation         TEXT NOT NULL,      -- max 200 words, learning-style adapted
    content_sequence    VARCHAR(20) NOT NULL DEFAULT 'video_first',
    -- 'video_first' | 'text_first'
    video_url           TEXT,               -- pulled from subtopic_content.videos (approved)
    video_title         TEXT,

    -- Pre and post quizzes (3 questions each, from question_bank)
    pre_quiz_question_ids   UUID[] NOT NULL DEFAULT '{}',
    post_quiz_question_ids  UUID[] NOT NULL DEFAULT '{}',
    post_quiz_score         FLOAT,          -- null until student completes post quiz
    post_quiz_completed_at  TIMESTAMPTZ,

    generated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ai_model        VARCHAR(100),

    UNIQUE(student_id, lesson_plan_id, learning_style, interest_category),
    CONSTRAINT chk_slp_content_sequence
        CHECK (content_sequence IN ('video_first', 'text_first')),
    CONSTRAINT chk_slp_post_score
        CHECK (post_quiz_score IS NULL OR post_quiz_score BETWEEN 0.0 AND 1.0)
);

CREATE INDEX idx_slp_student ON student_lesson_packs (student_id);
CREATE INDEX idx_slp_lesson_plan ON student_lesson_packs (lesson_plan_id);
CREATE INDEX idx_slp_lookup
    ON student_lesson_packs (student_id, lesson_plan_id, learning_style, interest_category);
```

### Deprecate `curriculum_chunks` (separate migration)

```python
# alembic migration — do NOT drop the table, just add deprecation comment
# Table is preserved for historical reference, never written to in v1.
# Comment on table to document this:
op.execute("""
    COMMENT ON TABLE curriculum_chunks IS
    'DEPRECATED in v1. PDF ingestion was abandoned.
     Table is not populated in v1.
     See subtopic_content table for the replacement architecture.
     Do not write to this table. Safe to query (always returns 0 rows).';
""")
```

---

## Part 2 — SQLAlchemy ORM Model

**`backend/app/models/subtopic_content.py`**

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
    explanation_review_status = Column(
        String(20), nullable=False, default="pending"
    )
    explanation_reviewed_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    explanation_reviewed_at = Column(DateTime(timezone=True), nullable=True)

    # Video candidates array
    videos = Column(JSONB, nullable=False, default=list)

    # Metadata
    audience = Column(String(20), nullable=False, default="both")

    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    subtopic = relationship("Subtopic", back_populates="content")

    def get_approved_videos(self) -> list[dict]:
        """Return only approved video entries from the JSONB array."""
        return [v for v in (self.videos or []) if v.get("status") == "approved"]

    def get_display_explanation(self) -> str | None:
        """Return approved explanation if available, otherwise llm_explanation."""
        return self.approved_explanation or self.llm_explanation
```

---

## Part 3 — Seed Script

**`backend/scripts/seed_subtopic_content.py`**

```
Usage: python seed_subtopic_content.py [--dry-run] [--subject MATH] [--limit 10]

Flags:
  --dry-run      Print what would be generated, do not write to DB
  --subject      Seed only one subject (e.g. MATH, SCI, ENG)
  --limit N      Seed at most N subtopics (for testing)
  --skip-videos  Generate explanations only, skip YouTube API calls
  --skip-llm     Run YouTube pipeline only, skip LLM explanation generation
```

### Step 1 — Load all subtopics

```python
subtopics = await db.execute(
    select(Subtopic)
    .join(CurriculumTopic, Subtopic.curriculum_topic_id == CurriculumTopic.id)
    .join(Subject, CurriculumTopic.subject_id == Subject.id)
    .where(Subtopic.is_active == True)
    .order_by(CurriculumTopic.grade_id, Subject.code, Subtopic.sequence_order)
)
```

### Step 2 — Generate LLM explanation per subtopic

Skip if `subtopic_content` row already has `llm_explanation IS NOT NULL` (idempotent).

LLM call via LiteLLM:
```python
MODEL = os.getenv("LLM_SUBTOPIC_CONTENT_MODEL", "gemini/gemini-2.5-pro")
TIMEOUT_S = 30

prompt = f"""You are a curriculum expert writing a clear, factual explanation
for a {grade_name} {subject_name} subtopic.

Subtopic: {subtopic.name}
Learning objective: {subtopic.learning_objective}
Curriculum: {curriculum_code}

Write a plain-language explanation of this subtopic for a {grade_name} student.
Requirements:
- Maximum 200 words
- Use simple, clear language appropriate for age {age_range}
- Include one concrete real-world example
- Do not reference specific exam boards or syllabuses
- No headers, no bullet points — flowing prose only
- Academic accuracy is mandatory — do not simplify to the point of being wrong

Return ONLY the explanation text. No preamble."""

response = await asyncio.wait_for(
    litellm.acompletion(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=300,
        temperature=0.3,
    ),
    timeout=TIMEOUT_S,
)
explanation = response.choices[0].message.content.strip()
```

Write to `subtopic_content.llm_explanation`. Set `llm_generated_at = now()`.
Set `explanation_review_status = 'pending'`.

### Step 3 — YouTube search per subtopic

Skip if `subtopic_content` row already has `videos` JSONB with 3+ pending entries.

```python
YOUTUBE_API_KEY = os.getenv("YOUTUBE_DATA_API_KEY")
YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_VIDEO_URL = "https://www.googleapis.com/youtube/v3/videos"

# Build search query
query = f"{subject_name} {subtopic.name} {curriculum_code} tutorial"

# Search for videos
search_params = {
    "part": "snippet",
    "q": query,
    "type": "video",
    "videoDuration": "medium",      # 4-20 minutes
    "videoDefinition": "high",
    "relevanceLanguage": "en",
    "maxResults": 10,
    "key": YOUTUBE_API_KEY,
}
search_response = await httpx_client.get(YOUTUBE_SEARCH_URL, params=search_params)
video_ids = [item["id"]["videoId"] for item in search_response.json()["items"]]

# Get video statistics
stats_params = {
    "part": "statistics,contentDetails",
    "id": ",".join(video_ids),
    "key": YOUTUBE_API_KEY,
}
stats_response = await httpx_client.get(YOUTUBE_VIDEO_URL, params=stats_params)

# Build candidate list scored by view_count
candidates = []
for item in stats_response.json()["items"]:
    vid_id = item["id"]
    stats = item["statistics"]
    view_count = int(stats.get("viewCount", 0))
    # Find matching snippet from search results
    snippet = next(
        s["snippet"] for s in search_response.json()["items"]
        if s["id"]["videoId"] == vid_id
    )
    candidates.append({
        "url": f"https://www.youtube.com/watch?v={vid_id}",
        "title": snippet["title"],
        "channel": snippet["channelTitle"],
        "view_count": view_count,
        "status": "pending",
        "last_checked_at": datetime.utcnow().isoformat(),
    })

# Sort by view_count descending, take top 3
top_3 = sorted(candidates, key=lambda v: v["view_count"], reverse=True)[:3]
```

Write `top_3` to `subtopic_content.videos`.

### Step 4 — Upsert to DB

```python
existing = await db.get(SubtopicContent, subtopic.id)
if existing is None:
    row = SubtopicContent(
        subtopic_id=subtopic.id,
        llm_explanation=explanation,
        llm_generated_at=datetime.utcnow(),
        videos=top_3,
    )
    db.add(row)
else:
    if existing.llm_explanation is None:
        existing.llm_explanation = explanation
        existing.llm_generated_at = datetime.utcnow()
    if not existing.videos:
        existing.videos = top_3
await db.commit()
```

### Step 5 — Progress reporting

```
[  1/193] MATH Grade 6 — Number Sense                    ✓ explanation + 3 videos
[  2/193] MATH Grade 6 — Place Value                     ✓ explanation + 3 videos
[  3/193] SCI  Grade 6 — Cell Structure                  ✓ explanation + 2 videos (1 filtered)
...
[193/193] PHY  Grade 10 — Electromagnetic Spectrum       ✓ explanation + 3 videos

Seed complete: 193 subtopics processed
  Explanations generated: 193
  Explanations skipped (already exist): 0
  Videos found: 571 (avg 2.96 per subtopic)
  YouTube API errors: 2 (see warnings above)
  LLM errors: 0
```

---

## Part 4 — Acceptance Criteria

- [ ] Migration runs without errors: `alembic upgrade head`
- [ ] `subtopic_content` table exists with all columns and constraints
- [ ] `student_lesson_packs` table exists with all columns and constraints
- [ ] `curriculum_chunks` table has deprecation comment applied
- [ ] Seed script is idempotent — running twice produces no duplicates
- [ ] Seed script `--dry-run` prints output without writing to DB
- [ ] Seed script `--subject MATH` seeds only MATH subtopics
- [ ] Every seeded `subtopic_content` row has `llm_explanation IS NOT NULL`
- [ ] Every seeded `subtopic_content` row has at least 1 entry in `videos` JSONB
- [ ] All video entries start with `status = 'pending'`
- [ ] `get_approved_videos()` returns empty list when all videos are pending
- [ ] `get_display_explanation()` returns `llm_explanation` when no approved version exists
- [ ] YouTube API failure on one subtopic → logs WARNING, script continues to next subtopic
- [ ] LLM failure on one subtopic → logs WARNING, script continues to next subtopic
- [ ] `KAIHLE_ADMIN` bypass pattern applied to any service method that reads this table

---

## Part 5 — Tests

**`backend/tests/unit/test_subtopic_content_seed.py`**

```python
def test_seed_when_subtopic_has_no_content_then_row_created()
def test_seed_when_subtopic_already_has_explanation_then_not_overwritten()
def test_seed_when_subtopic_already_has_videos_then_not_overwritten()
def test_seed_when_youtube_fails_then_warning_logged_and_continues()
def test_seed_when_llm_fails_then_warning_logged_and_continues()
def test_seed_dry_run_when_called_then_no_db_writes()
def test_get_approved_videos_when_all_pending_then_returns_empty()
def test_get_approved_videos_when_one_approved_then_returns_one()
def test_get_display_explanation_when_no_approved_then_returns_llm()
def test_get_display_explanation_when_approved_exists_then_returns_approved()
def test_video_candidates_sorted_by_view_count_descending()
def test_only_top_3_videos_stored_per_subtopic()
```

**`backend/tests/integration/test_subtopic_content_pipeline.py`**

```python
def test_migration_when_run_then_subtopic_content_table_exists()
def test_migration_when_run_then_student_lesson_packs_table_exists()
def test_seed_pipeline_when_run_against_seeded_db_then_all_subtopics_have_content()
def test_subtopic_content_row_when_queried_by_subtopic_id_then_returns_row()
```

---

## Do NOT Touch

- `curriculum_chunks` table — do not write to it, do not drop it
- `subtopics.embedding` column — do not use or populate it
- Any `embedder.py` or `retriever.py` files — do not create them
- Existing `M1-2-T1_curriculum_graph_seeding.md` logic — the seeded subtopics are the input to this script

---

## Required Addition to `questionnaire_config.py`

M4-2-T1 calls `get_interest_category(interests)` from `app.core.questionnaire_config`.
Add this function in the same task (or as a separate micro-task if questionnaire_config
is complex). The function must:

```python
def get_interest_category(student_interests: list[str]) -> str | None:
    """
    Maps a student's raw interest list to one of the 4 canonical interest categories.
    Returns the first matching category for the first matching interest.
    Returns None if no interest matches a known category.

    Categories:
      'sports_movement' — sports, football, basketball, swimming, running, dance, athletics, cricket
      'tech_gaming'     — gaming, technology, coding, programming, robots, computers, apps
      'nature_animals'  — animals, nature, wildlife, environment, plants, ecology
      'arts_culture'    — music, art, drawing, films, movies, stories, design, culture, cooking

    Note: 'cooking' maps to 'arts_culture' for the interest category system even though
    it is a standalone interest in the questionnaire — it has the closest thematic fit.
    """
```

This function belongs in `questionnaire_config.py` alongside `get_compatible_interests()`
(which already exists per M3-1-T2 correction note). Do not duplicate this logic in
service files.

---

*Task M3-0-T1 · Kramer (Technical Lead) · April 2026*
