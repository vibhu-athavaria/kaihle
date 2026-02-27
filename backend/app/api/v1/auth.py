from datetime import timedelta
import uuid
import re
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import create_access_token, verify_token
from app.core.config import settings
from app.crud.user import authenticate_user, create_user, get_user_by_email, get_user_by_username, get_user
from app.crud.school import get_school_by_code, get_school
from app.schemas.auth import Token, UserCreate, UserResponse, UserLogin, SchoolAdminRegisterRequest, SchoolAdminRegisterResponse, StudentRegisterRequest, StudentRegisterResponse, CurrentUserResponse
from app.schemas.school import SchoolCreate
from app.models.user import UserRole
from app.models.school import SchoolStatus
from app.services.billing_service import billing_service
from app.models.school import School
from app.models.user import StudentProfile
from app.models.school_registration import StudentSchoolRegistration, RegistrationStatus

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


@router.post("/signup", response_model=UserResponse)
def signup(user: UserCreate, db: Session = Depends(get_db)):
    # Validate role
    if user.role not in [role.value for role in UserRole]:
        raise HTTPException(status_code=400, detail="Invalid role")

    if user.role in [UserRole.SUPER_ADMIN.value, UserRole.PARENT.value]:
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


def generate_school_code(db: Session) -> str:
    """
    Generate a unique 8-character school code.
    Format: 8 chars, uppercase alphanumeric. Exclude ambiguous chars: 0, O, 1, I, L.
    Algorithm: uuid4() → base36 encode → first 8 chars → uniqueness check against DB → retry on collision (max 10 attempts)
    """
    import random
    import string

    # Characters to exclude: 0, O, 1, I, L
    valid_chars = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"

    for _ in range(10):  # Max 10 attempts
        # Generate a random string of 8 characters
        school_code = ''.join(random.choices(valid_chars, k=8))

        # Check if this code already exists
        existing_school = db.query(School).filter(School.school_code == school_code).first()
        if not existing_school:
            return school_code

    # If we couldn't generate a unique code after 10 attempts, raise an error
    raise RuntimeError("Could not generate unique school code after 10 attempts")


@router.post("/register/school-admin", response_model=SchoolAdminRegisterResponse, status_code=201)
def register_school_admin(request: SchoolAdminRegisterRequest, db: Session = Depends(get_db)):
    """
    Register a new school admin and create a pending school.

    This endpoint creates both a user account and a school record in a single
    atomic transaction. The school will have PENDING_APPROVAL status until
    approved by a super admin.

    Args:
        request: School admin registration data including admin details and school info
        db: Database session

    Returns:
        SchoolAdminRegisterResponse with user_id, school_id, and status

    Raises:
        HTTPException: 400 if email already registered, 500 on transaction failure
    """
    # Check if email is already registered
    if get_user_by_email(db, email=request.admin_email):
        raise HTTPException(status_code=400, detail="Email already registered")

    # Use explicit transaction for atomic multi-table operations
    # This ensures both user and school are created together or not at all
    try:
        # Create school admin user
        user_create = UserCreate(
            email=request.admin_email,
            username=request.admin_email.split("@")[0],  # Use part before @ as username
            password=request.password,
            full_name=request.admin_name,
            role=UserRole.SCHOOL_ADMIN.value
        )
        db_user = create_user(db=db, user=user_create)

        # Create school with PENDING_APPROVAL status and NULL school_code
        school_create = SchoolCreate(
            name=request.school_name,
            country=request.country,
            curriculum_id=request.curriculum_id
        )

        # Create school in database
        db_school = School(
            id=uuid.uuid4(),
            admin_id=db_user.id,
            name=request.school_name,
            slug=re.sub(r'[^a-zA-Z0-9-]', '', request.school_name.lower().replace(' ', '-')),
            school_code=None,  # NULL until approved
            curriculum_id=request.curriculum_id,
            country=request.country,
            timezone="Asia/Makassar",
            status=SchoolStatus.PENDING_APPROVAL,
            is_active=True
        )
        db.add(db_school)
        db.commit()
        db.refresh(db_school)
        db.refresh(db_user)

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Rollback on any other error
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to complete registration. Please try again."
        )

    # TODO: Send confirmation email "Your school is under review."

    return SchoolAdminRegisterResponse(
        user_id=db_user.id,
        school_id=db_school.id,
        status="pending_approval"
    )


