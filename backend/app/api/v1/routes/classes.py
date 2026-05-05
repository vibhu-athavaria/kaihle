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

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, _check_school_access, require_role
from app.models.curriculum import Grade, Subject
from app.models.school import Class
from app.models.user import User, UserRole
from app.schemas.class_enrollment import (
    ClassCreate,
    ClassResponse,
    ClassUpdate,
    ClassWithSummary,
    EnrollRequest,
    EnrollResponse,
    StudentSummary,
    TeacherStudentsResponse,
    UnenrollRequest,
)
from app.services.class_service import ClassService
from app.services.gap_service import GapService

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
    """Create a class for a school. SchoolAdmin or KaihleAdmin only.

    Optionally enroll students immediately via body.student_ids.
    Diagnostics are teacher-designed and NOT auto-dispatched on enrollment.
    """
    _check_school_access(school_id, current_user)
    service = ClassService(db)
    try:
        class_ = await service.create_class(school_id, body)
    except ValueError as e:
        msg = str(e)
        if "not subscribed" in msg:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
    return _class_to_response(class_)


@router.get("/schools/{school_id}/classes")
async def list_classes(
    school_id: uuid.UUID,
    include_summary: bool = Query(False, description="Include grade/subject names and class summary"),
    include_inactive: bool = Query(False, description="Include inactive classes (admin only; ignored for teachers)"),
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN, UserRole.SCHOOL_ADMIN, UserRole.TEACHER)),
    db: AsyncSession = Depends(get_db),
) -> list[ClassWithSummary] | list[ClassResponse]:
    """List classes. Teacher sees own classes only. SchoolAdmin/KaihleAdmin see all.

    When include_summary=true, returns enriched data including grade_name, subject_name,
    avg_mastery, student_count, and students_below_threshold. This is more efficient than
    making separate calls for each class.
    When include_inactive=true, inactive classes are included (admin roles only).
    """
    _check_school_access(school_id, current_user)
    service = ClassService(db)
    teacher_id = current_user.id if current_user.role == UserRole.TEACHER else None
    # Teachers always see active-only regardless of the query param
    effective_inactive = include_inactive if current_user.role != UserRole.TEACHER else False
    classes = await service.list_classes(school_id, teacher_id, include_inactive=effective_inactive)

    if include_summary:
        grades_result = await db.execute(select(Grade).where(Grade.id.in_([c.grade_id for c in classes])))
        grade_objects = list(grades_result.scalars().all())
        grades = {g.id: g.name for g in grade_objects}
        grade_levels = {g.id: g.level for g in grade_objects}

        subjects_result = await db.execute(select(Subject).where(Subject.id.in_([c.subject_id for c in classes])))
        subjects = {s.id: s.name for s in subjects_result.scalars().all()}

        teacher_ids = [c.teacher_id for c in classes if c.teacher_id]
        teachers_result = await db.execute(select(User).where(User.id.in_(teacher_ids)))
        teachers = {t.id: f"{t.first_name} {t.last_name}".strip() for t in teachers_result.scalars().all()}

        gap_service = GapService(db)
        summaries = await gap_service.get_class_summaries_batch(
            class_ids=[c.id for c in classes],
            school_id=school_id,
        )

        results = []
        for cls in classes:
            summary = summaries.get(cls.id)
            results.append(
                ClassWithSummary(
                    id=cls.id,
                    school_id=cls.school_id,
                    grade_id=cls.grade_id,
                    subject_id=cls.subject_id,
                    curriculum_id=cls.curriculum_id,
                    teacher_id=cls.teacher_id,
                    teacher_name=teachers.get(cls.teacher_id) if cls.teacher_id else None,
                    has_teacher=cls.teacher_id is not None,
                    name=cls.name,
                    academic_year=cls.academic_year,
                    is_active=cls.is_active,
                    grade_name=grades.get(cls.grade_id, ""),
                    grade_level=grade_levels.get(cls.grade_id),
                    subject_name=subjects.get(cls.subject_id, ""),
                    avg_mastery=summary.avg_mastery if summary else None,
                    student_count=summary.student_count if summary else 0,
                    students_below_threshold=summary.students_below_threshold if summary else 0,
                )
            )
        return results

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


@router.patch("/classes/{class_id}", response_model=ClassResponse)
async def update_class(
    class_id: uuid.UUID,
    body: ClassUpdate,
    current_user: CurrentUser = Depends(require_role(UserRole.SCHOOL_ADMIN, UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> ClassResponse:
    """Update a class. SCHOOL_ADMIN and KAIHLE_ADMIN only.

    Editable: name, teacher_id, academic_year, is_active.
    Locked:   grade_id, subject_id, curriculum_id.
    """
    if current_user.school_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no school associated",
        )
    service = ClassService(db)
    try:
        class_ = await service.update_class(class_id, current_user.school_id, body)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    await db.commit()
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
    return await service.get_class_students(class_id, class_.school_id)


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


@router.delete("/classes/{class_id}/enrollments", status_code=status.HTTP_204_NO_CONTENT)
async def unenroll_students(
    class_id: uuid.UUID,
    body: UnenrollRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.SCHOOL_ADMIN, UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft-delete enrollments. SCHOOL_ADMIN and KAIHLE_ADMIN only.

    Sets ClassEnrollment.is_active = False. Assessment history is preserved.
    """
    if not current_user.school_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no school associated",
        )
    service = ClassService(db)
    try:
        await service.unenroll_students(class_id, current_user.school_id, body.student_ids)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    await db.commit()
