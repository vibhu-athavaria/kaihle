"""Integration tests for class enrollment API endpoints."""

import uuid
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.curriculum import Curriculum, Grade, Subject
from app.models.school import Class, ClassEnrollment, School
from app.models.user import StudentProfile, User, UserRole


def auth_header(user: User) -> dict[str, str]:
    """Create auth header for user."""
    from app.core.security import create_access_token

    token = create_access_token(
        user_id=user.id,
        school_id=user.school_id,
        role=user.role,
        expires_in=3600,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def kaihle_admin(db_session: AsyncSession) -> User:
    """Create a KaihleAdmin user."""
    school = School(
        id=uuid.uuid4(),
        name="Kaihle HQ",
        slug=f"kaihle-hq-{uuid.uuid4().hex[:8]}",
        status="active",
    )
    db_session.add(school)
    await db_session.flush()

    admin = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"kaihle-admin-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Kaihle",
        last_name="Admin",
        role=UserRole.KAIHLE_ADMIN,
        is_active=True,
    )
    db_session.add(admin)
    await db_session.commit()
    return admin


@pytest.fixture
async def school_admin(db_session: AsyncSession, test_school: School) -> User:
    """Create a school admin user."""
    admin = User(
        id=uuid.uuid4(),
        school_id=test_school.id,
        email=f"admin-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Admin",
        last_name="User",
        role=UserRole.SCHOOL_ADMIN,
        is_active=True,
    )
    db_session.add(admin)
    await db_session.commit()
    return admin


@pytest.fixture
async def teacher(db_session: AsyncSession, test_school: School) -> User:
    """Create a teacher user."""
    teacher = User(
        id=uuid.uuid4(),
        school_id=test_school.id,
        email=f"teacher-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Test",
        last_name="Teacher",
        role=UserRole.TEACHER,
        is_active=True,
    )
    db_session.add(teacher)
    await db_session.commit()
    return teacher


@pytest.fixture
async def class_with_teacher(
    db_session: AsyncSession,
    test_school: School,
    test_grade: Grade,
    test_subject: Subject,
    test_curriculum: Curriculum,
    teacher: User,
) -> Class:
    """Create a test class with teacher."""
    class_ = Class(
        id=uuid.uuid4(),
        school_id=test_school.id,
        grade_id=test_grade.id,
        subject_id=test_subject.id,
        curriculum_id=test_curriculum.id,
        teacher_id=teacher.id,
        name="Test Class",
        academic_year="2026",
        is_active=True,
    )
    db_session.add(class_)
    await db_session.commit()
    return class_


@pytest.fixture
async def students(db_session: AsyncSession, test_school: School) -> list[User]:
    """Create multiple students for enrollment tests."""
    students_list = []
    for i in range(5):
        student = User(
            id=uuid.uuid4(),
            school_id=test_school.id,
            email=f"student{i}-{uuid.uuid4().hex[:8]}@example.com",
            first_name=f"Student{i}",
            last_name="Test",
            role=UserRole.STUDENT,
            is_active=True,
        )
        db_session.add(student)
        students_list.append(student)
    await db_session.commit()
    return students_list


@pytest.fixture
async def student_profiles(db_session: AsyncSession, students: list[User]) -> list[StudentProfile]:
    """Create student profiles for all students."""
    profiles = []
    for student in students:
        profile = StudentProfile(
            id=uuid.uuid4(),
            user_id=student.id,
        )
        db_session.add(profile)
        profiles.append(profile)
    await db_session.commit()
    return profiles


@pytest.fixture
async def another_school(db_session: AsyncSession) -> School:
    """Create another school for cross-school tests."""
    school = School(
        id=uuid.uuid4(),
        name="Another School",
        slug=f"another-school-{uuid.uuid4().hex[:8]}",
        status="active",
    )
    db_session.add(school)
    await db_session.commit()
    return school


@pytest.fixture
async def another_school_admin(db_session: AsyncSession, another_school: School) -> User:
    """Create admin for another school."""
    admin = User(
        id=uuid.uuid4(),
        school_id=another_school.id,
        email=f"other-admin-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Other",
        last_name="Admin",
        role=UserRole.SCHOOL_ADMIN,
        is_active=True,
    )
    db_session.add(admin)
    await db_session.commit()
    return admin


@pytest.fixture
async def other_teacher(db_session: AsyncSession, test_school: School) -> User:
    """Create a other teacher user."""
    teacher = User(
        id=uuid.uuid4(),
        school_id=test_school.id,
        email=f"other-teacher-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Other",
        last_name="Teacher",
        role=UserRole.TEACHER,
        is_active=True,
    )
    db_session.add(teacher)
    await db_session.commit()
    return teacher


