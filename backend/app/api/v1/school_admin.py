# School Admin API Endpoints
# All endpoints require authentication and authorization.
# Users must be SCHOOL_ADMIN role and associated with the school they are accessing.

import logging
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session, joinedload
from uuid import UUID
from typing import Optional

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.security import get_password_hash
from app.schemas.school_admin import (
    SchoolAdminRequest,
    SchoolAdminResponse,
    DashboardStats,
    TeacherResponse,
    StudentResponse,
    StudentProgress,
    SubtopicProgress,
    GradeResponse
)
from app.crud.school import get_school
from app.crud.teacher import get_teachers_by_school, create_teacher as crud_create_teacher, delete_teacher as crud_delete_teacher
from app.crud.student import get_student
from app.crud.grade import get_grades
from app.models.user import StudentProfile, User, UserRole
from app.models.teacher import Teacher
from app.models.school import School
from app.models.school_registration import StudentSchoolRegistration, RegistrationStatus
from app.models.assessment import Assessment, AssessmentStatus, AssessmentType
from app.models.study_plan import StudyPlan
from app.schemas.teacher import TeacherCreate

logger = logging.getLogger(__name__)

router = APIRouter()


def verify_school_admin_access(
    school_id: str,
    current_user: User,
    db: Session
) -> School:
    """
    Verify that the current user is a SCHOOL_ADMIN and has access to the specified school.

    Args:
        school_id: The UUID of the school to check access for
        current_user: The authenticated user making the request
        db: Database session

    Returns:
        School: The school object if access is granted

    Raises:
        HTTPException: 403 if user is not authorized, 404 if school not found
    """
    # Check if user has SCHOOL_ADMIN role
    if current_user.role != UserRole.SCHOOL_ADMIN:
        logger.warning(
            "Unauthorized access attempt",
            extra={
                "user_id": str(current_user.id),
                "user_role": current_user.role,
                "school_id": school_id,
                "reason": "User is not a SCHOOL_ADMIN"
            }
        )
        raise HTTPException(
            status_code=403,
            detail="Only school administrators can access this endpoint"
        )

    # Get the school
    school = get_school(db, school_id)
    if not school:
        raise HTTPException(status_code=404, detail="School not found")

    # Verify the user is the admin of this school
    if school.admin_id != current_user.id:
        logger.warning(
            "Unauthorized school access attempt",
            extra={
                "user_id": str(current_user.id),
                "school_id": school_id,
                "school_admin_id": str(school.admin_id),
                "reason": "User is not the admin of this school"
            }
        )
        raise HTTPException(
            status_code=403,
            detail="You are not authorized to access this school"
        )

    return school


