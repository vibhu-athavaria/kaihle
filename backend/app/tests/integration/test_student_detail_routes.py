"""Integration tests for GET /api/v1/students/{student_id}.

Tests the full student detail endpoint that returns class enrollments and
gap states. This endpoint is accessible only to SCHOOL_ADMIN and KAIHLE_ADMIN.

Response shape:
    id, first_name, last_name, grade_level (int), curriculum_name,
    enrolled_at, last_login_at,
    class_enrollments: [{class_id, class_name, teacher_name, gap_states}]
"""

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.curriculum import Curriculum, Grade, Subject
from app.models.school import Class, ClassEnrollment, School
from app.models.user import StudentProfile, User, UserRole
from app.tests.integration.conftest import make_auth_header

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_teacher(db: AsyncSession, school: School) -> User:
    teacher = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"teacher-sd-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Jane",
        last_name="Smith",
        role=UserRole.TEACHER,
        is_active=True,
    )
    db.add(teacher)
    await db.flush()
    return teacher


async def _make_student(db: AsyncSession, school: School, first_name: str = "Sam") -> User:
    student = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"student-sd-{uuid.uuid4().hex[:8]}@test.com",
        first_name=first_name,
        last_name="Lee",
        role=UserRole.STUDENT,
        is_active=True,
    )
    db.add(student)
    await db.flush()
    # grade_id set to None here; _make_class_with_enrollment updates it once the grade exists.
    db.add(StudentProfile(user_id=student.id, grade_id=None, is_learning_profile_complete=False))
    await db.flush()
    return student


async def _make_class_with_enrollment(
    db: AsyncSession,
    school: School,
    student: User,
    teacher: User,
    class_name: str = "Math 7A",
    grade_level: int = 7,
) -> tuple[Class, ClassEnrollment, Grade, Subject, Curriculum]:
    """Create a class with all FK dependencies and enroll the student."""
    subject = Subject(
        id=uuid.uuid4(),
        name=f"Subject-{uuid.uuid4().hex[:4]}",
        code=f"SC{uuid.uuid4().hex[:4]}",
        is_active=True,
    )
    grade = Grade(id=uuid.uuid4(), name=f"Grade {grade_level}", level=grade_level, is_active=True)
    curriculum = Curriculum(
        id=uuid.uuid4(),
        name=f"Cambridge Lower {uuid.uuid4().hex[:4]}",
        code=f"CU{uuid.uuid4().hex[:4]}",
        is_active=True,
    )
    db.add_all([subject, grade, curriculum])
    await db.flush()

    class_ = Class(
        id=uuid.uuid4(),
        school_id=school.id,
        grade_id=grade.id,
        subject_id=subject.id,
        curriculum_id=curriculum.id,
        teacher_id=teacher.id,
        name=class_name,
        academic_year="2026",
        is_active=True,
    )
    db.add(class_)
    await db.flush()

    enrollment = ClassEnrollment(
        class_id=class_.id,
        student_id=student.id,
        enrolled_at=datetime.now(UTC),
        is_active=True,
        onboarding_diagnostic_status="PENDING",
    )
    db.add(enrollment)
    await db.flush()

    # Keep student_profiles.grade_id in sync with the class grade — mirrors production behaviour.
    await db.execute(update(StudentProfile).where(StudentProfile.user_id == student.id).values(grade_id=grade.id))
    await db.flush()
    return class_, enrollment, grade, subject, curriculum


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_student_detail_when_unauthenticated_then_401(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
) -> None:
    """Unauthenticated request returns 401."""
    # Arrange
    student_id = uuid.uuid4()

    # Act
    response = await client.get(f"/api/v1/students/{student_id}")

    # Assert
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_student_detail_when_school_admin_views_own_school_student_then_200(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
    school_admin: User,
) -> None:
    """SchoolAdmin can fetch full detail for a student in their school.

    Asserts 200, correct id/first_name/last_name, grade_level as int,
    and class_enrollments with class_name and teacher_name.
    """
    # Arrange
    teacher = await _make_teacher(db_session, school)
    student = await _make_student(db_session, school, first_name="Priya")
    class_, _, grade, _, _ = await _make_class_with_enrollment(
        db_session, school, student, teacher, "Math 7A", grade_level=7
    )
    await db_session.commit()

    # Act
    response = await client.get(
        f"/api/v1/students/{student.id}",
        headers=make_auth_header(school_admin),
    )

    # Assert
    assert response.status_code == 200
    data = response.json()

    assert data["id"] == str(student.id)
    assert data["first_name"] == "Priya"
    assert data["last_name"] == "Lee"
    assert isinstance(data["grade_level"], int)
    assert data["grade_level"] == 7

    assert len(data["class_enrollments"]) == 1
    enrollment_data = data["class_enrollments"][0]
    assert enrollment_data["class_name"] == "Math 7A"
    assert enrollment_data["teacher_name"] == "Jane Smith"
    assert str(enrollment_data["class_id"]) == str(class_.id)


