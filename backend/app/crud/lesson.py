from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models.lesson import Lesson, StudyPlan, StudyPlanLesson
from app.schemas.lesson import LessonCreate, LessonUpdate, StudyPlanCreate, StudyPlanUpdate, StudyPlanLessonCreate
from typing import Optional, List

# Lesson CRUD operations
def get_lesson(db: Session, lesson_id: int) -> Optional[Lesson]:
    return db.query(Lesson).filter(Lesson.id == lesson_id).first()

def get_lessons(db: Session, skip: int = 0, limit: int = 100, subject: Optional[str] = None, difficulty: Optional[str] = None) -> List[Lesson]:
    query = db.query(Lesson).filter(Lesson.is_active == True)
    
    if subject:
        query = query.filter(Lesson.subject == subject)
    if difficulty:
        query = query.filter(Lesson.difficulty_level == difficulty)
    
    return query.offset(skip).limit(limit).all()

def create_lesson(db: Session, lesson: LessonCreate) -> Lesson:
    db_lesson = Lesson(**lesson.dict())
    db.add(db_lesson)
    db.commit()
    db.refresh(db_lesson)
    return db_lesson

def update_lesson(db: Session, lesson_id: int, lesson_update: LessonUpdate) -> Optional[Lesson]:
    db_lesson = get_lesson(db, lesson_id)
    if not db_lesson:
        return None
    
    update_data = lesson_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_lesson, field, value)
    
    db.commit()
    db.refresh(db_lesson)
    return db_lesson

def delete_lesson(db: Session, lesson_id: int) -> bool:
    db_lesson = get_lesson(db, lesson_id)
    if not db_lesson:
        return False
    
    # Soft delete by setting is_active to False
    db_lesson.is_active = False
    db.commit()
    return True

# Study Plan CRUD operations
def get_study_plan(db: Session, study_plan_id: int) -> Optional[StudyPlan]:
    return db.query(StudyPlan).filter(StudyPlan.id == study_plan_id).first()

def get_study_plans_by_student(db: Session, student_id: int) -> List[StudyPlan]:
    return db.query(StudyPlan).filter(
        StudyPlan.student_id == student_id,
        StudyPlan.is_active == True
    ).order_by(desc(StudyPlan.created_at)).all()

def create_study_plan(db: Session, study_plan: StudyPlanCreate) -> StudyPlan:
    # Create the study plan
    study_plan_data = study_plan.dict(exclude={'lesson_ids'})
    db_study_plan = StudyPlan(**study_plan_data)
    db.add(db_study_plan)
    db.commit()
    db.refresh(db_study_plan)
    
    # Add lessons to the study plan
    for index, lesson_id in enumerate(study_plan.lesson_ids):
        study_plan_lesson = StudyPlanLesson(
            study_plan_id=db_study_plan.id,
            lesson_id=lesson_id,
            order_index=index
        )
        db.add(study_plan_lesson)
    
    db.commit()
    db.refresh(db_study_plan)
    return db_study_plan

def update_study_plan(db: Session, study_plan_id: int, study_plan_update: StudyPlanUpdate) -> Optional[StudyPlan]:
    db_study_plan = get_study_plan(db, study_plan_id)
    if not db_study_plan:
        return None
    
    update_data = study_plan_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_study_plan, field, value)
    
    db.commit()
    db.refresh(db_study_plan)
    return db_study_plan

def add_lesson_to_study_plan(db: Session, study_plan_id: int, lesson_id: int) -> Optional[StudyPlanLesson]:
    # Check if lesson is already in the study plan
    existing = db.query(StudyPlanLesson).filter(
        StudyPlanLesson.study_plan_id == study_plan_id,
        StudyPlanLesson.lesson_id == lesson_id
    ).first()
    
    if existing:
        return existing
    
    # Get the next order index
    max_order = db.query(StudyPlanLesson).filter(
        StudyPlanLesson.study_plan_id == study_plan_id
    ).count()
    
    study_plan_lesson = StudyPlanLesson(
        study_plan_id=study_plan_id,
        lesson_id=lesson_id,
        order_index=max_order
    )
    db.add(study_plan_lesson)
    db.commit()
    db.refresh(study_plan_lesson)
    return study_plan_lesson

def remove_lesson_from_study_plan(db: Session, study_plan_id: int, lesson_id: int) -> bool:
    study_plan_lesson = db.query(StudyPlanLesson).filter(
        StudyPlanLesson.study_plan_id == study_plan_id,
        StudyPlanLesson.lesson_id == lesson_id
    ).first()
    
    if not study_plan_lesson:
        return False
    
    db.delete(study_plan_lesson)
    db.commit()
    return True

def mark_lesson_completed(db: Session, study_plan_id: int, lesson_id: int) -> Optional[StudyPlanLesson]:
    study_plan_lesson = db.query(StudyPlanLesson).filter(
        StudyPlanLesson.study_plan_id == study_plan_id,
        StudyPlanLesson.lesson_id == lesson_id
    ).first()
    
    if not study_plan_lesson:
        return None
    
    study_plan_lesson.is_completed = True
    study_plan_lesson.completed_at = datetime.utcnow()
    db.commit()
    db.refresh(study_plan_lesson)
    return study_plan_lesson

def get_study_plan_progress(db: Session, study_plan_id: int) -> dict:
    total_lessons = db.query(StudyPlanLesson).filter(
        StudyPlanLesson.study_plan_id == study_plan_id
    ).count()
    
    completed_lessons = db.query(StudyPlanLesson).filter(
        StudyPlanLesson.study_plan_id == study_plan_id,
        StudyPlanLesson.is_completed == True
    ).count()
    
    progress_percentage = (completed_lessons / total_lessons * 100) if total_lessons > 0 else 0
    
    return {
        "total_lessons": total_lessons,
        "completed_lessons": completed_lessons,
        "progress_percentage": round(progress_percentage, 2)
    }
