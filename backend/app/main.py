"""Kaihle API - Authentication & Authorization."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

from app.api.v1.routes import (
    analytics,
    assessments,
    attempts,
    auth,
    classes,
    curriculum,
    gap_map,
    health,
    lesson_plans,
    onboarding,
    parent,
    platform,
    question_bank,
    schools,
    student_content,
    students,
    study_plans,
    users,
)
from app.core.config import settings

# Import CurrentUser type for documentation
from app.core.deps import CurrentUser  # noqa: F401
from app.core.logging import configure_logging
from app.core.middleware import RequestLoggingMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler.

    Initializes Redis on startup and closes connections on shutdown.
    """
    # Startup
    configure_logging(log_level=settings.log_level)
    app.state.redis = Redis.from_url(settings.redis_url)
    yield
    # Shutdown
    await app.state.redis.aclose()


# Configure structured logging before app creation so all startup logs
# are captured in JSON format.
configure_logging()

app = FastAPI(
    title="Kaihle API",
    version="0.1.0",
    description="""
## Authentication

Use `Authorization: Bearer <access_token>` on all protected endpoints.

### Route Guards
- `get_current_user` — validates JWT Bearer token
- `require_role(*roles)` — enforces role-based access control
- `require_school_match` — ensures user's school matches resource school
- `require_onboarding_complete` — blocks students until onboarding is done
    """,
    lifespan=lifespan,
)

# Request logging middleware - must be first to capture all requests
app.add_middleware(RequestLoggingMiddleware)

# CORS middleware for frontend apps
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3001",  # apps/teacher
        "http://localhost:3002",  # apps/student
        "http://localhost:3003",  # apps/parent
        "http://localhost:3004",  # apps/school-admin
        "http://localhost:3005",  # apps/kaihle-admin
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
app.include_router(analytics.router, prefix="/api/v1")
app.include_router(assessments.router, prefix="/api/v1")
app.include_router(attempts.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(classes.router, prefix="/api/v1")
app.include_router(curriculum.router, prefix="/api/v1")
app.include_router(gap_map.router, prefix="/api/v1")
app.include_router(lesson_plans.router, prefix="/api/v1")
app.include_router(parent.router, prefix="/api/v1")
app.include_router(platform.router, prefix="/api/v1")
app.include_router(question_bank.router, prefix="/api/v1")
app.include_router(schools.router, prefix="/api/v1")
app.include_router(study_plans.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(onboarding.router, prefix="/api/v1")
app.include_router(student_content.router, prefix="/api/v1")
app.include_router(students.router, prefix="/api/v1")

# Register health routes at root level (no /api/v1 prefix)
app.include_router(health.router)
