from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.deps import get_current_active_user, get_current_admin_user
from app.crud.lesson import (
    get_lesson, get_lessons, create_lesson, update_lesson, delete_lesson
)
from app.schemas.lesson import Lesson, LessonCreate, LessonUpdate
from app.models.user import User as UserModel

router = APIRouter()

@router.get("/", response_model=List[Lesson])
def read_lessons(
    skip: int = 0,
    limit: int = 100,
    subject: Optional[str] = Query(None),
    difficulty: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Get all lessons with optional filtering"""
    return get_lessons(db, skip=skip, limit=limit, subject=subject, difficulty=difficulty)

@router.get("/{lesson_id}", response_model=Lesson)
def read_lesson(
    lesson_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Get a specific lesson by ID"""
    lesson = get_lesson(db, lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")
    return lesson

@router.post("/", response_model=Lesson)
def create_new_lesson(
    lesson: LessonCreate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_admin_user)
):
    """Create a new lesson (admin only)"""
    return create_lesson(db, lesson)

@router.put("/{lesson_id}", response_model=Lesson)
def update_lesson_endpoint(
    lesson_id: int,
    lesson_update: LessonUpdate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_admin_user)
):
    """Update a lesson (admin only)"""
    updated_lesson = update_lesson(db, lesson_id, lesson_update)
    if not updated_lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")
    return updated_lesson

@router.delete("/{lesson_id}")
def delete_lesson_endpoint(
    lesson_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_admin_user)
):
    """Delete a lesson (admin only)"""
    success = delete_lesson(db, lesson_id)
    if not success:
        raise HTTPException(status_code=404, detail="Lesson not found")
    return {"message": "Lesson deleted successfully"}