@router.post("/register/student", response_model=StudentRegisterResponse, status_code=201)
def register_student(request: StudentRegisterRequest, db: Session = Depends(get_db)):
    """
    Register a new student with a school.

    This endpoint creates a user account, student profile, and registration record
    in a single atomic transaction. The registration will have PENDING status until
    approved by a school admin.

    Args:
        request: Student registration data including school code
        db: Database session

    Returns:
        StudentRegisterResponse with user_id, school_name, and status

    Raises:
        HTTPException: 400 if email already registered, 403 if school not active,
                      422 if invalid school code, 500 on transaction failure
    """
    # Validate school_code length
    if len(request.school_code) != 8:
        raise HTTPException(status_code=422, detail="Invalid school code length. Must be 8 characters.")

    # Find school by school_code
    school = get_school_by_code(db, school_code=request.school_code)

    # Validate school exists and is active
    if not school:
        raise HTTPException(status_code=422, detail="Invalid school code.")

    if school.status != SchoolStatus.ACTIVE:
        if school.status == SchoolStatus.PENDING_APPROVAL:
            raise HTTPException(status_code=403, detail="School is pending approval.")
        elif school.status == SchoolStatus.SUSPENDED:
            raise HTTPException(status_code=403, detail="School is suspended.")

    # Check if email is already registered
    if get_user_by_email(db, email=request.email):
        raise HTTPException(status_code=400, detail="Email already registered")

    # Use explicit transaction for atomic multi-table operations
    # This ensures user, profile, and registration are created together or not at all
    try:
        # Create student user
        user_create = UserCreate(
            email=request.email,
            username=request.email.split("@")[0],  # Use part before @ as username
            password=request.password,
            full_name=request.full_name,
            role=UserRole.STUDENT.value
        )
        db_user = create_user(db=db, user=user_create)

        # Create student profile
        db_student_profile = StudentProfile(
            id=uuid.uuid4(),
            user_id=db_user.id,
            parent_id=db_user.id,  # For now, student is their own parent
            school_id=school.id
        )
        db.add(db_student_profile)

        # Create student registration with PENDING status
        db_registration = StudentSchoolRegistration(
            id=uuid.uuid4(),
            school_id=school.id,
            student_id=db_student_profile.id,
            status=RegistrationStatus.PENDING
        )
        db.add(db_registration)

        db.commit()
        db.refresh(db_user)
        db.refresh(db_student_profile)
        db.refresh(db_registration)

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Rollback on any other error
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to complete registration. Please try again."
        )

    # TODO: Send notification to school admin

    return StudentRegisterResponse(
        user_id=db_user.id,
        school_name=school.name,
        status="pending_approval"
    )


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

    # Get school_id for students
    school_id = None
    if user.role == UserRole.STUDENT and user.student_profile:
        school_id = user.student_profile.school_id

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=str(user.id),
        expires_delta=access_token_expires,
        role=user.role.value,
        school_id=str(school_id) if school_id else None
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role.value,
        "school_id": school_id
    }


@router.get("/me", response_model=CurrentUserResponse)
def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    # Extract user ID from token
    user_id = verify_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Get user from database
    current_user = get_user(db, UUID(user_id))
    if not current_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get school_id for students
    school_id = None
    if current_user.role == UserRole.STUDENT and current_user.student_profile:
        school_id = current_user.student_profile.school_id

    return CurrentUserResponse(
        id=current_user.id,
        email=current_user.email,
        username=current_user.username,
        full_name=current_user.full_name,
        role=current_user.role.value,
        school_id=school_id,
        is_active=current_user.is_active
    )


@router.post("/logout")
def logout():
    # In a stateless JWT system, logout is client-side
    return {"message": "Successfully logged out"}
