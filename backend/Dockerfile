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
