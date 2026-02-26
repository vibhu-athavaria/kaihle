# Kaihle — Diagnostic Assessment Module
## Comprehensive Project Plan for KiloCode

**Version:** 3.1
**Prepared by:** Kremer (Technical Lead)
**Target:** KiloCode AI Builder
**Stack:** FastAPI · PostgreSQL · pgvector · Redis · Celery · React + Vite · Docker · AWS S3 / MinIO · Manim · Google Gemini API

---

## How to Read This Document

This document is the single source of truth for all development on the Diagnostic Assessment
Module. Every architectural decision, every file path, every column name, every environment
variable, every queue name, every task name, and every acceptance criterion is **explicit**.

KiloCode must not infer, assume, or improvise anything not stated here.
If something appears ambiguous, stop and ask before writing any code.

**Explicit over implicit. Always.**

---

## Changelog from v2.0

| # | Change | Phases Affected |
|---|---|---|
| 1 | StudyPlan redesigned: one plan per subject (was one plan for all 4 subjects combined) | 12A, 12B |
| 2 | StudyPlan trigger redesigned: fires per-subject on assessment complete (was after all 4 done) | 12B |
| 3 | StudyPlan model: add `subject_id` FK + `profile_fingerprint` columns via migration | 12A |
| 4 | Old `tasks.generate_study_plan` task deprecated and replaced entirely | 12B |
| 5 | Old StudyPlan test rows purged via migration script | 12A |
| 6 | RAG pipeline added: PDF textbook extraction → chunking → embeddings → query service | 10A–10D |
| 7 | S3 content storage: all generated media stored permanently in S3 / MinIO | 11A–11C |
| 8 | Redis LLM cache rule updated: S3 replaces Redis for study plan + media generation tasks | AGENTS.md |
| 9 | LLM output redesigned: multi-modal content spec (animation, infographic, practice questions) | 12C–12E |
| 10 | Audio podcast content type eliminated: absorbed into Manim animation voiceover | 12D, 13A–13B |
| 11 | Manim animation: separate Docker container (`manim_worker`), dedicated `manim_queue`, CPU Cairo | 13A–13B |
| 12 | StudyPlanCourse: one row per subtopic with `activity_type='ai_content'`, media linked via GeneratedContent | 12E |
| 13 | Content reuse via profile fingerprinting: identical fingerprint → reuse S3 asset | 14A–14B |
| 14 | API layer: content delivery endpoints with presigned S3 URLs | 15 |
| 15 | Frontend: Phase 8 + Phase 9 folded into Phase 16 (full diagnostic + multi-modal) | 16 |

---

## Implementation Status

| Phase | Name | Status |
|---|---|---|
| Phase 0 | Docker Environment Setup | ✅ DONE |
| Phase 1 | Redis + Celery Application Setup | ✅ DONE |
| Phase 2 | Difficulty Scale Migration | ✅ DONE |
| Phase 3 | Adaptive Diagnostic Session Engine | ✅ DONE |
| Phase 4 | Response Collection Engine | ✅ DONE |
| Phase 5 | Scoring Engine & Report Generation | ✅ DONE |
| Phase 6 | Study Plan Generation v1 — **DEPRECATED by Phase 12B** | ✅ DONE (deprecated) |
| Phase 7 | REST API Layer | ✅ DONE |
| Phase 8 | React Frontend | 🔁 FOLDED INTO PHASE 16 |
| Phase 9 | Testing & Quality | 🔁 FOLDED INTO PHASE 16 |
| Phase 10A | RAG — pgvector Extension + Schema | 🆕 NEW |
| Phase 10B | RAG — PDF Extraction + DB Ingestion Pipeline | 🆕 NEW |
| Phase 10C | RAG — Embedding Ingestion (Celery Task) | 🆕 NEW |
| Phase 10D | RAG — Query Service | 🆕 NEW |
| Phase 11A | S3 — Infrastructure + S3Client (MinIO dev / AWS prod) | 🆕 NEW |
| Phase 11B | S3 — GeneratedContent Model + ContentMetadataService | 🆕 NEW |
| Phase 11C | S3 — Deterministic Key Generator + Prompt Hash | 🆕 NEW |
| Phase 12A | StudyPlan Migration — subject_id + profile_fingerprint + data purge | 🆕 NEW |
| Phase 12B | Deprecate Old Task + Trigger Redesign (per-subject chain) | 🆕 NEW |
| Phase 12C | New Study Plan Task — RAG Prompt Injection | 🆕 NEW |
| Phase 12D | New Study Plan Task — Multi-Modal LLM Output Schema + Validation | 🆕 NEW |
| Phase 12E | New Study Plan Task — DB Write + S3 + Dispatch Media Workers | 🆕 NEW |
| Phase 13A | Manim Worker — Docker Container + Queue + celery_app wiring | 🆕 NEW |
| Phase 13B | Manim Worker — Animation + Voiceover Celery Task | 🆕 NEW |
| Phase 13C | Media Worker — Practice Questions Task | 🆕 NEW |
| Phase 13D | Media Worker — Infographic Task (Gemini Imagen 3) | 🆕 NEW |
| Phase 14A | Content Reuse — Profile Fingerprint Service | 🆕 NEW |
| Phase 14B | Content Reuse — Pre-Generation Lookup + Dispatch | 🆕 NEW |
| Phase 15 | API Layer — Content Delivery Endpoints | 🆕 NEW |
| Phase 16 | Frontend — Full Diagnostic Flow + Multi-Modal Study Plan View + Tests | 🆕 NEW |

---

## AGENTS.md — Required Update Before Phase 12B

**Apply this change to `AGENTS.md` Section 3.4 before starting Phase 12B.**

Section 3.4 currently mandates Redis caching for ALL LLM calls.
The following amendment overrides that rule for specific tasks only.

### Amendment: Section 3.4.1 — S3-Backed Content Cache

The Redis LLM cache rule in Section 3.4 applies to ALL LLM calls **except** the following
tasks, which use S3 as their permanent content store instead of Redis:

| Task Name | Reason |
|---|---|
| `tasks.generate_enriched_study_plan` | Outputs multi-modal content spec stored permanently in S3 |
| `tasks.generate_animation_manim` | LLM generates Manim code; MP4 stored in S3 |
| `tasks.generate_infographic` | LLM constructs image prompt; PNG stored in S3 |

**The S3-backed cache protocol for these tasks (replaces Redis check):**

1. Build `prompt_hash` = SHA-256 of canonical prompt inputs (see Phase 11C for exact inputs).
2. Query `generated_content` table: does a row exist WHERE `prompt_hash = :hash`
   AND `content_type = :type` AND `status = 'completed'`?
3. If yes → return existing `s3_key`. Do NOT call LLM or any media API. Do NOT upload anything.
4. If no → call LLM, generate content, upload to S3, create `GeneratedContent` row with status = `'completed'`.

**All other LLM calls** (report generation, question-related tasks) continue to use
Redis caching per the existing Section 3.4 rules unchanged.

---

## Architecture Overview (v3.1)

```
Student answers final question for Subject X (e.g. Math)
        │
        ▼
response_handler.check_single_subject_complete(assessment_id, subject_id)
        │
        ▼ (fires immediately — does NOT wait for other subjects)
Celery chain per subject:
  generate_assessment_report.s(assessment_id)
  | generate_enriched_study_plan.s(assessment_id, subject_id)
        │
        ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  generate_enriched_study_plan  (Celery — default queue)                  │
│                                                                           │
│  1. Load AssessmentReport.knowledge_gaps for this subject                │
│  2. Load StudentProfile (grade_id, curriculum_id, learning_profile JSONB)│
│  3. Build profile_fingerprint for this subject (Phase 14A)               │
│  4. For each gap subtopic → RAGQueryService.retrieve_for_subtopic()      │
│  5. Build enriched multi-modal LLM prompt                                │
│  6. Call Gemini 2.5 Pro → Multi-Modal Content Spec JSON                  │
│  7. Validate JSON                                                         │
│  8. Upload raw spec JSON to S3                                            │
│  9. Write StudyPlan (subject-specific) + StudyPlanCourse rows to DB      │
│     (one StudyPlanCourse per subtopic, activity_type='ai_content')       │
│  10. Create GeneratedContent PENDING rows per subtopic × content type    │
│  11. Call reuse_or_dispatch for each content item (Phase 14B)            │
└──────────────────────────────────────────────────────────────────────────┘
        │
        ▼ (fanout — one task per subtopic per content type)
┌───────────────────────────────────┬────────────────────────────────────────┐
│ manim_queue                       │ default queue                          │
│ (manim_worker container)          │ (celery_worker container)              │
│                                   │                                        │
│ tasks.generate_animation_manim    │ tasks.generate_practice_questions      │
│  Stage 1: Scene Planner LLM call  │  Extract questions from spec JSON in S3│
│  Stage 2: Code Generator LLM call │  Validate + upload JSON to S3          │
│  Stage 3: Execute + Fix loop      │                                        │
│           (max 5 attempts)        │ tasks.generate_infographic             │
│  Stage 4: Gemini TTS voiceover    │  Build image prompt from spec          │
│  Stage 5: manim-voiceover render  │  Call Gemini Imagen 3 API              │
│  Stage 6: Upload MP4 to S3        │  Upload PNG to S3                      │
└──────────────┬────────────────────┴────────────────────────────────────────┘
               │
               ▼
  GeneratedContent rows updated: status = 'completed', s3_key set
               │
               ▼
  FastAPI GET /diagnostic/{student_id}/study-plan/content
  → generate presigned S3 URLs → React frontend renders media
```

---

## Global Standards (Non-Negotiable — Inherited from AGENTS.md)

- Difficulty values: Integer 1–5 only. No floats. No strings.
- LLM calls: Celery workers only. Never from FastAPI layer.
- Queue routing: explicit. Every task must declare its queue.
- Redis keys: follow `kaihle:{domain}:{key}:{id}` format with explicit TTL.
- Test coverage: ≥ 90% for all new code before phase closes.
- Git: one branch per phase, conventional commits, push before closing.

---

## Existing Models — Reference (Do Not Recreate)

### StudyPlan (current — pre-Phase 12A)

```python
# app/models/study_plan.py
class StudyPlan(Base, SerializerMixin):
    __tablename__ = "study_plans"
    id                  = Column(UUID, primary_key=True, default=uuid.uuid4)
    student_id          = Column(UUID, ForeignKey("student_profiles.id"), nullable=False)
    assessment_id       = Column(UUID, ForeignKey("assessments.id"), nullable=True)
    title               = Column(String(255), default="Personalized Study Plan")
    description         = Column(Text, nullable=True)
    summary             = Column(Text, nullable=True)
    total_weeks         = Column(Integer, nullable=True)
    hours_per_week      = Column(Integer, nullable=True)
    generation_metadata = Column(JSONB, nullable=True)
    status              = Column(String(20), default="active")
    progress_percentage = Column(Integer, default=0)
    is_active           = Column(Boolean, default=True)
    created_at          = Column(DateTime(timezone=True), server_default=func.now())
    updated_at          = Column(DateTime(timezone=True), onupdate=func.now())
    started_at          = Column(DateTime(timezone=True), nullable=True)
    completed_at        = Column(DateTime(timezone=True), nullable=True)
```

**After Phase 12A migration**, the model gains two new columns:
- `subject_id` — FK to `subjects.id`, nullable=False (set during migration)
- `profile_fingerprint` — VARCHAR(64), nullable=True, indexed

### StudyPlanCourse (current — no structural changes required)

```python
class StudyPlanCourse(Base, SerializerMixin):
    __tablename__ = "study_plan_courses"
    id                    = Column(UUID, primary_key=True, default=uuid.uuid4)
    study_plan_id         = Column(UUID, ForeignKey("study_plans.id"), nullable=False)
    course_id             = Column(UUID, ForeignKey("courses.id"), nullable=True)
    title                 = Column(String(255), nullable=False)
    description           = Column(Text, nullable=True)
    topic_id              = Column(UUID, ForeignKey("topics.id"), nullable=True)
    subtopic_id           = Column(UUID, ForeignKey("subtopics.id"), nullable=True)
    week                  = Column(Integer, nullable=True)
    day                   = Column(Integer, nullable=True)
    sequence_order        = Column(Integer, nullable=False)
    suggested_duration_mins = Column(Integer, nullable=True)
    activity_type         = Column(String(50), nullable=True)
    custom_content        = Column(JSONB, nullable=True)
    status                = Column(String(20), default="not_started")
    completed_at          = Column(DateTime(timezone=True), nullable=True)
    time_spent_minutes    = Column(Integer, default=0)
    created_at            = Column(DateTime(timezone=True), server_default=func.now())
    updated_at            = Column(DateTime(timezone=True), onupdate=func.now())
```

**`activity_type` valid values (full list):**
`"lesson"` | `"practice"` | `"review"` | `"assessment"` | `"ai_content"`

AI-generated subtopic rows always use `activity_type = "ai_content"`.

**`custom_content` JSONB schema for `activity_type = "ai_content"` rows:**
```json
{
  "subtopic_id": "uuid-string",
  "subtopic_name": "Linear Equations",
  "subject": "Math",
  "priority": "high",
  "mastery_level": 0.28,
  "animation_spec": {
    "title": "Understanding Linear Equations",
    "duration_seconds": 180,
    "scenes": [
      {
        "scene_index": 1,
        "title": "What is a Linear Equation?",
        "narration": "Full narration text for this scene...",
        "visual_elements": ["number line", "equation y=2x+1", "balance scale"],
        "duration_seconds": 45
      }
    ],
    "learning_objective": "Student can identify and solve a one-variable linear equation"
  },
  "infographic_spec": {
    "title": "Linear Equations at a Glance",
    "layout": "vertical",
    "sections": [
      {"heading": "What is a Linear Equation?", "body": "..."},
      {"heading": "Solving Steps", "body": "Step 1:... Step 2:..."},
      {"heading": "Common Mistakes", "body": "..."}
    ],
    "visual_style": "clean, Cambridge blue and white, Grade 8"
  },
  "practice_questions": [
    {
      "question_number": 1,
      "difficulty": 2,
      "question_text": "Solve for x: 3x + 5 = 14",
      "options": ["x = 1", "x = 2", "x = 3", "x = 4"],
      "correct_answer": "x = 3",
      "explanation": "Subtract 5 from both sides: 3x = 9. Divide by 3: x = 3.",
      "topic_tested": "Solving one-step linear equations"
    }
  ],
  "spec_s3_key": "specs/grade8/math/uuid-subtopic/prompt_hash.json"
}
```

Note: `difficulty` in `practice_questions` is **Integer 1–5**. This is enforced during
validation in Phase 12D. Any other value must cause the question to be rejected.

**`status` valid values for StudyPlan (full list):**
`"generating"` | `"active"` | `"generation_failed"` | `"completed"` | `"paused"` | `"archived"`

**`status` valid values for StudyPlanCourse (unchanged):**
`"not_started"` | `"in_progress"` | `"completed"` | `"skipped"`

---

## New Environment Variables (Add to `.env.example` progressively per phase)

```env
# ── Phase 10A ──────────────────────────────────────────────
EMBEDDING_PROVIDER=gemini          # gemini | openai
GEMINI_API_KEY=your_gemini_key
GEMINI_EMBEDDING_MODEL=text-embedding-004
EMBEDDING_DIMENSIONS=768           # 768 for Gemini text-embedding-004
RAG_TOP_K=5                        # max chunks returned per subtopic query
RAG_MIN_SIMILARITY=0.72            # cosine similarity threshold (0.0–1.0)
RAG_CHUNK_SIZE_TOKENS=400          # target tokens per content chunk
RAG_CHUNK_OVERLAP_TOKENS=50        # overlap between adjacent chunks

# ── Phase 10B ──────────────────────────────────────────────
PDF_STORAGE_PATH=/app/data/textbooks   # bind-mounted volume for PDF files

# ── Phase 11A ──────────────────────────────────────────────
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=us-east-1
S3_BUCKET_NAME=kaihle-generated-content
S3_PRESIGNED_URL_TTL_SECONDS=3600
USE_MINIO=true                     # true = dev (MinIO), false = prod (AWS S3)
MINIO_ENDPOINT=http://minio:9000

# ── Phase 12B ──────────────────────────────────────────────
GEMINI_LLM_MODEL=gemini-2.5-pro
GEMINI_FLASH_MODEL=gemini-2.5-flash   # used for code generation stage in Manim task
GEMINI_IMAGE_MODEL=imagen-3.0-generate-002

# Study plan generation config
STUDY_PLAN_MAX_WEEKS=16
STUDY_PLAN_MIN_WEEKS=4
ANIMATION_MAX_DURATION_SECONDS=180    # cap: 3 minutes per subtopic animation
ANIMATION_MAX_SCENES=6
PRACTICE_QUESTIONS_PER_SUBTOPIC=10
MANIM_QUALITY_FLAG=-qm               # -ql (low), -qm (medium), -qh (high)
MANIM_MAX_FIX_ATTEMPTS=5             # max stderr-feedback retry loops

# Gemini TTS for voiceover
GEMINI_TTS_VOICE=Kore                # Gemini TTS voice name
```

---

## New Files Map (v3.1 — new files only)

```
backend/
├── Dockerfile.manim                                    NEW (13A)
├── requirements.manim.txt                              NEW (13A)
├── data/
│   └── textbooks/                                      NEW (10B) — bind-mounted volume
├── scripts/
│   ├── extract_pdf_content.py                          NEW (10B)
│   └── purge_old_study_plans.py                        NEW (12A)
└── app/
    ├── models/
    │   ├── rag.py                                      NEW (10A)
    │   └── generated_content.py                        NEW (11B)
    ├── services/
    │   ├── rag/
    │   │   ├── __init__.py                             NEW (10A)
    │   │   ├── embedding_service.py                    NEW (10C)
    │   │   └── query_service.py                        NEW (10D)
    │   └── storage/
    │       ├── __init__.py                             NEW (11A)
    │       ├── s3_client.py                            NEW (11A)
    │       ├── content_metadata_service.py             NEW (11B)
    │       ├── key_generator.py                        NEW (11C)
    │       ├── profile_fingerprint.py                  NEW (14A)
    │       └── content_reuse_service.py                NEW (14B)
    └── worker/
        ├── celery_app.py                               MODIFIED (13A, 12B)
        └── tasks/
            ├── study_plan.py                           MODIFIED — deprecated task kept, not called
            ├── enriched_study_plan.py                  NEW (12B–12E)
            ├── rag_ingestion.py                        NEW (10C)
            └── media_generation/
                ├── __init__.py                         NEW (13A)
                ├── animation.py                        NEW (13B)
                ├── practice_questions.py               NEW (13C)
                └── infographic.py                      NEW (13D)

alembic/versions/
    ├── xxx_add_rag_tables.py                           NEW (10A)
    ├── xxx_add_generated_content.py                    NEW (11B)
    └── xxx_add_study_plan_subject_fingerprint.py       NEW (12A)

docker-compose.yml                                      MODIFIED (11A — MinIO, 13A — manim_worker)

frontend/src/
    ├── pages/diagnostic/
    │   ├── DiagnosticHub.jsx                           NEW (16)
    │   ├── DiagnosticSession.jsx                       NEW (16)
    │   ├── DiagnosticReport.jsx                        NEW (16)
    │   └── StudyPlanView.jsx                           NEW (16)
    ├── components/diagnostic/
    │   ├── SubjectCard.jsx                             NEW (16)
    │   ├── QuestionCard.jsx                            NEW (16)
    │   ├── OptionButton.jsx                            NEW (16)
    │   ├── DifficultyIndicator.jsx                     NEW (16)
    │   ├── MasteryRing.jsx                             NEW (16)
    │   ├── TopicBreakdownTable.jsx                     NEW (16)
    │   ├── KnowledgeGapBadge.jsx                       NEW (16)
    │   ├── WeekAccordion.jsx                           NEW (16)
    │   ├── CourseItem.jsx                              NEW (16)
    │   └── content/
    │       ├── SubtopicContentCard.jsx                 NEW (16)
    │       ├── AnimationPlayer.jsx                     NEW (16)
    │       ├── InfographicViewer.jsx                   NEW (16)
    │       ├── PracticeQuestionsPanel.jsx              NEW (16)
    │       ├── ContentStatusBadge.jsx                  NEW (16)
    │       └── ContentGenerationBanner.jsx             NEW (16)
    └── hooks/diagnostic/
        ├── useDiagnosticStatus.js                      NEW (16)
        ├── useNextQuestion.js                          NEW (16)
        ├── useSubmitAnswer.js                          NEW (16)
        ├── useDiagnosticReport.js                      NEW (16)
        ├── useStudyPlan.js                             NEW (16)
        └── useStudyPlanContent.js                      NEW (16)
```

