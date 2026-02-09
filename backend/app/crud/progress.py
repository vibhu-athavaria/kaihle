from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from app.models.progress import Progress
from app.schemas.progress import ProgressCreate, ProgressUpdate
from typing import Optional, List
from datetime import datetime
from uuid import UUID

def get_progress(db: Session, progress_id: UUID) -> Optional[Progress]:
    return db.query(Progress).filter(Progress.id == progress_id).first()

def get_progress_by_student_and_week(db: Session, student_id: UUID, week_start: datetime) -> Optional[Progress]:
    return db.query(Progress).filter(
        Progress.student_id == student_id,
        Progress.week_start == week_start
    ).first()

def create_progress(db: Session, progress: ProgressCreate) -> Progress:
    db_progress = Progress(**progress.dict())
    db.add(db_progress)
    db.commit()
    db.refresh(db_progress)
    return db_progress

def update_progress(db: Session, progress_id: UUID, progress_update: ProgressUpdate) -> Optional[Progress]:
    db_progress = get_progress(db, progress_id)
    if not db_progress:
        return None

    update_data = progress_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_progress, field, value)

    db.commit()
    db.refresh(db_progress)
    return db_progress

def get_student_progress_history(db: Session, student_id: UUID, limit: int = 10) -> List[Progress]:
    return db.query(Progress).filter(
        Progress.student_id == student_id
    ).order_by(desc(Progress.week_start)).limit(limit).all()

def get_student_total_points(db: Session, student_id: UUID) -> int:
    result = db.query(func.sum(Progress.points_earned)).filter(
        Progress.student_id == student_id
    ).scalar()
    return result or 0

def get_student_current_streak(db: Session, student_id: UUID) -> int:
    # Get the most recent progress record
    latest_progress = db.query(Progress).filter(
        Progress.student_id == student_id
    ).order_by(desc(Progress.week_start)).first()

    return latest_progress.streak_days if latest_progress else 0

def get_student_total_lessons(db: Session, student_id: UUID) -> int:
    result = db.query(func.sum(Progress.lessons_completed)).filter(
        Progress.student_id == student_id
    ).scalar()
    return result or 0
