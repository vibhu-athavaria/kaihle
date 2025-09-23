from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.crud.lesson import (
    get_study_plan, get_study_plans_by_student, create_study_plan, update_study_plan,
    add_lesson_to_study_plan, remove_lesson_from_study_plan, mark_lesson_completed,
    get_study_plan_progress
)
from app.crud.student import get_student_by_parent_and_id, get_student
from app.schemas.lesson import StudyPlan, StudyPlanCreate, StudyPlanUpdate
from app.models.user import User as UserModel

router = APIRouter()

@router.get("/student/{student_id}", response_model=List[StudyPlan])
def get_student_study_plans(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Get all study plans for a student"""
    # Verify access permissions
    if current_user.role == "parent":
        student = get_student_by_parent_and_id(db, current_user.id, student_id)
        if not student:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Student not found or not authorized"
            )
    elif current_user.role == "student":
        student = get_student(db, student_id)
        if not student or student.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view this student's study plans"
            )
    elif current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    return get_study_plans_by_student(db, student_id)

@router.post("/", response_model=StudyPlan)
def create_new_study_plan(
    study_plan: StudyPlanCreate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Create a new study plan"""
    # Verify access permissions
    if current_user.role == "parent":
        student = get_student_by_parent_and_id(db, current_user.id, study_plan.student_id)
        if not student:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Student not found or not authorized"
            )
    elif current_user.role == "student":
        student = get_student(db, study_plan.student_id)
        if not student or student.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to create study plan for this student"
            )
    elif current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    return create_study_plan(db, study_plan)

@router.get("/{study_plan_id}", response_model=StudyPlan)
def get_study_plan_details(
    study_plan_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Get study plan details"""
    study_plan = get_study_plan(db, study_plan_id)
    if not study_plan:
        raise HTTPException(status_code=404, detail="Study plan not found")
    
    # Verify access permissions
    if current_user.role == "parent":
        student = get_student_by_parent_and_id(db, current_user.id, study_plan.student_id)
        if not student:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view this study plan"
            )
    elif current_user.role == "student":
        student = get_student(db, study_plan.student_id)
        if not student or student.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view this study plan"
            )
    elif current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    return study_plan

@router.put("/{study_plan_id}", response_model=StudyPlan)
def update_study_plan_endpoint(
    study_plan_id: int,
    study_plan_update: StudyPlanUpdate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Update a study plan"""
    study_plan = get_study_plan(db, study_plan_id)
    if not study_plan:
        raise HTTPException(status_code=404, detail="Study plan not found")
    
    # Verify access permissions (same as get_study_plan_details)
    if current_user.role == "parent":
        student = get_student_by_parent_and_id(db, current_user.id, study_plan.student_id)
        if not student:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this study plan"
            )
    elif current_user.role == "student":
        student = get_student(db, study_plan.student_id)
        if not student or student.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this study plan"
            )
    elif current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    updated_study_plan = update_study_plan(db, study_plan_id, study_plan_update)
    return updated_study_plan

@router.post("/{study_plan_id}/lessons/{lesson_id}")
def add_lesson_to_plan(
    study_plan_id: int,
    lesson_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Add a lesson to a study plan"""
    study_plan = get_study_plan(db, study_plan_id)
    if not study_plan:
        raise HTTPException(status_code=404, detail="Study plan not found")
    
    # Verify permissions (same logic as update)
    if current_user.role == "parent":
        student = get_student_by_parent_and_id(db, current_user.id, study_plan.student_id)
        if not student:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    elif current_user.role == "student":
        student = get_student(db, study_plan.student_id)
        if not student or student.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    elif current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    
    study_plan_lesson = add_lesson_to_study_plan(db, study_plan_id, lesson_id)
    return {"message": "Lesson added to study plan successfully"}

@router.delete("/{study_plan_id}/lessons/{lesson_id}")
def remove_lesson_from_plan(
    study_plan_id: int,
    lesson_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Remove a lesson from a study plan"""
    study_plan = get_study_plan(db, study_plan_id)
    if not study_plan:
        raise HTTPException(status_code=404, detail="Study plan not found")
    
    # Verify permissions (same logic as update)
    if current_user.role == "parent":
        student = get_student_by_parent_and_id(db, current_user.id, study_plan.student_id)
        if not student:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    elif current_user.role == "student":
        student = get_student(db, study_plan.student_id)
        if not student or student.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    elif current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    
    success = remove_lesson_from_study_plan(db, study_plan_id, lesson_id)
    if not success:
        raise HTTPException(status_code=404, detail="Lesson not found in study plan")
    return {"message": "Lesson removed from study plan successfully"}

@router.post("/{study_plan_id}/lessons/{lesson_id}/complete")
def complete_lesson(
    study_plan_id: int,
    lesson_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Mark a lesson as completed in a study plan"""
    study_plan = get_study_plan(db, study_plan_id)
    if not study_plan:
        raise HTTPException(status_code=404, detail="Study plan not found")
    
    # Only students can mark lessons as completed
    if current_user.role == "student":
        student = get_student(db, study_plan.student_id)
        if not student or student.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to complete lessons for this student"
            )
    elif current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can mark lessons as completed"
        )
    
    study_plan_lesson = mark_lesson_completed(db, study_plan_id, lesson_id)
    if not study_plan_lesson:
        raise HTTPException(status_code=404, detail="Lesson not found in study plan")
    
    return {"message": "Lesson marked as completed"}

@router.get("/{study_plan_id}/progress")
def get_study_plan_progress_endpoint(
    study_plan_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Get progress statistics for a study plan"""
    study_plan = get_study_plan(db, study_plan_id)
    if not study_plan:
        raise HTTPException(status_code=404, detail="Study plan not found")
    
    # Verify permissions (same logic as get details)
    if current_user.role == "parent":
        student = get_student_by_parent_and_id(db, current_user.id, study_plan.student_id)
        if not student:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    elif current_user.role == "student":
        student = get_student(db, study_plan.student_id)
        if not student or student.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    elif current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    
    return get_study_plan_progress(db, study_plan_id)