---

## Database Changes Summary (v3.1)

| Change | Type | Phase |
|---|---|---|
| `CREATE EXTENSION IF NOT EXISTS vector` | Migration | 10A |
| `curriculum_content` table created | New table | 10A |
| `curriculum_embeddings` table + IVFFlat index | New table + index | 10A |
| `generated_content` table created | New table | 11B |
| `study_plans.subject_id` FK column added | Migration | 12A |
| `study_plans.profile_fingerprint` VARCHAR(64) + index added | Migration | 12A |
| Old StudyPlan rows deleted via script | Data purge script | 12A |

---

# PHASE DETAILS

---

## Phase 10A — RAG: pgvector Extension + Curriculum Content Schema

**Goal:** Install the pgvector extension and create the two tables that form the RAG
knowledge store: `curriculum_content` (raw text chunks) and `curriculum_embeddings`
(their vector representations). No ingestion logic yet — schema and infrastructure only.

**Branch:** `feature/phase-10a-rag-schema`

### 10A.1 Docker Image Change

In `docker-compose.yml`, `docker-compose.prod.yml`, and `docker-compose.test.yml`,
replace the db service image:

```yaml
# BEFORE
db:
  image: postgres:16-alpine

# AFTER
db:
  image: pgvector/pgvector:pg16
```

`pgvector/pgvector:pg16` is the official pgvector-enabled PostgreSQL image.
It includes the `vector` extension pre-installed. No other changes to the db service.

### 10A.2 New Python Dependency

Add to `backend/requirements.txt`:
```
pgvector==0.3.6
```

### 10A.3 New SQLAlchemy Models

**Create: `app/models/rag.py`**

```python
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Text, ForeignKey, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector
from app.core.database import Base


class CurriculumContent(Base):
    """
    Raw educational text chunks extracted from Cambridge textbook PDFs.
    One row per chunk. A single subtopic may have multiple chunks.
    Populated by Phase 10B extraction pipeline.
    """
    __tablename__ = "curriculum_content"

    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subtopic_id    = Column(UUID(as_uuid=True), ForeignKey("subtopics.id", ondelete="CASCADE"),
                            nullable=False)
    topic_id       = Column(UUID(as_uuid=True), ForeignKey("topics.id", ondelete="CASCADE"),
                            nullable=False)
    subject_id     = Column(UUID(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"),
                            nullable=False)
    grade_id       = Column(UUID(as_uuid=True), ForeignKey("grades.id", ondelete="CASCADE"),
                            nullable=False)
    chunk_index    = Column(Integer, nullable=False, default=0)
    # Human-readable, e.g. "cambridge_grade8_math_textbook_chapter3"
    content_source = Column(String(255), nullable=False)
    content_text   = Column(Text, nullable=False)
    token_count    = Column(Integer, nullable=True)   # estimated token count of this chunk
    created_at     = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_cc_subtopic_id", "subtopic_id"),
        Index("idx_cc_subject_grade", "subject_id", "grade_id"),
    )


class CurriculumEmbedding(Base):
    """
    pgvector embeddings for each CurriculumContent chunk.
    One row per CurriculumContent row — linked by content_id.
    Populated by Phase 10C ingestion task.
    """
    __tablename__ = "curriculum_embeddings"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content_id   = Column(UUID(as_uuid=True),
                          ForeignKey("curriculum_content.id", ondelete="CASCADE"),
                          nullable=False, unique=True)
    subtopic_id  = Column(UUID(as_uuid=True), ForeignKey("subtopics.id"), nullable=False)
    # Dimension must match EMBEDDING_DIMENSIONS env var.
    # Using Gemini text-embedding-004: 768 dimensions.
    # NEVER change this dimension after data is loaded — requires full re-migration.
    embedding    = Column(Vector(768), nullable=False)
    model_name   = Column(String(100), nullable=False)   # e.g. "text-embedding-004"
    created_at   = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_ce_subtopic_id", "subtopic_id"),
        # IVFFlat index created separately in migration (see below)
    )
```

### 10A.4 Alembic Migration

**Create: `alembic/versions/xxx_add_rag_tables.py`**

```python
"""Add pgvector extension and RAG curriculum tables

Revision ID: (auto-generated)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

def upgrade():
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # curriculum_content table
    op.create_table(
        "curriculum_content",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("subtopic_id", UUID(as_uuid=True),
                  sa.ForeignKey("subtopics.id", ondelete="CASCADE"), nullable=False),
        sa.Column("topic_id", UUID(as_uuid=True),
                  sa.ForeignKey("topics.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subject_id", UUID(as_uuid=True),
                  sa.ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("grade_id", UUID(as_uuid=True),
                  sa.ForeignKey("grades.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("content_source", sa.String(255), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_cc_subtopic_id", "curriculum_content", ["subtopic_id"])
    op.create_index("idx_cc_subject_grade", "curriculum_content", ["subject_id", "grade_id"])

    # curriculum_embeddings table
    op.create_table(
        "curriculum_embeddings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("content_id", UUID(as_uuid=True),
                  sa.ForeignKey("curriculum_content.id", ondelete="CASCADE"),
                  nullable=False, unique=True),
        sa.Column("subtopic_id", UUID(as_uuid=True),
                  sa.ForeignKey("subtopics.id"), nullable=False),
        sa.Column("embedding", sa.Text(), nullable=False),   # placeholder; overridden by pgvector
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.execute("ALTER TABLE curriculum_embeddings ALTER COLUMN embedding TYPE vector(768)")
    op.create_index("idx_ce_subtopic_id", "curriculum_embeddings", ["subtopic_id"])

    # IVFFlat index for approximate nearest neighbour search
    # lists=100 is appropriate for up to ~1M rows; tune upward at scale
    op.execute("""
        CREATE INDEX idx_ce_embedding_ivfflat
        ON curriculum_embeddings
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """)


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_ce_embedding_ivfflat")
    op.drop_table("curriculum_embeddings")
    op.drop_table("curriculum_content")
    op.execute("DROP EXTENSION IF EXISTS vector")
```

### Phase 10A Acceptance Criteria

- [ ] `docker-compose.yml`, `docker-compose.prod.yml`, `docker-compose.test.yml` all use `pgvector/pgvector:pg16` image
- [ ] `make migrate` runs the migration without error
- [ ] `CREATE EXTENSION IF NOT EXISTS vector` is idempotent (re-running migration does not fail)
- [ ] `curriculum_content` table exists with all columns and FK constraints
- [ ] `curriculum_embeddings` table exists; `embedding` column is type `vector(768)`
- [ ] IVFFlat index `idx_ce_embedding_ivfflat` created (verify: `\d curriculum_embeddings` in psql)
- [ ] `downgrade()` cleanly removes all tables and the extension
- [ ] `pgvector==0.3.6` in `requirements.txt`

---

## Phase 10B — RAG: PDF Extraction + DB Ingestion Pipeline

**Goal:** Build the admin CLI script that reads Cambridge textbook PDF files,
extracts text, chunks it, and inserts `CurriculumContent` rows into the DB.
No embeddings generated here — that is Phase 10C.

**Branch:** `feature/phase-10b-rag-pdf-extraction`

### 10B.1 New Python Dependencies

Add to `backend/requirements.txt`:
```
pymupdf==1.24.14        # PDF extraction (fitz)
tiktoken==0.8.0         # token counting for chunk size estimation
```

### 10B.2 PDF Storage Volume

Add to `docker-compose.yml` and `docker-compose.prod.yml`:

```yaml
# In celery_worker and api services — add volume mount:
volumes:
  - ./backend:/app
  - ./data/textbooks:/app/data/textbooks   # ADD THIS LINE

# In volumes section at bottom:
volumes:
  postgres_data:
  redis_data:
  minio_data:          # added in Phase 11A
  textbook_data:       # ADD THIS
```

Create directory: `backend/data/textbooks/.gitkeep`
Add to `backend/.dockerignore`: `data/textbooks/*.pdf`

**Admin workflow:**
```bash
# Admin places PDF files in: backend/data/textbooks/
# File naming convention (REQUIRED — script parses this):
# {grade_code}_{subject_code}_{content_type}.pdf
# Examples:
#   grade8_math_textbook.pdf
#   grade8_math_workbook.pdf
#   grade10_science_textbook.pdf
# Valid grade_codes:  grade5 grade6 grade7 grade8 grade9 grade10 grade11 grade12
# Valid subject_codes: math science english humanities
```

### 10B.3 Extraction Script

**Create: `backend/scripts/extract_pdf_content.py`**

```python
"""
PDF Content Extraction Pipeline

Usage:
    docker-compose exec api python scripts/extract_pdf_content.py \
        --file grade8_math_textbook.pdf \
        --dry-run

    docker-compose exec api python scripts/extract_pdf_content.py \
        --file grade8_math_textbook.pdf

    docker-compose exec api python scripts/extract_pdf_content.py \
        --all   # processes all PDFs in /app/data/textbooks/

Arguments:
    --file      Single PDF filename (must be in /app/data/textbooks/)
    --all       Process all PDF files in /app/data/textbooks/
    --dry-run   Print extracted chunks without writing to DB
    --force     Re-process already-ingested files (default: skip if content_source exists)

Exit codes:
    0 = success
    1 = file not found
    2 = PDF parse error
    3 = subtopic mapping error (no matching subtopic found)

Chunking strategy:
    1. Extract full text per page using PyMuPDF (fitz.open)
    2. Split text into paragraphs on double newline
    3. Group paragraphs into chunks targeting RAG_CHUNK_SIZE_TOKENS tokens
       with RAG_CHUNK_OVERLAP_TOKENS overlap between adjacent chunks
    4. Skip chunks with fewer than 50 tokens (noise/headers)
    5. Attempt subtopic mapping: match chunk text against subtopic names
       using fuzzy keyword match (no LLM call — purely string matching)
    6. Insert CurriculumContent rows; print summary

Output per run:
    Processed: grade8_math_textbook.pdf
    Pages read: 312
    Chunks extracted: 847
    Chunks inserted: 823 (24 skipped — below min token threshold)
    Subtopics mapped: 18/20
    Unmapped chunks written with subtopic_id=NULL (review manually)

NOTE: Chunks with subtopic_id=NULL are inserted but will be EXCLUDED
from embedding ingestion and RAG queries until manually mapped.
A summary of unmapped chunks is printed at script end.
"""

PDF_DIR = "/app/data/textbooks"
MIN_CHUNK_TOKENS = 50

def extract_and_ingest(filename: str, dry_run: bool = False, force: bool = False):
    """Main entry point per file."""
    ...

def extract_pages(pdf_path: str) -> list[str]:
    """Uses fitz.open to extract text per page. Returns list of page strings."""
    ...

def chunk_text(
    pages: list[str],
    chunk_size_tokens: int,
    overlap_tokens: int,
) -> list[str]:
    """
    Groups paragraphs into chunks.
    Uses tiktoken cl100k_base encoder for token counting.
    Respects chunk_size_tokens target with overlap_tokens sliding window.
    """
    ...

def map_subtopic(
    chunk_text: str,
    grade_id: UUID,
    subject_id: UUID,
    subtopics: list[Subtopic],
) -> UUID | None:
    """
    Attempts to match chunk to a subtopic by keyword overlap.
    Returns subtopic_id or None if no confident match (confidence < 0.4).
    Does NOT call any LLM.
    """
    ...

def parse_filename(filename: str) -> tuple[str, str, str]:
    """
    Parses '{grade_code}_{subject_code}_{content_type}.pdf'.
    Returns (grade_code, subject_code, content_type).
    Raises ValueError on invalid format.
    """
    ...
```

### 10B.4 Makefile Targets

Add to `Makefile`:

```makefile
extract-pdf:
    docker-compose exec api python scripts/extract_pdf_content.py --file $(file)

extract-pdf-all:
    docker-compose exec api python scripts/extract_pdf_content.py --all

extract-pdf-dry:
    docker-compose exec api python scripts/extract_pdf_content.py --file $(file) --dry-run
```

### Phase 10B Acceptance Criteria

- [ ] `make extract-pdf file=grade8_math_textbook.pdf` runs without error on a test PDF
- [ ] `--dry-run` prints chunks but writes zero DB rows
- [ ] `--force` flag re-processes a file that was already ingested (replaces existing rows)
- [ ] Without `--force`, re-running on an already-ingested file skips it (idempotent)
- [ ] Chunks below `MIN_CHUNK_TOKENS=50` are skipped and counted in summary
- [ ] Unmapped chunks (subtopic_id=NULL) are inserted and listed in summary
- [ ] `parse_filename` raises `ValueError` for filenames not matching convention
- [ ] `make extract-pdf-all` processes all PDF files in directory sequentially
- [ ] `CurriculumContent` rows have correct `subject_id`, `grade_id`, `chunk_index`, `content_source`

---

## Phase 10C — RAG: Embedding Ingestion (Celery Task)

**Goal:** Build the `EmbeddingService` and the Celery task that reads `CurriculumContent`
rows (where `subtopic_id IS NOT NULL`) and generates + stores their vector embeddings in
`CurriculumEmbedding`. Called by admin via Makefile after Phase 10B ingestion.

**Branch:** `feature/phase-10c-rag-embedding-ingestion`

### 10C.1 New Python Dependency

Add to `backend/requirements.txt`:
```
google-generativeai==0.8.4    # Gemini SDK (also used for LLM in Phase 12C)
```

### 10C.2 Embedding Service

**Create: `app/services/rag/embedding_service.py`**

```python
"""
EmbeddingService — wraps the configured embedding API.
Provider is determined by EMBEDDING_PROVIDER env var.
Supported values: "gemini" | "openai"

Current default: "gemini" using text-embedding-004 (768 dimensions).

IMPORTANT: The embedding dimension (768) is hardcoded into the
curriculum_embeddings table schema (Phase 10A). Changing the model
to one with a different dimension requires a full DB migration and
re-ingestion of all content. Never change EMBEDDING_PROVIDER or
GEMINI_EMBEDDING_MODEL without a coordinated migration plan.

Called ONLY from Celery worker tasks. Never from the API layer.
"""
import google.generativeai as genai
from app.core.config import settings


class EmbeddingService:

    def __init__(self):
        if settings.EMBEDDING_PROVIDER == "gemini":
            genai.configure(api_key=settings.GEMINI_API_KEY)
            self.model_name = settings.GEMINI_EMBEDDING_MODEL  # "text-embedding-004"
        else:
            raise ValueError(f"Unsupported EMBEDDING_PROVIDER: {settings.EMBEDDING_PROVIDER}")

    def embed_text(self, text: str) -> list[float]:
        """
        Embeds a single text string.
        Returns a list of floats (length = EMBEDDING_DIMENSIONS = 768).
        Raises on API failure — let Celery handle retry.
        Truncates input to 2048 tokens if necessary (Gemini model limit).
        """
        result = genai.embed_content(
            model=f"models/{self.model_name}",
            content=text,
            task_type="retrieval_document",
        )
        return result["embedding"]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Embeds a list of texts.
        Gemini text-embedding-004 supports up to 100 texts per batch call.
        If len(texts) > 100, splits into batches of 100 and concatenates results.
        Returns list of embedding vectors in same order as input texts.
        """
        ...
```

### 10C.3 Embedding Ingestion Task

**Create: `app/worker/tasks/rag_ingestion.py`**

```python
"""
Celery tasks for RAG embedding ingestion.
These tasks are run by the admin via Makefile, not triggered by student actions.
Queue: default (no dedicated queue needed — low frequency admin operation).
"""
from app.worker.celery_app import celery_app
from app.services.rag.embedding_service import EmbeddingService
from app.models.rag import CurriculumContent, CurriculumEmbedding
from app.core.database import SessionLocal
import logging

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    max_retries=3,
    name="tasks.ingest_curriculum_embeddings",
    rate_limit="30/m",    # respect Gemini embedding API rate limits
)
def ingest_curriculum_embeddings(
    self,
    content_ids: list[str] | None = None,
) -> dict:
    """
    Generates and stores vector embeddings for CurriculumContent rows.

    Arguments:
        content_ids: list of CurriculumContent UUID strings to process.
                     If None, processes ALL rows WHERE subtopic_id IS NOT NULL
                     AND no matching CurriculumEmbedding row exists.

    Pipeline:
        1. Load CurriculumContent rows matching criteria (exclude NULL subtopic_id)
        2. Exclude rows that already have a CurriculumEmbedding (idempotent)
        3. Batch embed via EmbeddingService.embed_batch() in groups of 100
        4. Insert CurriculumEmbedding rows
        5. Log summary

    Returns:
        {
          "processed": N,   # rows successfully embedded
          "skipped": M,     # rows already had embeddings
          "failed": K,      # rows that failed after retries
          "unmapped": J     # rows skipped because subtopic_id is NULL
        }

    On API failure: Celery retries up to max_retries times with exponential backoff.
    """
    ...


@celery_app.task(
    bind=True,
    max_retries=3,
    name="tasks.ingest_single_embedding",
)
def ingest_single_embedding(self, content_id: str) -> None:
    """
    Embeds and stores a single CurriculumContent row.
    Called after manual insertion of a single content row.
    Skips if embedding already exists for this content_id.
    """
    ...
```

### 10C.4 Makefile Targets

