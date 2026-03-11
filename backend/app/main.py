"""Kaihle API - Authentication & Authorization.

## Authentication Middleware & Route Guards

This application uses FastAPI dependency injection for authentication and authorization.
The following guards are available in `app.core.deps`:

- `get_current_user` - Validates JWT Bearer token and loads User from DB
- `require_role(*roles)` - Factory for role-based access control
- `require_school_match(school_id)` - Ensures user's school_id matches resource's school_id
  (KAIHLE_ADMIN bypasses this check)
- `require_onboarding_complete` - Blocks students until onboarding is complete
  (checks both student_profiles.onboarding_diagnostic_status == 'COMPLETED'
   AND student_learning_profiles.completed_at IS NOT NULL)

## Usage Example

```python
from app.core.deps import get_current_user, require_role, require_school_match

@app.get("/protected")
async def protected_route(user: CurrentUser = Depends(get_current_user)):
    return {"user": user.email}

@app.get("/admin-only")
async def admin_route(user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN))):
    return {"admin": user.email}

@app.get("/school/{school_id}/resource")
async def school_resource(
    school_id: UUID,
    user: CurrentUser = Depends(require_school_match(school_id))
):
    return {"school": school_id}
```
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

<<<<<<< HEAD
from app.api.v1.routes import auth, health, onboarding, schools, users
=======
from app.api.v1.routes import auth, onboarding, schools, users
>>>>>>> a4ba5a9 (Merge: add missing route files from main and register onboarding router)
from app.core.config import settings

# Import CurrentUser type for documentation
from app.core.deps import CurrentUser  # noqa: F401
<<<<<<< HEAD
from app.core.logging import configure_logging
from app.core.middleware import RequestLoggingMiddleware
=======
>>>>>>> a4ba5a9 (Merge: add missing route files from main and register onboarding router)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup
    configure_logging(log_level=settings.log_level)
    yield
    # Shutdown


# Configure structured logging before app creation so all startup logs
# are captured in JSON format.
configure_logging()

app = FastAPI(
    title="Kaihle API",
    version="0.1.0",
    lifespan=lifespan,
)

<<<<<<< HEAD
# Request logging middleware - must be first to capture all requests
app.add_middleware(RequestLoggingMiddleware)

# Register API routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(schools.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(onboarding.router, prefix="/api/v1")

# Register health routes at root level (no /api/v1 prefix)
app.include_router(health.router)
=======
# Register API routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(onboarding.router, prefix="/api/v1")
app.include_router(schools.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse(content={"status": "ok", "environment": settings.environment, "version": "0.1.0"})
>>>>>>> a4ba5a9 (Merge: add missing route files from main and register onboarding router)
