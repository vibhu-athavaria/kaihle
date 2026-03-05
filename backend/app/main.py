from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.routes import health
from app.core.config import settings
from app.core.logging import configure_logging
from app.core.middleware import RequestLoggingMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup
    configure_logging(log_level=settings.log_level)
    yield
    # Shutdown


app = FastAPI(
    title="Kaihle API",
    version="0.1.0",
    lifespan=lifespan,
)

# Request logging middleware - must be first to capture all requests
app.add_middleware(RequestLoggingMiddleware)

# Register health routes at root level (no /api/v1 prefix)
app.include_router(health.router)