Add to `Makefile`:

```makefile
ingest-embeddings:
    docker-compose exec celery_worker celery -A app.worker.celery_app call \
        tasks.ingest_curriculum_embeddings

ingest-embeddings-check:
    docker-compose exec api python -c \
        "from app.core.database import SessionLocal; \
         from app.models.rag import CurriculumContent, CurriculumEmbedding; \
         db = SessionLocal(); \
         total = db.query(CurriculumContent).count(); \
         embedded = db.query(CurriculumEmbedding).count(); \
         print(f'Content rows: {total}, Embedded: {embedded}, Pending: {total-embedded}')"
```

### Phase 10C Acceptance Criteria

- [ ] `ingest_curriculum_embeddings` with `content_ids=None` embeds all un-embedded rows where `subtopic_id IS NOT NULL`
- [ ] Re-running is idempotent: rows with existing embeddings are skipped, not duplicated
- [ ] Rows with `subtopic_id=NULL` are counted in `"unmapped"` result and skipped
- [ ] Batch size of 100 is respected — no single API call exceeds 100 texts
- [ ] Rate limit `30/m` prevents API quota breach
- [ ] `ingest_single_embedding` skips if embedding already exists for that `content_id`
- [ ] `make ingest-embeddings-check` correctly reports pending vs embedded count
- [ ] Returned dict contains all four keys: `processed`, `skipped`, `failed`, `unmapped`
- [ ] Task retries on Gemini API error with exponential backoff

---

## Phase 10D — RAG: Query Service

**Goal:** Build the service that the study plan task calls during prompt construction.
Takes a subtopic_id and a query string, returns the top-K most relevant text chunks
via cosine similarity search against `curriculum_embeddings`.

**Branch:** `feature/phase-10d-rag-query-service`

### 10D.1 ContentChunk Dataclass

**Create: `app/services/rag/query_service.py`**

```python
"""
RAGQueryService — retrieves relevant curriculum content for a given subtopic
using pgvector cosine similarity search.

Called ONLY from Celery worker tasks. Never from the FastAPI layer.

Graceful degradation contract:
  If no content chunks are found for a subtopic, return an empty list.
  Do NOT raise an exception. The caller (study plan task) handles
  the missing context by omitting that subtopic's content section from
  the LLM prompt. This is NOT a failure condition.
"""
from dataclasses import dataclass
from uuid import UUID
import logging

logger = logging.getLogger(__name__)


@dataclass
class ContentChunk:
    content_id: UUID
    subtopic_id: UUID
    content_text: str
    content_source: str
    similarity_score: float    # cosine similarity, range 0.0–1.0
    chunk_index: int


class RAGQueryService:

    def __init__(self, db_session, embedding_service):
        """
        db_session: synchronous SQLAlchemy session (used inside Celery tasks)
        embedding_service: EmbeddingService instance
        """
        self.db = db_session
        self.embedding_service = embedding_service
        self.top_k = int(settings.RAG_TOP_K)                  # default: 5
        self.min_similarity = float(settings.RAG_MIN_SIMILARITY)  # default: 0.72

    def retrieve_for_subtopic(
        self,
        subtopic_id: UUID,
        query_text: str,
    ) -> list[ContentChunk]:
        """
        1. Embed query_text via EmbeddingService.embed_text()
        2. Execute cosine similarity query (see SQL below)
        3. Filter results below min_similarity threshold
        4. Return list[ContentChunk] sorted by similarity descending
        5. If zero results: log WARNING and return []

        Args:
            subtopic_id: UUID of the subtopic to search within
            query_text:  Natural language description of what to find.
                         Typically: "{subtopic_name} — {grade} level explanation"
        """
        query_vector = self.embedding_service.embed_text(query_text)
        results = self.db.execute(
            """
            SELECT
                ce.content_id,
                ce.subtopic_id,
                cc.content_text,
                cc.content_source,
                cc.chunk_index,
                1 - (ce.embedding <=> :query_vector::vector) AS similarity
            FROM curriculum_embeddings ce
            JOIN curriculum_content cc ON cc.id = ce.content_id
            WHERE ce.subtopic_id = :subtopic_id
            ORDER BY ce.embedding <=> :query_vector::vector
            LIMIT :top_k
            """,
            {
                "query_vector": str(query_vector),
                "subtopic_id": str(subtopic_id),
                "top_k": self.top_k,
            }
        ).fetchall()

        chunks = [
            ContentChunk(
                content_id=row.content_id,
                subtopic_id=row.subtopic_id,
                content_text=row.content_text,
                content_source=row.content_source,
                similarity_score=float(row.similarity),
                chunk_index=row.chunk_index,
            )
            for row in results
            if float(row.similarity) >= self.min_similarity
        ]

        if not chunks:
            logger.warning(
                "RAG: no content chunks found for subtopic_id=%s "
                "(top_k=%d, min_similarity=%.2f). Prompt will use LLM general knowledge.",
                subtopic_id, self.top_k, self.min_similarity
            )
        return chunks

    def retrieve_for_subtopics(
        self,
        subtopics: list[dict],  # [{"subtopic_id": UUID, "subtopic_name": str}, ...]
        grade_label: str,       # e.g. "Grade 8"
    ) -> dict[str, list[ContentChunk]]:
        """
        Calls retrieve_for_subtopic for each subtopic in the list.
        Returns dict mapping str(subtopic_id) → list[ContentChunk].
        Subtopics with zero results map to [].
        Does NOT raise even if all subtopics return empty.

        query_text per subtopic is constructed as:
            "{subtopic_name} — {grade_label} level curriculum explanation"
        """
        results = {}
        for s in subtopics:
            query_text = f"{s['subtopic_name']} — {grade_label} level curriculum explanation"
            chunks = self.retrieve_for_subtopic(
                subtopic_id=s["subtopic_id"],
                query_text=query_text,
            )
            results[str(s["subtopic_id"])] = chunks
        return results
```

### Phase 10D Acceptance Criteria

- [ ] `retrieve_for_subtopic` returns chunks sorted by similarity descending
- [ ] Chunks with `similarity < RAG_MIN_SIMILARITY` are excluded
- [ ] Zero-result case returns `[]` and logs WARNING — does NOT raise exception
- [ ] `retrieve_for_subtopics` returns a dict with an entry for every subtopic_id, even empty ones
- [ ] IVFFlat index is used for the similarity search — verify with `EXPLAIN ANALYZE` in tests
- [ ] Unit tests mock the DB session and embedding service; verify ranking and threshold filtering
- [ ] Integration test: seed two chunks for one subtopic with known similarity scores; verify correct filtering

---

## Phase 11A — S3: Infrastructure + S3Client

**Goal:** Wire S3 (AWS) and MinIO (dev) into the application. Build the S3Client service
with upload, download, presign, and existence-check operations.
No business logic yet — infrastructure and client only.

**Branch:** `feature/phase-11a-s3-infrastructure`

### 11A.1 New Python Dependency

Add to `backend/requirements.txt`:
```
boto3==1.35.0
```

### 11A.2 MinIO Service (Development Only)

Add to `docker-compose.yml`:

```yaml
minio:
  image: minio/minio:RELEASE.2024-11-07T00-52-20Z
  container_name: kaihle_minio
  restart: unless-stopped
  ports:
    - "9000:9000"      # S3 API
    - "9001:9001"      # MinIO web console
  volumes:
    - minio_data:/data
  environment:
    MINIO_ROOT_USER: ${AWS_ACCESS_KEY_ID}
    MINIO_ROOT_PASSWORD: ${AWS_SECRET_ACCESS_KEY}
  command: server /data --console-address ":9001"
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
    interval: 10s
    timeout: 5s
    retries: 5
```

Add `minio_data:` to the `volumes:` section of `docker-compose.yml`.

**MinIO is NOT added to `docker-compose.prod.yml`.**
In production, `USE_MINIO=false` and all S3 calls route to real AWS S3.

### 11A.3 S3Client Service

**Create: `app/services/storage/s3_client.py`**

```python
"""
S3Client — unified S3/MinIO wrapper.

Routes to MinIO (dev) or AWS S3 (prod) based on USE_MINIO env var.
Called ONLY from Celery worker tasks, EXCEPT generate_presigned_url
which is called from the FastAPI layer (read-only metadata operation,
no data transfer — permitted exception to worker-only rule).

All upload operations are worker-only. Never call upload_bytes,
upload_json, or delete_object from the API layer.
"""
import json
import boto3
from botocore.exceptions import ClientError
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class S3Client:

    def __init__(self):
        kwargs = dict(
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )
        if settings.USE_MINIO:
            kwargs["endpoint_url"] = settings.MINIO_ENDPOINT
        self._client = boto3.client("s3", **kwargs)
        self.bucket = settings.S3_BUCKET_NAME

    def upload_bytes(
        self,
        key: str,
        data: bytes,
        content_type: str,
        metadata: dict[str, str] | None = None,
    ) -> str:
        """
        Uploads raw bytes to S3/MinIO.
        metadata values must all be str — S3 rejects non-string values.
        Returns the s3_key on success.
        Raises on failure — let Celery handle retry.
        """
        extra_args = {"ContentType": content_type}
        if metadata:
            extra_args["Metadata"] = {k: str(v) for k, v in metadata.items()}
        self._client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            **extra_args,
        )
        logger.info("S3 upload: bucket=%s key=%s size=%d", self.bucket, key, len(data))
        return key

    def upload_json(
        self,
        key: str,
        data: dict,
        metadata: dict[str, str] | None = None,
    ) -> str:
        """
        Serialises dict to JSON bytes (UTF-8) and uploads.
        Content-Type is set to application/json.
        Returns the s3_key on success.
        """
        json_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        return self.upload_bytes(
            key=key,
            data=json_bytes,
            content_type="application/json",
            metadata=metadata,
        )

    def download_json(self, key: str) -> dict:
        """
        Downloads and deserialises a JSON object from S3.
        Raises S3Client.NotFoundError if key does not exist.
        Raises json.JSONDecodeError if content is not valid JSON.
        """
        try:
            response = self._client.get_object(Bucket=self.bucket, Key=key)
            return json.loads(response["Body"].read().decode("utf-8"))
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                raise S3Client.NotFoundError(f"Key not found: {key}")
            raise

    def generate_presigned_url(
        self,
        key: str,
        ttl_seconds: int | None = None,
    ) -> str:
        """
        Generates a time-limited presigned GET URL.
        ttl_seconds defaults to S3_PRESIGNED_URL_TTL_SECONDS env var (default: 3600).
        This method MAY be called from the FastAPI layer (read-only, no upload).
        """
        ttl = ttl_seconds or settings.S3_PRESIGNED_URL_TTL_SECONDS
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=ttl,
        )

    def object_exists(self, key: str) -> bool:
        """Returns True if the key exists in the bucket. Uses head_object."""
        try:
            self._client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            raise

    def delete_object(self, key: str) -> None:
        """Deletes object. Does NOT raise if key does not exist."""
        self._client.delete_object(Bucket=self.bucket, Key=key)

    class NotFoundError(Exception):
        pass


# Module-level singleton factory
_s3_client_instance: S3Client | None = None

def get_s3_client() -> S3Client:
    """Returns cached S3Client singleton. Thread-safe for Celery workers."""
    global _s3_client_instance
    if _s3_client_instance is None:
        _s3_client_instance = S3Client()
    return _s3_client_instance
```

### 11A.4 Makefile Targets

Add to `Makefile`:

```makefile
minio-console:
    open http://localhost:9001

create-bucket:
    @echo "Creating S3 bucket: $(S3_BUCKET_NAME)"
    docker-compose exec -T minio mc alias set local \
        http://localhost:9000 \
        $(AWS_ACCESS_KEY_ID) \
        $(AWS_SECRET_ACCESS_KEY) && \
    docker-compose exec -T minio mc mb local/$(S3_BUCKET_NAME) --ignore-existing
    @echo "Bucket ready."
```

Add `create-bucket` as a dependency step in the dev onboarding `README.md`.

### Phase 11A Acceptance Criteria

- [ ] MinIO container starts and passes healthcheck in dev compose
- [ ] `make create-bucket` creates the bucket; re-running is idempotent
- [ ] `upload_bytes` uploads a file; `object_exists` confirms `True`
- [ ] `generate_presigned_url` returns a URL that serves the object via HTTP GET
- [ ] `download_json` round-trips a dict correctly (upload → download → compare)
- [ ] `download_json` raises `S3Client.NotFoundError` for non-existent key
- [ ] `delete_object` does NOT raise when key does not exist
- [ ] `USE_MINIO=true` routes to MinIO; changing to `USE_MINIO=false` routes to AWS (tested via mock)
- [ ] `upload_bytes` and `upload_json` are never called from any FastAPI route handler

---

## Phase 11B — S3: GeneratedContent Model + ContentMetadataService

**Goal:** Create the `GeneratedContent` DB table — the source of truth tracking every
S3-stored media asset: what it is, which student it belongs to, where it lives in S3,
and what its generation status is. Build the service that manages its lifecycle.

**Branch:** `feature/phase-11b-generated-content-model`

### 11B.1 New SQLAlchemy Model

**Create: `app/models/generated_content.py`**

```python
"""
GeneratedContent — tracks every media asset generated for a student.

One row per student × subtopic × content_type combination.
S3 path is set when status transitions to 'completed'.
reused_from_id is set when this row reuses another student's asset (Phase 14B).

content_type values:
    'animation'          — MP4 file (Manim rendered with voiceover)
    'infographic'        — PNG file (Gemini Imagen 3)
    'practice_questions' — JSON file (extracted from LLM spec)

status values:
    'pending'   — row created, generation task not yet complete
    'completed' — s3_key is set, asset is available
    'failed'    — generation failed after max retries
    'reused'    — s3_key points to another student's completed asset
"""
import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, Index, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


class ContentType(str, enum.Enum):
    ANIMATION           = "animation"
    INFOGRAPHIC         = "infographic"
    PRACTICE_QUESTIONS  = "practice_questions"


class GenerationStatus(str, enum.Enum):
    PENDING   = "pending"
    COMPLETED = "completed"
    FAILED    = "failed"
    REUSED    = "reused"


class GeneratedContent(Base):
    __tablename__ = "generated_content"

    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id          = Column(UUID(as_uuid=True),
                                 ForeignKey("student_profiles.id", ondelete="CASCADE"),
                                 nullable=False)
    study_plan_id       = Column(UUID(as_uuid=True),
                                 ForeignKey("study_plans.id", ondelete="CASCADE"),
                                 nullable=False)
    subtopic_id         = Column(UUID(as_uuid=True),
                                 ForeignKey("subtopics.id", ondelete="CASCADE"),
                                 nullable=False)
    content_type        = Column(SAEnum(ContentType), nullable=False)
    status              = Column(SAEnum(GenerationStatus), nullable=False,
                                 default=GenerationStatus.PENDING)

    # Set on completion
    s3_key              = Column(String(500), nullable=True)
    s3_bucket           = Column(String(100), nullable=True)
    file_size_bytes     = Column(Integer, nullable=True)

    # Deterministic hashes (see Phase 11C)
    profile_fingerprint = Column(String(64), nullable=False)   # SHA-256
    prompt_hash         = Column(String(64), nullable=False)   # SHA-256

    # Provider tracking
    llm_provider        = Column(String(50), nullable=True)    # e.g. "gemini"
    media_provider      = Column(String(50), nullable=True)    # e.g. "manim", "gemini_imagen"

    # Error info
    error_message       = Column(Text, nullable=True)

    # Reuse link (Phase 14B)
    reused_from_id      = Column(UUID(as_uuid=True),
                                 ForeignKey("generated_content.id", ondelete="SET NULL"),
                                 nullable=True)

    created_at          = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at        = Column(DateTime, nullable=True)

    __table_args__ = (
        # Fast lookup: does this student have content for this subtopic+type?
        Index("idx_gc_student_subtopic_type",
              "student_id", "subtopic_id", "content_type"),
        # Content reuse lookup: find completed content with same fingerprint+type (Phase 14B)
        Index("idx_gc_fingerprint_type_subtopic",
              "profile_fingerprint", "content_type", "subtopic_id"),
        # Prompt hash dedup lookup
        Index("idx_gc_prompt_hash_type",
              "prompt_hash", "content_type"),
        # Study plan → content lookup
        Index("idx_gc_study_plan_id", "study_plan_id"),
    )
```

### 11B.2 Alembic Migration

**Create: `alembic/versions/xxx_add_generated_content.py`**

```python
"""Add generated_content table

Revision ID: (auto-generated)
"""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from alembic import op

def upgrade():
    op.execute("CREATE TYPE contenttype AS ENUM ('animation','infographic','practice_questions')")
    op.execute("CREATE TYPE generationstatus AS ENUM ('pending','completed','failed','reused')")

    op.create_table(
        "generated_content",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("student_id", UUID(as_uuid=True),
                  sa.ForeignKey("student_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("study_plan_id", UUID(as_uuid=True),
                  sa.ForeignKey("study_plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subtopic_id", UUID(as_uuid=True),
                  sa.ForeignKey("subtopics.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content_type", sa.Enum("animation","infographic","practice_questions",
                  name="contenttype"), nullable=False),
        sa.Column("status", sa.Enum("pending","completed","failed","reused",
                  name="generationstatus"), nullable=False, server_default="pending"),
        sa.Column("s3_key", sa.String(500), nullable=True),
        sa.Column("s3_bucket", sa.String(100), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("profile_fingerprint", sa.String(64), nullable=False),
        sa.Column("prompt_hash", sa.String(64), nullable=False),
        sa.Column("llm_provider", sa.String(50), nullable=True),
        sa.Column("media_provider", sa.String(50), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("reused_from_id", UUID(as_uuid=True),
                  sa.ForeignKey("generated_content.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("idx_gc_student_subtopic_type", "generated_content",
                    ["student_id", "subtopic_id", "content_type"])
    op.create_index("idx_gc_fingerprint_type_subtopic", "generated_content",
                    ["profile_fingerprint", "content_type", "subtopic_id"])
    op.create_index("idx_gc_prompt_hash_type", "generated_content",
                    ["prompt_hash", "content_type"])
    op.create_index("idx_gc_study_plan_id", "generated_content", ["study_plan_id"])


def downgrade():
    op.drop_table("generated_content")
    op.execute("DROP TYPE IF EXISTS contenttype")
    op.execute("DROP TYPE IF EXISTS generationstatus")
```

### 11B.3 ContentMetadataService

**Create: `app/services/storage/content_metadata_service.py`**

