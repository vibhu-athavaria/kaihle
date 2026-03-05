"""Authentication API routes."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import InvalidTokenError
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    MagicLinkRequest,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new user."""
    service = AuthService(db)
    try:
        return await service.register(
            email=body.email,
            password=body.password,
            role=body.role,
            school_id=body.school_id,
            first_name=body.first_name,
            last_name=body.last_name,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Login with email and password."""
    service = AuthService(db)
    try:
        return await service.login(body.email, body.password)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )


@router.post("/magic-link")
async def send_magic_link(
    body: MagicLinkRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Send a magic link to the user's email."""
    service = AuthService(db)
    base_url = str(request.base_url).rstrip("/")
    await service.send_magic_link(body.email, base_url)
    # Always return success — never reveal whether email exists
    return {"message": "If that email is registered, a login link has been sent."}


@router.get("/magic-link/verify", response_model=LoginResponse)
async def verify_magic_link(token: str, db: AsyncSession = Depends(get_db)):
    """Verify a magic link token and return JWT tokens."""
    service = AuthService(db)
    try:
        return await service.verify_magic_link(token)
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Magic link is invalid or has expired",
        )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Refresh an access token using a refresh token."""
    service = AuthService(db)
    try:
        return await service.refresh_access_token(body.refresh_token)
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is invalid or expired",
        )


@router.post("/logout")
async def logout(body: LogoutRequest, db: AsyncSession = Depends(get_db)):
    """Logout by invalidating the refresh token."""
    service = AuthService(db)
    await service.logout(body.refresh_token)
    return {"message": "Logged out"}
