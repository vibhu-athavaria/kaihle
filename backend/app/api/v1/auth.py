from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import create_access_token
from app.core.config import settings
from app.crud.user import authenticate_user, create_user, get_user_by_email, get_user_by_username
from app.schemas.auth import Token, UserCreate, UserResponse, UserLogin
from app.models.user import UserRole
from app.services.billing_service import billing_service

router = APIRouter()


@router.post("/signup", response_model=UserResponse)
def signup(user: UserCreate, db: Session = Depends(get_db)):
    # Validate role
    if user.role not in [role.value for role in UserRole]:
        raise HTTPException(status_code=400, detail="Invalid role")

    if user.role in [UserRole.ADMIN.value, UserRole.PARENT.value]:
        # Email is required for parent/admin
        if not user.email:
            raise HTTPException(status_code=400, detail="Email is required for parents and admins")
        if get_user_by_email(db, email=user.email):
            raise HTTPException(status_code=400, detail="Email already registered")

        # Username is optional → only check if provided
        if user.username and get_user_by_username(db, username=user.username):
            raise HTTPException(status_code=400, detail="Username already taken")

    elif user.role == UserRole.STUDENT.value:
        raise HTTPException(status_code=400, detail="Wrong endpoint for student signup")

    # Create the user
    db_user = create_user(db=db, user=user)

    return db_user


@router.post("/login", response_model=Token)
def login(request: UserLogin, db: Session = Depends(get_db)):
    if request.role not in [role.value for role in UserRole]:
        raise HTTPException(status_code=400, detail="Invalid role")

    # Unified authentication → identifier can be username or email
    user = authenticate_user(db, request.identifier, request.password)

    # Role must match
    if not user or user.role.value != request.role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # For students → must log in with username
    if user.role == UserRole.STUDENT and "@" in request.identifier:
        raise HTTPException(status_code=400, detail="Students must log in with username")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(subject=user.id, expires_delta=access_token_expires)

    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/logout")
def logout():
    # In a stateless JWT system, logout is client-side
    return {"message": "Successfully logged out"}