```python
"""
ContentMetadataService — manages the GeneratedContent row lifecycle.
All methods are async (used in async Celery tasks via asyncio.run() wrapper).
"""
from uuid import UUID
from datetime import datetime
from app.models.generated_content import GeneratedContent, ContentType, GenerationStatus
from app.core.config import settings


class ContentMetadataService:

    def __init__(self, db_session):
        self.db = db_session

    async def create_pending(
        self,
        student_id: UUID,
        study_plan_id: UUID,
        subtopic_id: UUID,
        content_type: ContentType,
        profile_fingerprint: str,
        prompt_hash: str,
    ) -> GeneratedContent:
        """
        Creates a PENDING row before the generation task runs.
        Returns the new GeneratedContent instance.
        """
        row = GeneratedContent(
            student_id=student_id,
            study_plan_id=study_plan_id,
            subtopic_id=subtopic_id,
            content_type=content_type,
            status=GenerationStatus.PENDING,
            profile_fingerprint=profile_fingerprint,
            prompt_hash=prompt_hash,
            created_at=datetime.utcnow(),
        )
        self.db.add(row)
        await self.db.flush()
        return row

    async def mark_completed(
        self,
        content_id: UUID,
        s3_key: str,
        file_size_bytes: int,
        media_provider: str,
        llm_provider: str | None = None,
    ) -> None:
        """
        Transitions status PENDING → COMPLETED.
        Sets s3_key, s3_bucket, file_size_bytes, completed_at.
        Raises ValueError if row is not in PENDING status.
        """
        row = await self.db.get(GeneratedContent, content_id)
        if row is None:
            raise ValueError(f"GeneratedContent not found: {content_id}")
        if row.status != GenerationStatus.PENDING:
            raise ValueError(
                f"Cannot mark completed: status is {row.status}, expected PENDING"
            )
        row.status = GenerationStatus.COMPLETED
        row.s3_key = s3_key
        row.s3_bucket = settings.S3_BUCKET_NAME
        row.file_size_bytes = file_size_bytes
        row.media_provider = media_provider
        row.llm_provider = llm_provider
        row.completed_at = datetime.utcnow()
        await self.db.flush()

    async def mark_failed(
        self,
        content_id: UUID,
        error_message: str,
    ) -> None:
        """
        Transitions status PENDING → FAILED.
        Stores error_message for debugging.
        """
        row = await self.db.get(GeneratedContent, content_id)
        if row is None:
            raise ValueError(f"GeneratedContent not found: {content_id}")
        row.status = GenerationStatus.FAILED
        row.error_message = error_message[:2000]  # truncate to column limit
        await self.db.flush()

    async def mark_reused(
        self,
        content_id: UUID,
        reused_from_id: UUID,
        s3_key: str,
    ) -> None:
        """
        Transitions status PENDING → REUSED.
        Sets reused_from_id and s3_key (pointing to the original asset).
        """
        row = await self.db.get(GeneratedContent, content_id)
        if row is None:
            raise ValueError(f"GeneratedContent not found: {content_id}")
        row.status = GenerationStatus.REUSED
        row.reused_from_id = reused_from_id
        row.s3_key = s3_key
        row.s3_bucket = settings.S3_BUCKET_NAME
        row.completed_at = datetime.utcnow()
        await self.db.flush()

    async def get_by_student_study_plan(
        self,
        student_id: UUID,
        study_plan_id: UUID,
    ) -> list[GeneratedContent]:
        """
        Returns all GeneratedContent rows for a student's study plan.
        Used by the content delivery API endpoint (Phase 15).
        """
        ...

    async def get_by_subtopic(
        self,
        student_id: UUID,
        subtopic_id: UUID,
    ) -> list[GeneratedContent]:
        """Returns all content types for a student × subtopic combination."""
        ...
```

### Phase 11B Acceptance Criteria

- [ ] Migration creates `generated_content` table with all columns, types, and indexes
- [ ] All four enum values for `ContentType` and `GenerationStatus` are correct
- [ ] `create_pending` → `mark_completed` lifecycle round-trips with correct field values
- [ ] `mark_completed` raises `ValueError` if row status is not PENDING
- [ ] `mark_reused` correctly sets `reused_from_id` and copies `s3_key`
- [ ] `mark_failed` truncates `error_message` to 2000 chars
- [ ] `idx_gc_fingerprint_type_subtopic` index exists (verified in psql)
- [ ] `downgrade()` drops table and both enum types cleanly

---

## Phase 11C — S3: Deterministic Key Generator + Prompt Hash

**Goal:** Define the exact naming convention for every S3 object and the exact inputs
used to build the `prompt_hash`. This is the foundation for content deduplication and
reuse. Get this right before any media is generated.

**Branch:** `feature/phase-11c-key-generator`

### 11C.1 Key Generator

**Create: `app/services/storage/key_generator.py`**

```python
"""
S3 key and prompt hash generation for generated content.

S3 Key format:
  {content_type}/{grade_code}/{subject_code}/{subtopic_id}/{prompt_hash}.{ext}

Examples:
  animation/grade8/math/550e8400-e29b-41d4-a716-446655440000/a3f9c1d2abcd1234.mp4
  infographic/grade8/math/550e8400-e29b-41d4-a716-446655440000/a3f9c1d2abcd1234.png
  practice_questions/grade8/math/550e8400-e29b-41d4-a716-446655440000/a3f9c1d2abcd1234.json
  specs/grade8/math/550e8400-e29b-41d4-a716-446655440000/a3f9c1d2abcd1234_spec.json

prompt_hash = SHA-256(canonical JSON string of all prompt inputs)
The canonical JSON string is produced by json.dumps(inputs, sort_keys=True, ensure_ascii=True).
Any change to any input field produces a different hash.

Key properties:
  - Same inputs → same key → S3 object reused (never re-generated)
  - File path is human-readable and traceable without DB lookup
  - Changing grade, subject, subtopic, mastery band, RAG chunks, or learning style
    always produces a different key → fresh generation
"""
import hashlib
import json
from app.models.generated_content import ContentType


CONTENT_TYPE_EXT: dict[ContentType, str] = {
    ContentType.ANIMATION:           "mp4",
    ContentType.INFOGRAPHIC:         "png",
    ContentType.PRACTICE_QUESTIONS:  "json",
}


def build_prompt_hash(prompt_inputs: dict) -> str:
    """
    Builds a 64-char hex SHA-256 hash from the prompt inputs dict.

    Required keys in prompt_inputs (all must be present — raise KeyError if missing):
        "grade_code"         str  e.g. "grade8"
        "subject_code"       str  e.g. "math"
        "subtopic_id"        str  UUID string of the subtopic
        "mastery_band"       str  "beginning" | "developing" | "approaching"
                                  (discretised from mastery_level — see Phase 14A)
        "priority"           str  "high" | "medium" | "low"
        "rag_content_ids"    list sorted list of UUID strings of ContentChunks used
                                  (empty list [] if no RAG content found)
        "learning_style"     str  from StudentProfile.learning_profile["learning_style"]
                                  use "general" if field is absent or None
        "content_type"       str  ContentType enum value string

    The dict is serialised with sort_keys=True to guarantee determinism.
    """
    required_keys = {
        "grade_code", "subject_code", "subtopic_id", "mastery_band",
        "priority", "rag_content_ids", "learning_style", "content_type",
    }
    missing = required_keys - set(prompt_inputs.keys())
    if missing:
        raise KeyError(f"build_prompt_hash: missing required keys: {missing}")

    # Ensure rag_content_ids is sorted for determinism
    inputs = dict(prompt_inputs)
    inputs["rag_content_ids"] = sorted(inputs["rag_content_ids"])

    canonical = json.dumps(inputs, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_s3_key(
    content_type: ContentType,
    grade_code: str,
    subject_code: str,
    subtopic_id: str,
    prompt_hash: str,
) -> str:
    """
    Builds the S3 object key for a generated content asset.
    grade_code and subject_code are lowercase strings (e.g. "grade8", "math").
    prompt_hash is a 64-char hex string from build_prompt_hash().
    """
    ext = CONTENT_TYPE_EXT[content_type]
    return f"{content_type.value}/{grade_code}/{subject_code}/{subtopic_id}/{prompt_hash}.{ext}"


def build_spec_s3_key(
    grade_code: str,
    subject_code: str,
    subtopic_id: str,
    prompt_hash: str,
) -> str:
    """
    Builds the S3 key for the raw LLM content spec JSON.
    This is a separate key from the media assets — stored under 'specs/' prefix.
    """
    return f"specs/{grade_code}/{subject_code}/{subtopic_id}/{prompt_hash}_spec.json"


def build_s3_metadata(
    student_id: str,
    subtopic_id: str,
    subject_code: str,
    grade_code: str,
    prompt_hash: str,
    profile_fingerprint: str,
    content_type: str,
    llm_provider: str,
) -> dict[str, str]:
    """
    Returns the S3 object metadata dict for every upload.
    All values must be strings (S3 requirement).
    This metadata is stored on the S3 object itself for traceability.
    """
    return {
        "student-id":           student_id,
        "subtopic-id":          subtopic_id,
        "subject-code":         subject_code,
        "grade-code":           grade_code,
        "prompt-hash":          prompt_hash,
        "profile-fingerprint":  profile_fingerprint,
        "content-type":         content_type,
        "llm-provider":         llm_provider,
        "generated-at":         datetime.utcnow().isoformat(),
    }
```

### Phase 11C Acceptance Criteria

- [ ] `build_prompt_hash` is deterministic: same dict → same hash across process restarts
- [ ] `build_prompt_hash` raises `KeyError` if any required key is missing
- [ ] `rag_content_ids` sorted before hashing: `["b", "a"]` and `["a", "b"]` produce same hash
- [ ] Different `mastery_band` values produce different hashes (tested: "beginning" vs "developing")
- [ ] Different `learning_style` values produce different hashes
- [ ] `build_s3_key` produces correct path format for all three `ContentType` values
- [ ] `build_spec_s3_key` produces path under `specs/` prefix ending in `_spec.json`
- [ ] `build_s3_metadata` returns a dict where all values are `str` type

---

## Phase 12A — StudyPlan Migration: subject_id + profile_fingerprint + data purge

**Goal:** Migrate the existing `study_plans` table to support the new per-subject
design. Add `subject_id` and `profile_fingerprint` columns. Delete existing test rows.

**Branch:** `feature/phase-12a-studyplan-migration`

### 12A.1 Alembic Migration

**Create: `alembic/versions/xxx_add_study_plan_subject_fingerprint.py`**

```python
"""Add subject_id and profile_fingerprint to study_plans

Revision ID: (auto-generated)
Depends on: (previous migration)
"""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from alembic import op


def upgrade():
    # Add subject_id column (nullable first — existing rows have no subject)
    op.add_column("study_plans",
        sa.Column("subject_id", UUID(as_uuid=True),
                  sa.ForeignKey("subjects.id", ondelete="SET NULL"),
                  nullable=True)
    )

    # Add profile_fingerprint column
    op.add_column("study_plans",
        sa.Column("profile_fingerprint", sa.String(64), nullable=True)
    )

    # Index on subject_id for per-subject queries
    op.create_index("idx_sp_student_subject", "study_plans", ["student_id", "subject_id"])

    # Index on profile_fingerprint for reuse lookups
    op.create_index("idx_sp_profile_fingerprint", "study_plans", ["profile_fingerprint"])

    # NOTE: Do NOT set nullable=False on subject_id here.
    # Existing rows (test data) will be deleted by the purge script (Phase 12A.2).
    # New rows written by generate_enriched_study_plan will always have subject_id set.


def downgrade():
    op.drop_index("idx_sp_profile_fingerprint", table_name="study_plans")
    op.drop_index("idx_sp_student_subject", table_name="study_plans")
    op.drop_column("study_plans", "profile_fingerprint")
    op.drop_column("study_plans", "subject_id")
```

### 12A.2 Data Purge Script

**Create: `backend/scripts/purge_old_study_plans.py`**

```python
"""
Purge script — deletes all StudyPlan and StudyPlanCourse rows created by the
deprecated Phase 6 task (tasks.generate_study_plan).

These are test-only rows with no subject_id. Safe to delete.
StudyPlanCourse rows are deleted via CASCADE from study_plans.

Usage:
    docker-compose exec api python scripts/purge_old_study_plans.py --dry-run
    docker-compose exec api python scripts/purge_old_study_plans.py --confirm

Options:
    --dry-run  Print count of rows that would be deleted. No DB changes.
    --confirm  Actually delete rows. Required for real deletion.

Criteria for deletion:
    DELETE FROM study_plans WHERE subject_id IS NULL;
    (StudyPlanCourse rows deleted by ON DELETE CASCADE)
"""
```

Add to `Makefile`:

```makefile
purge-old-study-plans:
    docker-compose exec api python scripts/purge_old_study_plans.py --confirm

purge-old-study-plans-dry:
    docker-compose exec api python scripts/purge_old_study_plans.py --dry-run
```

### 12A.3 Updated StudyPlan Model

**Modify: `app/models/study_plan.py`** — add two new columns to `StudyPlan`:

```python
# Add these two columns to StudyPlan class, after assessment_id:
subject_id          = Column(UUID(as_uuid=True),
                             ForeignKey("subjects.id", ondelete="SET NULL"),
                             nullable=True, index=True)

profile_fingerprint = Column(String(64), nullable=True, index=True)
```

Add to `__table_args__`:
```python
Index("idx_sp_student_subject", "student_id", "subject_id"),
Index("idx_sp_profile_fingerprint", "profile_fingerprint"),
```

Add to relationships:
```python
subject = relationship("Subject")
```

**Full documented status values for StudyPlan.status after this phase:**
- `"generating"` — task running, not yet written to DB as active
- `"active"` — successfully generated, available to student
- `"generation_failed"` — task exhausted max_retries
- `"completed"` — student has completed all courses in this plan
- `"paused"` — student paused the plan
- `"archived"` — plan superseded or manually archived

### Phase 12A Acceptance Criteria

- [ ] Migration adds `subject_id` and `profile_fingerprint` columns with no errors
- [ ] Both new indexes created (verify in psql: `\d study_plans`)
- [ ] `make purge-old-study-plans-dry` prints correct row count
- [ ] `make purge-old-study-plans` deletes all rows where `subject_id IS NULL`
- [ ] After purge, zero `StudyPlan` rows remain in dev DB
- [ ] After purge, zero `StudyPlanCourse` rows remain (CASCADE confirmed)
- [ ] `StudyPlan` SQLAlchemy model updated with new columns and relationships

---

## Phase 12B — Deprecate Old Task + Trigger Redesign (Per-Subject Chain)

**Goal:** This phase does two things that must be implemented together:
(1) Deprecate `tasks.generate_study_plan` in `study_plan.py`.
(2) Redesign the trigger point in `response_handler.py` from "fire after all 4 subjects"
to "fire per subject as soon as that subject's assessment completes".

**Branch:** `feature/phase-12b-trigger-redesign`

### 12B.1 Old Task Deprecation

**Modify: `app/worker/tasks/study_plan.py`**

Add a deprecation header to the existing task. Do NOT delete the function — it must
remain to avoid breaking any Celery task IDs that may be in-flight in Redis.

```python
# app/worker/tasks/study_plan.py
# ─────────────────────────────────────────────────────────────────────
# DEPRECATED — Phase 12B (Kaihle v3.1)
# This task is no longer dispatched. It is kept to allow any in-flight
# Celery task IDs to complete without error.
# The replacement task is: tasks.generate_enriched_study_plan
# in app/worker/tasks/enriched_study_plan.py
# Do NOT call generate_study_plan.delay() or .apply_async() anywhere.
# ─────────────────────────────────────────────────────────────────────

@celery_app.task(bind=True, max_retries=0, name="tasks.generate_study_plan")
def generate_study_plan(self, student_id: str) -> str:
    """DEPRECATED. See app/worker/tasks/enriched_study_plan.py."""
    import logging
    logging.getLogger(__name__).warning(
        "DEPRECATED task tasks.generate_study_plan called for student_id=%s. "
        "This task should no longer be dispatched. "
        "Use tasks.generate_enriched_study_plan instead.",
        student_id,
    )
    return student_id
```

### 12B.2 Trigger Redesign in Response Handler

**Modify: `app/services/diagnostic/response_handler.py`**

Remove: `check_all_subjects_complete()` method.
Add: `check_single_subject_complete()` method.

```python
async def check_single_subject_complete(
    self,
    assessment_id: UUID,
    subject_id: UUID,
    student_id: UUID,
) -> bool:
    """
    Called after every answer submission. Checks if the current subject's
    assessment is fully complete (all subtopics answered).

    If complete AND not already triggered:
      1. Set Redis flag: kaihle:diagnostic:generating:{student_id}:{subject_id} = "reports"
         TTL: 2 hours
      2. Dispatch Celery chain:
         generate_assessment_report.s(str(assessment_id))
         | generate_enriched_study_plan.s()
      3. Returns True

    If not complete OR already triggered: returns False.

    Redis guard key: kaihle:diagnostic:generating:{student_id}:{subject_id}
    Check this key BEFORE dispatching to prevent double-trigger.
    If key already exists: return False immediately (chain already dispatched).
    """
    from app.worker.tasks.enriched_study_plan import generate_enriched_study_plan
    from app.worker.tasks.report_generation import generate_assessment_report
    from celery import chain as celery_chain

    # Check if this assessment is complete
    session_state = await self.get_session_state(assessment_id)
    if session_state["status"] != "completed":
        return False

    # Redis guard: prevent double-trigger
    redis_flag_key = f"kaihle:diagnostic:generating:{student_id}:{subject_id}"
    already_triggered = await self.redis.exists(redis_flag_key)
    if already_triggered:
        return False

    # Set flag before dispatching (prevents race condition)
    await self.redis.setex(redis_flag_key, 7200, "reports")  # TTL: 2 hours

    # Dispatch per-subject chain
    celery_chain(
        generate_assessment_report.s(str(assessment_id)),
        generate_enriched_study_plan.s(),
    ).delay()

    return True
```

**Modify: `app/services/diagnostic/response_handler.py` — `submit_answer` method:**

Replace the call to `check_all_subjects_complete()` with:
```python
# After recording answer and updating state:
await self.check_single_subject_complete(
    assessment_id=assessment_id,
    subject_id=session_state["subject_id"],
    student_id=session_state["student_id"],
)
```

### 12B.3 Redis Flag Format (Updated)

**Per-subject flags (new):**

| Key format | Value | TTL | Meaning |
|---|---|---|---|
| `kaihle:diagnostic:generating:{student_id}:{subject_id}` | `"reports"` | 2 hours | Generating assessment report for this subject |
| `kaihle:diagnostic:generating:{student_id}:{subject_id}` | `"study_plan"` | 2 hours | Generating enriched study plan for this subject |
| `kaihle:diagnostic:generating:{student_id}:{subject_id}` | `"media_generation"` | 2 hours | Media tasks dispatched |
| `kaihle:diagnostic:generating:{student_id}:{subject_id}` | `"complete"` | 2 hours | All content ready |
| `kaihle:diagnostic:generating:{student_id}:{subject_id}` | `"failed"` | 2 hours | Task chain failed |

The existing `kaihle:diagnostic:generating:{student_id}` key format (without subject_id)
**is no longer used**. All new code uses the per-subject format above.

The FastAPI `/diagnostic/{student_id}/status` endpoint must read per-subject flags
to report status. Update it to read all 4 subject-specific keys.

