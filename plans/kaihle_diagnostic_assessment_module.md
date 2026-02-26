# Kaihle — Diagnostic Assessment Module
## Comprehensive Project Plan for KiloCode

**Version:** 2.0
**Prepared by:** Kremer (Technical Lead)
**Target:** KiloCode AI Builder
**Stack:** FastAPI · PostgreSQL · Redis · Celery · React + Vite · Docker

---

## Changelog from v1.0

| # | Change | Impact |
|---|---|---|
| 1 | Adaptive questioning — fixed N questions per subtopic, difficulty adjusts after each answer | Redesigns Phase 3 (session init), Phase 4 (response handler), Phase 5 (scoring) |
| 2 | Difficulty scale standardised to Integer 1–5 everywhere | Model migration required, all band mappings updated |
| 3 | Full Docker environment added as Phase 0 | New phase, prerequisite for all other phases |

---

## Overview & Context

Kaihle is an AI-powered homeschool and school learning platform. The **Diagnostic Assessment Module** is the entry point for every new student. It runs once at onboarding, covers all four subjects (Math, Science, English, Humanities), delivers an adaptive question sequence per subtopic, measures proficiency per subtopic, identifies knowledge gaps, and automatically generates a personalised study plan.

### What Already Exists
- User registration and auth (Parent, Student roles)
- Parent → Child management and student profile creation
- Student self-onboarding via parent-created credentials
- Cambridge curriculum mapped: Grades 5–12, Subjects: Math, Science, English, Humanities
- ~7,000 questions in `question_bank` with `subject_id`, `topic_id`, `subtopic_id`, `grade_id`
- Full SQLAlchemy models: `Assessment`, `AssessmentQuestion`, `QuestionBank`, `AssessmentReport`, `StudentKnowledgeProfile`, `StudyPlan`, `StudyPlanCourse`, `StudentProfile`, `Curriculum`, `CurriculumTopic`, `Subtopic`

### What This Module Builds
1. Full Docker environment (dev + prod)
2. Redis + Celery infrastructure
3. Difficulty scale migration (1–5 integers, standardised everywhere)
4. Adaptive Diagnostic Session Engine
5. Response Collection Engine (with adaptive next-question logic)
6. Scoring Engine (per-subtopic, difficulty-weighted)
7. Report Generation Engine (knowledge gaps, strengths, recommendations)
8. StudentKnowledgeProfile population
9. AI-Powered Study Plan Generator (async via Celery + LLM)
10. Full REST API layer
11. React frontend (multi-subject adaptive diagnostic flow)

---

## Difficulty Scale — Global Standard

> **This is the single source of truth for difficulty across the entire Kaihle codebase.**

| Integer Value | Label | Meaning |
|---|---|---|
| `1` | Beginner | Recall / basic recognition |
| `2` | Easy | Simple application of single concept |
| `3` | Medium | Multi-step reasoning, standard grade-level |
| `4` | Hard | Complex application, cross-concept |
| `5` | Expert | Advanced, above grade-level challenge |

**Rules:**
- `QuestionBank.difficulty_level` stores Integer 1–5 (migration required — currently Float 0.0–1.0)
- All API responses, scoring formulas, and frontend displays use this 1–5 scale
- No `easy/medium/hard` string enums anywhere in the diagnostic module — use integers
- `Topic.difficulty_level` and `Subtopic.difficulty_level` already use Integer 1–5 (no change needed)
- `CurriculumTopic.difficulty_level` already uses Integer 1–5 (no change needed)

**Adaptive Step Rules:**
```
Correct answer   → next question difficulty = min(current_difficulty + 1, 5)
Incorrect answer → next question difficulty = max(current_difficulty - 1, 1)
Starting difficulty for every subtopic = 3 (Medium)
```

---

## Architecture Summary

```
Student completes profile
        │
        ▼
Diagnostic Trigger (auto on profile completion)
        │
        ▼
┌──────────────────────────────────────────────┐
│         Diagnostic Session Engine            │
│  - One Assessment per subject (4 total)      │
│  - Subtopic list locked at session init      │
│  - Questions selected ADAPTIVELY one by one  │
│  - assessment_questions populated on the fly │
└─────────────────┬────────────────────────────┘
                  │
                  ▼
     Student answers question N for subtopic X
                  │
                  ▼
     Adaptive Engine selects question N+1
     for same subtopic at adjusted difficulty
                  │
                  ▼
     Repeat until N questions answered per subtopic
                  │
                  ▼
┌────────────────────────────────┐
│        Scoring Engine          │
│  Per-subtopic mastery score    │
│  Difficulty-weighted (1–5)     │
└──────────────┬─────────────────┘
               │
               ▼
┌──────────────────────────────────┐
│        AssessmentReport          │
│  knowledge_gaps, strengths,      │
│  topic_breakdown, recommendations│
└──────────────┬───────────────────┘
               │
               ├──► StudentKnowledgeProfile (upsert per subtopic)
               │
               ▼
┌──────────────────────────────────────┐
│  Celery Task Chain:                  │
│  generate_reports → generate_plan    │
│  LLM prompt with gaps + profile      │
│  → StudyPlan + StudyPlanCourses      │
└──────────────────────────────────────┘
```

### Key Design Decisions

| Decision | Choice | Reason |
|---|---|---|
| Assessment records | One per subject (4 total) | `Assessment.subject_id` is non-nullable |
| Questions per subtopic | 5 (configurable via env var) | Enough signal for reliable mastery estimate |
| Starting difficulty | 3 (Medium) | Neutral entry point for all students |
| Adaptive step | ±1 per answer, clamped 1–5 | Simple, effective, no IRT required at this stage |
| Question selection timing | Dynamic — selected one at a time as answers come in | Core requirement of adaptive assessment |
| Session state | Redis cache + DB persistence | Redis for fast adaptive logic, DB for durability |
| `assessment_questions` population | Incremental (one row added per question served) | Matches adaptive model; not pre-locked |
| Already-used questions | Excluded per session | Prevents repetition within same diagnostic |
| Study plan generation | Async Celery task | Non-blocking |
| LLM calls | Only at study plan generation | Never during assessment delivery |

