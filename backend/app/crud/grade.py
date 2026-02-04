from uuid import UUID
from sqlalchemy.orm import Session
from typing import List
from app.models.curriculum import Grade
from app.schemas.grade import GradeCreate, GradeUpdate


def get_grades(db: Session) -> List[Grade]:
    return db.query(Grade).filter(Grade.is_active == True).order_by(Grade.level).all()


def get_grade(db: Session, grade_id: UUID) -> Grade:
    return db.query(Grade).filter(Grade.id == grade_id).first()


def create_grade(db: Session, grade: GradeCreate) -> Grade:
    db_grade = Grade(**grade.model_dump())
    db.add(db_grade)
    db.commit()
    db.refresh(db_grade)
    return db_grade


def update_grade(db: Session, grade_id: UUID, grade_update: GradeUpdate) -> Grade:
    db_grade = db.query(Grade).filter(Grade.id == grade_id).first()
    if db_grade:
        for key, value in grade_update.model_dump(exclude_unset=True).items():
            setattr(db_grade, key, value)
        db.commit()
        db.refresh(db_grade)
    return db_grade


def delete_grade(db: Session, grade_id: UUID) -> bool:
    db_grade = db.query(Grade).filter(Grade.id == grade_id).first()
    if db_grade:
        db.delete(db_grade)
        db.commit()
        return True
    return False