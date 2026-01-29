from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.deps import get_current_active_user, get_current_admin_user
from app.crud.study_plan import (
    get_course, get_courses, create_course, update_course, delete_course
)
from app.schemas.study_plan import Course, CourseCreate, CourseUpdate
from app.models.user import User as UserModel

router = APIRouter()

@router.get("/", response_model=List[Course])
def read_courses(
    skip: int = 0,
    limit: int = 100,
    subject: Optional[str] = Query(None),
    difficulty: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Get all courses with optional filtering"""
    return get_courses(db, skip=skip, limit=limit, subject=subject, difficulty=difficulty)

@router.get("/{course_id}", response_model=Course)
def read_course(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Get a specific course by ID"""
    course = get_course(db, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return course

@router.post("/", response_model=Course)
def create_new_course(
    course: CourseCreate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_admin_user)
):
    """Create a new course (admin only)"""
    return create_course(db, course)

@router.put("/{course_id}", response_model=Course)
def update_course_endpoint(
    course_id: int,
    course_update: CourseUpdate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_admin_user)
):
    """Update a course (admin only)"""
    updated_course = update_course(db, course_id, course_update)
    if not updated_course:
        raise HTTPException(status_code=404, detail="Course not found")
    return updated_course

@router.delete("/{course_id}")
def delete_course_endpoint(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_admin_user)
):
    """Delete a course (admin only)"""
    success = delete_course(db, course_id)
    if not success:
        raise HTTPException(status_code=404, detail="Course not found")
    return {"message": "Course deleted successfully"}
