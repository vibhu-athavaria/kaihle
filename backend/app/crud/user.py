from sqlalchemy.orm import Session, joinedload
from app.models.user import User, StudentProfile, UserRole
from app.schemas.user import UserCreate, UserUpdate, StudentProfileCreate, StudentProfileUpdate
from app.core.security import get_password_hash, verify_password
from typing import Optional

def get_user(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).options(joinedload(User.student_profile)).filter(User.id == user_id).first()

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()

def get_user_by_username(db: Session, username: str) -> Optional[User]:
    return db.query(User).filter(User.username == username).first()

def create_user(db: Session, user: UserCreate) -> User:
    hashed_password = get_password_hash(user.password)
    db_user = User(
        email=user.email,
        username=user.username,
        hashed_password=hashed_password,
        full_name=user.full_name,
        role=user.role
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def authenticate_user(db: Session, identifier: str, password: str) -> Optional[User]:
    # Identifier can be email or username
    user = None
    if "@" in identifier:  # crude check: treat as email
        user = get_user_by_email(db, identifier)
    else:
        user = get_user_by_username(db, identifier)

    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user

def update_user(db: Session, user_id: int, user_update: UserUpdate) -> Optional[User]:
    db_user = get_user(db, user_id)
    if not db_user:
        return None

    update_data = user_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_user, field, value)

    db.commit()
    db.refresh(db_user)
    return db_user

def create_student(db: Session, student: StudentProfileCreate, parent_id: int) -> StudentProfile:
    hashed_password = get_password_hash(student.password)
    # Step 1: Create a User entry for the student
    student_user = User(
        role=UserRole.STUDENT,
        full_name=student.name,
        username=student.username,   # required for student
        email=student.email,         # optional
        hashed_password=hashed_password  # should be hashed before
    )
    db.add(student_user)
    db.commit()
    db.refresh(student_user)

    # Step 2: Create StudentProfile linked to that user and parent
    db_student_profile = StudentProfile(
        user_id=student_user.id,
        parent_id=parent_id,
        age=student.age,
        grade_level=student.grade_level,
        math_checkpoint=student.checkpoints.get("math") if student.checkpoints else None,
        science_checkpoint=student.checkpoints.get("science") if student.checkpoints else None,
        english_checkpoint=student.checkpoints.get("english") if student.checkpoints else None,
    )
    db.add(db_student_profile)
    db.commit()
    db.refresh(db_student_profile)

    return db_student_profile

def update_student(db: Session, student_id: int, student_update: StudentProfileUpdate) -> Optional[StudentProfile]:
    db_student = db.query(StudentProfile).filter(StudentProfile.id == student_id).first()
    if not db_student:
        return None

    update_data = student_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_student, field, value)

    db.commit()
    db.refresh(db_student)
    return db_student

def get_students_by_parent(db: Session, parent_id: int):
    return db.query(StudentProfile).filter(StudentProfile.parent_id == parent_id).all()
