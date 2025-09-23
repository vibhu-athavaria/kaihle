from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.crud.student import get_student_by_parent_and_id, update_student, delete_student
from app.schemas.user import Student, StudentUpdate
from app.models.user import User as UserModel

router = APIRouter()

@router.get("/{student_id}", response_model=Student)
def read_student(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Get student by ID (only if user is the parent or admin)"""
    if current_user.role == "admin":
        from app.crud.student import get_student
        student = get_student(db, student_id)
    elif current_user.role == "parent":
        student = get_student_by_parent_and_id(db, current_user.id, student_id)
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return student

@router.put("/{student_id}", response_model=Student)
def update_student_profile(
    student_id: int,
    student_update: StudentUpdate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Update student profile (only if user is the parent or admin)"""
    if current_user.role == "parent":
        # Verify the student belongs to this parent
        existing_student = get_student_by_parent_and_id(db, current_user.id, student_id)
        if not existing_student:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Student not found or not authorized"
            )
    elif current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    updated_student = update_student(db, student_id, student_update)
    if not updated_student:
        raise HTTPException(status_code=404, detail="Student not found")
    return updated_student

@router.delete("/{student_id}")
def delete_student_profile(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Delete student profile (only if user is the parent or admin)"""
    if current_user.role == "parent":
        # Verify the student belongs to this parent
        existing_student = get_student_by_parent_and_id(db, current_user.id, student_id)
        if not existing_student:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Student not found or not authorized"
            )
    elif current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    success = delete_student(db, student_id)
    if not success:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"message": "Student deleted successfully"}