---

## Phase 0 — Docker Environment Setup

**Goal:** Containerise the entire Kaihle development stack so every developer and KiloCode itself works in an identical, reproducible environment. This phase is the prerequisite for all other phases.

### 0.1 Container Overview

| Container | Image | Purpose |
|---|---|---|
| `api` | Custom (Python 3.12) | FastAPI application |
| `db` | postgres:16-alpine | PostgreSQL database |
| `redis` | redis:7-alpine | Session cache + Celery broker |
| `celery_worker` | Same as `api` | Background task processor |
| `celery_beat` | Same as `api` | Scheduled task scheduler |
| `flower` | Same as `api` | Celery monitoring UI |
| `frontend` | node:20-alpine | React + Vite dev server |

### 0.2 Project Root Structure

```
kaihle/
├── backend/
│   ├── app/
│   ├── tests/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── alembic/
├── frontend/
│   ├── src/
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml           # Development
├── docker-compose.prod.yml      # Production overrides
├── docker-compose.test.yml      # Test environment
├── .env.example
├── .env                         # Git-ignored
└── Makefile
```

### 0.3 Backend Dockerfile

**File: `backend/Dockerfile`**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN adduser --disabled-password --gecos '' appuser && chown -R appuser /app
USER appuser

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 0.4 Frontend Dockerfile

**File: `frontend/Dockerfile`**

```dockerfile
FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
```

### 0.5 docker-compose.yml (Development)

```yaml
version: '3.9'

services:

  db:
    image: postgres:16-alpine
    container_name: kaihle_db
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: kaihle_redis
    restart: unless-stopped
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  api:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: kaihle_api
    restart: unless-stopped
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    ports:
      - "8000:8000"
    volumes:
      - ./backend:/app
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - SECRET_KEY=${SECRET_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ENVIRONMENT=development
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy

  celery_worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: kaihle_celery_worker
    restart: unless-stopped
    command: celery -A app.worker.celery_app worker --loglevel=info --concurrency=4
    volumes:
      - ./backend:/app
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - CELERY_BROKER_URL=${CELERY_BROKER_URL}
      - CELERY_RESULT_BACKEND=${CELERY_RESULT_BACKEND}
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy

  celery_beat:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: kaihle_celery_beat
    restart: unless-stopped
    command: celery -A app.worker.celery_app beat --loglevel=info
    volumes:
      - ./backend:/app
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - CELERY_BROKER_URL=${CELERY_BROKER_URL}
      - CELERY_RESULT_BACKEND=${CELERY_RESULT_BACKEND}
    depends_on:
      - redis

  flower:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: kaihle_flower
    restart: unless-stopped
    command: celery -A app.worker.celery_app flower --port=5555
    ports:
      - "5555:5555"
    environment:
      - CELERY_BROKER_URL=${CELERY_BROKER_URL}
      - CELERY_RESULT_BACKEND=${CELERY_RESULT_BACKEND}
    depends_on:
      - redis

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: kaihle_frontend
    restart: unless-stopped
    ports:
      - "5173:5173"
    volumes:
      - ./frontend:/app
      - /app/node_modules
    environment:
      - VITE_API_BASE_URL=http://localhost:8000/api/v1
    depends_on:
      - api

volumes:
  postgres_data:
  redis_data:
```

### 0.6 docker-compose.prod.yml (Production Overrides)

```yaml
version: '3.9'

services:

  api:
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
    volumes: []
    environment:
      - ENVIRONMENT=production

  celery_worker:
    command: celery -A app.worker.celery_app worker --loglevel=warning --concurrency=8
    volumes: []

  frontend:
    command: sh -c "npm run build && npx serve -s dist -l 5173"
    volumes: []
```

### 0.7 .env.example

```env
# PostgreSQL
POSTGRES_DB=kaihle_db
POSTGRES_USER=kaihle_user
POSTGRES_PASSWORD=changeme_in_production
DATABASE_URL=postgresql+asyncpg://kaihle_user:changeme_in_production@db:5432/kaihle_db

# Redis
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/1

# Application
SECRET_KEY=changeme_generate_with_openssl_rand_hex_32
ENVIRONMENT=development
DEBUG=true

# LLM
OPENAI_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini
LLM_MAX_TOKENS=4000

# Diagnostic Configuration
DIAGNOSTIC_QUESTIONS_PER_SUBTOPIC=5
DIAGNOSTIC_STARTING_DIFFICULTY=3
```

### 0.8 Makefile

```makefile
.PHONY: up down build logs migrate seed test shell worker-logs

up:
	docker-compose up -d

down:
	docker-compose down

build:
	docker-compose build --no-cache

logs:
	docker-compose logs -f api

worker-logs:
	docker-compose logs -f celery_worker

shell:
	docker-compose exec api bash

db-shell:
	docker-compose exec db psql -U $(POSTGRES_USER) -d $(POSTGRES_DB)

migrate:
	docker-compose exec api alembic upgrade head

migrate-create:
	docker-compose exec api alembic revision --autogenerate -m "$(msg)"

seed:
	docker-compose exec api python scripts/seed.py

test:
	docker-compose -f docker-compose.test.yml up --abort-on-container-exit --exit-code-from tests

flower:
	open http://localhost:5555

docs:
	open http://localhost:8000/docs

restart-worker:
	docker-compose restart celery_worker

ps:
	docker-compose ps
```