@router.get("/{school_id}/dashboard", response_model=DashboardStats)
def dashboard(
    school_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get dashboard statistics for a school.
    Requires SCHOOL_ADMIN role and must be admin of the specified school.
    """
    school = verify_school_admin_access(school_id, current_user, db)

    logger.info(
        "Dashboard accessed",
        extra={
            "user_id": str(current_user.id),
            "school_id": school_id
        }
    )

    # Get student count for this school
    student_count = db.query(StudentProfile).filter(
        StudentProfile.school_id == UUID(school_id)
    ).count()

    # Get pending registrations (not approved)
    pending_registrations = db.query(StudentSchoolRegistration).filter(
        StudentSchoolRegistration.school_id == UUID(school_id),
        StudentSchoolRegistration.status == RegistrationStatus.PENDING
    ).count()

    # Get teacher count for this school
    teacher_count = db.query(Teacher).filter(
        Teacher.school_id == UUID(school_id)
    ).count()

    # Calculate average assessment percentage
    assessments = db.query(Assessment).join(StudentProfile).filter(
        StudentProfile.school_id == UUID(school_id),
        Assessment.assessment_type == AssessmentType.DIAGNOSTIC,
        Assessment.status == AssessmentStatus.COMPLETED
    ).all()

    avg_assessment_pct = 0.0
    if assessments:
        total_pct = sum(
            (a.questions_answered / a.total_questions * 100)
            for a in assessments
            if a.total_questions > 0
        )
        avg_assessment_pct = round(total_pct / len(assessments), 1)

    return DashboardStats(
        student_count=student_count,
        pending_registrations=pending_registrations,
        teacher_count=teacher_count,
        avg_assessment_pct=avg_assessment_pct
    )


@router.post("/{school_id}/teachers", response_model=TeacherResponse)
def create_teacher(
    school_id: str,
    teacher: SchoolAdminRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new teacher for a school.
    Requires SCHOOL_ADMIN role and must be admin of the specified school.
    """
    school = verify_school_admin_access(school_id, current_user, db)

    logger.info(
        "Creating teacher",
        extra={
            "user_id": str(current_user.id),
            "school_id": school_id,
            "teacher_email": teacher.email
        }
    )

    # Check if user with email already exists
    existing_user = db.query(User).filter(User.email == teacher.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User with this email already exists")

    # Create the user
    user_data = {
        "email": teacher.email,
        "username": teacher.email.split("@")[0],
        "hashed_password": get_password_hash("temporary_password"),  # Would be set via invite flow
        "role": UserRole.TEACHER,
        "full_name": teacher.name
    }

    try:
        from app.crud.user import create_user
        user = create_user(db, user_data)
    except Exception as e:
        logger.error(
            "Failed to create user for teacher",
            extra={
                "email": teacher.email,
                "error": str(e)
            }
        )
        raise HTTPException(status_code=400, detail=f"Failed to create user: {str(e)}")

    # Create teacher profile
    teacher_data = TeacherCreate(
        user_id=user.id,
        school_id=UUID(school_id)
    )

    try:
        db_teacher = crud_create_teacher(db, teacher_data)
    except Exception as e:
        logger.error(
            "Failed to create teacher profile",
            extra={
                "user_id": str(user.id),
                "school_id": school_id,
                "error": str(e)
            }
        )
        raise HTTPException(status_code=400, detail=f"Failed to create teacher: {str(e)}")

    return TeacherResponse(
        teacher_id=str(db_teacher.id),
        name=teacher.name,
        email=teacher.email,
        is_active=db_teacher.is_active,
        created_at=db_teacher.created_at.isoformat() if db_teacher.created_at else None
    )


@router.get("/{school_id}/teachers", response_model=list[TeacherResponse])
def list_teachers(
    school_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all teachers for a school.
    Requires SCHOOL_ADMIN role and must be admin of the specified school.
    """
    school = verify_school_admin_access(school_id, current_user, db)

    # Get teachers for this school
    teachers = get_teachers_by_school(db, UUID(school_id))

    result = []
    for teacher in teachers:
        user = db.query(User).filter(User.id == teacher.user_id).first()
        result.append(TeacherResponse(
            teacher_id=str(teacher.id),
            name=user.full_name if user else "Unknown",
            email=user.email if user else "",
            is_active=teacher.is_active,
            created_at=teacher.created_at.isoformat() if teacher.created_at else None
        ))

    return result


@router.delete("/{school_id}/teachers/{teacher_id}")
def delete_teacher_endpoint(
    school_id: str,
    teacher_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a teacher from a school.
    Requires SCHOOL_ADMIN role and must be admin of the specified school.
    """
    school = verify_school_admin_access(school_id, current_user, db)

    logger.info(
        "Deleting teacher",
        extra={
            "user_id": str(current_user.id),
            "school_id": school_id,
            "teacher_id": teacher_id
        }
    )

    # Delete teacher
    success = crud_delete_teacher(db, UUID(teacher_id))
    if not success:
        raise HTTPException(status_code=404, detail="Teacher not found")

    return {"status": "deleted", "teacher_id": teacher_id}


@router.get("/{school_id}/students", response_model=list[StudentResponse])
def list_students(
    school_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all students for a school.
    Requires SCHOOL_ADMIN role and must be admin of the specified school.
    """
    school = verify_school_admin_access(school_id, current_user, db)

    # Get students for this school
    students = db.query(StudentProfile).options(
        joinedload(StudentProfile.user),
        joinedload(StudentProfile.grade)
    ).filter(
        StudentProfile.school_id == UUID(school_id)
    ).all()

    result = []
    for student in students:
        # Get diagnostic assessment status
        assessment = db.query(Assessment).filter(
            Assessment.student_id == student.id,
            Assessment.assessment_type == AssessmentType.DIAGNOSTIC
        ).order_by(Assessment.created_at.desc()).first()

        if assessment:
            if assessment.status == AssessmentStatus.COMPLETED:
                diagnostic_status = "completed"
            elif assessment.status in [AssessmentStatus.IN_PROGRESS, AssessmentStatus.STARTED]:
                diagnostic_status = "in_progress"
            else:
                diagnostic_status = "not_started"
        else:
            diagnostic_status = "not_started"

        # Get study plans count
        plans_linked = db.query(StudyPlan).filter(
            StudyPlan.student_id == student.id
        ).count()

        # Calculate average progress (simplified)
        avg_progress_pct = 0.0
        if plans_linked > 0:
            # This would be calculated from actual progress data
            avg_progress_pct = 0.0

        grade_name = student.grade.name if student.grade else "Unassigned"

        result.append(StudentResponse(
            student_id=str(student.id),
            name=student.user.full_name if student.user else "Unknown",
            email=student.user.email if student.user else "",
            grade=grade_name,
            grade_id=str(student.grade_id) if student.grade_id else None,
            diagnostic_status=diagnostic_status,
            plans_linked=plans_linked,
            plans_total=8,  # Would be calculated from curriculum
            avg_progress_pct=avg_progress_pct
        ))

    return result


@router.patch("/{school_id}/students/{student_id}/grade")
def update_student_grade(
    school_id: str,
    student_id: str,
    grade_id: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update a student's grade.
    Requires SCHOOL_ADMIN role and must be admin of the specified school.
    """
    school = verify_school_admin_access(school_id, current_user, db)

    logger.info(
        "Updating student grade",
        extra={
            "user_id": str(current_user.id),
            "school_id": school_id,
            "student_id": student_id,
            "new_grade_id": grade_id
        }
    )

    # Get student
    student = db.query(StudentProfile).filter(
        StudentProfile.id == UUID(student_id),
        StudentProfile.school_id == UUID(school_id)
    ).first()

    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Update grade
    student.grade_id = UUID(grade_id)
    db.commit()

    return {"status": "updated", "student_id": student_id, "grade_id": grade_id}


@router.get("/{school_id}/students/{student_id}", response_model=StudentResponse)
def get_student_detail(
    school_id: str,
    student_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get details for a specific student.
    Requires SCHOOL_ADMIN role and must be admin of the specified school.
    """
    school = verify_school_admin_access(school_id, current_user, db)

    # Get student
    student = db.query(StudentProfile).options(
        joinedload(StudentProfile.user),
        joinedload(StudentProfile.grade)
    ).filter(
        StudentProfile.id == UUID(student_id),
        StudentProfile.school_id == UUID(school_id)
    ).first()

    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Get diagnostic assessment status
    assessment = db.query(Assessment).filter(
        Assessment.student_id == student.id,
        Assessment.assessment_type == AssessmentType.DIAGNOSTIC
    ).order_by(Assessment.created_at.desc()).first()

    if assessment:
        if assessment.status == AssessmentStatus.COMPLETED:
            diagnostic_status = "completed"
        elif assessment.status in [AssessmentStatus.IN_PROGRESS, AssessmentStatus.STARTED]:
            diagnostic_status = "in_progress"
        else:
            diagnostic_status = "not_started"
    else:
        diagnostic_status = "not_started"

    # Get study plans count
    plans_linked = db.query(StudyPlan).filter(
        StudyPlan.student_id == student.id
    ).count()

    grade_name = student.grade.name if student.grade else "Unassigned"

    return StudentResponse(
        student_id=str(student.id),
        name=student.user.full_name if student.user else "Unknown",
        email=student.user.email if student.user else "",
        grade=grade_name,
        grade_id=str(student.grade_id) if student.grade_id else None,
        diagnostic_status=diagnostic_status,
        plans_linked=plans_linked,
        plans_total=8,
        avg_progress_pct=0.0
    )


@router.get("/{school_id}/students/{student_id}/progress", response_model=StudentProgress)
def get_student_progress(
    school_id: str,
    student_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get progress data for a specific student.
    Requires SCHOOL_ADMIN role and must be admin of the specified school.
    """
    school = verify_school_admin_access(school_id, current_user, db)

    # Get student
    student = db.query(StudentProfile).filter(
        StudentProfile.id == UUID(student_id),
        StudentProfile.school_id == UUID(school_id)
    ).first()

    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # For now, return empty progress - this would be expanded with actual progress data
    return StudentProgress(
        student_id=student_id,
        subtopics=[]
    )


@router.get("/{school_id}/grades", response_model=list[GradeResponse])
def list_grades(
    school_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get grades available for a school.
    Requires SCHOOL_ADMIN role and must be admin of the specified school.
    """
    school = verify_school_admin_access(school_id, current_user, db)

    # Get all active grades
    grades = get_grades(db)

    result = []
    for grade in grades:
        result.append(GradeResponse(
            grade_id=str(grade.id),
            name=grade.name,
            level=grade.level
        ))

    return result
