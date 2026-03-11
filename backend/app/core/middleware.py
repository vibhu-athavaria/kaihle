"""Request logging middleware.

Produces one structured JSON log line per HTTP request containing:
timestamp, level, event, service, request_id, method, path,
status_code, duration_ms, user_id, and school_id.

The request_id is injected into structlog contextvars so every log
line emitted during the request lifecycle carries it automatically.
"""

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.security import InvalidTokenError, decode_token

SERVICE_NAME = "kaihle-api"


def _extract_identity_from_request(request: Request) -> tuple[str | None, str | None]:
    """Extract user_id and school_id from the Authorization header JWT.

    Returns (user_id, school_id) as strings, or (None, None) if the token
    is absent, malformed, or invalid.  This function MUST NOT raise — the
    logging middleware must never block a request.
    """
    auth_header = request.headers.get("authorization")
    if not auth_header:
        return None, None

    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None, None

    try:
        payload = decode_token(parts[1])
        user_id = payload.get("sub")
        school_id = payload.get("school_id")
        return user_id, school_id
    except (InvalidTokenError, Exception):
        # Any failure decoding the token is non-fatal for logging purposes.
        return None, None


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that logs every completed HTTP request as structured JSON."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = str(uuid.uuid4())
        start_time = time.monotonic()

        # Bind request_id into structlog contextvars so all downstream log
        # calls within this request automatically include it.
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        user_id, school_id = _extract_identity_from_request(request)

        # Set request_id header for downstream consumers / response correlation.
        try:
            response = await call_next(request)
        except Exception:
            # If the handler raises an unhandled exception, still log the
            # request before re-raising so we never swallow observability.
            duration_ms = round((time.monotonic() - start_time) * 1000, 2)
            log = structlog.get_logger()
            log.error(
                "request_completed",
                service=SERVICE_NAME,
                method=request.method,
                path=request.url.path,
                status_code=500,
                duration_ms=duration_ms,
                user_id=user_id,
                school_id=school_id,
            )
            raise

        duration_ms = round((time.monotonic() - start_time) * 1000, 2)

        log = structlog.get_logger()
        log.info(
            "request_completed",
            service=SERVICE_NAME,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            user_id=user_id,
            school_id=school_id,
        )

        return response
