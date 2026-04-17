.PHONY: up down rebuild nuke-db

up:
	docker compose up -d

rebuild:
	docker compose up --build -d

down:
	docker compose down

# ⚠️ DESTROYS POSTGRES DATA — never run in production
nuke-db:
	@echo "⚠️  WARNING: This destroys ALL postgres data. You have 5 seconds to Ctrl+C."
	@sleep 5
	docker compose down -v