from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.core.database import get_db
from app.core.security import create_access_token
from app.models.user import User, UserRole
from app.models.school import School, SchoolStatus
from app.models.school_grade import SchoolGrade
from app.models.school_registration import StudentSchoolRegistration, RegistrationStatus
from app.models.user import StudentProfile
from app.models.grade import Grade
from app.schemas.school import (
    School, SchoolCreate, SchoolUpdate, SchoolWithDetails,
    SchoolGradeCreate, SchoolGrade,
    StudentRegistration, StudentRegistrationCreate, StudentRegistrationUpdate,
    SchoolDashboard
)
from app.schemas.auth import Token
from app.crud.user import get_user_by_id
from app.crud.school import get_school_by_id

router = APIRouter()


def generate_school_code(db: Session) -> str:
    """
    Generate a unique 8-character school code.
    Format: 8 chars, uppercase alphanumeric. Exclude ambiguous chars: 0, O, 1, I, L.
    Algorithm: uuid4() → base36 encode → first 8 chars → uniqueness check against DB → retry on collision (max 10 attempts)
    """
    import random
    import string

    # Characters to exclude: 0, O, 1, I, L
    valid_chars = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"

    for _ in range(10):  # Max 10 attempts
        # Generate a random string of 8 characters
        school_code = ''.join(random.choices(valid_chars, k=8))

        # Check if this code already exists
        existing_school = db.query(School).filter(School.school_code == school_code).first()
        if not existing_school:
            return school_code

    # If we couldn't generate a unique code after 10 attempts, raise an error
    raise RuntimeError("Could not generate unique school code after 10 attempts")


# Dependency to get current user
def get_current_user():
    # This is a placeholder - in a real implementation, you would extract the user from the JWT token
    # For now, we'll just return a mock user
    return User(id=UUID('12345678-1234-5678-1234-567812345678'), role=UserRole.SCHOOL_ADMIN)


