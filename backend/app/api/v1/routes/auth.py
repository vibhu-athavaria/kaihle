"""Authentication API routes."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import InvalidTokenError
from app.schemas.auth import (
    KaihleAdminRegisterRequest,
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    MagicLinkRequest,
    ParentRegisterRequest,
    RefreshRequest,
    RegisterResponse,
    SchoolAdminRegisterRequest,
    StudentRegisterRequest,
    TeacherRegisterRequest,
    TokenResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


# Role-specific registration endpoints
@router.post(
    "/register/school-admin",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_school_admin(
    body: SchoolAdminRegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> RegisterResponse:
    """Register a new school administrator."""
    service = AuthService(db)
    try:
        return await service.register_school_admin(
            email=body.email,
            password=body.password,
            school_id=body.school_id,
            first_name=body.first_name,
            last_name=body.last_name,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.post(
    "/register/teacher",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_teacher(
    body: TeacherRegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> RegisterResponse:
    """Register a new teacher."""
    service = AuthService(db)
    try:
        return await service.register_teacher(
            email=body.email,
            password=body.password,
            school_id=body.school_id,
            first_name=body.first_name,
            last_name=body.last_name,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.post(
    "/register/student",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_student(
    body: StudentRegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> RegisterResponse:
    """Register a new student."""
    service = AuthService(db)
    try:
        return await service.register_student(
            email=body.email,
            password=body.password,
            school_id=body.school_id,
            grade_id=body.grade_id,
            first_name=body.first_name,
            last_name=body.last_name,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.post(
    "/register/parent",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_parent(
    body: ParentRegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> RegisterResponse:
    """Register a new parent."""
    service = AuthService(db)
    try:
        return await service.register_parent(
            email=body.email,
            password=body.password,
            first_name=body.first_name,
            last_name=body.last_name,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.post(
    "/register/kaihle-admin",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_kaihle_admin(
    body: KaihleAdminRegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> RegisterResponse:
    """Register a new Kaihle administrator."""
    service = AuthService(db)
    try:
        return await service.register_kaihle_admin(
            email=body.email,
            password=body.password,
            first_name=body.first_name,
            last_name=body.last_name,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


# Unified login endpoint (works for all user types)
@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)) -> LoginResponse:
    """Login with email and password. Works for all user types."""
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


@router.get("/magic-link/verify", response_model=LoginResponse)
async def verify_magic_link(token: str, db: AsyncSession = Depends(get_db)) -> LoginResponse:
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
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    """Refresh an access token using a refresh token."""
    service = AuthService(db)
    try:
        access_token = await service.refresh_access_token(body.refresh_token)
        return TokenResponse(access_token=access_token)
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is invalid or expired",
        )


@router.post("/logout")
async def logout(body: LogoutRequest, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """Logout by invalidating the refresh token."""
    service = AuthService(db)
    await service.logout(body.refresh_token)
    return {"message": "Logged out"}
