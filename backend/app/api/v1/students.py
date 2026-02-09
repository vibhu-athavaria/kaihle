from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.crud.badge import get_student_earned_badges
from app.crud.student import (
    get_student, get_student_by_parent_and_id, update_student, delete_student,
    get_student_with_assessments, update_learning_profile
)
from app.crud.subject import get_subjects_for_student

from app.schemas.badge import StudentBadgeResponse
from app.schemas.dashboard import StudentSubjectDashboardItem
from app.schemas.user import (
    StudentProfileUpdate, StudentProfileResponse, StudentDetailResponse,
    LearningProfileIntakePayload, StudentLearningProfileUpdate
)
from app.models.user import User as UserModel
from app.constants.learning_intake_form import INTAKE_FORM_JSON

router = APIRouter()

@router.get("/{student_id}", response_model=StudentProfileResponse)
def read_student(
    student_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Get student by ID"""
    if current_user.role == "parent":
        student = get_student_by_parent_and_id(db, current_user.id, student_id)
    elif current_user.role == "admin" or current_user.role == "student":
        student = get_student(db, student_id)

    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return student

@router.put("/{student_id}", response_model=StudentProfileResponse)
def update_student_profile(
    student_id: UUID,
    student_update: StudentProfileUpdate,
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

@router.patch("/{student_id}/learning-profile", response_model=StudentLearningProfileUpdate)
def update_student_learning_profile(
    student_id: UUID,
    learning_update: LearningProfileIntakePayload,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Update student learning profile"""
    if current_user.role == "parent":
        # Verify the student belongs to this parent
        existing_student = get_student_by_parent_and_id(db, current_user.id, student_id)
        if not existing_student:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Student not found or not authorized"
            )
    elif current_user.role == "student":
        # Students can only update their own profile
        if not current_user.student_profile or current_user.student_profile.id != student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Students can only update their own profile"
            )
    elif current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )

    updated_student = update_learning_profile(db, student_id, learning_update)
    if not updated_student:
        raise HTTPException(status_code=404, detail="Student not found")
    return updated_student

@router.get("/learning-profile/intake-form")
def get_learning_profile_intake_form():
    return INTAKE_FORM_JSON

@router.get("/{student_id}/assessments", response_model=StudentDetailResponse)
def get_student_assessments(
    student_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Get student's assessments information (only if user is the parent, student, or admin)"""
    if current_user.role == "parent":
        # Verify the student belongs to this parent
        student = get_student_by_parent_and_id(db, current_user.id, student_id)
        if not student:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Student not found or not authorized"
            )
    elif current_user.role == "student":
        # Students can only view their own profile
        if not current_user.student_profile or current_user.student_profile.id != student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Students can only view their own profile"
            )
    elif current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )

    student = get_student_with_assessments(db, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return student

@router.delete("/{student_id}")
def delete_student_profile(
    student_id: UUID,
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

@router.get("/{student_id}/subjects", response_model=list[StudentSubjectDashboardItem])
def get_student_subjects(student_id: str, db: Session = Depends(get_db), current_user: UserModel = Depends(get_current_active_user)):
    return get_subjects_for_student(db, student_id)

@router.get("/{student_id}/badges", response_model=list[StudentBadgeResponse])
def get_student_badges(student_id: str, db: Session = Depends(get_db), current_user: UserModel = Depends(get_current_active_user)):
    return get_student_earned_badges(db, student_id)