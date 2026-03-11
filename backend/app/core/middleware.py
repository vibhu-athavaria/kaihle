"""Request logging middleware for structured logging."""

import time
import uuid
from typing import Any

import structlog
from fastapi import Request, Response
from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware
from structlog.contextvars import bind_contextvars, clear_contextvars

from app.core.config import settings

logger = structlog.get_logger()

# Health check endpoints that should not be logged at INFO level
HEALTH_ENDPOINTS = {"/health", "/ready"}


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware that logs every request with structured JSON output.

    Generates a unique request_id per request and extracts user context
    from JWT tokens for authenticated requests. Never raises exceptions.
    Health check endpoints are logged at DEBUG only to reduce noise.
    """

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        """Process request and log completion with timing and context."""
        request_id = str(uuid.uuid4())
        bind_contextvars(request_id=request_id)

        start_time = time.time()
        status_code = 500
        is_health_endpoint = request.url.path in HEALTH_ENDPOINTS

        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception:
            status_code = 500
            raise
        finally:
            duration_ms = round((time.time() - start_time) * 1000)
            user_id, school_id = self._extract_user_context(request)

            log_data = {
                "service": "kaihle-api",
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
                "duration_ms": duration_ms,
                "user_id": user_id,
                "school_id": school_id,
            }

            if is_health_endpoint:
                logger.debug("request_completed", **log_data)
            else:
                logger.info("request_completed", **log_data)
            clear_contextvars()

    def _extract_user_context(self, request: Request) -> tuple[str | None, str | None]:
        """Extract user_id and school_id from JWT token if present.

        Returns (None, None) if token is missing, invalid, or verification fails.
        Never raises exceptions.
        """
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return (None, None)

        token = auth_header[7:]

        if not settings.jwt_secret_key:
            return (None, None)

        try:
            payload = jwt.decode(
                token,
                key=settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
            )
            user_id = payload.get("sub")
            school_id = payload.get("school_id")
            return (user_id, school_id)
        except JWTError:
            return (None, None)
