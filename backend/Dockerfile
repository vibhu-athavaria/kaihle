# ── Stage 1: Dependencies ────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

# Create virtual environment
RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy dependency file
COPY pyproject.toml .

# Install only production dependencies (no [dev] extras)
RUN uv pip install "."

# ── Stage 2: Runtime ─────────────────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# Install postgresql-client-16 so pg_dump/psql match the server version.
# Required for the db-tools export/import endpoints in Kaihle Admin.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gnupg \
    lsb-release \
  && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor -o /usr/share/keyrings/postgresql.gpg \
  && echo "deb [signed-by=/usr/share/keyrings/postgresql.gpg] https://apt.postgresql.org/pub/repos/apt bookworm-pgdg main" \
     > /etc/apt/sources.list.d/pgdg.list \
  && apt-get update && apt-get install -y --no-install-recommends postgresql-client-16 \
  && apt-get purge -y curl gnupg lsb-release \
  && apt-get autoremove -y \
  && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create non-root user for security
RUN groupadd -r app && useradd -r -g app app

# Copy application source
COPY --chown=app:app . .

# Switch to non-root user
USER app

EXPOSE 8000

# Allow worker count to be configured via environment variable
ENV UVICORN_WORKERS=2

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS}"]
