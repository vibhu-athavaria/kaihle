from uuid import UUID
from sqlalchemy.orm import Session
from app.models.subject import Subject


def get_all_subject(db: Session):
    """Get teacher by ID"""
    return db.query(Subject).filter(is_active=True).all()

def get_subject_by_curriculum(db: Session, curriculum_id: UUID):
    """Get teacher by ID"""
    return db.query(Subject).filter(Subject.curriculum_id == curriculum_id).all()
