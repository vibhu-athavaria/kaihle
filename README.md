# Kaihle

An AI-powered learning diagnostics platform for small international schools running Cambridge and IB curricula.

## Project Structure

```
kaihle/
├── backend/           # FastAPI backend
│   └── app/          # Application code
├── frontend/         # React monorepo
│   ├── apps/        # Teacher, Student, Parent, School Admin, Kaihle Admin apps
│   └── packages/    # Shared UI components and utilities
└── docs/           # Documentation
```

## Applications and Ports

| Application | Port | Description |
|-------------|------|-------------|
| Backend API | 8000 | FastAPI REST API |
| PostgreSQL | 5433 | Database (pgvector enabled) |
| Redis | 6379 | Cache and message broker |
| Teacher App | 3001 | Teacher dashboard |
| Student App | 3002 | Student learning interface |
| Parent App | 3003 | Parent portal |
| School Admin | 3004 | School administration |
| Kaihle Admin | 3005 | Platform administration |

## Getting Started

### Prerequisites

- Python 3.12+
- Node.js 20+
- pnpm
- Docker and Docker Compose

### Docker Setup (Recommended)

The development environment MUST be started via Docker Compose from the project root before running any backend or frontend code locally:

```bash
# Start all services
docker compose up -d

# View logs
docker compose logs -f

# Stop all services (data is preserved)
docker compose down

# Rebuild images without touching data
docker compose up --build -d
```

> ⚠️ **WARNING: Never run `docker compose down -v` unless you explicitly intend to destroy all database data.**
> Use `make nuke-db` instead — it has a 5-second warning window. See the Makefile section below.

---

### Makefile

A `Makefile` is provided at the project root to prevent accidental data loss and standardise common commands:

```bash
make up        # Start all services
make down      # Stop all services (data preserved)
make rebuild   # Rebuild images and restart (data preserved)
make nuke-db   # ⚠️  DESTROYS ALL POSTGRES DATA — local reset only, never in production
```

---

### Backend Database Setup

After starting Docker Compose, set up the database schema and seed all data in the following order. **All steps are required.**

#### Step 1 — Run Alembic Migrations

Creates all 35 tables in the correct schema:

```bash
docker compose exec backend alembic upgrade head
```

**Verify:**
```bash
docker compose exec postgres psql -U kaihle -d kaihle -c "\dt" | wc -l
# Should show 35+ tables
```

Rollback the last migration if needed:
```bash
docker compose exec backend alembic downgrade -1
```

> **Note on `init_db.sql`:** The file at `backend/scripts/init_db.sql` enables three required Postgres extensions (`pgvector`, `pgcrypto`, `pg_trgm`). It runs automatically on first container initialisation via `docker-entrypoint-initdb.d` — you never need to run it manually. Alembic migrations depend on these extensions being present, so the container must be initialised before running migrations.

---

#### Step 2 — Seed Curriculum Graph

Seeds the full Cambridge curriculum hierarchy: curricula, subjects, grades, topics, subtopics, and prerequisites.

```bash
docker compose exec backend python -m scripts.seed_curriculum_graph
```

**Verify:**
```bash
docker compose exec postgres psql -U kaihle -d kaihle -c "SELECT COUNT(*) FROM curricula;"
# Expected: 4

docker compose exec postgres psql -U kaihle -d kaihle -c "SELECT COUNT(*) FROM subjects;"
# Expected: 10

docker compose exec postgres psql -U kaihle -d kaihle -c "SELECT COUNT(*) FROM subtopics;"
# Expected: 293
```

**Dry run** (validates JSON without DB writes):
```bash
docker compose exec backend python -m scripts.seed_curriculum_graph --dry-run
```

> This script is **idempotent** — safe to re-run using `ON CONFLICT DO NOTHING`.

---

#### Step 3 — Seed Test Data

Seeds a test school, users, classes, and enrollments. Requires curriculum to be seeded first.

```bash
docker compose exec backend python -m scripts.seed_test_data
```

**Verify:**
```bash
docker compose exec postgres psql -U kaihle -d kaihle -c "SELECT COUNT(*) FROM schools;"
# Expected: 1

docker compose exec postgres psql -U kaihle -d kaihle -c "SELECT COUNT(*) FROM users;"
# Expected: 5

docker compose exec postgres psql -U kaihle -d kaihle -c "SELECT COUNT(*) FROM classes;"
# Expected: 3
```

**Test accounts created:**
| Email | Password | Role |
|-------|----------|------|
| teacher@kaihle.com | Test1234! | TEACHER |
| student@kaihle.com | Test1234! | STUDENT |
| admin@kaihle.com | Test1234! | SCHOOL_ADMIN |
| parent@kaihle.com | Test1234! | PARENT |

> This script is **idempotent** — safe to re-run using `ON CONFLICT DO NOTHING`.

---

#### Step 4 — Import Question Bank

Imports 6,397 pre-generated assessment questions mapped to the curriculum graph. Requires curriculum graph to be seeded first.

**Always dry-run first:**
```bash
docker compose exec backend python scripts/import_questions.py \
  --file data/question-bank/pre_generated_questions.json \
  --strategy reresolve \
  --mapping-file data/subtopic_mapping_final.json \
  --dry-run
```

Dry run should show: `Inserted: 6397`, `Skipped (dup): 0`, `Skipped (err): 0`

