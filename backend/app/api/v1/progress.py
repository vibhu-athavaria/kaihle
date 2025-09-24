from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.deps import get_current_active_user, get_current_admin_user
from app.crud.progress import (
    get_progress_by_student_and_week, create_progress, update_progress,
    get_student_progress_history, get_student_total_points, get_student_current_streak,
    get_student_total_lessons, get_student_badges, check_and_award_badges,
    create_badge, get_all_badges
)
from app.crud.student import get_student_by_parent_and_id, get_student
from app.schemas.progress import (
    Progress, ProgressCreate, ProgressUpdate, ProgressSummary,
    Badge, BadgeCreate, StudentBadgeResponse
)
from app.models.user import User as UserModel
from datetime import datetime

router = APIRouter()

@router.get("/{student_id}", response_model=ProgressSummary)
def get_student_progress_summary(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Get comprehensive progress summary for a student"""
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
        if not student or student.id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view this student's progress"
            )
    elif current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )

    # Get progress data
    total_points = get_student_total_points(db, student_id)
    current_streak = get_student_current_streak(db, student_id)
    total_lessons = get_student_total_lessons(db, student_id)
    badges = get_student_badges(db, student_id)
    weekly_progress = get_student_progress_history(db, student_id)

    return ProgressSummary(
        total_points=total_points,
        current_streak=current_streak,
        total_lessons_completed=total_lessons,
        badges_earned=badges,
        weekly_progress=weekly_progress
    )

@router.post("/{student_id}", response_model=Progress)
def update_student_progress(
    student_id: int,
    progress_update: ProgressUpdate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Update student progress for current week"""
    # Verify access permissions (only admins and the student themselves can update progress)
    if current_user.role == "student":
        student = get_student(db, student_id)
        if not student or student.id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this student's progress"
            )
    elif current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )

    # Get current week start (Monday)
    now = datetime.now()
    days_since_monday = now.weekday()
    week_start = now - timedelta(days=days_since_monday)
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)

    # Get or create progress record for this week
    existing_progress = get_progress_by_student_and_week(db, student_id, week_start)

    if existing_progress:
        updated_progress = update_progress(db, existing_progress.id, progress_update)
    else:
        progress_data = ProgressCreate(
            student_id=student_id,
            week_start=week_start,
            **progress_update.dict(exclude_unset=True)
        )
        updated_progress = create_progress(db, progress_data)

    # Check and award badges
    check_and_award_badges(db, student_id)

    return updated_progress

@router.get("/{student_id}/history", response_model=List[Progress])
def get_student_progress_history_endpoint(
    student_id: int,
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Get student's progress history"""
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
        if not student or student.id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view this student's progress"
            )
    elif current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )

    return get_student_progress_history(db, student_id, limit)

# Badge management endpoints
@router.post("/badges", response_model=Badge)
def create_new_badge(
    badge: BadgeCreate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_admin_user)
):
    """Create a new badge (admin only)"""
    return create_badge(db, badge)

@router.get("/badges", response_model=List[Badge])
def list_all_badges(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Get all available badges"""
    return get_all_badges(db)
