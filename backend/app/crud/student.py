from sqlalchemy.orm import Session
from app.models.user import Student
from app.schemas.user import StudentUpdate
from typing import Optional
from app.core.security import verify_password

def get_student(db: Session, student_id: int) -> Optional[Student]:
    return db.query(Student).filter(Student.id == student_id).first()

def get_student_by_username(db: Session, username: str) -> Optional[Student]:
    query = db.query(Student).filter(Student.username == username)
    print(str(query.statement))   # prints the SQL (with placeholders like :param_1)
    return query.first()

def update_student(db: Session, student_id: int, student_update: StudentUpdate) -> Optional[Student]:
    db_student = get_student(db, student_id)
    if not db_student:
        return None

    update_data = student_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_student, field, value)

    db.commit()
    db.refresh(db_student)
    return db_student

def delete_student(db: Session, student_id: int) -> bool:
    db_student = get_student(db, student_id)
    if not db_student:
        return False

    db.delete(db_student)
    db.commit()
    return True

def get_student_by_parent_and_id(db: Session, parent_id: int, student_id: int) -> Optional[Student]:
    return db.query(Student).filter(
        Student.parent_id == parent_id,
        Student.id == student_id
    ).first()

def authenticate_student(db: Session, username: str, password: str) -> Optional[Student]:
    student = get_student_by_username(db, username)
    if not student:
        return None
    if not verify_password(password, student.hashed_password):
        return None
    return student