# Kaihle

Kaihle is an **AI-powered, full-stack product prototype** focused on using LLMs to assist with structured thinking, reflection, and decision-making. The project demonstrates how to build **reliable, production-oriented AI features** on top of a modern web stack, with a strong emphasis on backend architecture, prompt design, and system correctness.

This repository is intentionally designed as a **realistic product codebase**, not a demo script, showcasing full-stack engineering, API design, and practical LLM integration.

---

## What This Project Demonstrates

* End-to-end **full-stack development** (frontend + backend)
* **LLM-powered product features** integrated into real application flows
* Backend-first architecture with clear API boundaries
* Practical AI patterns: prompt iteration, RAG-style retrieval, structured outputs
* Production-minded concerns: cost awareness, reliability, and extensibility

---

## High-Level Architecture

```
Frontend (React / TypeScript)
        ↓
Backend APIs (Python / FastAPI)
        ↓
Business Logic & AI Layer
        ↓
LLM APIs + Data Stores (Postgres / Supabase)
```

* **Frontend** focuses on user interaction and product workflows
* **Backend** owns business logic, orchestration, and AI integration
* **AI layer** encapsulates prompt logic, context assembly, and response validation

---

## Tech Stack

### Frontend

* React
* TypeScript
* Modern component-based UI
* API-driven architecture

### Backend

* Python
* FastAPI
* REST APIs
* Environment-based configuration

### Data & Infrastructure

* PostgreSQL (via Supabase)
* SQL-based data modeling
* Cloud-ready deployment patterns

### AI / LLM Features

* LLM-powered responses integrated into backend services
* Prompt design and iteration handled server-side
* Retrieval-Augmented Generation (RAG-style) using structured data and documents
* Structured outputs (JSON/schema-driven where applicable)
* Cost-aware usage and response evaluation considerations

---

## Deployment

### Prerequisites

Before deploying Kaihle, ensure you have the following:

| Requirement | Description |
|-------------|-------------|
| **Docker** | Docker Desktop (macOS/Windows) or Docker Engine (Linux) |
| **Docker Compose** | Version 2.x or higher |
| **RAM** | At least 8GB allocated to Docker |
| **Ports** | 5173, 5555, 6379, 5432, 8000 must be available |

### Quick Start (Development)

```bash
# Clone the repository
git clone https://github.com/vibhu-athavaria/kaihle.git
cd kaihle

# Copy environment file
cp .env.example .env

# Edit .env with your configuration
# IMPORTANT: Change SECRET_KEY and database passwords before production!
# Generate a secure secret key: openssl rand -hex 32

# Start all services
make up

# Run database migrations
make migrate

# (Optional) Seed initial data
make seed
```

#### Access the Application

| Service | URL | Description |
|---------|-----|-------------|
| Frontend | http://localhost:5173 | React + Vite development server |
| API Docs | http://localhost:8000/docs | FastAPI Swagger documentation |
| API ReDoc | http://localhost:8000/redoc | FastAPI ReDoc documentation |
| Flower | http://localhost:5555 | Celery task monitoring UI |

### Production Deployment

For production deployments, use the production Docker Compose override:

```bash
# Deploy with production settings
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

#### Production Configuration Checklist

1. **Environment Variables** - Update all values in `.env`:
   - `SECRET_KEY` - Generate with `openssl rand -hex 32`
   - `POSTGRES_PASSWORD` - Use a strong, unique password
   - `DATABASE_URL` - Update with the new password
   - `ENVIRONMENT=production`
   - `DEBUG=false`

2. **LLM Provider** - Configure your preferred LLM provider:
   ```bash
   # Options: runpod, autocontentapi, google
   LLM_PROVIDER=runpod
   RUNPOD_API_KEY=your_production_api_key
   ```

3. **Security Considerations**:
   - Enable HTTPS with a reverse proxy (nginx, Traefik, or cloud load balancer)
   - Configure firewall rules to restrict port access
   - Use secrets management (Docker secrets, HashiCorp Vault, etc.)
   - Enable database connection encryption
   - Set up regular database backups

4. **SSL/TLS Setup** (recommended):
   ```bash
   # Example with Certbot for Let's Encrypt
   certbot certonly --standalone -d yourdomain.com
   ```

### Available Make Commands

| Command | Description |
|---------|-------------|
| `make up` | Start all services in detached mode |
| `make down` | Stop all services |
| `make build` | Build all containers from scratch (no cache) |
| `make logs` | View API logs (follow mode) |
| `make worker-logs` | View Celery worker logs (follow mode) |
| `make shell` | Open bash shell in API container |
| `make db-shell` | Open PostgreSQL shell |
| `make migrate` | Run database migrations |
| `make migrate-create m="description"` | Create a new migration |
| `make seed` | Seed initial data |
| `make test` | Run tests with coverage (≥90% required) |
| `make flower` | Open Flower monitoring UI in browser |
| `make docs` | Open API documentation in browser |
| `make restart-worker` | Restart Celery worker |
| `make ps` | Show status of all containers |

### Container Architecture

Kaihle runs 7 Docker containers in development:

| Container | Image | Port | Purpose |
|-----------|-------|------|---------|
| `kaihle-db` | postgres:16-alpine | 5432 | PostgreSQL database for persistent storage |
| `kaihle-redis` | redis:7-alpine | 6379 | Session cache, Celery broker, rate limiting |
| `kaihle-api` | Custom (FastAPI) | 8000 | REST API server with hot reload |
| `kaihle-celery-worker` | Custom (FastAPI) | - | Background task processor (LLM calls, reports) |
| `kaihle-celery-beat` | Custom (FastAPI) | - | Scheduled task scheduler |
| `kaihle-flower` | Custom (FastAPI) | 5555 | Celery monitoring dashboard |
| `kaihle-frontend` | Custom (Node) | 5173 | React + Vite development server |

#### Architecture Diagram

```
                    ┌─────────────────────────────────────────────────────────┐
                    │                    Docker Network                        │
                    │                   (kaihle-network)                       │
                    │                                                          │
   Browser ────────►│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐ │
                    │  │  Frontend   │───►│     API     │───►│  PostgreSQL │ │
   :5173            │  │  (Vite)     │    │  (FastAPI)  │    │    (db)     │ │
                    │  └─────────────┘    └──────┬──────┘    └─────────────┘ │
                    │                            │                           │
                    │         ┌──────────────────┼──────────────────┐        │
                    │         ▼                  ▼                  ▼        │
                    │  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐ │
                    │  │   Celery    │    │   Celery    │    │   Flower    │ │
                    │  │   Worker    │    │    Beat     │    │  (Monitor)  │ │
                    │  └──────┬──────┘    └──────┬──────┘    └─────────────┘ │
                    │         │                  │                           │
                    │         └────────┬─────────┘                           │
                    │                  ▼                                     │
                    │          ┌─────────────┐                               │
                    │          │    Redis    │                               │
                    │          │  (Broker)   │                               │
                    │          └─────────────┘                               │
                    └─────────────────────────────────────────────────────────┘
```

### Troubleshooting

#### Common Issues

| Issue | Solution |
|-------|----------|
| **Port already in use** | Stop conflicting services: `lsof -i :8000` then `kill -9 <PID>` |
| **Database connection failed** | Wait for db health check, or run `make down && make up` |
| **Migration errors** | Check db logs: `docker compose logs db` |
| **Celery tasks not running** | Check worker logs: `make worker-logs` |
| **Frontend not connecting to API** | Verify `VITE_API_URL` in `.env` matches API URL |
| **Permission denied errors** | On Linux, may need to adjust file permissions or run with sudo |

#### Checking Logs

```bash
# All container logs
docker compose logs

# Specific service logs
docker compose logs api
docker compose logs celery_worker
docker compose logs db

# Follow logs in real-time
docker compose logs -f api
```

#### Restarting Services

```bash
# Restart all services
make down && make up

# Restart specific service
docker compose restart api
docker compose restart celery_worker

# Full rebuild (after dependency changes)
make build && make up
```

#### Database Issues

```bash
# Connect to database
make db-shell

# Check migrations status
docker compose exec api alembic current

# Rollback last migration
docker compose exec api alembic downgrade -1

# Reset database (WARNING: destroys all data)
make down
docker volume rm kaihle_postgres_data
make up
make migrate
```

### Development Workflow

#### Hot Reload

Both frontend and backend support hot reload in development:

- **Frontend**: Vite automatically reloads on file changes
- **Backend**: Uvicorn reloads on Python file changes (mounted volume)

#### Running Tests

```bash
# Run all tests with coverage
make test

# Run specific test file
docker compose exec api pytest tests/test_api_endpoints.py -v

# Run with coverage report
docker compose exec api pytest --cov=app --cov-report=html
```

#### Creating Migrations

```bash
# After modifying models, create a migration
make migrate-create m="add_new_table"

# Apply the migration
make migrate

# View migration history
docker compose exec api alembic history
```

#### Adding Dependencies

```bash
# Backend (Python)
# Add to backend/requirements.txt, then:
make build && make up

# Frontend (Node.js)
# Add to frontend/package.json, then:
docker compose exec frontend npm install
```

---

## AI Design Notes

This project intentionally treats AI as **product infrastructure**, not a black box:

* Prompts are designed, versioned, and iterated as part of the backend
* Context is assembled explicitly to avoid uncontrolled hallucination
* Outputs are validated before being surfaced to users
* The system is designed to support:

  * Prompt refinement
  * Evaluation and testing
  * Cost and latency optimization

These patterns are representative of how LLMs are used in **real production products**, not demos.

---

## Why This Repo Is Shared

This repository is shared as a **code portfolio example** to demonstrate:

* Senior-level backend and full-stack engineering
* Practical, production-minded AI/LLM integration
* Clear system design and ownership of complexity
* Ability to translate product ideas into working software

It is **not** intended as a polished open-source framework, but as a realistic snapshot of how an AI-enabled product is built and evolved.

---

## License

MIT (or project-specific license if applicable)