### 12B.4 celery_app.py Updates

**Modify: `app/worker/celery_app.py`**

```python
celery_app = Celery(
    "kaihle",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.worker.tasks.report_generation",
        "app.worker.tasks.study_plan",              # kept — deprecated task
        "app.worker.tasks.enriched_study_plan",     # new
        "app.worker.tasks.rag_ingestion",           # new (Phase 10C)
        "app.worker.tasks.media_generation.animation",        # new (Phase 13B)
        "app.worker.tasks.media_generation.practice_questions",  # new (Phase 13C)
        "app.worker.tasks.media_generation.infographic",      # new (Phase 13D)
    ]
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "app.worker.tasks.report_generation.*":              {"queue": "reports"},
        "app.worker.tasks.study_plan.*":                     {"queue": "study_plans"},
        "app.worker.tasks.enriched_study_plan.*":            {"queue": "study_plans"},
        "app.worker.tasks.rag_ingestion.*":                  {"queue": "default"},
        "app.worker.tasks.media_generation.animation.*":     {"queue": "manim_queue"},
        "app.worker.tasks.media_generation.practice_questions.*": {"queue": "default"},
        "app.worker.tasks.media_generation.infographic.*":   {"queue": "default"},
    },
)
```

### Phase 12B Acceptance Criteria

- [ ] `tasks.generate_study_plan` still exists in celery_app includes; calling it logs WARNING and returns student_id — does NOT raise
- [ ] `check_single_subject_complete()` fires Celery chain immediately when a subject's final question is answered
- [ ] Redis guard prevents double-dispatch: calling `check_single_subject_complete()` twice for the same assessment fires chain exactly once
- [ ] Redis flag key format is `kaihle:diagnostic:generating:{student_id}:{subject_id}` — NOT the old format
- [ ] A student completing Math assessment triggers chain for Math only — Science/English/Humanities not affected
- [ ] All four queues registered in `task_routes`: `reports`, `study_plans`, `default`, `manim_queue`
- [ ] Old `check_all_subjects_complete()` method removed from response_handler.py (no callers remain)
- [ ] `StudentProfile.has_completed_assessment` flag still set to True after all 4 subjects complete — add separate check for this: when all 4 per-subject flags exist and all equal "complete", set the flag

---

## Phase 12C — New Study Plan Task: RAG Prompt Injection

**Goal:** Create the `generate_enriched_study_plan` Celery task skeleton with the RAG
context retrieval step. The task receives `assessment_id` from the chain, loads the
assessment report, retrieves RAG content per gap subtopic, and constructs the enriched
prompt. The LLM call itself is Phase 12D.

**Branch:** `feature/phase-12c-rag-prompt-injection`

### 12C.1 New Task File

**Create: `app/worker/tasks/enriched_study_plan.py`**

```python
"""
generate_enriched_study_plan — replaces the deprecated tasks.generate_study_plan.

Receives assessment_id from the Celery chain (output of generate_assessment_report).
Operates on a SINGLE subject's assessment — generates one StudyPlan per subject.

Queue: study_plans
Task name: tasks.generate_enriched_study_plan
"""
from celery import Task
from app.worker.celery_app import celery_app
from app.services.rag.query_service import RAGQueryService
from app.services.rag.embedding_service import EmbeddingService
from app.core.database import SessionLocal
from app.models.assessment import Assessment, AssessmentReport
from app.models.student_profile import StudentProfile
import logging

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    max_retries=3,
    name="tasks.generate_enriched_study_plan",
    queue="study_plans",
    default_retry_delay=30,      # seconds between retries
    time_limit=300,              # 5 minutes max (LLM call + RAG + DB write)
    soft_time_limit=270,
)
def generate_enriched_study_plan(self, assessment_id: str) -> str:
    """
    Full pipeline (phases broken across 12C, 12D, 12E for review — all in this one task):

    Phase 12C (this phase) — Data loading + RAG:
        1. Load Assessment by assessment_id → get subject_id, student_id
        2. Load AssessmentReport for this assessment (knowledge_gaps JSON)
        3. Load StudentProfile → grade_id, curriculum_id, learning_profile JSONB
        4. Derive grade_code (e.g. "grade8") and subject_code (e.g. "math")
        5. Extract gap subtopics from knowledge_gaps (priority != null)
        6. For each gap subtopic → RAGQueryService.retrieve_for_subtopic()
        7. Build rag_context dict: {subtopic_id_str: [ContentChunk, ...]}

    Phase 12D — LLM call (implemented in same task):
        8. Build profile_fingerprint (Phase 14A service called here)
        9. Build enriched LLM prompt
        10. S3 dedup check via prompt_hash (AGENTS.md 3.4.1 rule)
        11. Call Gemini 2.5 Pro
        12. Validate JSON output

    Phase 12E — Persistence (implemented in same task):
        13. Upload raw spec JSON to S3
        14. Write StudyPlan + StudyPlanCourse rows to DB
        15. Create GeneratedContent PENDING rows
        16. Call reuse_or_dispatch per content item
        17. Update Redis flag to "media_generation"

    On JSONDecodeError from LLM: retry (max_retries=3)
    On S3 upload failure: retry
    On DB write failure: retry
    On ALL retries exhausted:
        - Create StudyPlan with status="generation_failed"
        - Update Redis flag to "failed"
        - Do not raise — task completes with failure recorded
    """
    ...
```

### 12C.2 Prompt Builder Function

```python
def build_enriched_prompt(
    student_profile: StudentProfile,
    grade_code: str,
    subject_code: str,
    knowledge_gaps: list[dict],
    rag_context: dict[str, list],  # str(subtopic_id) → [ContentChunk, ...]
    recommended_weeks: int,
) -> str:
    """
    Constructs the user-side prompt for the study plan LLM call.

    Output structure:
    ────────────────────────────────────────────────────────────
    ## Student Profile
    Grade: {grade_code}
    Subject: {subject_code}
    Learning Style: {learning_profile.get("learning_style", "general")}
    Pace: {learning_profile.get("pace", "standard")}
    Preferences: {learning_profile.get("preferences", "none specified")}

    ## Knowledge Gaps (ordered by priority: high → medium → low)

    ### {subtopic_name} | Priority: {priority} | Mastery: {mastery_level:.0%}

    #### Curriculum Reference Content
    Source: {content_source}
    {content_text}

    [Repeated for each ContentChunk for this subtopic]
    [If no RAG content: "No curriculum reference available — use general knowledge"]

    ## Generation Task
    Generate a personalised {recommended_weeks}-week study plan for the above student
    covering ONLY the knowledge gap subtopics listed above.
    Return ONLY valid JSON conforming exactly to the schema specified in the system prompt.
    No markdown. No explanation. No commentary outside the JSON object.
    ────────────────────────────────────────────────────────────

    Notes:
    - knowledge_gaps are sorted: high priority first, then medium, then low
    - Each gap subtopic section includes ALL ContentChunks for that subtopic
      (up to RAG_TOP_K chunks, already filtered by RAG_MIN_SIMILARITY)
    - If rag_context[subtopic_id] is empty list, the "Curriculum Reference Content"
      section is omitted entirely for that subtopic (not replaced with placeholder text)
    """
    ...


def calculate_recommended_weeks(gaps: list[dict]) -> int:
    """
    Unchanged from Phase 6 implementation. Kept in this file.
    high * 1.0 + medium * 0.5 + low * 0.25, clamped to [4, 16].
    """
    high   = sum(1 for g in gaps if g["priority"] == "high")
    medium = sum(1 for g in gaps if g["priority"] == "medium")
    low    = sum(1 for g in gaps if g["priority"] == "low")
    return max(4, min(round((high * 1.0) + (medium * 0.5) + (low * 0.25)) + 1, 16))
```

### Phase 12C Acceptance Criteria

- [ ] Task receives `assessment_id` string from chain (output of `generate_assessment_report`)
- [ ] `Assessment` loaded by `assessment_id`; `subject_id` and `student_id` extracted
- [ ] `AssessmentReport` loaded for this assessment; `knowledge_gaps` extracted
- [ ] `StudentProfile.learning_profile` JSONB accessed without error even if specific keys are absent
- [ ] `grade_code` derived correctly: e.g. grade 8 → `"grade8"`
- [ ] `subject_code` derived correctly: e.g. Math subject → `"math"`
- [ ] `RAGQueryService.retrieve_for_subtopic()` called once per gap subtopic
- [ ] Subtopics with zero RAG results do NOT crash the task — they map to `[]`
- [ ] `build_enriched_prompt` excludes the "Curriculum Reference Content" section for subtopics with empty RAG context
- [ ] Unit tests: mock AssessmentReport with 3 gaps; assert prompt contains all 3 subtopic sections

---

## Phase 12D — New Study Plan Task: Multi-Modal LLM Output Schema + Validation

**Goal:** Define the LLM system prompt, the exact JSON schema the LLM must return,
and all validation rules applied before any DB or S3 write. Implement the LLM call
and validation inside `generate_enriched_study_plan`.

**Branch:** `feature/phase-12d-multimodal-llm-schema`

### 12D.1 LLM System Prompt

```python
STUDY_PLAN_SYSTEM_PROMPT = """
You are an expert Cambridge curriculum content designer for Grade 5 to Grade 12 students.

Your task: Given a student's knowledge gaps and available curriculum reference content,
generate a personalised multi-modal study plan as structured JSON.

For each knowledge gap subtopic you receive, you must produce:
1. An animation specification (video script broken into scenes with narration and visual cues)
2. An infographic specification (layout, sections, visual style)
3. Practice questions with answers and explanations (minimum 10 questions)

Rules you must follow without exception:
- Return ONLY valid JSON. No markdown code fences. No preamble. No explanation text.
- The JSON must conform exactly to the schema provided below.
- animation scenes: maximum {ANIMATION_MAX_SCENES} scenes per subtopic.
- animation total duration: maximum {ANIMATION_MAX_DURATION_SECONDS} seconds.
- practice question difficulty: MUST be an integer between 1 and 5 (1=Beginner, 5=Expert).
  Any other value is invalid.
- Minimum 10 practice questions per subtopic. Maximum 15.
- Each question must have: question_text, options (list of 4), correct_answer, explanation, difficulty.
- Use the curriculum reference content provided to inform the language, examples, and focus.
  If no reference content is provided for a subtopic, use your general Cambridge curriculum knowledge.
- Do NOT invent subtopic_ids. Use the exact subtopic_id strings provided in the user prompt.
- week values must be >= 1 and <= total_weeks.
- day values must be >= 1 and <= 5.

JSON Schema:
{
  "study_plan_meta": {
    "subject": string,
    "grade": string,
    "total_weeks": integer,
    "generated_at": "ISO8601 datetime string"
  },
  "subtopic_specs": [
    {
      "subtopic_id": "uuid-string (use exactly as provided)",
      "subtopic_name": string,
      "subject": string,
      "priority": "high" | "medium" | "low",
      "mastery_level": float (0.0 to 1.0),
      "week": integer,
      "day": integer (1-5),
      "animation_spec": {
        "title": string,
        "total_duration_seconds": integer (max 180),
        "learning_objective": string,
        "scenes": [
          {
            "scene_index": integer (1-based),
            "title": string,
            "narration": string (full narration text for this scene),
            "visual_elements": [string, ...],
            "duration_seconds": integer
          }
        ]
      },
      "infographic_spec": {
        "title": string,
        "layout": "vertical" | "horizontal" | "grid",
        "visual_style": string,
        "sections": [
          {
            "heading": string,
            "body": string
          }
        ]
      },
      "practice_questions": [
        {
          "question_number": integer (1-based),
          "difficulty": integer (1-5),
          "question_text": string,
          "options": [string, string, string, string],
          "correct_answer": string (must match one of the options exactly),
          "explanation": string,
          "topic_tested": string
        }
      ]
    }
  ]
}
"""
```

### 12D.2 LLM Call

```python
def call_gemini_for_study_plan(
    system_prompt: str,
    user_prompt: str,
) -> dict:
    """
    Calls Gemini 2.5 Pro via Google Generative AI SDK.
    Returns parsed JSON dict.

    Raises:
        json.JSONDecodeError — if response is not valid JSON (triggers Celery retry)
        Exception — for API errors (triggers Celery retry)

    Configuration:
        model: settings.GEMINI_LLM_MODEL ("gemini-2.5-pro")
        temperature: 0.3
        max_output_tokens: 8192  (large — multi-modal specs are verbose)
    """
    import google.generativeai as genai
    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel(
        model_name=settings.GEMINI_LLM_MODEL,
        system_instruction=system_prompt,
        generation_config=genai.types.GenerationConfig(
            temperature=0.3,
            max_output_tokens=8192,
        ),
    )
    response = model.generate_content(user_prompt)
    raw_text = response.text.strip()
    # Strip markdown code fences if LLM wraps output despite instructions
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
    return json.loads(raw_text)
```

### 12D.3 Validation Rules (Apply in Order)

All validation happens BEFORE any DB write or S3 upload.
Any validation failure that cannot be recovered gracefully triggers a Celery retry.

```python
def validate_llm_output(
    raw_output: dict,
    gap_subtopic_ids: list[str],
    total_weeks: int,
) -> list[dict]:
    """
    Validates and sanitises LLM output. Returns list of valid specs.
    Invalid specs are skipped with a WARNING log — they do not abort the task.

    Validation rules applied to each spec in raw_output["subtopic_specs"]:

    Rule 1: subtopic_id must be in gap_subtopic_ids list.
            If not: skip spec, log WARNING.

    Rule 2: week must be >= 1 and <= total_weeks.
            If not: clamp to [1, total_weeks]. Log WARNING.

    Rule 3: day must be >= 1 and <= 5.
            If not: clamp to [1, 5]. Log WARNING.

    Rule 4: animation_spec.total_duration_seconds must be <= ANIMATION_MAX_DURATION_SECONDS.
            If not: truncate scenes until total duration fits.

    Rule 5: len(animation_spec.scenes) must be <= ANIMATION_MAX_SCENES.
            If not: truncate to first ANIMATION_MAX_SCENES scenes.

    Rule 6: Each scene must have non-empty narration string.
            If empty: skip that scene. If ALL scenes empty: skip entire spec, log WARNING.

    Rule 7: len(practice_questions) must be >= 10.
            If < 10: skip spec, log WARNING ("insufficient questions").

    Rule 8: Each practice question difficulty must be Integer 1–5.
            If float: round to nearest int and clamp to [1, 5].
            If string: attempt int() conversion; if fails: set to 3 (Medium).

    Rule 9: Each practice question correct_answer must match one of its options exactly.
            If not: skip that question. If remaining questions < 10: skip entire spec.

    Rule 10: infographic_spec must have at least 2 sections.
             If not: skip spec, log WARNING.

    Returns list of validated spec dicts. Raises ValueError if resulting list is empty
    (nothing usable from LLM output — triggers retry).
    """
    ...
```

### Phase 12D Acceptance Criteria

- [ ] System prompt is a module-level constant in `enriched_study_plan.py` (not built at runtime)
- [ ] `ANIMATION_MAX_SCENES` and `ANIMATION_MAX_DURATION_SECONDS` read from settings
- [ ] `call_gemini_for_study_plan` strips markdown code fences before JSON parsing
- [ ] `validate_llm_output` returns only validated specs; skips invalid ones with WARNING
- [ ] Difficulty values: floats rounded+clamped, strings converted, invalids set to 3 — never rejected
- [ ] `correct_answer` not matching any option causes question rejection
- [ ] Spec with fewer than 10 valid questions after Rule 9 is skipped entirely
- [ ] Empty validated list raises `ValueError` → triggers Celery retry
- [ ] Unit tests cover each of the 10 validation rules with a dedicated fixture

---

## Phase 12E — New Study Plan Task: DB Write + S3 + Dispatch Media Workers

**Goal:** Complete `generate_enriched_study_plan`. After validated specs are ready:
write `StudyPlan` + `StudyPlanCourse` rows, upload spec JSON to S3, create
`GeneratedContent` PENDING rows, and dispatch media tasks via `reuse_or_dispatch`.

**Branch:** `feature/phase-12e-persist-and-dispatch`

### 12E.1 StudyPlan + StudyPlanCourse Write

```python
def write_study_plan_to_db(
    db,
    student_id: UUID,
    assessment_id: UUID,
    subject_id: UUID,
    grade_code: str,
    subject_code: str,
    profile_fingerprint: str,
    validated_specs: list[dict],
    total_weeks: int,
) -> StudyPlan:
    """
    Writes one StudyPlan row and one StudyPlanCourse row per validated spec.
    All writes in a single DB transaction.

    StudyPlan fields:
        student_id:          from argument
        assessment_id:       from argument (the single subject's assessment)
        subject_id:          from argument
        title:               "{subject_code.title()} Study Plan — Grade {grade_number}"
                             e.g. "Math Study Plan — Grade 8"
        status:              "active"
        total_weeks:         from argument
        profile_fingerprint: from argument
        generation_metadata: {
            "grade_code": grade_code,
            "subject_code": subject_code,
            "gap_count": len(validated_specs),
            "model_version": settings.GEMINI_LLM_MODEL,
            "generated_at": utcnow().isoformat(),
        }

    StudyPlanCourse fields per spec:
        study_plan_id:       new StudyPlan.id
        course_id:           NULL (AI-generated content, not from courses table)
        title:               spec["animation_spec"]["title"]
        description:         spec["animation_spec"]["learning_objective"]
        topic_id:            NULL (set later if mapping is possible)
        subtopic_id:         UUID(spec["subtopic_id"])
        week:                spec["week"]
        day:                 spec["day"]
        sequence_order:      loop index + 1
        suggested_duration_mins: spec["animation_spec"]["total_duration_seconds"] // 60 + 10
                                 (animation duration + 10 min for infographic + practice)
        activity_type:       "ai_content"   ← ALWAYS this value for AI-generated rows
        custom_content:      full spec dict (animation_spec, infographic_spec,
                             practice_questions, subtopic metadata)
                             PLUS "spec_s3_key" added after S3 upload
        status:              "not_started"

    Returns the created StudyPlan instance.
    """
    ...
```

### 12E.2 S3 Spec Upload

```python
def upload_spec_to_s3(
    s3_client: S3Client,
    spec: dict,
    grade_code: str,
    subject_code: str,
    subtopic_id: str,
    prompt_hash: str,
    student_id: str,
    profile_fingerprint: str,
) -> str:
    """
    Uploads the validated spec dict for one subtopic to S3.
    Returns the s3_key.

    Key: build_spec_s3_key(grade_code, subject_code, subtopic_id, prompt_hash)
    Metadata: build_s3_metadata(...)
    Content-Type: application/json

    After upload: update StudyPlanCourse.custom_content["spec_s3_key"] = s3_key
    """
    ...
```

### 12E.3 GeneratedContent PENDING Rows + Dispatch

