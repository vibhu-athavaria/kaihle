"""Authentication API routes."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, get_token_payload, require_full_access
from app.core.security import InvalidTokenError
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    MagicLinkRequest,
    MagicLinkVerifyResponse,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    ResetPasswordRequest,
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
            username=body.username,
        )
    except SchoolNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email or username already registered")


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)) -> LoginResponse:
    """Login with email or username and password."""
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
    token_payload: Annotated[dict[str, Any], Depends(get_token_payload)],
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """Set password for a magic-link-invited user on first login.

    Requires a JWT with scope: password_setup (issued by verify_magic_link).
    Returns a full-access JWT pair (access + refresh) on success.
    Raises 400 if token is invalid or password already set.
    """
    service = AuthService(db)
    try:
        return await service.set_password_from_scoped_token(token_payload, body.password)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except InvalidTokenError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@router.post("/forgot-password")
async def forgot_password(body: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """Send a password reset link to the user's email.

    Always returns 200 — never reveals whether the email is registered.
    """
    service = AuthService(db)
    await service.send_password_reset_email(body.email)
    return {"message": "If that email is registered, a reset link has been sent."}


@router.post("/reset-password")
async def reset_password(body: ResetPasswordRequest, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """Reset password using a valid reset token from the forgot-password email."""
    service = AuthService(db)
    try:
        await service.reset_password(body.token, body.password)
        return {"message": "Password reset successfully"}
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Reset link is invalid or has expired",
        )


@router.post("/logout")
async def logout(body: LogoutRequest, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """Logout by invalidating the refresh token."""
    service = AuthService(db)
    await service.logout(body.refresh_token)
    return {"message": "Logged out"}


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    body: ChangePasswordRequest,
    current_user: CurrentUser = Depends(require_full_access),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Change the current user's password.

    Requires a full-access JWT (not a password_setup scoped token).
    Returns 204 on success with no response body.
    Returns 400 if current password is incorrect.
    """
    service = AuthService(db)
    try:
        await service.change_password(current_user.id, body.current_password, body.new_password)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
