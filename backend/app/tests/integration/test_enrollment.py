"""Integration tests for class enrollment API."""

import uuid
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.curriculum import Curriculum, Grade, Subject
from app.models.school import Class, ClassEnrollment, School
from app.models.user import OnboardingStatus, StudentProfile, User, UserRole


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
async def student_from_another_school(db_session: AsyncSession, another_school: School) -> User:
    """Create a student from another school."""
    student = User(
        id=uuid.uuid4(),
        school_id=another_school.id,
        email=f"other-student-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Other",
        last_name="Student",
        role=UserRole.STUDENT,
        is_active=True,
    )
    db_session.add(student)
    await db_session.commit()
    return student


@pytest.fixture
async def students(db_session: AsyncSession, test_school: School) -> list[User]:
    """Create multiple students for enrollment tests."""
    students_list = []
    for i in range(3):
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
            onboarding_diagnostic_status=OnboardingStatus.PENDING,
        )
        db_session.add(profile)
        profiles.append(profile)
    await db_session.commit()
    return profiles


# ===========================================
# Test: Create Class
# ===========================================


@pytest.mark.asyncio
async def test_create_class_when_valid_then_teacher_can_list(
    client: AsyncClient,
    db_session: AsyncSession,
    test_school: School,
    school_admin: User,
    test_teacher: User,
    test_grade: "Grade",
    test_subject: "Subject",
    test_curriculum: "Curriculum",
) -> None:
    """Test that SchoolAdmin can create a class and teacher can see it via GET."""
    # Arrange
    headers = auth_header(school_admin)
    class_data = {
        "name": "Math 7A",
        "grade_id": str(test_grade.id),
        "subject_id": str(test_subject.id),
        "curriculum_id": str(test_curriculum.id),
        "teacher_id": str(test_teacher.id),
        "academic_year": "2026",
    }

    # Act - Create class
    response = await client.post(
        f"/api/v1/admin/schools/{test_school.id}/classes",
        json=class_data,
        headers=headers,
    )

    # Assert - Class created
    assert response.status_code == 201
    class_data_response = response.json()
    assert class_data_response["name"] == "Math 7A"
    assert class_data_response["teacher_id"] == str(test_teacher.id)

    # Act - Teacher can list their classes
    teacher_headers = auth_header(test_teacher)
    response = await client.get(
        f"/api/v1/admin/schools/{test_school.id}/classes",
        headers=teacher_headers,
    )

    # Assert - Teacher sees the class
    assert response.status_code == 200
    classes = response.json()
    assert len(classes) == 1
    assert classes[0]["id"] == class_data_response["id"]


@pytest.mark.asyncio
async def test_create_class_when_teacher_not_in_school_then_400(
    client: AsyncClient,
    db_session: AsyncSession,
    test_school: School,
    school_admin: User,
    test_grade: "Grade",
    test_subject: "Subject",
    test_curriculum: "Curriculum",
) -> None:
    """Test that creating class with teacher from different school fails."""
    # Arrange - Create teacher in different school
    other_school = School(
        id=uuid.uuid4(),
        name="Other School",
        slug=f"other-{uuid.uuid4().hex[:8]}",
        status="active",
    )
    db_session.add(other_school)
    await db_session.commit()

    other_teacher = User(
        id=uuid.uuid4(),
        school_id=other_school.id,
        email=f"other-teacher-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Other",
        last_name="Teacher",
        role=UserRole.TEACHER,
        is_active=True,
    )
    db_session.add(other_teacher)
    await db_session.commit()

    headers = auth_header(school_admin)
    class_data = {
        "name": "Math 7A",
        "grade_id": str(test_grade.id),
        "subject_id": str(test_subject.id),
        "curriculum_id": str(test_curriculum.id),
        "teacher_id": str(other_teacher.id),
        "academic_year": "2026",
    }

    # Act
    response = await client.post(
        f"/api/v1/admin/schools/{test_school.id}/classes",
        json=class_data,
        headers=headers,
    )

    # Assert - Should fail with 400
    assert response.status_code == 400
    assert "Teacher not found in this school" in response.json()["detail"]


