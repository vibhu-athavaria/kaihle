from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from app.models.progress import Progress, Badge, StudentBadge
from app.schemas.progress import ProgressCreate, ProgressUpdate, BadgeCreate
from typing import Optional, List
from datetime import datetime, timedelta
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

# Badge management
def create_badge(db: Session, badge: BadgeCreate) -> Badge:
    db_badge = Badge(**badge.dict())
    db.add(db_badge)
    db.commit()
    db.refresh(db_badge)
    return db_badge

def get_all_badges(db: Session) -> List[Badge]:
    return db.query(Badge).all()

def get_badge(db: Session, badge_id: UUID) -> Optional[Badge]:
    return db.query(Badge).filter(Badge.id == badge_id).first()

def award_badge_to_student(db: Session, student_id: UUID, badge_id: UUID) -> StudentBadge:
    # Check if student already has this badge
    existing = db.query(StudentBadge).filter(
        StudentBadge.student_id == student_id,
        StudentBadge.badge_id == badge_id
    ).first()

    if existing:
        return existing

    db_student_badge = StudentBadge(
        student_id=student_id,
        badge_id=badge_id
    )
    db.add(db_student_badge)
    db.commit()
    db.refresh(db_student_badge)
    return db_student_badge

def get_student_badges(db: Session, student_id: UUID) -> List[StudentBadge]:
    return db.query(StudentBadge).filter(
        StudentBadge.student_id == student_id
    ).all()

def check_and_award_badges(db: Session, student_id: UUID):
    """Check if student qualifies for any badges and award them"""
    total_points = get_student_total_points(db, student_id)

    # Get all badges the student doesn't have yet
    earned_badge_ids = db.query(StudentBadge.badge_id).filter(
        StudentBadge.student_id == student_id
    ).subquery()

    available_badges = db.query(Badge).filter(
        ~Badge.id.in_(earned_badge_ids),
        Badge.points_required <= total_points
    ).all()

    # Award qualifying badges
    for badge in available_badges:
        award_badge_to_student(db, student_id, badge.id)
