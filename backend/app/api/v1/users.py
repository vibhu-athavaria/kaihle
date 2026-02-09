from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.deps import get_current_active_user, get_current_admin_user
from app.crud.user import get_user, update_user, get_students_by_parent, create_student, update_student
from app.schemas.user import User, UserUpdate, StudentProfileCreate, StudentProfileBase, StudentProfileUpdate
from app.models.user import User as UserModel
from app.crud.user import get_user as get_user_crud

router = APIRouter()

@router.get("/me", response_model=User)
def read_user_me(current_user: UserModel = Depends(get_current_active_user)):
    """Get current user's profile"""
    return current_user

@router.put("/me", response_model=User)
def update_user_me(
    user_update: UserUpdate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Update current user's profile"""
    updated_user = update_user(db, current_user.id, user_update)
    if not updated_user:
        raise HTTPException(status_code=404, detail="User not found")
    return updated_user

@router.get("/me/students", response_model=List[StudentProfileBase])
def read_my_students(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Get current user's students (for parents)"""
    if current_user.role != "parent":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only parents can access student information"
        )
    students = get_students_by_parent(db, current_user.id)
    return students

@router.post("/me/students", response_model=StudentProfileBase)
def create_student_for_me(
    student: StudentProfileCreate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Create a new student profile (for parents)"""
    if current_user.role != "parent":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only parents can create student profiles"
        )
    return create_student(db, student, current_user.id)

@router.put("/me/students/{student_id}", response_model=StudentProfileBase)
def update_student_for_me(
    student_id: int,
    student: StudentProfileUpdate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Update a student profile (for parents)"""
    if current_user.role != "parent":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only parents can update student profiles"
        )
    return update_student(db, student_id, student)

@router.get("/{user_id}", response_model=User)
def read_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_admin_user)
):
    """Get user by ID (admin only)"""
    user = get_user_crud(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.put("/{user_id}", response_model=User)
def update_user_by_id(
    user_id: int,
    user_update: UserUpdate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_admin_user)
):
    """Update user by ID (admin only)"""
    updated_user = update_user(db, user_id, user_update)
    if not updated_user:
        raise HTTPException(status_code=404, detail="User not found")
    return updated_user
