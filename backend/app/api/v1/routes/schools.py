"""School management API routes for KaihleAdmin."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, require_role
from app.models.school import Class
from app.models.user import UserRole
from app.schemas.school import (
    ClassCreate,
    ClassResponse,
    EnrollRequest,
    EnrollResponse,
    SchoolCreate,
    SchoolListResponse,
    SchoolResponse,
    SchoolUpdate,
    StudentSummary,
)
from app.services.school_service import SchoolService

router = APIRouter(prefix="/admin/schools", tags=["schools"])


def _school_to_response(school: Any) -> SchoolResponse:
    """Convert School model to SchoolResponse schema.

    Handles the mapping from status field to is_active boolean.
    """
    return SchoolResponse(
        id=school.id,
        name=school.name,
        slug=school.slug,
        country=school.country,
        timezone=school.timezone,
        is_active=school.status == "active",
    )


@router.post("", response_model=SchoolResponse, status_code=status.HTTP_201_CREATED)
async def create_school(
    body: SchoolCreate,
    _: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> SchoolResponse:
    """Create a new school. KaihleAdmin only."""
    service = SchoolService(db)
    try:
        school = await service.create_school(body)
        return _school_to_response(school)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get("", response_model=SchoolListResponse)
async def list_schools(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> SchoolListResponse:
    """List all schools with pagination. KaihleAdmin only."""
    service = SchoolService(db)
    schools, total = await service.list_schools(page, page_size)
    return SchoolListResponse(
        schools=[_school_to_response(s) for s in schools],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{school_id}", response_model=SchoolResponse)
async def get_school(
    school_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN, UserRole.SCHOOL_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> SchoolResponse:
    """Get a single school by ID.

    KaihleAdmin can see any school.
    SchoolAdmin can see only their own school.
    """
    if current_user.role == UserRole.SCHOOL_ADMIN and current_user.school_id != school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access school from different organization",
        )

    service = SchoolService(db)
    try:
        school = await service.get_school(school_id)
        return _school_to_response(school)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School not found",
        )


@router.patch("/{school_id}", response_model=SchoolResponse)
async def update_school(
    school_id: uuid.UUID,
    body: SchoolUpdate,
    _: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> SchoolResponse:
    """Update a school. KaihleAdmin only."""
    service = SchoolService(db)
    try:
        school = await service.update_school(school_id, body)
        return _school_to_response(school)
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# ===========================================
# Class Management Routes
# ===========================================


def _class_to_response(class_: Class) -> ClassResponse:
    """Convert Class model to ClassResponse schema."""
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


def _check_school_access(school_id: uuid.UUID, current_user: CurrentUser) -> None:
    """Check if user can access school.
    KaihleAdmin can access any school.
    SchoolAdmin can only access own school.
    Teachers can only access their own school.

    """

    # Other roles must match school_id
    if current_user.school_id != school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this school's data",
        )


@router.post("/{school_id}/classes", response_model=ClassResponse, status_code=status.HTTP_201_CREATED)
async def create_class(
    school_id: uuid.UUID,
    body: ClassCreate,
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN, UserRole.SCHOOL_ADMIN, UserRole.TEACHER)),
    db: AsyncSession = Depends(get_db),
) -> ClassResponse:
    """Create a new class for a school.

    SchoolAdmin or KaihleAdmin can create classes.
    """
    # Check role
    if current_user.role not in (UserRole.SCHOOL_ADMIN, UserRole.KAIHLE_ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only SchoolAdmin or KaihleAdmin can create classes",
        )

    # Check school access
    _check_school_access(school_id, current_user)

    service = SchoolService(db)
    try:
        class_ = await service.create_class(school_id, body)
        return _class_to_response(class_)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{school_id}/classes", response_model=list[ClassResponse])
async def list_classes(
    school_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN, UserRole.SCHOOL_ADMIN, UserRole.TEACHER)),
    db: AsyncSession = Depends(get_db),
) -> list[ClassResponse]:
    """List classes for a school.

    - Teacher: returns only their own classes
    - SchoolAdmin: returns all classes in their school
    - KaihleAdmin: returns all classes in any school
    """
    # Check school access
    _check_school_access(school_id, current_user)

    service = SchoolService(db)

    # If teacher, filter by their teacher_id
    teacher_id = None
    if current_user.role == UserRole.TEACHER:
        teacher_id = current_user.id

    classes = await service.list_classes(school_id, teacher_id)
    return [_class_to_response(c) for c in classes]


# ===========================================
# Enrollment Routes
# ===========================================


@router.post("/{school_id}/classes/{class_id}/enroll", response_model=EnrollResponse)
async def enroll_students(
    school_id: uuid.UUID,
    class_id: uuid.UUID,
    body: EnrollRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.SCHOOL_ADMIN, UserRole.TEACHER)),
    db: AsyncSession = Depends(get_db),
) -> EnrollResponse:
    """Enroll students in a class.

    SchoolAdmin or Teacher can enroll students.
    Returns: {enrolled: int, skipped: int, errors: list}
    """

    # Check school access
    _check_school_access(school_id, current_user)

    # Verify class belongs to school
    service = SchoolService(db)
    try:
        class_ = await service.verify_class_school(class_id, school_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    # Teachers can only enroll in their own class
    if current_user.role == UserRole.TEACHER and class_.teacher_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only enroll students in your own classes",
        )

    # Enroll students
    result = await service.enroll_students(class_id, body.student_ids)
    return result


@router.get("/{school_id}/classes/{class_id}/students", response_model=list[StudentSummary])
async def get_class_students(
    school_id: uuid.UUID,
    class_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN, UserRole.SCHOOL_ADMIN, UserRole.TEACHER)),
    db: AsyncSession = Depends(get_db),
) -> list[StudentSummary]:
    """Get students enrolled in a class.

    Teacher: can only see students in their own classes
    SchoolAdmin: can see all students in their school's classes
    KaihleAdmin: can see all students
    """
    # Check school access
    _check_school_access(school_id, current_user)

    service = SchoolService(db)

    # Verify class belongs to school
    try:
        class_ = await service.verify_class_school(class_id, school_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    # Teachers can only see their own classes
    if current_user.role == UserRole.TEACHER:
        if class_.teacher_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view students in your own classes",
            )

    students = await service.get_class_students(class_id)
    return students