### 0.9 .dockerignore Files

**`backend/.dockerignore`:**
```
__pycache__
*.pyc
.env
.env.*
!.env.example
.git
tests/
.pytest_cache/
htmlcov/
.coverage
```

**`frontend/.dockerignore`:**
```
node_modules
dist
.env
.env.*
!.env.example
.git
```

### Phase 0 Acceptance Criteria
- [ ] `make up` starts all 7 containers with no errors
- [ ] `make migrate` runs all Alembic migrations successfully
- [ ] FastAPI docs accessible at `http://localhost:8000/docs`
- [ ] React dev server accessible at `http://localhost:5173` with hot reload working
- [ ] Flower monitoring accessible at `http://localhost:5555`
- [ ] PostgreSQL data persists across `make down && make up`
- [ ] Redis data persists across `make down && make up`
- [ ] Celery worker connects and processes a test task
- [ ] `.env.example` contains every required variable — no undocumented secrets

---

## Phase 1 — Redis + Celery Application Setup

**Goal:** Wire Redis and Celery into the FastAPI application code.

### 1.1 New Python Dependencies

```
redis==5.0.1
celery==5.3.6
celery[redis]==5.3.6
flower==2.0.1
kombu==5.3.4
openai>=1.0.0
```

### 1.2 Redis Client

**Create: `app/core/redis.py`**

```python
import redis.asyncio as aioredis
import redis as syncredis
from app.core.config import settings

async_redis_client = aioredis.from_url(
    settings.REDIS_URL,
    encoding="utf-8",
    decode_responses=True,
    max_connections=20
)

sync_redis_client = syncredis.from_url(
    settings.REDIS_URL,
    decode_responses=True
)

SESSION_TTL = 60 * 60 * 24       # 24 hours
REPORT_POLL_TTL = 60 * 60        # 1 hour
```

### 1.3 Celery Application

**Create: `app/worker/celery_app.py`**

```python
from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "kaihle",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.worker.tasks.report_generation",
        "app.worker.tasks.study_plan",
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
        "app.worker.tasks.report_generation.*": {"queue": "reports"},
        "app.worker.tasks.study_plan.*":        {"queue": "study_plans"},
    }
)
```

### 1.4 Config Additions

Add to `app/core/config.py`:

```python
REDIS_URL: str
CELERY_BROKER_URL: str
CELERY_RESULT_BACKEND: str
OPENAI_API_KEY: str
LLM_MODEL: str = "gpt-4o-mini"
LLM_MAX_TOKENS: int = 4000
DIAGNOSTIC_QUESTIONS_PER_SUBTOPIC: int = 5
DIAGNOSTIC_STARTING_DIFFICULTY: int = 3
```

### Phase 1 Acceptance Criteria
- [ ] FastAPI starts with Redis connection confirmed in logs
- [ ] Celery worker registers all tasks (visible in Flower)
- [ ] Test Celery task executes end-to-end

---

## Phase 2 — Difficulty Scale Migration

**Goal:** Standardise `QuestionBank.difficulty_level` from Float (0.0–1.0) to Integer (1–5).

### 2.1 Model Changes

**`app/models/assessment.py`:**

```python
# QuestionBank — BEFORE
difficulty_level = Column(Float, default=0.5)

# QuestionBank — AFTER
difficulty_level = Column(Integer, default=3)  # 1-5 scale

# Assessment — BEFORE
difficulty_level = Column(Enum(DifficultyLevel), default=DifficultyLevel.MEDIUM)

# Assessment — AFTER
difficulty_level = Column(Integer, default=3, nullable=True)  # 1-5, avg of session
```

Remove `DifficultyLevel` enum class entirely from `assessment.py`. Search entire codebase for any remaining references and update them.

### 2.2 Alembic Migration

**Create: `alembic/versions/xxx_standardise_difficulty_to_integer.py`**

```python
"""Standardise difficulty_level to integer 1-5

Conversion from Float 0.0-1.0 to Integer 1-5:
  <= 0.25  → 1
  <= 0.45  → 2
  <= 0.55  → 3  (default 0.5 maps to 3)
  <= 0.75  → 4
  >  0.75  → 5
"""

def upgrade():
    # question_bank: float → integer
    op.add_column('question_bank',
        sa.Column('difficulty_level_new', sa.Integer(), nullable=True)
    )
    op.execute("""
        UPDATE question_bank SET difficulty_level_new = CASE
            WHEN difficulty_level <= 0.25 THEN 1
            WHEN difficulty_level <= 0.45 THEN 2
            WHEN difficulty_level <= 0.55 THEN 3
            WHEN difficulty_level <= 0.75 THEN 4
            ELSE 5
        END
    """)
    op.alter_column('question_bank', 'difficulty_level_new',
        nullable=False, server_default='3')
    op.drop_column('question_bank', 'difficulty_level')
    op.alter_column('question_bank', 'difficulty_level_new',
        new_column_name='difficulty_level')
    op.create_check_constraint(
        'chk_qb_difficulty_range', 'question_bank',
        'difficulty_level BETWEEN 1 AND 5'
    )

    # assessments: drop enum column, add integer column
    op.execute("ALTER TABLE assessments DROP COLUMN difficulty_level")
    op.add_column('assessments',
        sa.Column('difficulty_level', sa.Integer(), nullable=True)
    )

    # update index
    op.drop_index('idx_qb_subject_topic_difficulty', table_name='question_bank')
    op.create_index('idx_qb_subject_topic_difficulty',
        'question_bank', ['subject_id', 'topic_id', 'difficulty_level'])

    # new index for adaptive query
    op.create_index('idx_qb_subtopic_difficulty_active',
        'question_bank', ['subtopic_id', 'difficulty_level'],
        postgresql_where=sa.text('is_active = true'))
```

