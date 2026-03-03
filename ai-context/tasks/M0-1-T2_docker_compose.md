# M0-1-T2 — Docker Compose Dev Environment
**Milestone:** M0 — Foundations
**Epic:** M0-1 — Repository & Project Setup
**Task ID:** M0-1-T2
**Mode:** Code (MiniMax)
**Estimated effort:** 2–3 hours

---

## Context

This task creates the full local development environment using Docker Compose. Every developer and CI run uses this to spin up the complete stack with a single command. No manual steps should be required after `docker-compose up`.

**Depends on:** M0-1-T1 (monorepo structure must exist)

---

## User Story

As a developer, I want to run `docker-compose up` and have the entire stack running locally without any manual configuration steps.

---

## What To Build

### `/kaihle/docker-compose.yml`

```yaml
version: "3.9"

services:

  postgres:
    image: pgvector/pgvector:pg16
    container_name: kaihle_postgres
    environment:
      POSTGRES_USER: kaihle
      POSTGRES_PASSWORD: kaihle
      POSTGRES_DB: kaihle
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backend/scripts/init_db.sql:/docker-entrypoint-initdb.d/init_db.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U kaihle -d kaihle"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: kaihle_redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: kaihle_backend
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    ports:
      - "8000:8000"
    volumes:
      - ./backend:/app
    env_file:
      - .env
    environment:
      DATABASE_URL: postgresql+asyncpg://kaihle:kaihle@postgres:5432/kaihle
      REDIS_URL: redis://redis:6379/0
      CELERY_BROKER_URL: redis://redis:6379/1
      CELERY_RESULT_BACKEND: redis://redis:6379/2
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

  celery-worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: kaihle_celery
    command: celery -A app.tasks.celery_app worker --loglevel=info
    volumes:
      - ./backend:/app
    env_file:
      - .env
    environment:
      DATABASE_URL: postgresql+asyncpg://kaihle:kaihle@postgres:5432/kaihle
      REDIS_URL: redis://redis:6379/0
      CELERY_BROKER_URL: redis://redis:6379/1
      CELERY_RESULT_BACKEND: redis://redis:6379/2
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

  frontend-teacher:
    build:
      context: ./frontend
      dockerfile: apps/teacher/Dockerfile.dev
    container_name: kaihle_teacher
    ports:
      - "3001:3001"
    volumes:
      - ./frontend:/app
      - /app/node_modules
    environment:
      VITE_API_URL: http://localhost:8000

  frontend-student:
    build:
      context: ./frontend
      dockerfile: apps/student/Dockerfile.dev
    container_name: kaihle_student
    ports:
      - "3002:3002"
    volumes:
      - ./frontend:/app
      - /app/node_modules
    environment:
      VITE_API_URL: http://localhost:8000

  frontend-parent:
    build:
      context: ./frontend
      dockerfile: apps/parent/Dockerfile.dev
    container_name: kaihle_parent
    ports:
      - "3003:3003"
    volumes:
      - ./frontend:/app
      - /app/node_modules
    environment:
      VITE_API_URL: http://localhost:8000

volumes:
  postgres_data:
  redis_data:
```

---

### `/kaihle/backend/Dockerfile`

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy dependency file first (layer caching)
COPY pyproject.toml .

# Install dependencies
RUN uv pip install --system -e ".[dev]"

# Copy application code
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

### `/kaihle/backend/scripts/init_db.sql`

Runs automatically on first PostgreSQL container start. Enables required extensions:

```sql
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Enable pgcrypto for gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Enable pg_trgm for trigram text search
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

---

### Frontend Dev Dockerfiles

**`/kaihle/frontend/apps/teacher/Dockerfile.dev`:**
```dockerfile
FROM node:20-alpine

WORKDIR /app

RUN npm install -g pnpm

COPY package.json pnpm-workspace.yaml* ./
COPY apps/teacher/package.json apps/teacher/
COPY packages/ui/package.json packages/ui/
COPY packages/api-client/package.json packages/api-client/
COPY packages/auth/package.json packages/auth/
COPY packages/types/package.json packages/types/

RUN pnpm install

COPY . .

EXPOSE 3001
CMD ["pnpm", "dev:teacher"]
```

Create identical files for `student` (port 3002) and `parent` (port 3003) — only the CMD and EXPOSE differ.

---

### `/kaihle/backend/app/tasks/celery_app.py`

Celery needs a minimal app definition to start the worker:

```python
from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "kaihle",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.gap_tasks", "app.tasks.onboarding_tasks",
             "app.tasks.lesson_plan_tasks", "app.tasks.parent_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
)
```

Create empty placeholder task files so Celery import doesn't fail:
- `/backend/app/tasks/gap_tasks.py` — empty, tasks added in M1-4-T3
- `/backend/app/tasks/onboarding_tasks.py` — empty, tasks added in M0-6-T2
- `/backend/app/tasks/lesson_plan_tasks.py` — empty, tasks added in M4-1-T1
- `/backend/app/tasks/parent_tasks.py` — empty, tasks added in M5-1-T1

---

### Update `/kaihle/backend/app/main.py`

Add startup event to confirm DB and Redis connectivity:

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.core.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown

app = FastAPI(
    title="Kaihle API",
    version="0.1.0",
    lifespan=lifespan,
)

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "environment": settings.environment,
        "version": "0.1.0"
    }
```

(Full health check with DB + Redis ping is implemented in M0-5-T2)

---

## Files To Create / Modify

```
/kaihle/docker-compose.yml                          ← CREATE
/kaihle/backend/Dockerfile                          ← CREATE
/kaihle/backend/scripts/init_db.sql                 ← CREATE
/kaihle/backend/scripts/__init__.py                 ← CREATE (empty)
/kaihle/backend/app/tasks/celery_app.py             ← CREATE
/kaihle/backend/app/tasks/gap_tasks.py              ← CREATE (empty placeholder)
/kaihle/backend/app/tasks/onboarding_tasks.py       ← CREATE (empty placeholder)
/kaihle/backend/app/tasks/lesson_plan_tasks.py      ← CREATE (empty placeholder)
/kaihle/backend/app/tasks/parent_tasks.py           ← CREATE (empty placeholder)
/kaihle/frontend/apps/teacher/Dockerfile.dev        ← CREATE
/kaihle/frontend/apps/student/Dockerfile.dev        ← CREATE
/kaihle/frontend/apps/parent/Dockerfile.dev         ← CREATE
/kaihle/backend/app/main.py                         ← MODIFY (add lifespan)
```

---

## Acceptance Criteria

- [ ] `docker-compose up` starts all 7 services without errors
- [ ] `GET http://localhost:8000/health` returns `{ "status": "ok" }`
- [ ] `GET http://localhost:3001` renders teacher React app with no console errors
- [ ] `GET http://localhost:3002` renders student React app
- [ ] `GET http://localhost:3003` renders parent React app
- [ ] PostgreSQL pgvector: `SELECT * FROM pg_extension WHERE extname = 'vector'` returns one row
- [ ] Redis: `docker exec kaihle_redis redis-cli ping` returns `PONG`
- [ ] Celery worker starts without import errors (empty task modules are fine)
- [ ] `docker-compose down -v && docker-compose up` (fresh start) works without errors

---

## Dependencies

- M0-1-T1 — monorepo structure must exist before Docker files can reference paths

## Output (What Next Tasks Can Use)

- Full stack running locally via `docker-compose up`
- PostgreSQL with pgvector extension enabled
- Redis available on port 6379
- Backend hot-reload working (code changes reflect without restart)
- Celery worker running (ready to accept tasks once they are registered in later milestones)
