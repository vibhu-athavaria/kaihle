"""Health check endpoints for monitoring and readiness probes."""

import redis.asyncio as redis
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db

router = APIRouter(tags=["health"])

VERSION = "2.1.0"


async def _check_database(db: AsyncSession) -> str:
    """Check database connectivity by running SELECT 1.

    Returns "connected" on success, "error" on failure.
    """
    try:
        await db.execute(text("SELECT 1"))
        return "connected"
    except Exception:
        return "error"


async def _check_redis() -> str:
    """Check Redis connectivity by running ping.

    Returns "connected" on success, "error" on failure.
    """
    redis_client = None
    try:
        redis_client = redis.from_url(settings.redis_url)
        await redis_client.ping()
        return "connected"
    except Exception:
        return "error"
    finally:
        if redis_client:
            await redis_client.close()


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)) -> JSONResponse:
    """Health check endpoint for monitoring and uptime checks.

    Returns 200 OK when healthy, 503 when degraded.
    """
    db_status = await _check_database(db)
    redis_status = await _check_redis()

    is_healthy = db_status == "connected" and redis_status == "connected"
    status_code = status.HTTP_200_OK if is_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    status_text = "ok" if is_healthy else "degraded"

    return JSONResponse(
        status_code=status_code,
        content={
            "status": status_text,
            "version": VERSION,
            "db": db_status,
            "redis": redis_status,
        },
    )


@router.get("/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)) -> JSONResponse:
    """Readiness probe endpoint for Render.

    Returns 200 only when both DB and Redis are connected.
    Returns 503 otherwise.
    """
    db_status = await _check_database(db)
    redis_status = await _check_redis()

    is_ready = db_status == "connected" and redis_status == "connected"
    status_code = status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        status_code=status_code,
        content={"ready": is_ready},
    )