@pytest.fixture
async def another_school_class(
    db_session: AsyncSession,
    another_school: School,
    test_grade: Grade,
    test_subject: Subject,
    test_curriculum: Curriculum,
    teacher: User,
) -> Class:
    """Create a class in another school."""
    class_ = Class(
        id=uuid.uuid4(),
        school_id=another_school.id,
        grade_id=test_grade.id,
        subject_id=test_subject.id,
        curriculum_id=test_curriculum.id,
        teacher_id=teacher.id,
        name="Other School Class",
        academic_year="2026",
        is_active=True,
    )
    db_session.add(class_)
    await db_session.commit()
    return class_


# ===========================================
# Happy Path Tests
# ===========================================


@pytest.mark.asyncio
async def test_enroll_01_school_admin_enrolls_valid_students_returns_200(
    client: AsyncClient,
    db_session: AsyncSession,
    test_school: School,
    school_admin: User,
    class_with_teacher: Class,
    students: list[User],
    student_profiles: list[StudentProfile],
) -> None:
    """ENROLL-01: SchoolAdmin enrolls valid student IDs → 200."""
    headers = auth_header(school_admin)
    enroll_data: dict = {
        "student_ids": [str(students[0].id)],
    }

    with patch("app.services.school_service.trigger_onboarding_diagnostics"):
        response = await client.post(
            f"/api/v1/admin/schools/{test_school.id}/classes/{class_with_teacher.id}/enroll",
            json=enroll_data,
            headers=headers,
        )

    assert response.status_code == 200
    result = response.json()
    assert result["enrolled"] == 1
    assert result["skipped"] == 0
    assert len(result["errors"]) == 0


@pytest.mark.asyncio
async def test_enroll_03_teacher_enrolls_students_returns_200(
    client: AsyncClient,
    db_session: AsyncSession,
    test_school: School,
    teacher: User,
    class_with_teacher: Class,
    students: list[User],
    student_profiles: list[StudentProfile],
) -> None:
    """ENROLL-03: teacher enrolls students → 200."""
    headers = auth_header(teacher)
    enroll_data: dict = {
        "student_ids": [str(students[0].id)],
    }

    with patch("app.services.school_service.trigger_onboarding_diagnostics"):
        response = await client.post(
            f"/api/v1/admin/schools/{test_school.id}/classes/{class_with_teacher.id}/enroll",
            json=enroll_data,
            headers=headers,
        )

    assert response.status_code == 200
    result = response.json()
    assert result["enrolled"] == 1
    assert result["skipped"] == 0
    assert len(result["errors"]) == 0


@pytest.mark.asyncio
async def test_enroll_04_enroll_multiple_students_returns_correct_count(
    client: AsyncClient,
    db_session: AsyncSession,
    test_school: School,
    school_admin: User,
    class_with_teacher: Class,
    students: list[User],
    student_profiles: list[StudentProfile],
) -> None:
    """ENROLL-04: Enroll multiple students at once → 200, correct count."""
    headers = auth_header(school_admin)
    enroll_data: dict = {
        "student_ids": [str(s.id) for s in students[:3]],
    }

    with patch("app.services.school_service.trigger_onboarding_diagnostics"):
        response = await client.post(
            f"/api/v1/admin/schools/{test_school.id}/classes/{class_with_teacher.id}/enroll",
            json=enroll_data,
            headers=headers,
        )

    assert response.status_code == 200
    result = response.json()
    assert result["enrolled"] == 3
    assert result["skipped"] == 0
    assert len(result["errors"]) == 0


@pytest.mark.asyncio
async def test_enroll_05_enroll_student_triggers_diagnostic_status_pending(
    client: AsyncClient,
    db_session: AsyncSession,
    test_school: School,
    school_admin: User,
    class_with_teacher: Class,
    students: list[User],
    student_profiles: list[StudentProfile],
) -> None:
    """ENROLL-05: Enroll student triggers diagnostic status → enrollment status = PENDING."""
    headers = auth_header(school_admin)
    enroll_data: dict = {
        "student_ids": [str(students[0].id)],
    }

    with patch("app.services.school_service.trigger_onboarding_diagnostics"):
        response = await client.post(
            f"/api/v1/admin/schools/{test_school.id}/classes/{class_with_teacher.id}/enroll",
            json=enroll_data,
            headers=headers,
        )

    assert response.status_code == 200

    result = await db_session.execute(
        select(ClassEnrollment).where(
            ClassEnrollment.class_id == class_with_teacher.id,
            ClassEnrollment.student_id == students[0].id,
        )
    )
    enrollment = result.scalar_one_or_none()
    assert enrollment is not None
    assert enrollment.onboarding_diagnostic_status == "PENDING"


# ===========================================
# Bad Behavior Tests
# ===========================================