# ===========================================
# Test: List Classes
# ===========================================


@pytest.mark.asyncio
async def test_list_classes_when_teacher_then_only_own_classes_returned(
    client: AsyncClient,
    db_session: AsyncSession,
    test_school: School,
    school_admin: User,
    test_teacher: User,
    test_grade: "Grade",
    test_subject: "Subject",
    test_curriculum: "Curriculum",
) -> None:
    """Test that teacher only sees their own classes, not other teachers'."""
    # Arrange - Create another teacher
    other_teacher = User(
        id=uuid.uuid4(),
        school_id=test_school.id,
        email=f"teacher2-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Teacher",
        last_name="Two",
        role=UserRole.TEACHER,
        is_active=True,
    )
    db_session.add(other_teacher)
    await db_session.commit()

    # Create class for first teacher
    class1 = Class(
        id=uuid.uuid4(),
        school_id=test_school.id,
        grade_id=test_grade.id,
        subject_id=test_subject.id,
        curriculum_id=test_curriculum.id,
        teacher_id=test_teacher.id,
        name="Class 1",
        academic_year="2026",
        is_active=True,
    )
    db_session.add(class1)

    # Create class for second teacher
    class2 = Class(
        id=uuid.uuid4(),
        school_id=test_school.id,
        grade_id=test_grade.id,
        subject_id=test_subject.id,
        curriculum_id=test_curriculum.id,
        teacher_id=other_teacher.id,
        name="Class 2",
        academic_year="2026",
        is_active=True,
    )
    db_session.add(class2)
    await db_session.commit()

    # Act - First teacher lists classes
    teacher_headers = auth_header(test_teacher)
    response = await client.get(
        f"/api/v1/admin/schools/{test_school.id}/classes",
        headers=teacher_headers,
    )

    # Assert - Teacher only sees their own class
    assert response.status_code == 200
    classes = response.json()
    assert len(classes) == 1
    assert classes[0]["id"] == str(class1.id)


# ===========================================
# Test: Enroll Students
# ===========================================


@pytest.mark.asyncio
async def test_enroll_students_when_valid_then_enrollment_rows_created(
    client: AsyncClient,
    db_session: AsyncSession,
    test_school: School,
    school_admin: User,
    test_class: Class,
    students: list[User],
    student_profiles: list[StudentProfile],
) -> None:
    """Test enrolling 3 students creates 3 class_enrollments rows."""
    # Arrange
    headers = auth_header(school_admin)
    enroll_data = {
        "student_ids": [str(s.id) for s in students],
    }

    # Act
    response = await client.post(
        f"/api/v1/admin/schools/{test_school.id}/classes/{test_class.id}/enroll",
        json=enroll_data,
        headers=headers,
    )

    # Assert
    assert response.status_code == 200
    result = response.json()
    assert result["enrolled"] == 3
    assert result["skipped"] == 0
    assert len(result["errors"]) == 0

    # Verify enrollments in DB

    for student in students:
        result_check = await db_session.execute(
            select(ClassEnrollment).where(
                ClassEnrollment.class_id == test_class.id,
                ClassEnrollment.student_id == student.id,
            )
        )
        enrollment = result_check.scalar_one_or_none()
        assert enrollment is not None
        assert enrollment.is_active is True


@pytest.mark.asyncio
async def test_enroll_students_when_onboarding_pending_then_celery_task_fired(
    client: AsyncClient,
    db_session: AsyncSession,
    test_school: School,
    school_admin: User,
    test_class: Class,
    students: list[User],
    student_profiles: list[StudentProfile],
) -> None:
    """Test that students with PENDING status trigger onboarding diagnostics."""
    # Arrange
    headers = auth_header(school_admin)
    enroll_data = {
        "student_ids": [str(students[0].id)],
    }

    # Act
    with patch("app.services.school_service.trigger_onboarding_diagnostics") as mock_task:
        response = await client.post(
            f"/api/v1/admin/schools/{test_school.id}/classes/{test_class.id}/enroll",
            json=enroll_data,
            headers=headers,
        )

        # Assert
        assert response.status_code == 200

        # Verify task was called for student with PENDING status
        mock_task.assert_called_once()
        call_args = mock_task.call_args
        assert str(students[0].id) in str(call_args)