### 2.3 Post-Migration Verification Query

```sql
SELECT difficulty_level, COUNT(*) as count,
       ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) as pct
FROM question_bank
GROUP BY difficulty_level ORDER BY difficulty_level;
```

### Phase 2 Acceptance Criteria
- [ ] Migration runs with zero data loss
- [ ] All 7,000 questions have Integer 1–5 difficulty
- [ ] No `NULL` difficulty values after migration
- [ ] `DifficultyLevel` enum removed with no remaining references
- [ ] `idx_qb_subtopic_difficulty_active` index created
- [ ] Existing tests pass

---

## Phase 3 — Adaptive Diagnostic Session Engine

**Goal:** Session initialisation locks the subtopic structure. Questions are selected one at a time, adaptively, as the student progresses.

### 3.1 Adaptive Rules

```
Per subtopic:
  Total questions  = DIAGNOSTIC_QUESTIONS_PER_SUBTOPIC (default: 5)
  Start difficulty = DIAGNOSTIC_STARTING_DIFFICULTY (default: 3)
  Correct answer   → next difficulty = min(current + 1, 5)
  Incorrect answer → next difficulty = max(current - 1, 1)
  Never repeat a question already used in this session

Fallback if no question at target difficulty:
  1. Try target + 1
  2. Try target - 1
  3. Try any available difficulty not yet used
  4. Skip slot (do not fail the session)

Subtopic order: sequential by CurriculumTopic.sequence_order
All 5 questions for subtopic 1 → all 5 for subtopic 2 → ...
```

### 3.2 Redis Session State Schema

Cache key: `kaihle:diagnostic:session:{assessment_id}`  TTL: 24 hours

```json
{
  "assessment_id": "uuid",
  "student_id": "uuid",
  "subject_id": "uuid",
  "status": "started | in_progress | completed",
  "subtopics": [
    {
      "subtopic_id": "uuid",
      "subtopic_name": "Linear Equations",
      "questions_total": 5,
      "questions_answered": 0,
      "current_difficulty": 3,
      "used_question_ids": []
    }
  ],
  "current_subtopic_index": 0,
  "current_question_bank_id": null,
  "total_questions": 25,
  "answered_count": 0,
  "started_at": "ISO8601",
  "last_activity": "ISO8601"
}
```

### 3.3 Question Selector Service

**Create: `app/services/diagnostic/question_selector.py`**

```python
class AdaptiveDiagnosticSelector:

    async def get_next_question(
        self,
        subtopic_id: UUID,
        grade_id: UUID,
        subject_id: UUID,
        target_difficulty: int,        # Integer 1-5
        used_question_ids: list[UUID],
    ) -> QuestionBank | None:
        """
        Fallback chain:
        1. Exact target_difficulty, not in used_question_ids, RANDOM()
        2. target_difficulty + 1 (if < 5)
        3. target_difficulty - 1 (if > 1)
        4. Any difficulty, not in used_question_ids
        5. Return None (subtopic exhausted)
        """
        ...

    async def get_subtopics_for_session(
        self,
        curriculum_id: UUID,
        grade_id: UUID,
        subject_id: UUID,
    ) -> list[Subtopic]:
        """
        Returns active subtopics ordered by CurriculumTopic.sequence_order
        via: CurriculumTopic → Subtopic join
        """
        ...
```

### 3.4 Session Manager Service

**Create: `app/services/diagnostic/session_manager.py`**

```python
class DiagnosticSessionManager:

    async def initialize_diagnostic(self, student_id: UUID) -> DiagnosticInitResponse:
        """
        Idempotent. If diagnostic already exists, returns existing sessions.
        1. Verify student profile has grade_id and curriculum_id
        2. For each subject: create Assessment(type=DIAGNOSTIC, status=STARTED)
        3. Load subtopics for each subject
        4. Cache session state in Redis (no questions selected yet)
        5. Return 4 session summaries
        """
        ...

    async def get_current_question(
        self, assessment_id: UUID
    ) -> tuple[QuestionBank | None, dict]:
        """
        Returns (question, session_state).
        If no current_question_bank_id in state:
          - Selects first question for current subtopic at starting difficulty
          - Creates AssessmentQuestion row (unanswered)
          - Updates session state current_question_bank_id in Redis
        Returns (None, state) if session complete.
        """
        ...

    async def record_answer_and_advance(
        self,
        assessment_id: UUID,
        question_bank_id: UUID,
        is_correct: bool,
    ) -> dict:
        """
        1. Add question_bank_id to subtopic.used_question_ids
        2. Increment subtopic.questions_answered
        3. Adjust subtopic.current_difficulty (±1, clamped 1-5)
        4. Clear current_question_bank_id
        5. If subtopic complete → increment current_subtopic_index
        6. If all subtopics complete → set status = completed
        7. Save to Redis + DB (Assessment.questions_answered, Assessment.status)
        8. Return updated state
        """
        ...

    async def get_session_state(self, assessment_id: UUID) -> dict:
        """
        Returns from Redis. Falls back to DB reconstruction if cache cold.
        """
        ...
```

### Phase 3 Acceptance Criteria
- [ ] `initialize_diagnostic` creates exactly 4 `Assessment` records; idempotent on re-call
- [ ] Redis session state populated for all 4 subjects with subtopic structure
- [ ] First question served at difficulty 3 for every subtopic
- [ ] `get_subtopics_for_session` returns subtopics in curriculum sequence order
- [ ] Fallback difficulty selection works when target tier has no available questions
- [ ] `used_question_ids` prevents repetition within a subtopic
- [ ] Session advances `current_subtopic_index` correctly when subtopic exhausted
- [ ] Session marked `completed` when all subtopics done

---

## Phase 4 — Response Collection Engine

