from sqlalchemy import desc
from sqlalchemy.sql import func
from sqlalchemy.orm import Session, selectinload
from uuid import UUID

from app.models.user import StudentProfile, User
from app.models.assessment import Assessment, AssessmentStatus, AssessmentType
from app.models.curriculum import CurriculumSubject
from app.models.subject import Subject
from app.schemas.user import StudentProfileUpdate, LearningProfileIntakePayload
from typing import Optional
from app.core.security import verify_password, get_password_hash
from app.services.students import normalize_learning_profile
from app.crud.assessment import resolve_diagnostic_assessment


def get_student(db: Session, student_id: UUID) -> Optional[StudentProfile]:
    return db.query(StudentProfile).filter(StudentProfile.id == student_id).first()

def get_student_by_username(db: Session, username: str) -> Optional[StudentProfile]:
    query = db.query(StudentProfile).filter(StudentProfile.username == username)
    return query.first()

def get_student_with_assessments(db: Session, student_id: UUID) -> Optional[dict]:
    # Load the student and base relations
    query = (
        db.query(StudentProfile)
        .options(selectinload(StudentProfile.user))
        .filter(StudentProfile.id == student_id)
    )

    student = query.first()
    if not student:
        return None

    student_dict = student.__dict__.copy()

    # Fetch most recent assessment per subject
    assessments = (
        db.query(Assessment)
        .filter(Assessment.student_id == student_id)
        .order_by(Assessment.subject_id, desc(Assessment.created_at))
        .all()
    )

    # Keep only the latest assessment per subject
    unique_latest = {}
    for a in assessments:
        if a.subject not in unique_latest:  # first occurrence = most recent
            unique_latest[a.subject] = {
                "assessment_id": a.id,
                "status": a.status,
            }

    # Replace the structure in student_dict
    student_dict["assessments"] = unique_latest

    return student_dict

def get_student_assessments(db:Session, student_id: UUID) -> Optional[dict]:
    # Load the student and base relations
    query = (
        db.query(StudentProfile)
        .options(selectinload(StudentProfile.user))
        .filter(StudentProfile.id == student_id)
    )

    student = query.first()
    if not student:
        return None

    student_dict = student.__dict__.copy()

    # Fetch most recent assessment per subject
    assessments = (
        db.query(Assessment)
        .filter(Assessment.student_id == student_id)
        .order_by(Assessment.subject_id, desc(Assessment.created_at))
        .all()
    )

    # Keep only the latest assessment per subject
    unique_latest = {}
    for a in assessments:
        if a.subject not in unique_latest:  # first occurrence = most recent
            unique_latest[a.subject] = {
                "assessment_id": a.id,
                "status": a.status,
            }

    # Replace the structure in student_dict
    student_dict["assessments"] = unique_latest

    return student_dict

def update_student(db: Session, student_id: UUID, updates: StudentProfileUpdate) -> StudentProfile | None:
    # Fetch student profile
    db_student_profile = db.query(StudentProfile).filter(StudentProfile.id == student_id).first()
    if not db_student_profile:
        return None

    # Fetch linked user
    db_user = db.query(User).filter(User.id == db_student_profile.user_id).first()
    if not db_user:
        return None

    # Update User fields
    if updates.full_name is not None:
        db_user.full_name = updates.full_name
    if updates.username is not None:
        db_user.username = updates.username
    if updates.email is not None:
        db_user.email = updates.email
    if updates.password is not None:
        db_user.hashed_password = get_password_hash(updates.password)

    # Update StudentProfile fields
    if updates.age is not None:
        db_student_profile.age = updates.age
    if updates.grade_level is not None:
        db_student_profile.grade_level = updates.grade_level
    if updates.checkpoints is not None:
        db_student_profile.math_checkpoint = updates.checkpoints.get("math")
        db_student_profile.science_checkpoint = updates.checkpoints.get("science")
        db_student_profile.english_checkpoint = updates.checkpoints.get("english")
    if updates.interests is not None:
        db_student_profile.interests = updates.interests
    if updates.preferred_format is not None:
        db_student_profile.preferred_format = updates.preferred_format
    if updates.preferred_session_length is not None:
        db_student_profile.preferred_session_length = updates.preferred_session_length
    # Handle profile completion by setting registration_completed_at
    if db_student_profile.registration_completed_at is None and (
        db_student_profile.interests and
        db_student_profile.preferred_format and
        db_student_profile.preferred_session_length
    ):
        db_student_profile.registration_completed_at = func.now()

    db.commit()
    db.refresh(db_student_profile)

    return db_student_profile

def update_learning_profile(db: Session, student_id: UUID, updates: LearningProfileIntakePayload) -> StudentProfile | None:

    db_student_profile = db.query(StudentProfile).filter(StudentProfile.id == student_id).first()
    if not db_student_profile:
        return None

    normalized_learning_profile = normalize_learning_profile(updates.answers)
    db_student_profile.learning_profile = normalized_learning_profile

    # Handle profile completion by setting registration_completed_at
    if db_student_profile.registration_completed_at is None:
        db_student_profile.registration_completed_at = func.now()

    db.commit()
    db.refresh(db_student_profile)

    return db_student_profile

def delete_student(db: Session, student_id: UUID) -> bool:
    db_student = get_student(db, student_id)
    if not db_student:
        return False

    db.delete(db_student)
    db.commit()
    return True

def get_student_by_parent_and_id(db: Session, parent_id: UUID, student_id: UUID) -> Optional[StudentProfile]:
    return db.query(StudentProfile).filter(
        StudentProfile.parent_id == parent_id,
        StudentProfile.id == student_id
    ).first()

def authenticate_student(db: Session, username: str, password: str) -> Optional[StudentProfile]:
    student = get_student_by_username(db, username)
    if not student:
        return None
    if not verify_password(password, student.hashed_password):
        return None
    return student


def get_student_subjects_with_diagnostic_assessment(db: Session, student_id: UUID, student_curriculum_id : UUID):

    subjects = (
        db.query(Subject)
        .join(CurriculumSubject)
        .filter(CurriculumSubject.curriculum_id == student_curriculum_id)
        .filter(Subject.is_active == True)
        .all()
    )

    diagnostic_assessments = db.query(Assessment).filter(
            Assessment.student_id == student_id,
            Assessment.assessment_type == AssessmentType.DIAGNOSTIC
        ).order_by(
            Assessment.subject_id, desc(Assessment.created_at)
        ).all()

    assessments_by_subject: dict[UUID, Assessment] = {}
    for assessment in diagnostic_assessments:
        if assessment.subject_id not in assessments_by_subject:
            assessments_by_subject[assessment.subject_id] = assessment

    response = []

    for subject in subjects:
        assessment = assessments_by_subject.get(subject.id)

        if not assessment:
            status = "not_started"
            progress = None
        elif assessment.status in [AssessmentStatus.IN_PROGRESS, AssessmentStatus.STARTED]:
            status = "in_progress"
            progress = (
                (assessment.questions_answered / assessment.total_questions) * 100
                if assessment.total_questions > 0
                else 0
            )
        else:
            status = "completed"
            progress = 100

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
            "assessment_id": assessment.id if assessment else None,
            "progress": progress,
        })

    return response
