from uuid import UUID
from sqlalchemy.orm import Session
from app.models.teacher import Teacher
from app.schemas.teacher import TeacherCreate, TeacherUpdate
from typing import Optional, List


def get_teacher(db: Session, teacher_id: UUID) -> Optional[Teacher]:
    """Get teacher by ID"""
    return db.query(Teacher).filter(Teacher.id == teacher_id).first()


def get_teacher_by_user(db: Session, user_id: UUID) -> Optional[Teacher]:
    """Get teacher by user ID"""
    return db.query(Teacher).filter(Teacher.user_id == user_id).first()


def get_teachers_by_school(db: Session, school_id: UUID, skip: int = 0, limit: int = 100) -> List[Teacher]:
    """Get teachers by school ID with pagination"""
    return db.query(Teacher).filter(Teacher.school_id == school_id).offset(skip).limit(limit).all()


def create_teacher(db: Session, teacher: TeacherCreate) -> Teacher:
    """Create a new teacher"""
    db_teacher = Teacher(**teacher.dict())
    db.add(db_teacher)
    db.commit()
    db.refresh(db_teacher)
    return db_teacher


def update_teacher(db: Session, teacher_id: UUID, teacher_update: TeacherUpdate) -> Optional[Teacher]:
    """Update a teacher"""
    db_teacher = db.query(Teacher).filter(Teacher.id == teacher_id).first()
    if db_teacher:
        update_data = teacher_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_teacher, field, value)
        db.commit()
        db.refresh(db_teacher)
    return db_teacher


def delete_teacher(db: Session, teacher_id: UUID) -> bool:
    """Delete a teacher"""
    db_teacher = db.query(Teacher).filter(Teacher.id == teacher_id).first()
    if db_teacher:
        db.delete(db_teacher)
        db.commit()
        return True
    return False