@pytest.mark.asyncio
async def test_enroll_kaihle_admin_enrolls_students_returns_200(
    client: AsyncClient,
    db_session: AsyncSession,
    test_school: School,
    kaihle_admin: User,
    class_with_teacher: Class,
    students: list[User],
    student_profiles: list[StudentProfile],
) -> None:
    """ENROLL: KaihleAdmin enrolls students → 200 (per CONSTITUTION Rule 12)."""
    headers = auth_header(kaihle_admin)
    enroll_data: dict = {
        "student_ids": [str(students[0].id)],
    }

    response = await client.post(
        f"/api/v1/admin/schools/{test_school.id}/classes/{class_with_teacher.id}/enroll",
        json=enroll_data,
        headers=headers,
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_enroll_teacher_tries_to_enroll_returns_403(
    client: AsyncClient,
    db_session: AsyncSession,
    test_school: School,
    other_teacher: User,
    class_with_teacher: Class,
    students: list[User],
    student_profiles: list[StudentProfile],
) -> None:
    """ENROLL: Teacher tries to enroll → 403."""
    headers = auth_header(other_teacher)
    enroll_data: dict = {
        "student_ids": [str(students[0].id)],
    }

    response = await client.post(
        f"/api/v1/admin/schools/{test_school.id}/classes/{class_with_teacher.id}/enroll",
        json=enroll_data,
        headers=headers,
    )

    assert response.status_code == 403
    assert "You can only enroll students in your own classes" in response.json()["detail"]


@pytest.mark.asyncio
async def test_enroll_06_school_admin_enrolls_to_wrong_school_returns_403(
    client: AsyncClient,
    db_session: AsyncSession,
    test_school: School,
    another_school_admin: User,
    class_with_teacher: Class,
    students: list[User],
    student_profiles: list[StudentProfile],
) -> None:
    """ENROLL-06: SchoolAdmin enrolls to wrong school → 403."""
    headers = auth_header(another_school_admin)
    enroll_data: dict = {
        "student_ids": [str(students[0].id)],
    }

    response = await client.post(
        f"/api/v1/admin/schools/{test_school.id}/classes/{class_with_teacher.id}/enroll",
        json=enroll_data,
        headers=headers,
    )

    assert response.status_code == 403
    assert "Access denied to this school's data" in response.json()["detail"]


@pytest.mark.asyncio
async def test_enroll_07_enroll_nonexistent_student_id_returns_error_in_skipped(
    client: AsyncClient,
    db_session: AsyncSession,
    test_school: School,
    school_admin: User,
    class_with_teacher: Class,
    students: list[User],
    student_profiles: list[StudentProfile],
) -> None:
    """ENROLL-07: Enroll non-existent student ID → 200 with error in errors list."""
    headers = auth_header(school_admin)
    nonexistent_id = uuid.uuid4()
    enroll_data: dict = {
        "student_ids": [str(nonexistent_id)],
    }

    response = await client.post(
        f"/api/v1/admin/schools/{test_school.id}/classes/{class_with_teacher.id}/enroll",
        json=enroll_data,
        headers=headers,
    )

    assert response.status_code == 200
    result = response.json()
    assert result["enrolled"] == 0
    assert len(result["errors"]) > 0
    assert "not found in this school" in result["errors"][0]


@pytest.mark.asyncio
async def test_enroll_08_enroll_already_enrolled_student_handled_gracefully(
    client: AsyncClient,
    db_session: AsyncSession,
    test_school: School,
    school_admin: User,
    class_with_teacher: Class,
    students: list[User],
    student_profiles: list[StudentProfile],
) -> None:
    """ENROLL-08: Enroll already-enrolled student → 200, handled gracefully."""
    headers = auth_header(school_admin)
    enroll_data: dict = {
        "student_ids": [str(students[0].id)],
    }

    first_response = await client.post(
        f"/api/v1/admin/schools/{test_school.id}/classes/{class_with_teacher.id}/enroll",
        json=enroll_data,
        headers=headers,
    )
    assert first_response.status_code == 200
    assert first_response.json()["enrolled"] == 1

    second_response = await client.post(
        f"/api/v1/admin/schools/{test_school.id}/classes/{class_with_teacher.id}/enroll",
        json=enroll_data,
        headers=headers,
    )

    assert second_response.status_code == 200
    result = second_response.json()
    assert result["enrolled"] == 0
    assert result["skipped"] == 1
    assert len(result["errors"]) == 0


@pytest.mark.asyncio
async def test_enroll_09_empty_student_ids_list_returns_422(
    client: AsyncClient,
    db_session: AsyncSession,
    test_school: School,
    school_admin: User,
    class_with_teacher: Class,
) -> None:
    """ENROLL-09: Empty student_ids list → 422."""
    headers = auth_header(school_admin)
    enroll_data: dict = {
        "student_ids": [],
    }

    response = await client.post(
        f"/api/v1/admin/schools/{test_school.id}/classes/{class_with_teacher.id}/enroll",
        json=enroll_data,
        headers=headers,
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_enroll_10_invalid_school_id_uuid_returns_422(
    client: AsyncClient,
    db_session: AsyncSession,
    school_admin: User,
    class_with_teacher: Class,
    students: list[User],
) -> None:
    """ENROLL-10: Invalid school_id UUID → 422."""
    headers = auth_header(school_admin)
    enroll_data: dict = {
        "student_ids": [str(students[0].id)],
    }

    response = await client.post(
        f"/api/v1/admin/schools/not-a-uuid/classes/{class_with_teacher.id}/enroll",
        json=enroll_data,
        headers=headers,
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_enroll_11_invalid_class_id_uuid_returns_404(
    client: AsyncClient,
    db_session: AsyncSession,
    test_school: School,
    school_admin: User,
    students: list[User],
) -> None:
    """ENROLL-11: Invalid class_id UUID → 404."""
    headers = auth_header(school_admin)
    nonexistent_class_id = uuid.uuid4()
    enroll_data: dict = {
        "student_ids": [str(students[0].id)],
    }

    response = await client.post(
        f"/api/v1/admin/schools/{test_school.id}/classes/{nonexistent_class_id}/enroll",
        json=enroll_data,
        headers=headers,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_enroll_12_unauthenticated_returns_401(
    client: AsyncClient,
    db_session: AsyncSession,
    test_school: School,
    class_with_teacher: Class,
    students: list[User],
) -> None:
    """ENROLL-12: Unauthenticated → 401."""
    enroll_data: dict = {
        "student_ids": [str(students[0].id)],
    }

    response = await client.post(
        f"/api/v1/admin/schools/{test_school.id}/classes/{class_with_teacher.id}/enroll",
        json=enroll_data,
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_enroll_11_class_not_in_school_returns_404(
    client: AsyncClient,
    db_session: AsyncSession,
    test_school: School,
    school_admin: User,
    another_school_class: Class,
    students: list[User],
    student_profiles: list[StudentProfile],
) -> None:
    """Test that enrolling to a class not belonging to the school returns 404."""
    headers = auth_header(school_admin)
    enroll_data: dict = {
        "student_ids": [str(students[0].id)],
    }

    response = await client.post(
        f"/api/v1/admin/schools/{test_school.id}/classes/{another_school_class.id}/enroll",
        json=enroll_data,
        headers=headers,
    )

    assert response.status_code == 404
    assert "Class not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_enroll_response_structure_has_required_fields(
    client: AsyncClient,
    db_session: AsyncSession,
    test_school: School,
    school_admin: User,
    class_with_teacher: Class,
    students: list[User],
    student_profiles: list[StudentProfile],
) -> None:
    """Test that enrollment response has correct structure: {enrolled: int, skipped: int, errors: list}."""
    headers = auth_header(school_admin)
    enroll_data: dict = {
        "student_ids": [str(students[0].id)],
    }

    response = await client.post(
        f"/api/v1/admin/schools/{test_school.id}/classes/{class_with_teacher.id}/enroll",
        json=enroll_data,
        headers=headers,
    )

    assert response.status_code == 200
    result = response.json()

    assert "enrolled" in result
    assert "skipped" in result
    assert "errors" in result
    assert isinstance(result["enrolled"], int)
    assert isinstance(result["skipped"], int)
    assert isinstance(result["errors"], list)


@pytest.mark.asyncio
async def test_enroll_student_from_different_school_in_errors(
    client: AsyncClient,
    db_session: AsyncSession,
    test_school: School,
    school_admin: User,
    class_with_teacher: Class,
    another_school: School,
) -> None:
    """Test that enrolling student from different school adds error to errors list."""
    other_student = User(
        id=uuid.uuid4(),
        school_id=another_school.id,
        email=f"other-student-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Other",
        last_name="Student",
        role=UserRole.STUDENT,
        is_active=True,
    )
    db_session.add(other_student)
    await db_session.commit()

    headers = auth_header(school_admin)
    enroll_data: dict = {
        "student_ids": [str(other_student.id)],
    }

    response = await client.post(
        f"/api/v1/admin/schools/{test_school.id}/classes/{class_with_teacher.id}/enroll",
        json=enroll_data,
        headers=headers,
    )

    assert response.status_code == 200
    result = response.json()
    assert result["enrolled"] == 0
    assert len(result["errors"]) > 0
    assert "not found in this school" in result["errors"][0]
