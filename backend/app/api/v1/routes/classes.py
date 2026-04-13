"""Class management and enrollment API routes.

Separated from schools.py because class operations are a distinct domain concern
from school metadata management. School CRUD is a platform admin concern (KaihleAdmin).
Class and enrollment management is a school operational concern (SchoolAdmin, Teacher).

Prefix note: class list/create is nested under /schools/{school_id}/classes because
the school context is needed to scope the list. Individual class operations use
/classes/{class_id} without the school prefix because the class_id globally
identifies the class.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, _check_school_access, require_role
from app.models.school import Class
from app.models.user import UserRole
from app.schemas.class_enrollment import (
    ClassCreate,
    ClassResponse,
    EnrollRequest,
    EnrollResponse,
    StudentSummary,
    TeacherStudentsResponse,
)
from app.services.class_service import ClassService

router = APIRouter(tags=["classes"])


def _class_to_response(class_: Class) -> ClassResponse:
    """Convert Class ORM model to ClassResponse schema."""
    return ClassResponse(
        id=class_.id,
        school_id=class_.school_id,
        grade_id=class_.grade_id,
        subject_id=class_.subject_id,
        curriculum_id=class_.curriculum_id,
        teacher_id=class_.teacher_id,
        name=class_.name,
        academic_year=class_.academic_year,
        is_active=class_.is_active,
    )


# ── School-scoped class list + create ────────────────────────────────────────


@router.post(
    "/schools/{school_id}/classes",
    response_model=ClassResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_class(
    school_id: uuid.UUID,
    body: ClassCreate,
    current_user: CurrentUser = Depends(require_role(UserRole.SCHOOL_ADMIN, UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> ClassResponse:
    """Create a class for a school. SchoolAdmin or KaihleAdmin only."""
    _check_school_access(school_id, current_user)
    service = ClassService(db)
    try:
        class_ = await service.create_class(school_id, body)
        return _class_to_response(class_)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/schools/{school_id}/classes", response_model=list[ClassResponse])
async def list_classes(
    school_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN, UserRole.SCHOOL_ADMIN, UserRole.TEACHER)),
    db: AsyncSession = Depends(get_db),
) -> list[ClassResponse]:
    """List classes. Teacher sees own classes only. SchoolAdmin/KaihleAdmin see all."""
    _check_school_access(school_id, current_user)
    service = ClassService(db)
    teacher_id = current_user.id if current_user.role == UserRole.TEACHER else None
    classes = await service.list_classes(school_id, teacher_id)
    return [_class_to_response(c) for c in classes]


# ── Class-scoped operations ───────────────────────────────────────────────────


@router.get("/classes/{class_id}", response_model=ClassResponse)
async def get_class(
    class_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> ClassResponse:
    """Get a single class by ID."""
    service = ClassService(db)
    try:
        class_ = await service.get_class(class_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")
    _check_school_access(class_.school_id, current_user)
    return _class_to_response(class_)


# ── Enrollment (noun-based resource) ─────────────────────────────────────────


@router.get("/classes/{class_id}/enrollments", response_model=list[StudentSummary])
async def list_enrollments(
    class_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN, UserRole.SCHOOL_ADMIN, UserRole.TEACHER)),
    db: AsyncSession = Depends(get_db),
) -> list[StudentSummary]:
    """List students enrolled in a class."""
    service = ClassService(db)
    try:
        class_ = await service.get_class(class_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")
    _check_school_access(class_.school_id, current_user)
    if current_user.role == UserRole.TEACHER and class_.teacher_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view students in your own classes",
        )
    return await service.get_class_students(class_id)


@router.post("/classes/{class_id}/enrollments", response_model=EnrollResponse)
async def create_enrollments(
    class_id: uuid.UUID,
    body: EnrollRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.SCHOOL_ADMIN, UserRole.TEACHER, UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> EnrollResponse:
    """Enroll one or more students in a class.

    Body: { student_ids: list[UUID] }
    Response: { enrolled: int, skipped: int, errors: list[str] }

    Idempotent: enrolling an already-enrolled student is counted as skipped, not an error.
    """
    service = ClassService(db)
    try:
        class_ = await service.get_class(class_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")
    _check_school_access(class_.school_id, current_user)
    if current_user.role == UserRole.TEACHER and class_.teacher_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only enroll students in your own classes",
        )
    return await service.enroll_students(class_id, body.student_ids)


# ── Teacher student list (aggregated across all classes) ──────────────────────


@router.get("/teachers/me/students", response_model=TeacherStudentsResponse)
async def list_teacher_students(
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> TeacherStudentsResponse:
    """List all students enrolled in the current teacher's active classes.

    Returns lightweight student summaries (name, email, class_ids, class_names).
    Does NOT include mastery or learning profile data — those are loaded on-demand
    when viewing student detail.
    """
    service = ClassService(db)
    if not current_user.school_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no school associated",
        )
    students = await service.get_teacher_students(
        teacher_id=current_user.id,
        school_id=current_user.school_id,
    )
    return TeacherStudentsResponse(students=students)