# School Grade Endpoints
@router.post("/{school_id}/grades", response_model=SchoolGrade, status_code=201)
def add_grade_to_school(
    school_id: UUID,
    request: SchoolGradeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Check if school exists
    school = db.query(School).filter(School.id == school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found")

    # Check if grade exists
    grade = db.query(Grade).filter(Grade.id == request.grade_id).first()
    if not grade:
        raise HTTPException(status_code=404, detail="Grade not found")

    # Check if grade already exists for this school
    existing_school_grade = db.query(SchoolGrade).filter(
        SchoolGrade.school_id == school_id,
        SchoolGrade.grade_id == request.grade_id
    ).first()

    if existing_school_grade:
        raise HTTPException(status_code=409, detail="Grade already exists for this school")

    # Create school grade
    db_school_grade = SchoolGrade(
        school_id=school_id,
        grade_id=request.grade_id,
        is_active=True
    )
    db.add(db_school_grade)
    db.commit()
    db.refresh(db_school_grade)

    return db_school_grade


@router.get("/{school_id}/grades", response_model=List[SchoolGrade])
def list_school_grades(
    school_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Check if school exists
    school = db.query(School).filter(School.id == school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found")

    # Get all active grades for this school
    school_grades = db.query(SchoolGrade).filter(
        SchoolGrade.school_id == school_id,
        SchoolGrade.is_active == True
    ).all()

    return school_grades


@router.delete("/{school_id}/grades/{grade_id}", status_code=204)
def remove_grade_from_school(
    school_id: UUID,
    grade_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Check if school exists
    school = db.query(School).filter(School.id == school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found")

    # Check if school grade exists
    school_grade = db.query(SchoolGrade).filter(
        SchoolGrade.school_id == school_id,
        SchoolGrade.grade_id == grade_id
    ).first()

    if not school_grade:
        raise HTTPException(status_code=404, detail="Grade not found for this school")

    # Check if any students are assigned to this grade
    student_count = db.query(StudentProfile).filter(
        StudentProfile.school_id == school_id,
        StudentProfile.grade_id == grade_id
    ).count()

    if student_count > 0:
        raise HTTPException(status_code=400, detail="Cannot remove grade with assigned students")

    # Delete the school grade
    db.delete(school_grade)
    db.commit()

    return


# Student Registration Endpoints
@router.get("/{school_id}/student-registrations", response_model=List[StudentRegistration])
def list_student_registrations(
    school_id: UUID,
    status: RegistrationStatus = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Check if school exists
    school = db.query(School).filter(School.id == school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found")

    # Build query
    query = db.query(StudentSchoolRegistration).filter(
        StudentSchoolRegistration.school_id == school_id
    )

    # Filter by status if provided
    if status:
        query = query.filter(StudentSchoolRegistration.status == status)

    # Execute query
    registrations = query.all()

    return registrations


@router.patch("/{school_id}/student-registrations/{reg_id}/approve", response_model=StudentRegistration)
def approve_student_registration(
    school_id: UUID,
    reg_id: UUID,
    request: StudentRegistrationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Check if school exists
    school = db.query(School).filter(School.id == school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found")

    # Check if registration exists
    registration = db.query(StudentSchoolRegistration).filter(
        StudentSchoolRegistration.id == reg_id,
        StudentSchoolRegistration.school_id == school_id
    ).first()

    if not registration:
        raise HTTPException(status_code=404, detail="Registration not found")

    # Check if grade_id is provided
    if not request.grade_id:
        raise HTTPException(status_code=400, detail="Grade ID is required")

    # Check if grade exists in school's grade roster
    school_grade = db.query(SchoolGrade).filter(
        SchoolGrade.school_id == school_id,
        SchoolGrade.grade_id == request.grade_id,
        SchoolGrade.is_active == True
    ).first()

    if not school_grade:
        raise HTTPException(status_code=404, detail="Grade not found in school's grade roster")

    # Update registration
    registration.status = RegistrationStatus.APPROVED
    registration.grade_id = request.grade_id
    registration.reviewed_by = current_user.id
    registration.reviewed_at = db.query(db.func.now()).scalar()

    # Update student profile
    student_profile = db.query(StudentProfile).filter(
        StudentProfile.id == registration.student_id
    ).first()

    if student_profile:
        student_profile.grade_id = request.grade_id

    # Commit changes
    db.commit()
    db.refresh(registration)

    # TODO: Fire AutoEnrollmentEngine.enroll_student_into_grade_classes()
    # TODO: Send confirmation email to student

    return registration


@router.patch("/{school_id}/student-registrations/{reg_id}/reject", response_model=StudentRegistration)
def reject_student_registration(
    school_id: UUID,
    reg_id: UUID,
    request: StudentRegistrationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Check if school exists
    school = db.query(School).filter(School.id == school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found")

    # Check if registration exists
    registration = db.query(StudentSchoolRegistration).filter(
        StudentSchoolRegistration.id == reg_id,
        StudentSchoolRegistration.school_id == school_id
    ).first()

    if not registration:
        raise HTTPException(status_code=404, detail="Registration not found")

    # Update registration
    registration.status = RegistrationStatus.REJECTED
    registration.reviewed_by = current_user.id
    registration.reviewed_at = db.query(db.func.now()).scalar()

    # Commit changes
    db.commit()
    db.refresh(registration)

    return registration


# Super Admin Endpoints
@router.patch("/{school_id}/approve", response_model=School)
def approve_school(
    school_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Check if user is super admin
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Only super admins can approve schools")

    # Check if school exists
    school = db.query(School).filter(School.id == school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found")

    # Check if school is already approved
    if school.status == SchoolStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="School is already approved")

    # Generate school code
    school_code = generate_school_code(db)

    # Update school
    school.status = SchoolStatus.ACTIVE
    school.school_code = school_code
    school.approved_at = db.query(db.func.now()).scalar()
    school.approved_by = current_user.id

    # Commit changes
    db.commit()
    db.refresh(school)

    return school


@router.get("/{school_id}/dashboard", response_model=SchoolDashboard)
def get_school_dashboard(
    school_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Check if school exists
    school = db.query(School).filter(School.id == school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found")

    # Get stats
    student_count = db.query(StudentProfile).filter(
        StudentProfile.school_id == school_id
    ).count()

    pending_registrations = db.query(StudentSchoolRegistration).filter(
        StudentSchoolRegistration.school_id == school_id,
        StudentSchoolRegistration.status == RegistrationStatus.PENDING
    ).count()

    # For now, we'll return dummy data for other stats
    # In a real implementation, you would query the database for these values
    dashboard = SchoolDashboard(
        student_count=student_count,
        pending_registrations=pending_registrations,
        teacher_count=0,
        class_count=0,
        avg_assessment_pct=0.0
    )

    return dashboard