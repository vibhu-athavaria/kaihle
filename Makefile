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
