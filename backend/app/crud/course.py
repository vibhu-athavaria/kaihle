from sqlalchemy.orm import Session
from app.models.course import Course
from app.schemas.course import CourseCreate, CourseUpdate
from typing import Optional, List
from uuid import UUID

def get_course(db: Session, course_id: UUID) -> Optional[Course]:
    return db.query(Course).filter(Course.id == course_id).first()

def get_courses(db: Session, skip: int = 0, limit: int = 100, subject_id: Optional[UUID] = None, difficulty_level: Optional[int] = None) -> List[Course]:
    query = db.query(Course)
    if subject_id:
        query = query.filter(Course.subject_id == subject_id)
    if difficulty_level:
        query = query.filter(Course.difficulty_level == difficulty_level)
    return query.offset(skip).limit(limit).all()

def create_course(db: Session, course: CourseCreate) -> Course:
    db_course = Course(**course.dict())
    db.add(db_course)
    db.commit()
    db.refresh(db_course)
    return db_course

def update_course(db: Session, course_id: UUID, course_update: CourseUpdate) -> Optional[Course]:
    db_course = get_course(db, course_id)
    if not db_course:
        return None
    update_data = course_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_course, field, value)
    db.commit()
    db.refresh(db_course)
    return db_course

def delete_course(db: Session, course_id: UUID) -> bool:
    db_course = get_course(db, course_id)
    if not db_course:
        return False
    db.delete(db_course)
    db.commit()
    return True