**Goal:** Accept student answers, evaluate correctness, drive adaptive difficulty, persist to DB, detect completion.

### 4.1 Response Handler Service

**Create: `app/services/diagnostic/response_handler.py`**

```python
class DiagnosticResponseHandler:

    async def submit_answer(
        self,
        assessment_id: UUID,
        question_bank_id: UUID,
        student_answer: str,
        time_taken_seconds: int,
    ) -> AnswerResult:
        """
        Full pipeline:
        1. Load session state from Redis
        2. Validate: status not COMPLETED, question_bank_id == current_question_bank_id
        3. Load AssessmentQuestion row (must exist, must be unanswered)
        4. Evaluate correctness
        5. Calculate score = (difficulty_level / 5.0) if correct else 0.0
        6. Update AssessmentQuestion: student_answer, is_correct, score, time_taken, answered_at
        7. Call session_manager.record_answer_and_advance
        8. Update Assessment.questions_answered + status in DB
        9. Check all-subjects completion
        10. Return AnswerResult
        """
        ...

    def evaluate_answer(self, question: QuestionBank, student_answer: str) -> bool:
        """Case-insensitive exact match on correct_answer field."""
        return question.correct_answer.strip().lower() == student_answer.strip().lower()

    def calculate_score(self, is_correct: bool, difficulty_level: int) -> float:
        """
        score = (difficulty_level / 5.0) if is_correct else 0.0
        difficulty_level is Integer 1-5.
        Range: 0.0 to 1.0
        """
        return (difficulty_level / 5.0) if is_correct else 0.0

    async def check_all_subjects_complete(self, student_id: UUID) -> bool:
        """
        Returns True if all 4 subject assessments are COMPLETED.
        If True (and not already triggered):
          1. Set StudentProfile.has_completed_assessment = True
          2. Set Redis flag: kaihle:diagnostic:generating:{student_id} = "reports"
          3. Dispatch Celery chain: generate_reports.s() | generate_study_plan.s()
        Guard: check Redis flag before dispatching to prevent double-trigger.
        """
        ...
```

### 4.2 AssessmentQuestion Lifecycle

- **Created** when question is first served (`get_current_question`)
  - Fields set: `assessment_id`, `question_bank_id`, `question_number`
  - `student_answer`, `is_correct`, `score` all NULL at creation
- **Updated** when answer is submitted
  - Fields set: `student_answer`, `is_correct`, `score`, `time_taken`, `answered_at`

### 4.3 Assessment State Machine

```
STARTED ──────► IN_PROGRESS (first answer received)
IN_PROGRESS ──► COMPLETED   (final question answered)
IN_PROGRESS ──► ABANDONED   (future: explicit or timeout)
```

Both Redis state and `Assessment.status` must stay in sync on every transition.

### Phase 4 Acceptance Criteria
- [ ] `400` if assessment already COMPLETED
- [ ] `404` if `question_bank_id` != `current_question_bank_id` in session state
- [ ] `409` if `AssessmentQuestion.answered_at` is already set
- [ ] Score formula correct: difficulty 5 correct = 1.0, difficulty 3 correct = 0.6
- [ ] Difficulty adjusts ±1 and clamps correctly at 1 and 5
- [ ] Redis and DB stay in sync after every submission
- [ ] All 4 complete → `has_completed_assessment = True` + Celery chain fires exactly once
- [ ] Redis guard prevents Celery chain firing twice

---

## Phase 5 — Scoring Engine & AssessmentReport Generation

**Goal:** After all 4 assessments complete, compute mastery and generate `AssessmentReport` records via Celery.

### 5.1 Mastery Calculation

```
Per subtopic:
  max_possible = Σ (difficulty_level / 5.0) for all questions
  actual_score = Σ score for all questions
  mastery_level = actual_score / max_possible   (0.0 if max_possible == 0)

Per topic:
  topic_mastery = mean(mastery_level) across all subtopics in topic
```

### 5.2 Mastery Labels

| Range | Label |
|---|---|
| 0.00 – 0.39 | `beginning` |
| 0.40 – 0.59 | `developing` |
| 0.60 – 0.74 | `approaching` |
| 0.75 – 0.89 | `strong` |
| 0.90 – 1.00 | `mastery` |

### 5.3 Knowledge Gap Priority

| Mastery | Priority |
|---|---|
| < 0.40 | `high` |
| 0.40 – 0.59 | `medium` |
| 0.60 – 0.74 | `low` |
| ≥ 0.75 | *(strength, not a gap)* |

### 5.4 Report Generation Task

**Create: `app/worker/tasks/report_generation.py`**

```python
@celery_app.task(bind=True, max_retries=3, name="tasks.generate_assessment_reports")
def generate_assessment_reports(self, student_id: str) -> str:
    """
    For each of the 4 subject assessments:
      1. Load AssessmentQuestion rows with QuestionBank joins
      2. Group by subtopic → compute mastery_level
      3. Rollup to topic level
      4. Classify knowledge_gaps and strengths
      5. Build recommendations (ordered by gap priority)
      6. Build diagnostic_summary
      7. Upsert AssessmentReport
      8. Upsert StudentKnowledgeProfile (subtopic + topic level)
    Returns student_id (for task chain).
    Updates Redis flag: kaihle:diagnostic:generating:{student_id} = "study_plan"
    """
    ...
```

### 5.5 AssessmentReport JSONB Structures

**`topic_breakdown`:**
```json
{
  "topics": [{
    "topic_id": "uuid", "topic_name": "Algebra",
    "mastery_level": 0.67, "mastery_label": "approaching",
    "questions_attempted": 15, "questions_correct": 9,
    "subtopics": [{
      "subtopic_id": "uuid", "subtopic_name": "Linear Equations",
      "mastery_level": 0.85, "mastery_label": "strong",
      "questions_attempted": 5, "questions_correct": 4,
      "difficulty_path": [3, 4, 5, 4, 5],
      "correct_path": [true, true, false, true, true]
    }]
  }]
}
```

