"""Authentication API routes."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import InvalidTokenError
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    MagicLinkRequest,
    MagicLinkVerifyResponse,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    SetPasswordRequest,
    TokenResponse,
)
from app.services.auth_service import AuthService, SchoolNotFoundError

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)) -> RegisterResponse:
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
    except SchoolNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)) -> LoginResponse:
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
) -> dict[str, str]:
    """Send a magic link to the user's email."""
    service = AuthService(db)
    base_url = str(request.base_url).rstrip("/")
    await service.send_magic_link(body.email, base_url)
    # Always return success — never reveal whether email exists
    return {"message": "If that email is registered, a login link has been sent."}


@router.get("/magic-link/verify", response_model=MagicLinkVerifyResponse)
async def verify_magic_link(token: str, db: AsyncSession = Depends(get_db)) -> MagicLinkVerifyResponse:
    """Verify a magic link token and return a scoped JWT for password setup."""
    service = AuthService(db)
    try:
        setup_token = await service.verify_magic_link_get_token(token)
        return MagicLinkVerifyResponse(
            setup_token=setup_token,
            token_type="bearer",
            requires_password_setup=True,
        )
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Magic link is invalid or has expired",
        )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    """Refresh an access token using a refresh token."""
    service = AuthService(db)
    try:
        return await service.refresh_access_token(body.refresh_token)
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is invalid or expired",
        )


@router.post("/set-password", response_model=LoginResponse)
async def set_password(
    body: SetPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """Set password for a magic-link-invited user on first login.

    Requires a JWT with scope: password_setup (issued by verify_magic_link).
    Returns a full-access JWT pair (access + refresh) on success.
    Raises 403 if called with a full-access token (password already set).
    """
    service = AuthService(db)
    try:
        return await service.set_password_from_scoped_token(body.password)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/logout")
async def logout(body: LogoutRequest, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """Logout by invalidating the refresh token."""
    service = AuthService(db)
    await service.logout(body.refresh_token)
    return {"message": "Logged out"}
