# Kaihle

An AI-powered adaptive learning platform for Indonesian students.

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

# Stop all services
docker compose down

# Stop and remove volumes (reset database)
docker compose down -v
```

#### Backend Database Setup

After starting Docker Compose, set up the database schema and seed initial data:

**1. Run Alembic Migrations**

Apply all migrations to bring the schema up to date:

```bash
# Inside Docker (recommended)
docker compose exec backend alembic upgrade head

# Outside Docker
cd backend && alembic upgrade head
```

Rollback the last migration if needed:
```bash
docker compose exec backend alembic downgrade -1
```

**2. Seed the Database**

Database seeding requires two scripts run in order:

```bash
# Step 1: Seed Cambridge curriculum hierarchy
# (curricula, subjects, grades, topics, subtopics, prerequisites)
docker compose exec backend python -m scripts.seed_curriculum_graph

# Step 2: Seed test data (school, users, classes, enrollments)
# Requires curriculum to be seeded first
docker compose exec backend python -m scripts.seed_test_data

# Outside Docker:
cd backend && python -m scripts.seed_curriculum_graph
cd backend && python -m scripts.seed_test_data
```

Both seed scripts are **idempotent** — safe to re-run using `ON CONFLICT DO NOTHING`.

**Test accounts created:**
| Email | Password | Role |
|-------|----------|------|
| teacher@kaihle.com | Test1234! | TEACHER |
| student@kaihle.com | Test1234! | STUDENT |
| admin@kaihle.com | Test1234! | SCHOOL_ADMIN |
| parent@kaihle.com | Test1234! | PARENT |

**Dry run curriculum seeding** (validates JSON without DB writes):
```bash
docker compose exec backend python -m scripts.seed_curriculum_graph --dry-run
```

**Troubleshooting**

Reset the database:
```bash
# Stop services and remove volumes
docker compose down -v

# Restart (volumes will be recreated with init_db.sql)
docker compose up -d

# Re-run migrations and seeds
docker compose exec backend alembic upgrade head
docker compose exec backend python -m scripts.seed_curriculum_graph
docker compose exec backend python -m scripts.seed_test_data
```

Verify database health:
```bash
docker compose exec postgres pg_isready -U kaihle -d kaihle
```

#### Service Details

**Infrastructure Services:**
- **PostgreSQL** (port 5433): Database with pgvector extension for vector search
- **Redis** (port 6379): Cache and Celery message broker

**Application Services:**
- **Backend** (port 8000): FastAPI application with auto-reload
- **Celery Worker**: Background task processor
- **Frontend Apps**: React Vite apps for each user role

#### Environment Configuration

Copy the example environment file and configure:

```bash
cp .env.example .env
```

Required environment variables:
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `CELERY_BROKER_URL`: Celery message broker URL
- `CELERY_RESULT_BACKEND`: Celery result backend URL
- API keys for AI providers (OpenAI, Anthropic, Google)

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
pnpm dev:teacher  # Start teacher app on port 3001
pnpm dev:student  # Start student app on port 3002
pnpm dev:parent   # Start parent app on port 3003
pnpm dev:school-admin  # Start school admin app on port 3004
pnpm dev:kaihle-admin # Start kaihle admin app on port 3005

# Or run all frontends
pnpm dev
```

## Tech Stack

- **Backend**: FastAPI, SQLAlchemy, Alembic, PostgreSQL
- **Frontend**: React 18, Vite, TypeScript, Tailwind CSS
- **Task Queue**: Celery + Redis
- **AI**: OpenAI, Anthropic, Google Generative AI

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

Note: These IDs are set up in M6 when Render services are created.