**`knowledge_gaps`:**
```json
[{
  "subtopic_id": "uuid", "subtopic_name": "Quadratic Equations",
  "topic_name": "Algebra", "mastery_level": 0.28,
  "mastery_label": "beginning", "priority": "high",
  "difficulty_reached": 2, "correct_count": 1, "total_count": 5
}]
```

**`diagnostic_summary`:**
```json
{
  "overall_mastery": 0.61, "mastery_label": "approaching",
  "total_questions": 25, "total_correct": 15,
  "highest_difficulty_reached": 5, "average_difficulty_reached": 3.4,
  "strongest_subtopic": "Linear Equations",
  "weakest_subtopic": "Quadratic Equations",
  "completion_time_minutes": 22
}
```

### Phase 5 Acceptance Criteria
- [ ] Celery task runs after all 4 assessments complete
- [ ] One `AssessmentReport` per subject (4 total), idempotent
- [ ] `difficulty_path` and `correct_path` correctly reflect adaptive sequence
- [ ] Mastery labels and gap priorities correct
- [ ] `StudentKnowledgeProfile` upserted at subtopic and topic level
- [ ] `needs_review = True` where `mastery_level < 0.6`

---

## Phase 6 — AI-Powered Study Plan Generation

**Goal:** Use diagnostic results to generate a personalised `StudyPlan` asynchronously via Celery + LLM.

### 6.1 Study Plan Task

**Create: `app/worker/tasks/study_plan.py`**

```python
@celery_app.task(bind=True, max_retries=3, name="tasks.generate_study_plan")
def generate_study_plan(self, student_id: str) -> str:
    """
    1. Load all AssessmentReport knowledge_gaps (all 4 subjects)
    2. Load StudentProfile (grade, curriculum, learning_profile)
    3. Load Course records matching gap subtopics
    4. Calculate recommended_weeks
    5. Build LLM prompt
    6. Call LLM (OpenAI GPT-4o-mini)
    7. Validate JSON response
    8. Write StudyPlan + StudyPlanCourse in single DB transaction
    9. Set Redis flag: kaihle:diagnostic:generating:{student_id} = "complete"
    On failure after max retries:
      - Create StudyPlan with status = "generation_failed"
      - Set Redis flag = "failed"
    """
    ...
```

### 6.2 Recommended Weeks Calculation

```python
def calculate_recommended_weeks(gaps: list) -> int:
    high   = sum(1 for g in gaps if g["priority"] == "high")
    medium = sum(1 for g in gaps if g["priority"] == "medium")
    low    = sum(1 for g in gaps if g["priority"] == "low")
    weeks  = (high * 1.0) + (medium * 0.5) + (low * 0.25)
    return max(4, min(round(weeks) + 1, 16))  # Clamp 4–16 weeks
```

### 6.3 LLM System Prompt

```
You are an expert Cambridge curriculum learning designer for grades 5–12.
Generate a personalised study plan as structured JSON.
Return ONLY valid JSON. No markdown, no explanation.
```

### 6.4 LLM Response Validation

1. Parse JSON — `JSONDecodeError` → retry task
2. Validate all UUIDs (`course_id`, `topic_id`, `subtopic_id`) exist in DB — null any that don't
3. Re-number `sequence_order` sequentially (1, 2, 3...)
4. Validate `week ≤ total_weeks` and `day ≤ 5`
5. Write `StudyPlan` + all `StudyPlanCourse` in single transaction

### 6.5 Task Chain Setup

```python
# In response_handler.check_all_subjects_complete():
from celery import chain as celery_chain

celery_chain(
    generate_assessment_reports.s(str(student_id)),
    generate_study_plan.s()
).delay()
```

### 6.6 Generation Status Redis Flags

Key: `kaihle:diagnostic:generating:{student_id}` — TTL 2 hours

| Value | Meaning |
|---|---|
| `"reports"` | Generating assessment reports |
| `"study_plan"` | Generating study plan |
| `"complete"` | Everything done |
| `"failed"` | Task chain failed after max retries |

### Phase 6 Acceptance Criteria
- [ ] Task chain: reports first, study plan second
- [ ] LLM prompt includes all gaps from all 4 subjects + learning_profile
- [ ] JSON validated before any DB write
- [ ] Invalid UUIDs nullified gracefully
- [ ] Retries 3 times on failure; marks `generation_failed` on exhaustion
- [ ] Redis generation flag correctly progresses through states
- [ ] `StudyPlan.status = "active"` on successful creation

---

## Phase 7 — REST API Layer

**Goal:** 6 clean, authenticated, versioned FastAPI endpoints.

**New file: `app/api/v1/routers/diagnostic.py`**

### Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/diagnostic/initialize` | Init given subject assessments (idempotent) |
| `GET` | `/diagnostic/status/{student_id}` | Overall status across all subjects |
| `GET` | `/diagnostic/{assessment_id}/next-question` | Get next adaptive question |
| `POST` | `/diagnostic/{assessment_id}/answer` | Submit answer |
| `GET` | `/diagnostic/{student_id}/report` | Full diagnostic report (202 while generating) |
| `GET` | `/diagnostic/{student_id}/study-plan` | Generated study plan (202 while generating) |

### Key Response Rules

- `GET /next-question` → `200` with question, `204` when session complete
- `GET /report` → `200` when ready, `202` with `retry_after_seconds: 15` while generating
- `GET /study-plan` → `200` when ready, `202` while generating
- **Never expose** `correct_answer`, `explanation`, or `is_correct` via `next-question` endpoint

### Answer Response includes adaptive info