```python
def create_pending_and_dispatch(
    db,
    s3_client: S3Client,
    reuse_service,          # ContentReuseService (Phase 14B)
    student_id: UUID,
    study_plan_id: UUID,
    profile_fingerprint: str,
    validated_specs: list[dict],
    grade_code: str,
    subject_code: str,
    learning_style: str,
):
    """
    For each validated spec × each ContentType:
        1. Build prompt_hash for this content type
        2. Create GeneratedContent PENDING row via ContentMetadataService
        3. Call reuse_service.reuse_or_dispatch(...)

    Content types dispatched per spec:
        ContentType.ANIMATION          → tasks.generate_animation_manim
        ContentType.PRACTICE_QUESTIONS → tasks.generate_practice_questions
        ContentType.INFOGRAPHIC        → tasks.generate_infographic

    prompt_hash inputs per content type:

    For ANIMATION:
        {
            "grade_code": grade_code,
            "subject_code": subject_code,
            "subtopic_id": str(spec["subtopic_id"]),
            "mastery_band": mastery_band(spec["mastery_level"]),  # Phase 14A
            "priority": spec["priority"],
            "rag_content_ids": sorted([str(c.content_id) for c in rag_chunks]),
            "learning_style": learning_style,
            "content_type": "animation",
        }

    For PRACTICE_QUESTIONS:
        Same as above but "content_type": "practice_questions"

    For INFOGRAPHIC:
        Same as above but "content_type": "infographic"

    Note: rag_content_ids refers to the ContentChunk IDs used in the RAG query
    for this subtopic during Phase 12C. These must be passed through from 12C.
    """
    ...
```

### 12E.4 Redis Flag Updates

```python
# At end of successful generate_enriched_study_plan task:
redis_flag_key = f"kaihle:diagnostic:generating:{student_id}:{subject_id}"
await redis.setex(redis_flag_key, 7200, "media_generation")

# At task failure (all retries exhausted):
await redis.setex(redis_flag_key, 7200, "failed")
# Also write StudyPlan with status="generation_failed" in DB
```

### Phase 12E Acceptance Criteria

- [ ] Exactly one `StudyPlan` row created per task invocation (per-subject)
- [ ] Exactly one `StudyPlanCourse` row created per validated spec (one per gap subtopic)
- [ ] `StudyPlanCourse.activity_type` is always `"ai_content"` for these rows
- [ ] `StudyPlanCourse.custom_content` contains `animation_spec`, `infographic_spec`, `practice_questions`, AND `spec_s3_key` after S3 upload
- [ ] `StudyPlan.subject_id` correctly set to the subject of the assessment
- [ ] `StudyPlan.assessment_id` set to the assessment passed in from the chain
- [ ] `StudyPlan.profile_fingerprint` set correctly
- [ ] Spec JSON uploaded to S3 before DB write (if S3 upload fails, retry without partial DB write)
- [ ] All DB writes in a single transaction — no partial study plan possible
- [ ] `GeneratedContent` PENDING rows created for all 3 content types per subtopic
- [ ] Redis flag updated to `"media_generation"` on success, `"failed"` on exhaustion
- [ ] On failure after max_retries: `StudyPlan` with `status="generation_failed"` written; no `StudyPlanCourse` rows written
- [ ] Integration test: mock LLM + mock S3 + real DB; assert all rows created correctly

---

## Phase 13A — Manim Worker: Docker Container + Queue Setup

**Goal:** Create the `manim_worker` container with its own Dockerfile and
`requirements.manim.txt`. Wire it to the `manim_queue`. The `celery_worker` container
must NOT have Manim installed. Only `manim_worker` has it.

**Branch:** `feature/phase-13a-manim-worker-docker`

### 13A.1 Separate Manim Requirements File

**Create: `backend/requirements.manim.txt`**

```
# Manim and voiceover dependencies
# Installed ONLY in manim_worker container — NOT in celery_worker or api containers
manim==0.19.0
manim-voiceover==0.3.6
google-cloud-texttospeech==2.17.2   # Gemini TTS for manim-voiceover
# google-generativeai already in requirements.txt — do not duplicate
```

### 13A.2 Manim Worker Dockerfile

**Create: `backend/Dockerfile.manim`**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# System dependencies for Manim (Cairo, Pango, LaTeX, FFmpeg)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    # Manim core rendering dependencies
    libcairo2-dev \
    libpango1.0-dev \
    libgdk-pixbuf2.0-dev \
    # LaTeX for mathematical typesetting
    texlive \
    texlive-latex-extra \
    texlive-fonts-extra \
    texlive-science \
    dvipng \
    # FFmpeg for video assembly (replaced by PyAV in manim 0.19.0 but keep for compatibility)
    ffmpeg \
    # OpenGL fallback (headless)
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install base dependencies first
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Manim-specific dependencies
COPY requirements.manim.txt .
RUN pip install --no-cache-dir -r requirements.manim.txt

COPY . .

RUN adduser --disabled-password --gecos '' appuser && chown -R appuser /app
USER appuser

# Default command — overridden in docker-compose
CMD ["celery", "-A", "app.worker.celery_app", "worker", \
     "--loglevel=info", "--queues=manim_queue", "--concurrency=2"]
```

> **Why `--concurrency=2`?**
> Cairo rendering is CPU-intensive. Two concurrent Manim renders on a standard CPU pod
> is the safe maximum before renders begin to contend for CPU and slow each other down.
> Increase only if running on a multi-core pod with confirmed headroom.

> **Why NOT GPU / OpenGL?**
> Current deployment is a persistent CPU pod on RunPod. Cairo (CPU) is used.
> Migration path to GPU + OpenGL renderer: change `Dockerfile.manim` base image
> to a CUDA-enabled image, add `xvfb-run` prefix to CMD, change Manim CLI flag
> from default to `--renderer=opengl`. Application code is unchanged.

### 13A.3 docker-compose.yml Addition

Add `manim_worker` service to `docker-compose.yml`:

```yaml
manim_worker:
  build:
    context: ./backend
    dockerfile: Dockerfile.manim
  container_name: kaihle_manim_worker
  restart: unless-stopped
  command: celery -A app.worker.celery_app worker
           --loglevel=info
           --queues=manim_queue
           --concurrency=2
           --hostname=manim_worker@%h
  volumes:
    - ./backend:/app
    - manim_output:/tmp/manim_output    # temp storage for rendered MP4 before S3 upload
  environment:
    - DATABASE_URL=${DATABASE_URL}
    - REDIS_URL=${REDIS_URL}
    - CELERY_BROKER_URL=${CELERY_BROKER_URL}
    - CELERY_RESULT_BACKEND=${CELERY_RESULT_BACKEND}
    - AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
    - AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
    - AWS_REGION=${AWS_REGION}
    - S3_BUCKET_NAME=${S3_BUCKET_NAME}
    - USE_MINIO=${USE_MINIO}
    - MINIO_ENDPOINT=${MINIO_ENDPOINT}
    - GEMINI_API_KEY=${GEMINI_API_KEY}
    - GEMINI_LLM_MODEL=${GEMINI_LLM_MODEL}
    - GEMINI_FLASH_MODEL=${GEMINI_FLASH_MODEL}
    - GEMINI_TTS_VOICE=${GEMINI_TTS_VOICE}
    - MANIM_QUALITY_FLAG=${MANIM_QUALITY_FLAG}
    - MANIM_MAX_FIX_ATTEMPTS=${MANIM_MAX_FIX_ATTEMPTS}
    - ANIMATION_MAX_DURATION_SECONDS=${ANIMATION_MAX_DURATION_SECONDS}
    - ANIMATION_MAX_SCENES=${ANIMATION_MAX_SCENES}
  depends_on:
    db:
      condition: service_healthy
    redis:
      condition: service_healthy
```

Add `manim_output:` to the `volumes:` section.

**Add to `docker-compose.prod.yml`:**

```yaml
manim_worker:
  command: celery -A app.worker.celery_app worker
           --loglevel=warning
           --queues=manim_queue
           --concurrency=2
           --hostname=manim_worker@%h
  volumes:
    - manim_output:/tmp/manim_output
```

### 13A.4 Makefile Additions

```makefile
manim-logs:
    docker-compose logs -f manim_worker

restart-manim:
    docker-compose restart manim_worker

build-manim:
    docker-compose build --no-cache manim_worker
```

### Phase 13A Acceptance Criteria

- [ ] `docker-compose build manim_worker` completes without error (texlive install is slow — expected)
- [ ] `docker-compose up manim_worker` starts the container and connects to Redis broker
- [ ] `manim_worker` registers tasks in `manim_queue` (visible in Flower at `localhost:5555`)
- [ ] `celery_worker` container does NOT have `manim` installed (verify: `docker-compose exec celery_worker python -c "import manim"` raises `ModuleNotFoundError`)
- [ ] `manim_worker` container CAN import manim (`docker-compose exec manim_worker python -c "import manim; print(manim.__version__)"`)
- [ ] `manim_output` named volume mounted in `manim_worker` and writable
- [ ] `manim_queue` appears in Flower UI with `manim_worker` consuming it
- [ ] `celery_worker` does NOT consume `manim_queue` (confirmed in Flower)

---

## Phase 13B — Manim Worker: Animation + Voiceover Celery Task

**Goal:** Implement `tasks.generate_animation_manim`. This task runs exclusively in
`manim_worker`. It uses a 5-stage pipeline: scene planning LLM call, Manim code
generation LLM call, execution + fix loop, Gemini TTS voiceover, and MP4 upload to S3.

**Branch:** `feature/phase-13b-animation-task`

### 13B.1 Task File

**Create: `app/worker/tasks/media_generation/animation.py`**

```python
"""
generate_animation_manim — Manim animation + voiceover generation task.

Queue: manim_queue (consumed ONLY by manim_worker container)
Task name: tasks.generate_animation_manim

This task runs inside the manim_worker container which has Manim installed.
It must NEVER be routed to celery_worker — that container does not have Manim.

Pipeline:
  Stage 1: Load GeneratedContent PENDING row + download spec JSON from S3
  Stage 2: Scene Planner LLM call (Gemini 2.5 Pro)
  Stage 3: Manim Code Generator LLM call (Gemini 2.5 Flash)
  Stage 4: Execute + Fix Loop (subprocess.run, up to MANIM_MAX_FIX_ATTEMPTS)
  Stage 5: manim-voiceover render with Gemini TTS
  Stage 6: Upload MP4 to S3 + mark GeneratedContent COMPLETED
"""
import os
import tempfile
import subprocess
import json
import logging
from pathlib import Path
from uuid import UUID

from app.worker.celery_app import celery_app
from app.services.storage.s3_client import get_s3_client
from app.services.storage.content_metadata_service import ContentMetadataService
from app.services.storage.key_generator import build_s3_key
from app.models.generated_content import ContentType, GenerationStatus
from app.core.config import settings
from app.core.database import SessionLocal

logger = logging.getLogger(__name__)

MANIM_TEMP_DIR = "/tmp/manim_output"
os.makedirs(MANIM_TEMP_DIR, exist_ok=True)


@celery_app.task(
    bind=True,
    max_retries=3,
    name="tasks.generate_animation_manim",
    queue="manim_queue",
    time_limit=600,          # 10 minutes max — 3-minute animations can take 8+ min to render
    soft_time_limit=540,     # 9 minutes — gives task time to clean up temp files
    default_retry_delay=60,  # 1 minute between retries
)
def generate_animation_manim(
    self,
    generated_content_id: str,
    spec_s3_key: str,
) -> None:
    """
    Arguments:
        generated_content_id: UUID string of the GeneratedContent PENDING row
        spec_s3_key:          S3 key of the raw content spec JSON (uploaded in Phase 12E)

    On success: GeneratedContent status → COMPLETED, s3_key set to MP4 key
    On failure after max_retries: GeneratedContent status → FAILED, error_message set
    On SoftTimeLimitExceeded: retry (render may still complete on next attempt)
    """
    ...
```

### 13B.2 Stage 2: Scene Planner LLM Call

```python
SCENE_PLANNER_SYSTEM_PROMPT = """
You are an expert educational animation director for Cambridge curriculum content (Grades 5-12).

Given an animation specification for a subtopic, produce a detailed scene-by-scene plan
optimised for Manim rendering. Each scene must describe:
- What Manim objects to create (equations, graphs, geometric shapes, text, arrows)
- The animation sequence (how objects appear, move, transform)
- The narration text for that scene (verbatim — will be used for TTS voiceover)
- Estimated duration in seconds

Rules:
- Maximum {ANIMATION_MAX_SCENES} scenes total
- Total duration must not exceed {ANIMATION_MAX_DURATION_SECONDS} seconds
- Use standard Manim objects: MathTex, Text, Axes, Circle, Rectangle, Arrow, NumberLine, etc.
- Each scene narration must be a complete, self-contained explanation (30-60 seconds)
- Return ONLY valid JSON. No markdown. No explanation.

JSON Schema:
{
  "scenes": [
    {
      "scene_index": integer,
      "class_name": "SceneName (valid Python identifier, unique per scene)",
      "narration": "Full narration text",
      "duration_seconds": integer,
      "manim_objects": [
        {"type": "MathTex", "content": "3x + 5 = 14", "position": "CENTER"},
        {"type": "Arrow", "from": "left", "to": "right"}
      ],
      "animation_sequence": [
        "Write equation 3x + 5 = 14 at centre",
        "Highlight '5' in red",
        "Transform to show 3x = 9 by subtracting 5 from both sides"
      ]
    }
  ]
}
"""


def call_scene_planner(animation_spec: dict) -> list[dict]:
    """
    Calls Gemini 2.5 Pro with SCENE_PLANNER_SYSTEM_PROMPT.
    Returns list of scene dicts from parsed JSON.
    Raises json.JSONDecodeError on invalid response (triggers retry).
    """
    import google.generativeai as genai
    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel(
        model_name=settings.GEMINI_LLM_MODEL,
        system_instruction=SCENE_PLANNER_SYSTEM_PROMPT.format(
            ANIMATION_MAX_SCENES=settings.ANIMATION_MAX_SCENES,
            ANIMATION_MAX_DURATION_SECONDS=settings.ANIMATION_MAX_DURATION_SECONDS,
        ),
        generation_config=genai.types.GenerationConfig(temperature=0.2, max_output_tokens=4096),
    )
    user_prompt = json.dumps(animation_spec, indent=2)
    response = model.generate_content(user_prompt)
    raw = response.text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw)["scenes"]
```

### 13B.3 Stage 3: Manim Code Generator LLM Call

```python
MANIM_CODE_GEN_SYSTEM_PROMPT = """
You are an expert Manim (Community Edition v0.19.0) Python code generator.

Given a scene plan with narration, generate EXECUTABLE Manim Python code for each scene.
Each scene becomes a separate Python class inheriting from Scene.

Critical rules:
- Import: from manim import *
- Each class must have a construct(self) method
- Use ONLY these Manim objects (they are confirmed available in v0.19.0):
    MathTex, Tex, Text, VGroup, Circle, Square, Rectangle, Triangle,
    Arrow, Line, Dot, NumberLine, Axes, ParametricFunction,
    Create, Write, FadeIn, FadeOut, Transform, ReplacementTransform,
    MoveToTarget, Indicate, Circumscribe, SurroundingRectangle,
    self.play(), self.wait(), self.add(), self.remove()
- Do NOT use: CapsuleGeometry, Flash (use Indicate instead), AnimationGroup unless necessary
- Mathematical expressions: use MathTex with LaTeX syntax, e.g. MathTex(r"3x + 5 = 14")
- Text: use Text() for plain text, Tex() for LaTeX text with words
- Colours: RED, BLUE, GREEN, YELLOW, WHITE, BLACK, ORANGE, PURPLE (all uppercase)
- Positions: UP, DOWN, LEFT, RIGHT, CENTER, UR, UL, DR, DL (all uppercase)
- Scale: use .scale(factor) method
- Do NOT use voiceover syntax in this code — voiceover is added separately
- Each class construct() method must end with self.wait(1)
- Return ONLY valid Python code. No markdown. No explanation. No imports outside the code block.
"""

def call_code_generator(scenes: list[dict]) -> str:
    """
    Calls Gemini 2.5 Flash (faster, cheaper) for code generation.
    Returns full Python code string for all scenes combined.
    Raises on failure.
    """
    import google.generativeai as genai
    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel(
        model_name=settings.GEMINI_FLASH_MODEL,  # 2.5 Flash for code gen
        system_instruction=MANIM_CODE_GEN_SYSTEM_PROMPT,
        generation_config=genai.types.GenerationConfig(temperature=0.1, max_output_tokens=8192),
    )
    user_prompt = (
        "Generate Manim Python code for the following scenes:\n\n"
        + json.dumps(scenes, indent=2)
    )
    response = model.generate_content(user_prompt)
    code = response.text.strip()
    # Strip markdown if present
    if code.startswith("```"):
        lines = code.split("\n")
        code = "\n".join(lines[1:-1]) if lines[-1] == "```" else "\n".join(lines[1:])
    return code
```

### 13B.4 Stage 4: Execute + Fix Loop

```python
def execute_manim_with_fixes(
    code: str,
    scene_class_names: list[str],
    work_dir: str,
    max_attempts: int,
) -> list[Path]:
    """
    Writes code to a temp .py file, runs manim CLI, retries with error feedback.

    Arguments:
        code:               Full Python code string for all scenes
        scene_class_names:  List of class names to render (one per scene)
        work_dir:           Temp directory for this task invocation
        max_attempts:       MANIM_MAX_FIX_ATTEMPTS (default: 5)

    Returns list of Path objects pointing to rendered MP4 files (one per scene).
    Raises ManimExecutionError if all attempts fail.

    Algorithm:
        attempt = 1
        while attempt <= max_attempts:
            1. Write code to {work_dir}/scene.py
            2. For each class_name in scene_class_names:
               Run: manim {MANIM_QUALITY_FLAG} {work_dir}/scene.py {class_name}
                    --output_file {class_name}.mp4
                    --media_dir {work_dir}/media
                    --disable_caching
               (--disable_caching REQUIRED when using manim-voiceover)
            3. If ALL renders succeed (returncode == 0): return list of MP4 paths
            4. If any render fails:
               - Collect stderr from failed renders
               - Build error feedback prompt:
                   "The following Manim code produced these errors:\n{code}\n\nErrors:\n{stderr}\n
                    Fix the code to resolve ALL errors. Return ONLY corrected Python code."
               - Call Gemini 2.5 Flash with error feedback (temperature=0.1)
               - Replace code with corrected version
               - attempt += 1
        raise ManimExecutionError(f"Failed after {max_attempts} attempts")

    Important: Each Manim subprocess call uses:
        subprocess.run(
            ["manim", quality_flag, scene_file, class_name, ...],
            capture_output=True,
            text=True,
            timeout=120,   # 2 min per scene max
            cwd=work_dir,
        )
    """
    ...


class ManimExecutionError(Exception):
    """Raised when Manim code execution fails after all retry attempts."""
    pass
