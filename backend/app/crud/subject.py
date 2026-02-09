from uuid import UUID
from sqlalchemy.orm import Session
from app.models.subject import Subject
from app.models.curriculum import CurriculumSubject
from app.models.user import StudentProfile
from app.models.assessment import Assessment


def get_all_subject(db: Session):
    """Get teacher by ID"""
    return db.query(Subject).filter(is_active=True).all()

def get_subject_by_curriculum(db: Session, curriculum_id: UUID):
    """Get teacher by ID"""
    return db.query(Subject).filter(Subject.curriculum_id == curriculum_id).all()


def get_subjects_for_student(db: Session, student_id: UUID):
    student = (
        db.query(StudentProfile)
        .filter(StudentProfile.id == student_id)
        .first()
    )

    if not student or not student.curriculum_id:
        return []

    subjects = (
        db.query(Subject)
        .join(CurriculumSubject)
        .filter(CurriculumSubject.curriculum_id == student.curriculum_id)
        .filter(Subject.is_active == True)
        .all()
    )

    assessments = (
        db.query(Assessment)
        .filter(Assessment.student_id == student_id)
        .order_by(Assessment.created_at.desc())
        .all()
    )

    assessments_by_subject = {}
    for a in assessments:
        if a.subject_id not in assessments_by_subject:
            assessments_by_subject[a.subject_id] = a

    response = []

    for subject in subjects:
        assessment = assessments_by_subject.get(subject.id)

        if not assessment:
            status = "not_started"
            progress = None
            assessment_id = None
        elif assessment.status in ["started", "in_progress"]:
            status = "in_progress"
            progress = (
                (assessment.questions_answered / assessment.total_questions) * 100
                if assessment.total_questions > 0
                else 0
            )
            assessment_id = assessment.id
        else:
            status = "completed"
            progress = 100
            assessment_id = assessment.id

        response.append({
            "subject": {
                "id": str(subject.id),
                "name": subject.name,
                "code": subject.code,
                "icon": subject.icon,
                "gradient_key": subject.gradient_key,
            },
            "status": status,
            "description": subject.description or "",
            "assessment_id": assessment_id,
            "progress": progress,
        })

    return response