```json
{
  "is_correct": true,
  "score": 0.8,
  "difficulty_level": 4,
  "next_difficulty": 5,
  "questions_answered": 6,
  "total_questions": 25,
  "subtopic_complete": false,
  "assessment_status": "in_progress",
  "all_subjects_complete": false
}
```

### Pydantic Schemas

**Create: `app/schemas/diagnostic.py`** with models:
`DiagnosticInitRequest/Response`, `SessionSummaryItem`, `DiagnosticStatusResponse`, `SubjectStatusItem`, `NextQuestionResponse`, `QuestionItem`, `AnswerSubmitRequest/Response`, `DiagnosticReportResponse`, `SubjectReportItem`, `StudyPlanResponse`, `StudyPlanCourseItem`

All with `model_config = ConfigDict(from_attributes=True)`.

### Phase 7 Acceptance Criteria
- [ ] All 6 endpoints correct with valid schemas
- [ ] Students cannot access other students' data (403)
- [ ] Parents can access their children's data only
- [ ] `correct_answer` never appears during active session
- [ ] `202` correctly triggered by Redis generation flags
- [ ] All endpoints in OpenAPI at `/docs`

---

## Phase 8 — React Frontend

**Goal:** Student-facing adaptive diagnostic experience. Mobile-responsive.

### New Dependency

```bash
npm install @tanstack/react-query
```

### 8.1 Routes

```
/diagnostic                → DiagnosticHub
/diagnostic/:assessmentId  → DiagnosticSession
/diagnostic/report         → DiagnosticReport
/diagnostic/study-plan     → StudyPlanView
```

### 8.2 Pages

**`DiagnosticHub`** — 4 subject cards, overall progress, polls status every 8s while in_progress. Auto-redirects to `/diagnostic/report` when `all_complete = true`.

**`DiagnosticSession`** — Adaptive question flow.
- `QuestionProgressBar` — "Question 6 of 25 · Subtopic: Linear Equations"
- `DifficultyIndicator` — visual 1–5 dots showing current difficulty (updates after each answer)
- `QuestionCard` + `OptionButton` (locks after submit)
- `SubmitButton` (disabled until option selected)
- `FeedbackFlash` — brief ✓/✗ only (no correct answer shown during session)

State machine:
```
loading → question_displayed → option_selected → submitting
       → feedback_shown → loading_next → question_displayed
                                       → session_complete → hub
```

**`DiagnosticReport`** — Polls every 5s until `202 → 200`. Shows per-subject collapsible cards with `MasteryRing`, `TopicBreakdownTable` (includes difficulty path per subtopic), `KnowledgeGapBadge` (🔴/🟡/🟢), `StrengthsList`. `StudyPlanCTA` appears when `study_plan_ready = true`.

**`StudyPlanView`** — Week accordion (Week 1 open by default), `DayRow`, `CourseItem` with activity badge and duration.

### 8.3 React Query Hooks

**Create: `src/hooks/diagnostic/`**

```javascript
useDiagnosticStatus(studentId)     // polls while in_progress
useInitializeDiagnostic()          // mutation
useNextQuestion(assessmentId)      // on-demand fetch
useSubmitAnswer()                  // mutation
useDiagnosticReport(studentId)     // polls: 202 → 200
useStudyPlan(studentId)            // polls: 202 → 200
```

### Phase 8 Acceptance Criteria
- [ ] `DiagnosticHub` shows correct status for all 4 subjects
- [ ] `DifficultyIndicator` updates after each answer
- [ ] Option locks immediately — no double-submit
- [ ] Session resumes correctly after page refresh (Redis state preserved)
- [ ] Difficulty path shown per subtopic in report (e.g., 3→4→5→4→5)
- [ ] `DiagnosticReport` polls until ready, renders without manual refresh
- [ ] All pages mobile-responsive
- [ ] All loading, error, and empty states handled

---

## Phase 9 — Testing & Quality

### Backend Tests

```
tests/test_diagnostic/
  test_question_selector.py     # Adaptive selection, fallback logic, difficulty clamping
  test_session_manager.py       # Session init, state transitions, Redis/DB sync
  test_response_handler.py      # Answer submission, scoring formula, state machine
  test_scoring_engine.py        # Mastery calc, labels, gap priorities
  test_report_generation.py     # Celery task, JSONB structure correctness
  test_study_plan_task.py       # Mocked LLM, plan generation, UUID validation
  test_api_diagnostic.py        # All 6 endpoint integration tests
  test_difficulty_migration.py  # Migration correctness on sample Float data
```

### Performance Targets

| Operation | Target |
|---|---|
| Question selection query | < 100ms |
| Answer submission endpoint | < 200ms |
| Session state read (Redis) | < 20ms |
| Report generation task | < 30s |
| Study plan LLM generation | < 90s |

---

## Complete File Map (New Files Only)

