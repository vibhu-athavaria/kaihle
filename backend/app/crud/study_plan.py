from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models.study_plan import StudyPlan, StudyPlanCourse
from app.schemas.course import CourseCreate, CourseUpdate, StudyPlanCreate, StudyPlanUpdate, StudyPlanCourseCreate
from typing import Optional, List


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
    study_plan_data = study_plan.dict(exclude={'course_ids'})
    db_study_plan = StudyPlan(**study_plan_data)
    db.add(db_study_plan)
    db.commit()
    db.refresh(db_study_plan)

    # Add courses to the study plan
    for index, course_id in enumerate(study_plan.course_ids):
        study_plan_course = StudyPlanCourse(
            study_plan_id=db_study_plan.id,
            course_id=course_id,
            order_index=index
        )
        db.add(study_plan_course)

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

def add_course_to_study_plan(db: Session, study_plan_id: int, course_id: int) -> Optional[StudyPlanCourse]:
    # Check if course is already in the study plan
    existing = db.query(StudyPlanCourse).filter(
        StudyPlanCourse.study_plan_id == study_plan_id,
        StudyPlanCourse.course_id == course_id
    ).first()

    if existing:
        return existing

    # Get the next order index
    max_order = db.query(StudyPlanCourse).filter(
        StudyPlanCourse.study_plan_id == study_plan_id
    ).count()

    study_plan_course = StudyPlanCourse(
        study_plan_id=study_plan_id,
        course_id=course_id,
        order_index=max_order
    )
    db.add(study_plan_course)
    db.commit()
    db.refresh(study_plan_course)
    return study_plan_course

def remove_course_from_study_plan(db: Session, study_plan_id: int, course_id: int) -> bool:
    study_plan_course = db.query(StudyPlanCourse).filter(
        StudyPlanCourse.study_plan_id == study_plan_id,
        StudyPlanCourse.course_id == course_id
    ).first()

    if not study_plan_course:
        return False

    db.delete(study_plan_course)
    db.commit()
    return True

def mark_course_completed(db: Session, study_plan_id: int, course_id: int) -> Optional[StudyPlanCourse]:
    study_plan_course = db.query(StudyPlanCourse).filter(
        StudyPlanCourse.study_plan_id == study_plan_id,
        StudyPlanCourse.course_id == course_id
    ).first()

    if not study_plan_course:
        return None

    study_plan_course.is_completed = True
    study_plan_course.completed_at = datetime.utcnow()
    db.commit()
    db.refresh(study_plan_course)
    return study_plan_course

def get_study_plan_progress(db: Session, study_plan_id: int) -> dict:
    total_courses = db.query(StudyPlanCourse).filter(
        StudyPlanCourse.study_plan_id == study_plan_id
    ).count()

    completed_courses = db.query(StudyPlanCourse).filter(
        StudyPlanCourse.study_plan_id == study_plan_id,
        StudyPlanCourse.is_completed == True
    ).count()

    progress_percentage = (completed_courses / total_courses * 100) if total_courses > 0 else 0

    return {
        "total_courses": total_courses,
        "completed_courses": completed_courses,
        "progress_percentage": round(progress_percentage, 2)
    }
