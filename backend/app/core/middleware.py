"""Request logging middleware for structured logging."""

import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from fastapi import Request, Response
from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware
from structlog.contextvars import bind_contextvars, clear_contextvars

from app.core.config import settings

# Health check endpoints that should not be logged at INFO level
HEALTH_ENDPOINTS = {"/health", "/ready"}

# Path prefix stripped before deriving the component name.
_API_PREFIX = "/api/v1/"


def _component_for(path: str) -> str:
    """Derive a low-cardinality LLM-attribution component from a request path.

    The resource segment only — "/api/v1/subtopic-content/<uuid>/approve" becomes
    "api:subtopic-content". Using the full path would put a UUID in the component column and
    turn the cost report's grouping into one row per request.
    """
    if not path.startswith(_API_PREFIX):
        return "api:other"
    remainder = path[len(_API_PREFIX) :]
    resource = remainder.split("/", 1)[0] or "root"
    return f"api:{resource}"


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware that logs every request with structured JSON output.

    Generates a unique request_id per request and extracts user context
    from JWT tokens for authenticated requests. Never raises exceptions.
    Health check endpoints are logged at DEBUG only to reduce noise.
    """

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        """Process request and log completion with timing and context."""
        request_id = str(uuid.uuid4())
        # Bound BEFORE call_next, not in the finally block, because an LLM call made while
        # handling the request reads these. request_id doubles as the correlation id on
        # llm_usage_events; component attributes the call; school_id is what keeps NULL in
        # that column meaning "platform-level work" rather than "student traffic we failed
        # to attribute" (MLH-T2).
        _user_id, _school_id = self._extract_user_context(request)
        bind_contextvars(
            request_id=request_id,
            llm_component=_component_for(request.url.path),
            school_id=_school_id,
        )

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
            # Already decoded above when binding contextvars — decoding the JWT twice per
            # request is wasted work on every single request.
            user_id, school_id = _user_id, _school_id

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
                structlog.get_logger().debug("request_completed", **log_data)
            else:
                structlog.get_logger().info("request_completed", **log_data)
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