```

### 13B.5 Stage 5: Voiceover + Final MP4 Assembly

```python
def assemble_with_voiceover(
    scene_mp4_paths: list[Path],
    scenes: list[dict],           # scene dicts from Stage 2 (contain narration text)
    work_dir: str,
    subtopic_name: str,
) -> Path:
    """
    Adds Gemini TTS voiceover to rendered scenes and assembles final MP4.

    Strategy:
        manim-voiceover integrates TTS at render time, not post-production.
        Since Stage 4 already rendered scenes WITHOUT voiceover (for execution validation),
        we re-render them WITH voiceover by generating a voiceover-enabled Manim script.

    Steps:
        1. For each scene, call Gemini TTS to synthesise narration → MP3 bytes
           Save as {work_dir}/audio/{class_name}.mp3
        2. Generate new Python script using manim-voiceover pattern:
           - Import: from manim_voiceover import VoiceoverScene
           - Import: from manim_voiceover.services.gtts import GTTSService
             (or custom Gemini TTS adapter — see below)
           - Each scene class inherits from VoiceoverScene
           - Wrap each animation block with: with self.voiceover(text="...") as tracker:
           - Animation timing driven by tracker.duration
        3. Re-render with: manim {quality_flag} voiceover_scene.py {class_name} --disable_caching
        4. Concatenate all scene MP4s using ffmpeg:
           ffmpeg -f concat -safe 0 -i filelist.txt -c copy {work_dir}/final.mp4
        5. Return Path to final.mp4

    Gemini TTS adapter for manim-voiceover:
        manim-voiceover supports custom TTS services via AbstractSpeechService.
        Create a minimal GeminiTTSService adapter that calls:
            genai.GenerativeModel(settings.GEMINI_LLM_MODEL)
            model.generate_content with audio output config
        This adapter is defined inline in this task file (not a separate service class)
        because it is only used here.

    Error handling:
        TTS failure for one scene: use empty audio (silent voiceover) and log WARNING.
        FFmpeg concatenation failure: raise (triggers Celery retry).
    """
    ...
```

### 13B.6 Stage 6: S3 Upload + Completion

```python
def upload_mp4_and_complete(
    final_mp4_path: Path,
    generated_content_id: UUID,
    s3_key: str,
    metadata: dict,
) -> None:
    """
    Reads MP4 bytes from final_mp4_path.
    Uploads to S3 with content_type="video/mp4".
    Calls ContentMetadataService.mark_completed().
    Deletes work_dir temp files.
    """
    ...
```

### Phase 13B Acceptance Criteria

- [ ] Task is registered under name `tasks.generate_animation_manim` in `manim_queue`
- [ ] Stage 2 (scene planner) uses Gemini 2.5 Pro; Stage 3 (code gen) uses Gemini 2.5 Flash
- [ ] Execute + fix loop runs up to `MANIM_MAX_FIX_ATTEMPTS` times before raising `ManimExecutionError`
- [ ] `--disable_caching` flag always passed to manim CLI (required for voiceover)
- [ ] Each subprocess call has a `timeout=120` to prevent hung renders
- [ ] `SoftTimeLimitExceeded` caught and re-raised as Celery retry
- [ ] Final MP4 uploaded to correct S3 key (ContentType.ANIMATION)
- [ ] `GeneratedContent` transitions PENDING → COMPLETED with `s3_key` and `file_size_bytes` set
- [ ] Temp files in `work_dir` deleted after upload regardless of success/failure (use `try/finally`)
- [ ] On `ManimExecutionError` after max_retries: `GeneratedContent` marked FAILED
- [ ] Unit tests: mock all LLM calls and subprocess; verify stage transitions and S3 upload call

---

## Phase 13C — Media Worker: Practice Questions Task

**Goal:** Extract the pre-validated practice questions from the spec JSON in S3,
format them as the final storage format, and upload as a JSON file to S3.
This task requires no LLM call — questions already exist in the spec.

**Branch:** `feature/phase-13c-practice-questions-task`

### 13C.1 Task

**Create: `app/worker/tasks/media_generation/practice_questions.py`**

```python
"""
generate_practice_questions — extracts and stores practice questions from spec.

Queue: default (consumed by celery_worker container)
Task name: tasks.generate_practice_questions
No LLM call required. Questions already validated in Phase 12D.
"""

@celery_app.task(
    bind=True,
    max_retries=3,
    name="tasks.generate_practice_questions",
    queue="default",
    time_limit=60,
    default_retry_delay=15,
)
def generate_practice_questions(
    self,
    generated_content_id: str,
    spec_s3_key: str,
) -> None:
    """
    Pipeline:
        1. Load GeneratedContent row; verify status == PENDING
        2. Download spec JSON from S3 (spec_s3_key)
        3. Extract spec["practice_questions"] array
        4. Re-validate each question:
           - difficulty must be Integer 1–5 (clamp if needed)
           - correct_answer must match one of options exactly
           - question_text must be non-empty
           - Skip invalid questions (do not fail task)
        5. Build final JSON:
           {
             "subtopic_id": str,
             "subtopic_name": str,
             "subject": str,
             "grade_code": str,
             "questions": [...validated questions...],
             "total": N,
             "generated_at": "ISO8601"
           }
        6. Upload to S3:
           Key: build_s3_key(ContentType.PRACTICE_QUESTIONS, ...)
           Content-Type: application/json
        7. Mark GeneratedContent COMPLETED

    Error handling:
        S3 download failure → retry (spec may not yet be uploaded)
        json.JSONDecodeError from S3 → mark FAILED immediately (no retry)
        S3 upload failure → retry
        If fewer than 5 valid questions remain after re-validation:
            Mark FAILED with error_message="Insufficient valid questions after re-validation"
    """
    ...
```

### Final Practice Questions JSON Format

```json
{
  "subtopic_id": "uuid-string",
  "subtopic_name": "Linear Equations",
  "subject": "Math",
  "grade_code": "grade8",
  "questions": [
    {
      "question_number": 1,
      "difficulty": 2,
      "question_text": "Solve for x: 3x + 5 = 14",
      "options": ["x = 1", "x = 2", "x = 3", "x = 4"],
      "correct_answer": "x = 3",
      "explanation": "Subtract 5 from both sides: 3x = 9. Divide by 3: x = 3.",
      "topic_tested": "Solving one-step linear equations"
    }
  ],
  "total": 10,
  "generated_at": "2026-02-23T10:00:00Z"
}
```

### Phase 13C Acceptance Criteria

- [ ] Task registered under `tasks.generate_practice_questions` in `default` queue
- [ ] Downloaded spec JSON correctly parsed; `practice_questions` array extracted
- [ ] Re-validation clamps difficulty to Integer 1–5 — never rejects on difficulty alone
- [ ] Invalid questions (bad `correct_answer`, empty `question_text`) are skipped with WARNING log
- [ ] Task marks FAILED (not retry) if result is `json.JSONDecodeError` from S3 content
- [ ] Task marks FAILED if fewer than 5 valid questions remain
- [ ] Final JSON uploaded to `ContentType.PRACTICE_QUESTIONS` S3 key
- [ ] `GeneratedContent` transitions PENDING → COMPLETED with correct `s3_key`

---

## Phase 13D — Media Worker: Infographic Task (Gemini Imagen 3)

**Goal:** Generate an infographic image from the `infographic_spec` in the content spec
using Gemini Imagen 3 API. Upload PNG to S3.

**Branch:** `feature/phase-13d-infographic-task`

### 13D.1 Task

**Create: `app/worker/tasks/media_generation/infographic.py`**

```python
"""
generate_infographic — generates an educational infographic PNG via Gemini Imagen 3.

Queue: default (consumed by celery_worker container)
Task name: tasks.generate_infographic
"""

@celery_app.task(
    bind=True,
    max_retries=3,
    name="tasks.generate_infographic",
    queue="default",
    time_limit=120,
    default_retry_delay=30,
)
def generate_infographic(
    self,
    generated_content_id: str,
    spec_s3_key: str,
) -> None:
    """
    Pipeline:
        1. Load GeneratedContent row; verify status == PENDING
        2. Download spec JSON from S3
        3. Extract spec["infographic_spec"]
        4. Build image generation prompt via build_infographic_prompt()
        5. Call Gemini Imagen 3 API
        6. Upload PNG bytes to S3
        7. Mark GeneratedContent COMPLETED
    """
    ...


def build_infographic_prompt(infographic_spec: dict, grade_code: str, subject: str) -> str:
    """
    Converts infographic_spec into a Gemini Imagen 3 image prompt.

    Structure:
        "Educational infographic titled '{title}' for Cambridge {grade} {subject} students.
         {layout} layout.
         Sections:
         1. {heading1}: {body1}
         2. {heading2}: {body2}
         ...
         Visual style: {visual_style}.
         Requirements: legible text at all sizes, clear section separation,
         educational diagram style, no watermarks, no decorative borders,
         suitable for Grade {N} students."

    Truncation: if prompt exceeds 4000 characters, truncate section bodies
    (not headings) starting from the last section until under limit.

    Never truncate: title, grade reference, visual style, requirements.
    """
    ...


def call_gemini_imagen(prompt: str) -> bytes:
    """
    Calls Gemini Imagen 3 via google-generativeai SDK.
    Returns raw PNG bytes.
    Raises on API error (triggers Celery retry).

    Config:
        model: settings.GEMINI_IMAGE_MODEL ("imagen-3.0-generate-002")
        number_of_images: 1
        aspect_ratio: "9:16" (portrait — better for educational infographics)
        safety_filter_level: "block_some"
    """
    import google.generativeai as genai
    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.ImageGenerationModel(settings.GEMINI_IMAGE_MODEL)
    result = model.generate_images(
        prompt=prompt,
        number_of_images=1,
        aspect_ratio="9:16",
        safety_filter_level="block_some",
    )
    return result.images[0]._pil_image.tobytes("png", "png")
```

### Phase 13D Acceptance Criteria

- [ ] Task registered under `tasks.generate_infographic` in `default` queue
- [ ] `build_infographic_prompt` truncates section bodies (not titles/headings) when over 4000 chars
- [ ] `call_gemini_imagen` returns PNG bytes; any API error triggers Celery retry
- [ ] PNG uploaded to `ContentType.INFOGRAPHIC` S3 key with `content_type="image/png"`
- [ ] `GeneratedContent` transitions PENDING → COMPLETED with `file_size_bytes` set
- [ ] On Imagen safety filter rejection: mark FAILED immediately with descriptive error_message (no retry — safety block is deterministic)

---

## Phase 14A — Content Reuse: Profile Fingerprint Service

**Goal:** Implement the deterministic profile fingerprint. Two students whose learning
profiles and knowledge gaps fall into the same fingerprint will share S3 assets.

**Branch:** `feature/phase-14a-profile-fingerprint`

### 14A.1 Fingerprint Service

**Create: `app/services/storage/profile_fingerprint.py`**

```python
"""
Profile fingerprinting for content reuse.

A profile fingerprint is a 64-char SHA-256 hash derived from the subset of
student + knowledge profile attributes that determine what content is appropriate.

Two students with the same fingerprint receive identical generated content.
The fingerprint intentionally ignores minor score differences by discretising
mastery_level into bands.

Fingerprint inputs (all required):
    grade_code:        str  e.g. "grade8"
    curriculum_id:     str  UUID string
    subject_code:      str  e.g. "math"
    gap_subtopics:     list of {"subtopic_id": str, "mastery_level": float}
    learning_style:    str  from StudentProfile.learning_profile["learning_style"]
                            use "general" if absent or None

Mastery bands (discretisation prevents trivial score differences breaking reuse):
    mastery_level < 0.40              → band = "beginning"
    0.40 <= mastery_level < 0.60      → band = "developing"
    0.60 <= mastery_level < 0.75      → band = "approaching"
    mastery_level >= 0.75             → band = "strong"
    (note: "strong" subtopics are not knowledge gaps — should not appear here,
     but handle gracefully by mapping to "strong" band)
"""
import hashlib
import json


MASTERY_BANDS = [
    (0.40, "beginning"),
    (0.60, "developing"),
    (0.75, "approaching"),
]


def mastery_band(mastery_level: float) -> str:
    """
    Discretises a mastery_level float into a band string.
    mastery_level must be in range 0.0–1.0.
    """
    for threshold, band in MASTERY_BANDS:
        if mastery_level < threshold:
            return band
    return "strong"