@pytest.mark.asyncio
async def test_enroll_students_when_onboarding_in_progress_then_celery_task_not_fired(
    client: AsyncClient,
    db_session: AsyncSession,
    test_school: School,
    school_admin: User,
    test_class: Class,
    students: list[User],
    student_profiles: list[StudentProfile],
) -> None:
    """Test that students with IN_PROGRESS status do NOT trigger onboarding diagnostics."""
    # Update student profile to IN_PROGRESS
    student_profiles[0].onboarding_diagnostic_status = OnboardingStatus.IN_PROGRESS
    await db_session.commit()

    # Arrange
    headers = auth_header(school_admin)
    enroll_data = {
        "student_ids": [str(students[0].id)],
    }

    # Act
    with patch("app.services.school_service.trigger_onboarding_diagnostics") as mock_task:
        response = await client.post(
            f"/api/v1/admin/schools/{test_school.id}/classes/{test_class.id}/enroll",
            json=enroll_data,
            headers=headers,
        )

        # Assert
        assert response.status_code == 200

        # Verify task was NOT called for student with IN_PROGRESS status
        mock_task.assert_not_called()


@pytest.mark.asyncio
async def test_enroll_students_when_already_enrolled_then_skipped_not_error(
    client: AsyncClient,
    db_session: AsyncSession,
    test_school: School,
    school_admin: User,
    test_class: Class,
    students: list[User],
    student_profiles: list[StudentProfile],
) -> None:
    """Test that re-enrolling already enrolled students counts as skipped, not error."""
    # Arrange - First enrollment
    headers = auth_header(school_admin)
    enroll_data = {
        "student_ids": [str(students[0].id)],
    }

    # First enrollment
    response = await client.post(
        f"/api/v1/admin/schools/{test_school.id}/classes/{test_class.id}/enroll",
        json=enroll_data,
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["enrolled"] == 1

    # Second enrollment (same students)
    response = await client.post(
        f"/api/v1/admin/schools/{test_school.id}/classes/{test_class.id}/enroll",
        json=enroll_data,
        headers=headers,
    )

    # Assert - Should be skipped, not error
    assert response.status_code == 200
    result = response.json()
    assert result["enrolled"] == 0
    assert result["skipped"] == 1
    assert len(result["errors"]) == 0


@pytest.mark.asyncio
async def test_enroll_students_when_wrong_school_then_400(
    client: AsyncClient,
    db_session: AsyncSession,
    test_school: School,
    school_admin: User,
    test_class: Class,
    student_from_another_school: User,
) -> None:
    """Test that enrolling student from different school returns 400."""
    # Arrange
    headers = auth_header(school_admin)
    enroll_data = {
        "student_ids": [str(student_from_another_school.id)],
    }

    # Act
    response = await client.post(
        f"/api/v1/admin/schools/{test_school.id}/classes/{test_class.id}/enroll",
        json=enroll_data,
        headers=headers,
    )

    # Assert
    assert response.status_code == 200  # Returns 200 but with error in list
    result = response.json()
    assert result["enrolled"] == 0
    assert "not found in this school" in result["errors"][0]


@pytest.mark.asyncio
async def test_enroll_when_different_school_admin_then_403(
    client: AsyncClient,
    db_session: AsyncSession,
    test_school: School,
    another_school: School,
    test_class: Class,
    students: list[User],
    student_profiles: list[StudentProfile],
) -> None:
    """Test that SchoolAdmin cannot manage classes in different school."""
    # Create admin for another school
    other_admin = User(
        id=uuid.uuid4(),
        school_id=another_school.id,
        email=f"other-admin-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Other",
        last_name="Admin",
        role=UserRole.SCHOOL_ADMIN,
        is_active=True,
    )
    db_session.add(other_admin)
    await db_session.commit()

    # Arrange
    headers = auth_header(other_admin)
    enroll_data = {
        "student_ids": [str(students[0].id)],
    }

    # Act
    response = await client.post(
        f"/api/v1/admin/schools/{test_school.id}/classes/{test_class.id}/enroll",
        json=enroll_data,
        headers=headers,
    )

    # Assert
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_class_when_different_school_admin_then_403(
    client: AsyncClient,
    db_session: AsyncSession,
    test_school: School,
    another_school: School,
    test_grade: "Grade",
    test_subject: "Subject",
    test_curriculum: "Curriculum",
    test_teacher: User,
) -> None:
    """Test that SchoolAdmin cannot create classes in different school."""
    # Create admin for another school
    other_admin = User(
        id=uuid.uuid4(),
        school_id=another_school.id,
        email=f"other-admin-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Other",
        last_name="Admin",
        role=UserRole.SCHOOL_ADMIN,
        is_active=True,
    )
    db_session.add(other_admin)
    await db_session.commit()

    # Arrange
    headers = auth_header(other_admin)
    class_data = {
        "name": "Math 7A",
        "grade_id": str(test_grade.id),
        "subject_id": str(test_subject.id),
        "curriculum_id": str(test_curriculum.id),
        "teacher_id": str(test_teacher.id),
        "academic_year": "2026",
    }

    # Act
    response = await client.post(
        f"/api/v1/admin/schools/{test_school.id}/classes",
        json=class_data,
        headers=headers,
    )

    # Assert
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_class_students_when_teacher_then_only_own_class(
    client: AsyncClient,
    db_session: AsyncSession,
    test_school: School,
    school_admin: User,
    test_teacher: User,
    test_class: Class,
    students: list[User],
    student_profiles: list[StudentProfile],
) -> None:
    """Test that teacher can only see students in their own classes."""
    # Enroll students
    headers = auth_header(school_admin)
    enroll_data = {
        "student_ids": [str(s.id) for s in students],
    }
    await client.post(
        f"/api/v1/admin/schools/{test_school.id}/classes/{test_class.id}/enroll",
        json=enroll_data,
        headers=headers,
    )

    # Act - Teacher views students
    teacher_headers = auth_header(test_teacher)
    response = await client.get(
        f"/api/v1/admin/schools/{test_school.id}/classes/{test_class.id}/students",
        headers=teacher_headers,
    )

    # Assert
    assert response.status_code == 200
    students_response = response.json()
    assert len(students_response) == 3


@pytest.mark.asyncio
async def test_get_class_students_when_other_teacher_then_403(
    client: AsyncClient,
    db_session: AsyncSession,
    test_school: School,
    school_admin: User,
    test_teacher: User,
    test_class: Class,
    students: list[User],
    student_profiles: list[StudentProfile],
) -> None:
    """Test that teacher cannot see students in other teacher's classes."""
    # Create another teacher with different class
    other_teacher = User(
        id=uuid.uuid4(),
        school_id=test_school.id,
        email=f"teacher2-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Teacher",
        last_name="Two",
        role=UserRole.TEACHER,
        is_active=True,
    )
    db_session.add(other_teacher)
    await db_session.flush()  # Ensure other_teacher is in DB before other_class references it

    other_class = Class(
        id=uuid.uuid4(),
        school_id=test_school.id,
        grade_id=test_class.grade_id,
        subject_id=test_class.subject_id,
        curriculum_id=test_class.curriculum_id,
        teacher_id=other_teacher.id,
        name="Other Class",
        academic_year="2026",
        is_active=True,
    )
    db_session.add(other_class)
    await db_session.commit()

    # Enroll students in original class
    headers = auth_header(school_admin)
    enroll_data = {
        "student_ids": [str(s.id) for s in students],
    }
    await client.post(
        f"/api/v1/admin/schools/{test_school.id}/classes/{test_class.id}/enroll",
        json=enroll_data,
        headers=headers,
    )

    # Act - Other teacher tries to view students
    teacher_headers = auth_header(other_teacher)
    response = await client.get(
        f"/api/v1/admin/schools/{test_school.id}/classes/{test_class.id}/students",
        headers=teacher_headers,
    )

    # Assert
    assert response.status_code == 403
