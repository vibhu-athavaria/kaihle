from uuid import UUID
from sqlalchemy.orm import Session
from app.models.school import School
from app.schemas.school import SchoolCreate, SchoolUpdate
from typing import Optional, List


def get_school(db: Session, school_id: UUID) -> Optional[School]:
    """Get school by ID"""
    return db.query(School).filter(School.id == school_id).first()


def get_schools(db: Session, skip: int = 0, limit: int = 100) -> List[School]:
    """Get all schools with pagination"""
    return db.query(School).offset(skip).limit(limit).all()


def get_school_by_admin(db: Session, admin_id: UUID) -> Optional[School]:
    """Get school by admin ID"""
    return db.query(School).filter(School.admin_id == admin_id).first()


def create_school(db: Session, school: SchoolCreate) -> School:
    """Create a new school"""
    db_school = School(**school.dict())
    db.add(db_school)
    db.commit()
    db.refresh(db_school)
    return db_school


def update_school(db: Session, school_id: UUID, school_update: SchoolUpdate) -> Optional[School]:
    """Update a school"""
    db_school = db.query(School).filter(School.id == school_id).first()
    if db_school:
        update_data = school_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_school, field, value)
        db.commit()
        db.refresh(db_school)
    return db_school


def delete_school(db: Session, school_id: UUID) -> bool:
    """Delete a school"""
    db_school = db.query(School).filter(School.id == school_id).first()
    if db_school:
        db.delete(db_school)
        db.commit()
        return True
    return False