def build_profile_fingerprint(
    grade_code: str,
    curriculum_id: str,
    subject_code: str,
    gap_subtopics: list[dict],  # [{"subtopic_id": str, "mastery_level": float}, ...]
    learning_style: str | None,
) -> str:
    """
    Returns 64-char hex SHA-256 fingerprint.

    gap_subtopics is sorted by subtopic_id before hashing to ensure
    that different orderings of the same gaps produce the same fingerprint.

    learning_style: use "general" if None or empty string.
    """
    inputs = {
        "grade_code":    grade_code,
        "curriculum_id": curriculum_id,
        "subject_code":  subject_code,
        "gaps": sorted(
            [
                {
                    "subtopic_id": g["subtopic_id"],
                    "band": mastery_band(g["mastery_level"]),
                }
                for g in gap_subtopics
            ],
            key=lambda x: x["subtopic_id"],
        ),
        "learning_style": learning_style or "general",
    }
    canonical = json.dumps(inputs, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
```

### Phase 14A Acceptance Criteria

- [ ] `mastery_band(0.39)` → `"beginning"`, `mastery_band(0.40)` → `"developing"` (boundary test)
- [ ] `mastery_band(0.59)` → `"developing"`, `mastery_band(0.60)` → `"approaching"` (boundary test)
- [ ] `mastery_band(0.74)` → `"approaching"`, `mastery_band(0.75)` → `"strong"` (boundary test)
- [ ] Same inputs in different `gap_subtopics` order → same fingerprint
- [ ] `learning_style=None` and `learning_style="general"` → same fingerprint
- [ ] Different `grade_code` → different fingerprint
- [ ] Same subtopics with mastery 0.28 and 0.35 (both "beginning") → same fingerprint
- [ ] Same subtopics with mastery 0.39 and 0.40 (different bands) → different fingerprint
- [ ] Result is always a 64-char lowercase hex string
- [ ] Deterministic across Python process restarts (no random/time-based inputs)

---

## Phase 14B — Content Reuse: Pre-Generation Lookup + Dispatch

**Goal:** Before dispatching any media generation task, check if a COMPLETED
`GeneratedContent` row exists for the same `profile_fingerprint + subtopic_id + content_type`.
If so, mark the new row as REUSED and skip generation entirely.

**Branch:** `feature/phase-14b-content-reuse-dispatch`

### 14B.1 Content Reuse Service

**Create: `app/services/storage/content_reuse_service.py`**

```python
"""
ContentReuseService — implements the pre-generation deduplication check.

Uses idx_gc_fingerprint_type_subtopic index for fast lookup.
Called from generate_enriched_study_plan task (Phase 12E).
"""
from uuid import UUID
from typing import Callable
from app.models.generated_content import GeneratedContent, ContentType, GenerationStatus
from app.services.storage.content_metadata_service import ContentMetadataService
import logging

logger = logging.getLogger(__name__)


class ContentReuseService:

    def __init__(self, db_session, metadata_service: ContentMetadataService):
        self.db = db_session
        self.metadata_service = metadata_service

    async def find_reusable_content(
        self,
        profile_fingerprint: str,
        subtopic_id: UUID,
        content_type: ContentType,
    ) -> GeneratedContent | None:
        """
        Queries generated_content WHERE:
            profile_fingerprint = :fingerprint
            AND subtopic_id = :subtopic_id
            AND content_type = :content_type
            AND status = 'completed'

        Returns the most recently completed row (ORDER BY completed_at DESC LIMIT 1),
        or None if no match.

        Uses idx_gc_fingerprint_type_subtopic index.
        """
        ...

    async def reuse_or_dispatch(
        self,
        new_content_id: UUID,
        profile_fingerprint: str,
        subtopic_id: UUID,
        content_type: ContentType,
        spec_s3_key: str,
        dispatch_task_fn: Callable,
    ) -> bool:
        """
        Central dispatch decision point. Called once per content item.

        Arguments:
            new_content_id:    UUID of the newly created GeneratedContent PENDING row
            profile_fingerprint: fingerprint of current student's subject profile
            subtopic_id:       subtopic this content is for
            content_type:      which media type
            spec_s3_key:       S3 key of the raw spec JSON (passed to task if dispatched)
            dispatch_task_fn:  the Celery task's .delay() or .apply_async() callable

        Returns:
            True  — content was reused (existing S3 asset linked, task NOT dispatched)
            False — no reusable content found (task dispatched)

        Algorithm:
            1. Call find_reusable_content(profile_fingerprint, subtopic_id, content_type)
            2. If found:
                a. Call metadata_service.mark_reused(new_content_id, found.id, found.s3_key)
                b. Log: INFO "Reusing {content_type} for subtopic {subtopic_id} "
                         "from content_id {found.id} (fingerprint match)"
                c. Return True
            3. If not found:
                a. Call dispatch_task_fn(str(new_content_id), spec_s3_key)
                b. Log: INFO "Dispatching {content_type} generation for subtopic {subtopic_id}"
                c. Return False

        Note: This method does NOT check prompt_hash. It checks profile_fingerprint.
        Two students with the same fingerprint ALWAYS reuse — even if their RAG context
        IDs are slightly different (fingerprint is the coarser, higher-level match).
        prompt_hash is used for the S3 file naming (Phase 11C) to prevent overwriting
        different content with the same filename. These are two separate mechanisms.
        """
        ...
```

### Phase 14B Acceptance Criteria

- [ ] `find_reusable_content` queries using `idx_gc_fingerprint_type_subtopic` (verify via EXPLAIN)
- [ ] Returns most recently COMPLETED row when multiple matches exist
- [ ] Returns `None` when no COMPLETED row exists (PENDING/FAILED rows do NOT match)
- [ ] `reuse_or_dispatch` returns `True` and calls `mark_reused` when match found
- [ ] `reuse_or_dispatch` returns `False` and calls `dispatch_task_fn` when no match
- [ ] When reused: `GeneratedContent.s3_key` = original row's `s3_key` (not None)
- [ ] When reused: `GeneratedContent.reused_from_id` = original row's `id`
- [ ] Integration test: Student A generates animation for subtopic X. Student B with same fingerprint requests same subtopic X → animation is REUSED, task NOT dispatched
- [ ] Integration test: Student A and B have different fingerprints → both dispatch independently

---

## Phase 15 — API Layer: Content Delivery Endpoints

**Goal:** Add two new endpoints to the existing `diagnostic.py` router that return
all generated content status and presigned S3 URLs for a student's study plans.

**Branch:** `feature/phase-15-content-api`

### 15.1 New Endpoints

Add to **existing file: `app/api/v1/routers/diagnostic.py`**

| Method | Path | Description |
|---|---|---|
| `GET` | `/diagnostic/{student_id}/study-plans` | All study plans for student (one per completed subject) |
| `GET` | `/diagnostic/{student_id}/study-plans/{study_plan_id}/content` | All generated content + presigned URLs for one study plan |
| `GET` | `/diagnostic/{student_id}/study-plans/{study_plan_id}/content/{subtopic_id}` | Content for one subtopic |

### 15.2 New Pydantic Schemas

Add to **existing file: `app/schemas/diagnostic.py`**

```python
from app.models.generated_content import ContentType, GenerationStatus

class GeneratedContentItem(BaseModel):
    content_id: UUID
    content_type: ContentType
    status: GenerationStatus
    url: str | None            # presigned S3 URL; None if not COMPLETED or REUSED
    url_expires_at: str | None # ISO8601; None if url is None
    reused: bool               # True if status == REUSED
    file_size_bytes: int | None

    model_config = ConfigDict(from_attributes=True)


class SubtopicContentBundle(BaseModel):
    subtopic_id: UUID
    subtopic_name: str
    subject: str
    priority: str
    week: int
    day: int
    animation: GeneratedContentItem
    infographic: GeneratedContentItem
    practice_questions: GeneratedContentItem

    model_config = ConfigDict(from_attributes=True)


class StudyPlanContentResponse(BaseModel):
    student_id: UUID
    study_plan_id: UUID
    subject: str
    generation_status: str     # redis flag value: "generating"|"study_plan"|"media_generation"|"complete"|"failed"
    subtopics: list[SubtopicContentBundle]

    model_config = ConfigDict(from_attributes=True)


class StudentStudyPlansResponse(BaseModel):
    student_id: UUID
    study_plans: list[StudyPlanSummary]

    model_config = ConfigDict(from_attributes=True)


class StudyPlanSummary(BaseModel):
    study_plan_id: UUID
    subject_id: UUID
    subject_name: str
    status: str
    total_weeks: int | None
    generation_status: str    # from redis flag
    created_at: str

    model_config = ConfigDict(from_attributes=True)
```

### 15.3 Endpoint Logic

```python
@router.get("/{student_id}/study-plans")
async def get_student_study_plans(
    student_id: UUID,
    current_user = Depends(get_current_user),
    db = Depends(get_db),
    redis = Depends(get_redis),
) -> StudentStudyPlansResponse:
    """
    Returns all StudyPlan rows for the student, one per subject.

    Auth rules (enforced — not assumed):
        - If current_user is a student: student_id must equal current_user.student_profile.id
        - If current_user is a parent: student_id must belong to one of their children
        - Any other case: raise 403

    For each plan, reads Redis flag:
        kaihle:diagnostic:generating:{student_id}:{subject_id}
    to determine generation_status.
    """
    ...


@router.get("/{student_id}/study-plans/{study_plan_id}/content")
async def get_study_plan_content(
    student_id: UUID,
    study_plan_id: UUID,
    current_user = Depends(get_current_user),
    db = Depends(get_db),
    redis = Depends(get_redis),
) -> StudyPlanContentResponse:
    """
    Returns all GeneratedContent rows for the study plan, grouped by subtopic.
    Generates presigned S3 URLs for COMPLETED and REUSED rows.

    Presigned URL generation is permitted in the API layer because:
        - It is a read-only metadata operation
        - No data is transferred through the API server
        - No LLM is called
        - It is fast (< 10ms)

    For PENDING rows: url=None, url_expires_at=None
    For FAILED rows:  url=None, url_expires_at=None
    For COMPLETED/REUSED rows: url=presigned_url, url_expires_at=now+TTL

    Auth rules: same as get_student_study_plans.

    While generation_status != "complete", the frontend polls this endpoint
    every 8 seconds. Partial results (some COMPLETED, some PENDING) are
    returned without waiting for all content to finish.

    Returns 404 if study_plan_id does not belong to student_id.
    Returns 202 with generation_status="generating" if study plan itself
    is not yet written to DB (Redis flag = "reports" or "study_plan").
    """
    ...


@router.get("/{student_id}/study-plans/{study_plan_id}/content/{subtopic_id}")
async def get_subtopic_content(
    student_id: UUID,
    study_plan_id: UUID,
    subtopic_id: UUID,
    current_user = Depends(get_current_user),
    db = Depends(get_db),
) -> SubtopicContentBundle:
    """
    Returns content bundle for a single subtopic.
    Returns 404 if subtopic_id not found in this study_plan_id.
    Auth rules: same as above.
    """
    ...
```

### Phase 15 Acceptance Criteria

- [ ] Students cannot access other students' content — 403 returned (not 404)
- [ ] Parents can access content for their own children only — 403 for others
- [ ] COMPLETED/REUSED rows return valid presigned URLs (test: URL is fetchable)
- [ ] PENDING rows return `url=null`, `url_expires_at=null` (not error, not 404)
- [ ] FAILED rows return `url=null` (not error)
- [ ] `reused=true` on REUSED rows; `reused=false` on COMPLETED rows
- [ ] `get_study_plan_content` returns 202 if study plan not yet in DB (Redis flag = "reports" | "study_plan")
- [ ] `get_subtopic_content` returns 404 for subtopic_id not in this study plan
- [ ] `get_study_plan_content` returns 404 if `study_plan_id` does not belong to `student_id`
- [ ] All three endpoints visible in OpenAPI at `/docs`
- [ ] `url_expires_at` is set to `utcnow + S3_PRESIGNED_URL_TTL_SECONDS` in ISO8601 format

---

## Phase 16 — Frontend: Full Diagnostic Flow + Multi-Modal Study Plan View + Tests

**Goal:** This phase covers everything from Phase 8 (diagnostic flow), Phase 9
(testing), and the new multi-modal study plan view. All frontend work is in one phase.

**Branch:** `feature/phase-16-frontend`

### 16.1 New Dependencies

```bash
npm install @tanstack/react-query
npm install react-player         # for MP4 animation playback
```

### 16.2 Routes

```
/diagnostic                                       → DiagnosticHub
/diagnostic/:assessmentId                         → DiagnosticSession
/diagnostic/report                                → DiagnosticReport
/diagnostic/study-plans                           → StudyPlansHub (lists all 4 subjects)
/diagnostic/study-plans/:studyPlanId              → StudyPlanView
/diagnostic/study-plans/:studyPlanId/content      → StudyPlanContentView (multi-modal)
```

### 16.3 Pages

**`DiagnosticHub`:**
- Shows 4 subject cards. Each card shows subject name, question progress, and status.
- Polls `GET /diagnostic/status/{student_id}` every 8s while any subject is `in_progress`.
- Each subject card shows study plan generation status once that subject completes
  (reads per-subject Redis flag via status endpoint).
- Links to `DiagnosticSession` for in-progress subjects.
- Links to `StudyPlanView` for subjects where generation_status = "complete".

**`DiagnosticSession`:**
- Adaptive question flow. State machine:
  ```
  loading → question_displayed → option_selected → submitting
         → feedback_shown → loading_next → question_displayed
                                         → session_complete → DiagnosticHub
  ```
- Components:
  - `QuestionProgressBar` — "Question 6 of 25 · Subtopic: Linear Equations"
  - `DifficultyIndicator` — 5 dots, filled up to current difficulty
  - `QuestionCard` + `OptionButton` (locks immediately on select — no double-submit)
  - `SubmitButton` (disabled until option selected)
  - `FeedbackFlash` — shows ✓ or ✗ briefly (no correct answer shown during session)
- Session resumes after page refresh (Redis state preserved — fetch current question on mount)

**`DiagnosticReport`:**
- Polls `GET /diagnostic/{student_id}/report` every 5s while status = 202.
- Per-subject collapsible cards showing:
  - `MasteryRing` (circular progress indicator, 0–100%)
  - `TopicBreakdownTable` with difficulty path per subtopic (e.g. 3→4→5→4→5)
  - `KnowledgeGapBadge` (🔴 high / 🟡 medium / 🟢 low)
  - `StrengthsList`
- Shows "Study Plan Ready" CTA per subject when that subject's generation_status = "complete"

**`StudyPlansHub`:**
- Lists all 4 subjects with their study plan generation status.
- Each subject links to its `StudyPlanView`.
- Shows skeleton loaders for subjects still generating.

**`StudyPlanView`:**
- Week accordion (Week 1 open by default).
- Each day shows a `CourseItem` (subtopic name, duration, activity type badge).
- Clicking a `CourseItem` navigates to `StudyPlanContentView` for that subtopic.

**`StudyPlanContentView`:**
- Polls `GET /study-plans/{study_plan_id}/content/{subtopic_id}` every 8s while any item is PENDING.
- Shows `ContentGenerationBanner` while any content is PENDING.
- `SubtopicContentCard` contains:
  - `ContentStatusBadge` (PENDING/COMPLETED/FAILED/REUSED) per content type
  - `AnimationPlayer` — wraps ReactPlayer; shows when animation COMPLETED/REUSED
  - `InfographicViewer` — `<img>` with presigned URL; click opens full-screen modal
  - `PracticeQuestionsPanel` — interactive Q&A (local state only — no API calls)

### 16.4 React Query Hooks

**Create: `src/hooks/diagnostic/`**

```javascript
// useDiagnosticStatus.js
// Polls GET /diagnostic/status/{studentId} every 8s while any subject in_progress
export function useDiagnosticStatus(studentId) { ... }

// useInitializeDiagnostic.js
// Mutation: POST /diagnostic/initialize
export function useInitializeDiagnostic() { ... }

// useNextQuestion.js
// On-demand fetch: GET /diagnostic/{assessmentId}/next-question
export function useNextQuestion(assessmentId) { ... }

// useSubmitAnswer.js
// Mutation: POST /diagnostic/{assessmentId}/answer
export function useSubmitAnswer() { ... }

// useDiagnosticReport.js
// Polls: GET /diagnostic/{studentId}/report every 5s while 202
export function useDiagnosticReport(studentId) { ... }

// useStudyPlans.js
// Fetch: GET /diagnostic/{studentId}/study-plans (no polling — stable after generation)
export function useStudyPlans(studentId) { ... }

// useStudyPlanContent.js
// Polls GET /study-plans/{studyPlanId}/content every 8s while any item PENDING
export function useStudyPlanContent(studyPlanId) {
    return useQuery({
        queryKey: ["studyPlanContent", studyPlanId],
        queryFn: () => api.get(`/diagnostic/${studentId}/study-plans/${studyPlanId}/content`),
        refetchInterval: (data) =>
            data?.subtopics?.every(s =>
                ["completed","failed","reused"].includes(s.animation.status) &&
                ["completed","failed","reused"].includes(s.infographic.status) &&
                ["completed","failed","reused"].includes(s.practice_questions.status)
            ) ? false : 8000,
    });
}

// useSubtopicContent.js
// On-demand fetch: GET /study-plans/{studyPlanId}/content/{subtopicId}
export function useSubtopicContent(studyPlanId, subtopicId) { ... }
```

### 16.5 PracticeQuestionsPanel Behaviour

- Questions displayed one at a time.
- Student selects an option from 4 choices.
- On submit: reveals ✓/✗, shows `explanation` text, enables "Next Question" button.
- Score tracked in React `useState`: `{correct: N, total: M}`.
- Final screen shows score: "7 / 10 correct" with option to restart.
- **No localStorage.** All state in React `useState`. Resets on page reload.
- **No API calls** during Q&A — all data loaded from the initial content fetch.

### 16.6 Testing Requirements (Phase 9 Folded In)

**Backend tests (add to `tests/test_diagnostic/`):**

```
test_rag_query_service.py         # Phase 10D: similarity ranking, threshold, zero-result case
test_embedding_service.py         # Phase 10C: batch splitting, API error handling
test_s3_client.py                 # Phase 11A: upload, download, presign, exists, NotFoundError
test_content_metadata_service.py  # Phase 11B: lifecycle transitions, invalid transition error
test_key_generator.py             # Phase 11C: determinism, boundary inputs, all content types
test_profile_fingerprint.py       # Phase 14A: boundary mastery bands, order independence
test_content_reuse_service.py     # Phase 14B: reuse found, no reuse, dispatch called once
test_enriched_study_plan.py       # Phase 12C–12E: mocked LLM + S3 + real DB
test_animation_task.py            # Phase 13B: mocked subprocess + LLM + S3
test_practice_questions_task.py   # Phase 13C: extraction, re-validation, min-questions check
test_infographic_task.py          # Phase 13D: prompt truncation, API error → retry
test_content_api.py               # Phase 15: auth rules, 202 while generating, presigned URLs
test_response_handler_v2.py       # Phase 12B: per-subject trigger, Redis guard, double-dispatch
```

**Frontend tests:**

```
DiagnosticHub.test.jsx          # status polling, subject card states, auto-redirect
DiagnosticSession.test.jsx      # state machine transitions, double-submit prevention
DiagnosticReport.test.jsx       # 202 polling, mastery ring rendering
StudyPlanContentView.test.jsx   # polling stops when all complete, PENDING skeleton, FAILED state
PracticeQuestionsPanel.test.jsx # score tracking, no localStorage, no API calls
AnimationPlayer.test.jsx        # renders with presigned URL, handles null url
InfographicViewer.test.jsx      # full-screen modal, handles null url
```

**Coverage requirement:** ≥ 90% for all new backend and frontend code.

### Phase 16 Acceptance Criteria

**Diagnostic Flow (Phase 8 criteria):**
- [ ] `DiagnosticHub` shows correct per-subject status for all 4 subjects
- [ ] `DifficultyIndicator` updates after each answer submission
- [ ] `OptionButton` locks immediately on selection — double-submit impossible
- [ ] Session resumes correctly after page refresh (Redis state used)
- [ ] Difficulty path (e.g. 3→4→5→4→5) shown per subtopic in `DiagnosticReport`
- [ ] `DiagnosticReport` polls until ready, renders without manual refresh
- [ ] All pages mobile-responsive (tested at 375px and 768px widths)
- [ ] All loading, error, and empty states handled for every page

**Multi-Modal View:**
- [ ] `ContentGenerationBanner` shows while any content item is PENDING; hides when all done
- [ ] `AnimationPlayer` plays MP4 from presigned URL; shows skeleton when PENDING
- [ ] `InfographicViewer` renders PNG; click opens full-screen modal
- [ ] `PracticeQuestionsPanel` score tracking works; `localStorage` is NEVER accessed
- [ ] FAILED content items show "Content unavailable" message — no crash, no blank space
- [ ] REUSED content renders identically to originally-generated content (no visual difference)
- [ ] Polling stops automatically when all items are COMPLETED/FAILED/REUSED

**Testing:**
- [ ] All backend tests pass with ≥ 90% coverage
- [ ] All frontend tests pass with ≥ 90% line coverage
- [ ] No broken tests on `main` after merge

---

## Build Sequence (v3.1)

```
Already done:
  Phase 0 → 1 → 2 → 3 → 4 → 5 → 6(deprecated) → 7
  ✅       ✅   ✅   ✅   ✅   ✅   ✅              ✅

New phases — execute in this order:

  Phase 10A → 10B → 10C → 10D
    (RAG schema, PDF extraction, embeddings, query service — must be sequential)

  Phase 11A → 11B → 11C
    (S3 infra, GeneratedContent model, key generator — must be sequential)

  Phase 12A
    (StudyPlan migration + data purge — requires 11A done for S3 client import)

  Phase 12B
    (Trigger redesign — requires 12A done, celery_app.py updated)

  Phase 12C → 12D → 12E
    (New study plan task, built in 3 reviewed stages — must be sequential)
    (Requires: 10D done for RAG query service, 11C done for key generator,
     14A done for profile fingerprint — see dependency note below)

  Phase 13A
    (Manim worker container — requires 12B done for celery_app.py task_routes)

  Phase 13B → 13C → 13D
    (Media workers — can be done in any order once 13A and 12E are done)

  Phase 14A → 14B
    (Content reuse — 14A must be done before 14B)
    (14A must be done before Phase 12C because profile_fingerprint is built in 12C)

  Phase 15
    (API content endpoints — requires 11B done for GeneratedContent model,
     14B done for reuse service, 12E done for study plan creation)

  Phase 16
    (Frontend + all tests — requires Phase 15 done; all backend phases complete)
```

**Dependency note for 14A:**
Phase 14A (profile fingerprint) must be implemented **before** Phase 12C
because `generate_enriched_study_plan` calls `build_profile_fingerprint()` as part
of the prompt building step. Implement 14A after 11C, then proceed to 12C.

**Correct full sequence:**

```
10A → 10B → 10C → 10D
11A → 11B → 11C
12A → 12B
14A              ← implement before 12C
12C → 12D → 12E
13A
14B              ← implement after 12E (wired in reuse_or_dispatch)
13B → 13C → 13D
15
16
```

---

## Branch Naming Convention (v3.1)

| Phase | Branch Name |
|---|---|
| Phase 10A | `feature/phase-10a-rag-schema` |
| Phase 10B | `feature/phase-10b-rag-pdf-extraction` |
| Phase 10C | `feature/phase-10c-rag-embedding-ingestion` |
| Phase 10D | `feature/phase-10d-rag-query-service` |
| Phase 11A | `feature/phase-11a-s3-infrastructure` |
| Phase 11B | `feature/phase-11b-generated-content-model` |
| Phase 11C | `feature/phase-11c-key-generator` |
| Phase 12A | `feature/phase-12a-studyplan-migration` |
| Phase 12B | `feature/phase-12b-trigger-redesign` |
| Phase 12C | `feature/phase-12c-rag-prompt-injection` |
| Phase 12D | `feature/phase-12d-multimodal-llm-schema` |
| Phase 12E | `feature/phase-12e-persist-and-dispatch` |
| Phase 13A | `feature/phase-13a-manim-worker-docker` |
| Phase 13B | `feature/phase-13b-animation-task` |
| Phase 13C | `feature/phase-13c-practice-questions-task` |
| Phase 13D | `feature/phase-13d-infographic-task` |
| Phase 14A | `feature/phase-14a-profile-fingerprint` |
| Phase 14B | `feature/phase-14b-content-reuse-dispatch` |
| Phase 15  | `feature/phase-15-content-api` |
| Phase 16  | `feature/phase-16-frontend` |

---

## Open Decisions (Confirm Before Building Affected Phase)

| Decision | Confirm Before | Notes |
|---|---|---|
| Cambridge textbook PDFs sourced and placed in `backend/data/textbooks/` | Phase 10B | File naming convention must be followed: `{grade_code}_{subject_code}_{type}.pdf` |
| Gemini API key provisioned with Imagen 3 and TTS access | Phase 12C | Same key used for LLM, TTS, Imagen — confirm all three capabilities enabled |
| AWS S3 bucket region | Phase 11A | Choose region matching primary user geography; set in `.env` before Phase 11A |
| RunPod persistent pod specs for `manim_worker` | Phase 13A | CPU pod recommended initially; spec size determines `--concurrency` value |
| manim-voiceover Gemini TTS adapter | Phase 13B | Need to implement custom `AbstractSpeechService` subclass for Gemini TTS; evaluate existing GTTSService as fallback |

---

*End of Project Plan — Kaihle Diagnostic Assessment Module v3.1*
