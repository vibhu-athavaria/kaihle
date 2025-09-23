from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import create_access_token
from app.core.config import settings
from app.crud.user import authenticate_user, create_user, get_user_by_email, get_user_by_username
from app.schemas.auth import Token, UserCreate, UserResponse, UserLogin
from app.models.user import UserRole

router = APIRouter()

@router.post("/signup", response_model=UserResponse)
def signup(user: UserCreate, db: Session = Depends(get_db)):
    # Check if user already exists
    if get_user_by_email(db, email=user.email):
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )

    if get_user_by_username(db, username=user.username):
        raise HTTPException(
            status_code=400,
            detail="Username already taken"
        )

    # Validate role
    if user.role not in [role.value for role in UserRole]:
        raise HTTPException(
            status_code=400,
            detail="Invalid role"
        )

    db_user = create_user(db=db, user=user)
    return db_user

@router.post("/login", response_model=Token)
def login(request:UserLogin, db: Session = Depends(get_db)):
    user = authenticate_user(db, request.email, request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=user.id, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/logout")
def logout():
    # In a stateless JWT system, logout is handled client-side
    # by removing the token from storage
    return {"message": "Successfully logged out"}