@pytest.mark.asyncio
async def test_get_student_detail_when_student_has_no_enrollments_then_200_with_empty_class_enrollments(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
    school_admin: User,
) -> None:
    """Student with no active enrollments returns 200 with empty class_enrollments list."""
    # Arrange
    student = await _make_student(db_session, school, first_name="Omar")
    await db_session.commit()

    # Act
    response = await client.get(
        f"/api/v1/students/{student.id}",
        headers=make_auth_header(school_admin),
    )

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(student.id)
    assert data["class_enrollments"] == []


@pytest.mark.asyncio
async def test_get_student_detail_when_school_admin_views_other_school_student_then_403(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
    other_school: School,
    school_admin: User,
) -> None:
    """SchoolAdmin from school A cannot view a student in school B; returns 403."""
    # Arrange — student belongs to other_school
    other_student = User(
        id=uuid.uuid4(),
        school_id=other_school.id,
        email=f"other-student-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Elena",
        last_name="Ortiz",
        role=UserRole.STUDENT,
        is_active=True,
    )
    db_session.add(other_student)
    await db_session.commit()

    # Act — school_admin belongs to school (not other_school)
    response = await client.get(
        f"/api/v1/students/{other_student.id}",
        headers=make_auth_header(school_admin),
    )

    # Assert
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_student_detail_when_student_role_accesses_then_403(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
) -> None:
    """A STUDENT user cannot call the student detail endpoint; returns 403."""
    # Arrange — requester is a student
    requester = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"student-req-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Alex",
        last_name="Kim",
        role=UserRole.STUDENT,
        is_active=True,
    )
    # Target is a different student
    target = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"student-tgt-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Bella",
        last_name="Park",
        role=UserRole.STUDENT,
        is_active=True,
    )
    db_session.add_all([requester, target])
    await db_session.commit()

    # Act
    response = await client.get(
        f"/api/v1/students/{target.id}",
        headers=make_auth_header(requester),
    )

    # Assert
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_student_detail_when_nonexistent_id_then_404(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
    school_admin: User,
) -> None:
    """Non-existent student_id returns 404."""
    # Arrange
    nonexistent_id = uuid.uuid4()

    # Act
    response = await client.get(
        f"/api/v1/students/{nonexistent_id}",
        headers=make_auth_header(school_admin),
    )

    # Assert
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_student_detail_when_curriculum_name_present_then_returned_correctly(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
    school_admin: User,
) -> None:
    """curriculum_name is taken from the first enrollment's class curriculum."""
    # Arrange
    teacher = await _make_teacher(db_session, school)
    student = await _make_student(db_session, school, first_name="Nadia")
    _, _, _, _, curriculum = await _make_class_with_enrollment(
        db_session, school, student, teacher, "English 7A", grade_level=7
    )
    await db_session.commit()

    # Act
    response = await client.get(
        f"/api/v1/students/{student.id}",
        headers=make_auth_header(school_admin),
    )

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["curriculum_name"] == curriculum.name
