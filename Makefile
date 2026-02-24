# Kaihle Development Makefile
# Common commands for managing the development environment

.PHONY: up down build logs worker-logs shell db-shell migrate migrate-create seed test flower docs restart-worker ps

# Start all services
up:
	docker compose up -d

# Stop all services
down:
	docker compose down

# Build all containers from scratch
build:
	docker compose build --no-cache

# View API logs
logs:
	docker compose logs -f api

# View Celery worker logs
worker-logs:
	docker compose logs -f celery_worker

# Open shell in API container
shell:
	docker compose exec api bash

# Open PostgreSQL shell
db-shell:
	docker compose exec db psql -U kaihle_user -d kaihle_db

# Run database migrations
migrate:
	docker compose exec api alembic upgrade head

# Create a new migration (usage: make migrate-create m="description")
migrate-create:
	docker compose exec api alembic revision --autogenerate -m "$(m)"

# Seed initial data
seed:
	docker compose exec api python scripts/seed_grades.py

# Run tests with coverage
test:
	docker compose exec api pytest --cov=app --cov-fail-under=90

# Open Flower monitoring UI in browser
flower:
	open http://localhost:5555

# Open API documentation in browser
docs:
	open http://localhost:8000/docs

# Restart Celery worker
restart-worker:
	docker compose restart celery_worker

# Show status of all containers
ps:
	docker compose ps

# ── Phase 10B: PDF Extraction ─────────────────────────────────────────────

extract-pdf:
	docker compose exec api python scripts/extract_pdf_content.py --file $(file)

extract-pdf-all:
	docker compose exec api python scripts/extract_pdf_content.py --all

extract-pdf-dry:
	docker compose exec api python scripts/extract_pdf_content.py --file $(file) --dry-run

# ── Phase 10C: Embedding Ingestion ─────────────────────────────────────────

ingest-embeddings:
	docker compose exec celery_worker celery -A app.celery_app call tasks.ingest_curriculum_embeddings

ingest-embeddings-check:
	docker compose exec api python -c \
		"from app.core.database import SessionLocal; \
		 from app.models.rag import CurriculumContent, CurriculumEmbedding; \
		 db = SessionLocal(); \
		 total = db.query(CurriculumContent).count(); \
		 embedded = db.query(CurriculumEmbedding).count(); \
		 print(f'Content rows: {total}, Embedded: {embedded}, Pending: {total-embedded}')"
