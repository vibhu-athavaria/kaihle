"""Integration tests for teacher students endpoint.

Tests verify the GET /api/v1/teachers/me/students endpoint.

Run with: pytest backend/app/tests/integration/test_teacher_students_routes.py -v
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.curriculum import Curriculum, Grade, Subject
from app.models.school import Class, ClassEnrollment, School
from app.models.user import User, UserRole


def make_auth_header(user: User) -> dict[str, str]:
    """Generate Authorization header with a real JWT."""
    token = create_access_token(
        user_id=user.id,
        school_id=user.school_id,
        role=user.role,
    )
    return {"Authorization": f"Bearer {token}"}


async def _create_teacher_with_classes(
    db: AsyncSession,
    school: School,
    num_classes: int = 2,
    students_per_class: int = 3,
) -> tuple[User, list[Class], list[User]]:
    """Create a teacher with multiple classes and enrolled students."""
    teacher = User(
        id=uuid.uuid4(),
        email=f"teacher-{uuid.uuid4().hex[:6]}@school.com",
        first_name="Test",
        last_name="Teacher",
        role=UserRole.TEACHER,
        school_id=school.id,
        is_active=True,
    )
    db.add(teacher)
    await db.flush()

    classes = []
    all_students = []

    for i in range(num_classes):
        subject = Subject(
            id=uuid.uuid4(),
            name=f"Subject-{i}",
            code=f"S{uuid.uuid4().hex[:4]}",
            is_active=True,
        )
        grade = Grade(
            id=uuid.uuid4(),
            name=f"Grade {i}",
            level=i + 7,
            is_active=True,
        )
        curriculum = Curriculum(
            id=uuid.uuid4(),
            name=f"Curriculum-{i}",
            code=f"C{uuid.uuid4().hex[:4]}",
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
            name=f"Class {i}A",
            academic_year="2026",
            is_active=True,
        )
        db.add(class_)
        classes.append(class_)

        students = []
        for j in range(students_per_class):
            student = User(
                id=uuid.uuid4(),
                email=f"student-{i}-{j}-{uuid.uuid4().hex[:4]}@school.com",
                first_name=f"Student-{i}-{j}",
                last_name="Test",
                role=UserRole.STUDENT,
                school_id=school.id,
                is_active=True,
            )
            db.add(student)
            students.append(student)

        all_students.extend(students)
        await db.flush()

        for student in all_students:
            enrollment = ClassEnrollment(
                class_id=class_.id,
                student_id=student.id,
                is_active=True,
            )
            db.add(enrollment)

    await db.flush()
    return teacher, classes, all_students


@pytest.mark.asyncio
async def test_get_teacher_students_when_multiple_classes(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
) -> None:
    """Test that teacher sees students aggregated across their classes."""
    teacher, classes, students = await _create_teacher_with_classes(
        db_session, school, num_classes=2, students_per_class=3
    )
    await db_session.commit()

    response = await client.get(
        "/api/v1/teachers/me/students",
        headers=make_auth_header(teacher),
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    assert "students" in data
    assert len(data["students"]) == 6


@pytest.mark.asyncio
async def test_get_teacher_students_when_no_classes_then_empty(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
) -> None:
    """Test that teacher with no classes gets empty list."""
    teacher_with_no_class = User(
        id=uuid.uuid4(),
        email=f"teacher-no-class-{uuid.uuid4().hex[:6]}@school.com",
        first_name="Test",
        last_name="Teacher",
        role=UserRole.TEACHER,
        school_id=school.id,
        is_active=True,
    )
    db_session.add(teacher_with_no_class)
    await db_session.commit()

    response = await client.get(
        "/api/v1/teachers/me/students",
        headers=make_auth_header(teacher_with_no_class),
    )

    assert response.status_code == 200
    assert response.json() == {"students": []}


@pytest.mark.asyncio
async def test_get_teacher_students_when_unauthenticated_then_401(
    client: AsyncClient,
) -> None:
    """Test that unauthenticated request returns 401."""
    response = await client.get("/api/v1/teachers/me/students")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_teacher_students_when_student_role_then_403(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
) -> None:
    """Test that student role cannot access teacher students endpoint."""
    student = User(
        id=uuid.uuid4(),
        email=f"student-{uuid.uuid4().hex[:6]}@school.com",
        first_name="Test",
        last_name="Student",
        role=UserRole.STUDENT,
        school_id=school.id,
        is_active=True,
    )
    db_session.add(student)
    await db_session.commit()

    response = await client.get(
        "/api/v1/teachers/me/students",
        headers=make_auth_header(student),
    )
    assert response.status_code == 403