```
backend/
├── Dockerfile                                       NEW
├── app/
│   ├── core/redis.py                                NEW
│   ├── api/v1/routers/diagnostic.py                 NEW
│   ├── schemas/diagnostic.py                        NEW
│   ├── services/diagnostic/
│   │   ├── __init__.py                              NEW
│   │   ├── question_selector.py                     NEW
│   │   ├── session_manager.py                       NEW
│   │   └── response_handler.py                      NEW
│   └── worker/
│       ├── celery_app.py                            NEW
│       └── tasks/
│           ├── __init__.py                          NEW
│           ├── report_generation.py                 NEW
│           └── study_plan.py                        NEW
└── alembic/versions/
    └── xxx_standardise_difficulty_to_integer.py     NEW

frontend/
├── Dockerfile                                       NEW
└── src/
    ├── pages/diagnostic/
    │   ├── DiagnosticHub.jsx                        NEW
    │   ├── DiagnosticSession.jsx                    NEW
    │   ├── DiagnosticReport.jsx                     NEW
    │   └── StudyPlanView.jsx                        NEW
    ├── components/diagnostic/
    │   ├── SubjectCard.jsx                          NEW
    │   ├── QuestionCard.jsx                         NEW
    │   ├── OptionButton.jsx                         NEW
    │   ├── DifficultyIndicator.jsx                  NEW
    │   ├── MasteryRing.jsx                          NEW
    │   ├── TopicBreakdownTable.jsx                  NEW
    │   ├── KnowledgeGapBadge.jsx                    NEW
    │   ├── WeekAccordion.jsx                        NEW
    │   └── CourseItem.jsx                           NEW
    └── hooks/diagnostic/
        ├── useDiagnosticStatus.js                   NEW
        ├── useNextQuestion.js                       NEW
        ├── useSubmitAnswer.js                       NEW
        ├── useDiagnosticReport.js                   NEW
        └── useStudyPlan.js                          NEW

# Root
docker-compose.yml                                   NEW
docker-compose.prod.yml                              NEW
.env.example                                         NEW / UPDATE
Makefile                                             NEW
```

---

## Database Changes Summary

| Change | Type |
|---|---|
| `question_bank.difficulty_level` Float → Integer 1–5 | Migration |
| `assessments.difficulty_level` Enum → Integer 1–5 | Migration |
| `DifficultyLevel` enum removed | Code change |
| `idx_qb_subtopic_difficulty_active` | New index |
| `chk_qb_difficulty_range` | New constraint |

No new tables required.

---

## Git Workflow & Phase Completion Requirements

> **These rules are mandatory for every phase without exception. A phase is NOT complete until every item below is satisfied. Do not begin the next phase until the current phase is fully closed.**

### Branch Naming Convention

Each phase must be developed on its own dedicated branch, created from `main` (or the project's primary integration branch):

| Phase | Branch Name |
|---|---|
| Phase 0 | `feature/phase-0-docker-setup` |
| Phase 1 | `feature/phase-1-redis-celery` |
| Phase 2 | `feature/phase-2-difficulty-migration` |
| Phase 3 | `feature/phase-3-adaptive-session-engine` |
| Phase 4 | `feature/phase-4-response-handler` |
| Phase 5 | `feature/phase-5-scoring-report-generation` |
| Phase 6 | `feature/phase-6-study-plan-generation` |
| Phase 7 | `feature/phase-7-api-layer` |
| Phase 8 | `feature/phase-8-frontend` |
| Phase 9 | `feature/phase-9-testing-quality` |

### Phase Completion Checklist

Every phase must satisfy **all** of the following before it is considered done:

**1. Branch created from main**
```bash
git checkout main
git pull origin main
git checkout -b feature/phase-N-<name>
```

**2. All acceptance criteria met**
Every acceptance criteria checkbox listed under the phase must be verified and passing.

**3. Test coverage ≥ 90%**
- Run the test suite and generate a coverage report
- Overall coverage for all new code introduced in the phase must be **90% or above**
- Backend:
```bash
pytest --cov=app --cov-report=term-missing --cov-fail-under=90
```
- Frontend (Phase 8):
```bash
npm run test -- --coverage --coverageThreshold='{"global":{"lines":90}}'
```
- Coverage report output must be included in the final commit
- **The phase is blocked from closing if coverage is below 90%**

**4. All code committed and clean**
- No uncommitted changes (`git status` must be clean)
- No debug code, commented-out blocks, or TODO stubs left in production code paths
- All new environment variables documented in `.env.example`
- Migrations (if any) included in the commit

```bash
git add .
git commit -m "feat(phase-N): <concise description of what was built>"
```

Use conventional commit format:
- `feat(phase-N):` for new functionality
- `fix(phase-N):` for bug fixes within a phase
- `chore(phase-N):` for config, tooling, migration changes

**5. Branch pushed to origin**
```bash
git push origin feature/phase-N-<name>
```
Confirm the push is acknowledged by origin with no errors before considering the phase closed.

**6. No broken tests on main**
Before pushing, run the full test suite one final time to confirm nothing is broken:
```bash
pytest --cov=app --cov-fail-under=90
```

### Summary Flow Per Phase

```
Create branch from main
        │
        ▼
Build phase features
        │
        ▼
Verify all acceptance criteria
        │
        ▼
Run tests → coverage ≥ 90%?
    No  → Write missing tests → Re-run
    Yes → Continue
        │
        ▼
git add . && git commit
        │
        ▼
git push origin feature/phase-N-<name>
        │
        ▼
Phase CLOSED — begin next phase
```

---

## Build Sequence for KiloCode

**Execute phases strictly in order. Do not begin a phase until all its acceptance criteria are met AND the Git workflow requirements above are fully satisfied.**

```
Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5+6 → Phase 7 → Phase 8 → Phase 9
 Docker   Celery   Difficulty  Adaptive  Response  Scoring +   API     Frontend  Testing
 Setup    Setup    Migration   Session   Handler   StudyPlan
```

Phases 5 and 6 are tightly coupled (same Celery task chain) and should be developed together.

---

## Open Decisions (Confirm Before Phase 3)

| Decision | Recommendation |
|---|---|
| Questions per subtopic | **5** (configurable via `DIAGNOSTIC_QUESTIONS_PER_SUBTOPIC`) |
| LLM provider | **OpenAI GPT-4o-mini** — reliable JSON output, low cost |
| Subject order in diagnostic | **Fixed:** Math → Science → English → Humanities |
| Session timeout | **24 hours** — student can resume same day |
| Show correct answer during session | **No** — revealed only in report |
| Diagnostic retake | **Disabled for now** — add in future release |

---

*End of Project Plan — Kaihle Diagnostic Assessment Module v2.0*