**Real import:**
```bash
docker compose exec backend python scripts/import_questions.py \
  --file data/question-bank/pre_generated_questions.json \
  --strategy reresolve \
  --mapping-file data/subtopic_mapping_final.json
```

**Verify:**
```bash
docker compose exec postgres psql -U kaihle -d kaihle -c "SELECT COUNT(*) FROM question_bank;"
# Expected: 6397
```

---

### Full Setup Sequence Summary

```bash
# 1. Start containers
docker compose up -d

# 2. Run migrations
docker compose exec backend alembic upgrade head

# 3. Seed curriculum
docker compose exec backend python -m scripts.seed_curriculum_graph

# 4. Seed test data
docker compose exec backend python -m scripts.seed_test_data

# 5. Import questions (dry run first)
docker compose exec backend python scripts/import_questions.py \
  --file data/question-bank/pre_generated_questions.json \
  --strategy reresolve \
  --mapping-file data/subtopic_mapping_final.json \
  --dry-run

# 6. Import questions (real)
docker compose exec backend python scripts/import_questions.py \
  --file data/question-bank/pre_generated_questions.json \
  --strategy reresolve \
  --mapping-file data/subtopic_mapping_final.json
```

---

### Troubleshooting

#### Verify database health
```bash
docker compose exec postgres pg_isready -U kaihle -d kaihle
```

#### Full database reset (local development only)

> ⚠️ **This destroys all data. Use `make nuke-db` which includes a 5-second warning window.**

```bash
make nuke-db

# Then re-run the full setup sequence above
docker compose up -d
docker compose exec backend alembic upgrade head
docker compose exec backend python -m scripts.seed_curriculum_graph
docker compose exec backend python -m scripts.seed_test_data
docker compose exec backend python scripts/import_questions.py \
  --file data/question-bank/pre_generated_questions.json \
  --strategy reresolve \
  --mapping-file data/subtopic_mapping_final.json
```

#### Quick data verification (all counts at once)
```bash
docker compose exec postgres psql -U kaihle -d kaihle -c "
SELECT
  (SELECT COUNT(*) FROM curricula)    AS curricula,
  (SELECT COUNT(*) FROM subjects)     AS subjects,
  (SELECT COUNT(*) FROM subtopics)    AS subtopics,
  (SELECT COUNT(*) FROM schools)      AS schools,
  (SELECT COUNT(*) FROM users)        AS users,
  (SELECT COUNT(*) FROM classes)      AS classes,
  (SELECT COUNT(*) FROM question_bank) AS questions;
"
# Expected: 4 | 10 | 293 | 1 | 5 | 3 | 6397
```

---

### Service Details

**Infrastructure Services:**
- **PostgreSQL** (port 5433): Database with pgvector extension for vector search
- **Redis** (port 6379): Cache and Celery message broker (ephemeral — data loss on restart is expected and safe)

**Application Services:**
- **Backend** (port 8000): FastAPI application with auto-reload
- **Celery Worker**: Background task processor
- **Frontend Apps**: React Vite apps for each user role

---

### Environment Configuration

Copy the example environment file and configure:

```bash
cp .env.example .env
```

Required environment variables:
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `CELERY_BROKER_URL`: Celery message broker URL
- `CELERY_RESULT_BACKEND`: Celery result backend URL
- `OPENROUTER_API_KEY`: OpenRouter API key (Qwen, Gemini access)
- `GEMINI_API_KEY`: Google Gemini API key (lesson plan generation)
- `ANTHROPIC_API_KEY`: Anthropic API key

---

### Local Development Without Docker

#### Backend Setup

```bash
cd backend
cp .env.example .env  # Configure your environment variables
uv pip install -e .
uvicorn app.main:app --reload
```

#### Frontend Setup

```bash
cd frontend
pnpm install
pnpm dev:teacher      # Start teacher app on port 3001
pnpm dev:student      # Start student app on port 3002
pnpm dev:parent       # Start parent app on port 3003
pnpm dev:school-admin # Start school admin app on port 3004
pnpm dev:kaihle-admin # Start kaihle admin app on port 3005

# Or run all frontends
pnpm dev
```

---

## Tech Stack

- **Backend**: FastAPI, SQLAlchemy, Alembic, PostgreSQL 16 + pgvector
- **Frontend**: React 18, Vite, TypeScript, Tailwind CSS (pnpm monorepo)
- **Task Queue**: Celery + Redis
- **AI**: Gemini 2.5 Pro (lesson plans), Qwen via OpenRouter (curriculum mapping), Anthropic Claude

## License

Proprietary — All rights reserved.

---

## GitHub Secrets (for CI/CD)

The following secrets must be set in your GitHub repository Settings → Secrets and variables → Actions:

| Secret | Description |
|--------|-------------|
| `RENDER_API_KEY` | Render account API key |
| `RENDER_BACKEND_SERVICE_ID` | Render service ID for FastAPI backend |
| `RENDER_TEACHER_SERVICE_ID` | Render service ID for teacher frontend |
| `RENDER_STUDENT_SERVICE_ID` | Render service ID for student frontend |
| `RENDER_PARENT_SERVICE_ID` | Render service ID for parent frontend |
| `RENDER_SCHOOL_ADMIN_SERVICE_ID` | Render service ID for school admin frontend |
| `RENDER_KAIHLE_ADMIN_SERVICE_ID` | Render service ID for Kaihle admin frontend |

> Note: These IDs are set up in M6 when Render services are created.