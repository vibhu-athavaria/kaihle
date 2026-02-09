from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from app.models.badge import Badge, StudentBadge
from app.schemas.badge import BadgeResponse, BadgeCreate, StudentBadgeResponse
from app.crud.progress import get_student_total_points, get_student_total_lessons
from typing import Optional, List
from uuid import UUID


def create_badge(db: Session, badge: BadgeCreate) -> BadgeResponse:
    db_badge = Badge(**badge.dict())
    db.add(db_badge)
    db.commit()
    db.refresh(db_badge)
    return db_badge

def get_all_badges(db: Session) -> List[BadgeResponse]:
    return db.query(Badge).all()

def get_badge(db: Session, badge_id: UUID) -> Optional[BadgeResponse]:
    return db.query(Badge).filter(Badge.id == badge_id).first()

def award_badge_to_student(db: Session, student_id: UUID, badge_id: UUID) -> StudentBadgeResponse:
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

def get_student_earned_badges(db: Session, student_id: UUID):
    badges = (
        db.query(StudentBadge)
        .filter(StudentBadge.student_id == student_id)
        .all()
    )

    return [
        {
            "id": str(b.id),
            "name": b.badge.name,
            "icon": b.badge.icon,
            "color_key": b.badge.color_key,
            "unlocked": b.unlocked,
        }
        for b in badges
    ]


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
