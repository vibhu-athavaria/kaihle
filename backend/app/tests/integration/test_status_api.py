"""Integration tests for onboarding status API endpoints.

Tests cover:
- GET /api/v1/onboarding/status - Current user's onboarding status
- GET /api/v1/onboarding/status/{student_id} - Specific student's onboarding status
"""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token
from app.models.curriculum import Curriculum, Grade, Subject
from app.models.onboarding import StudentLearningProfile
from app.models.school import Class, ClassEnrollment, School
from app.models.user import StudentProfile, User, UserRole

settings.jwt_secret_key = "test-secret-key-for-testing"


@pytest_asyncio.fixture
async def school(db_session: AsyncSession) -> School:
    """Create a test school."""
    school = School(
        id=uuid.uuid4(),
        name="Test School",
        slug=f"test-school-{uuid.uuid4().hex[:8]}",
        status="active",
    )
    db_session.add(school)
    await db_session.commit()
    return school


@pytest_asyncio.fixture
async def teacher(db_session: AsyncSession, school: School) -> User:
    """Create a test teacher user."""
    teacher = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"teacher-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Test",
        last_name="Teacher",
        role=UserRole.TEACHER,
    )
    db_session.add(teacher)
    await db_session.commit()
    return teacher


@pytest_asyncio.fixture
async def student_no_profile(db_session: AsyncSession, school: School) -> User:
    """Create a student user without a student profile."""
    student = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"student-{uuid.uuid4().hex[:8]}@example.com",
        first_name="New",
        last_name="Student",
        role=UserRole.STUDENT,
    )
    db_session.add(student)
    await db_session.commit()
    return student


@pytest_asyncio.fixture
async def student_with_profile(db_session: AsyncSession, school: School) -> User:
    """Create a student user with an incomplete student profile."""
    student = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"student-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Incomplete",
        last_name="Student",
        role=UserRole.STUDENT,
    )
    db_session.add(student)
    await db_session.commit()

    profile = StudentProfile(
        id=uuid.uuid4(),
        user_id=student.id,
        is_learning_profile_complete=False,
    )
    db_session.add(profile)
    await db_session.commit()

    return student


@pytest_asyncio.fixture
async def student_with_complete_profile(db_session: AsyncSession, school: School) -> User:
    """Create a student user with a completed learning profile."""
    student = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"student-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Complete",
        last_name="Student",
        role=UserRole.STUDENT,
    )
    db_session.add(student)
    await db_session.commit()

    profile = StudentProfile(
        id=uuid.uuid4(),
        user_id=student.id,
        is_learning_profile_complete=True,
    )
    db_session.add(profile)
    await db_session.commit()

    learning_profile = StudentLearningProfile(
        id=uuid.uuid4(),
        student_id=student.id,
        school_id=school.id,
        modality_scores={"visual": 0.8},
        work_style={"prefers_solo": True},
        questionnaire_version="v1",
    )
    db_session.add(learning_profile)
    await db_session.commit()

    return student


@pytest_asyncio.fixture
async def parent_user(db_session: AsyncSession, school: School) -> User:
    """Create a test parent user."""
    parent = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"parent-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Test",
        last_name="Parent",
        role=UserRole.PARENT,
    )
    db_session.add(parent)
    await db_session.commit()
    return parent


@pytest_asyncio.fixture
async def kaihle_admin(db_session: AsyncSession, school: School) -> User:
    """Create a test KaihleAdmin user."""
    admin = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"admin-{uuid.uuid4().hex[:8]}@kaihle.com",
        first_name="Kaihle",
        last_name="Admin",
        role=UserRole.KAIHLE_ADMIN,
    )
    db_session.add(admin)
    await db_session.commit()
    return admin


@pytest_asyncio.fixture
async def class_with_enrollment(
    db_session: AsyncSession,
    school: School,
    teacher: User,
    student_with_profile: User,
    test_grade: Grade,
    test_subject: Subject,
    test_curriculum: Curriculum,
) -> Class:
    """Create a test class with the student enrolled."""
    class_ = Class(
        id=uuid.uuid4(),
        school_id=school.id,
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

    enrollment = ClassEnrollment(
        class_id=class_.id,
        student_id=student_with_profile.id,
        is_active=True,
        onboarding_diagnostic_status="COMPLETED",
    )
    db_session.add(enrollment)
    await db_session.commit()

    return class_


@pytest_asyncio.fixture
async def class_with_pending_enrollment(
    db_session: AsyncSession,
    school: School,
    teacher: User,
    student_with_profile: User,
    test_grade: Grade,
    test_subject: Subject,
    test_curriculum: Curriculum,
) -> Class:
    """Create a test class with the student enrolled with PENDING status."""
    class_ = Class(
        id=uuid.uuid4(),
        school_id=school.id,
        grade_id=test_grade.id,
        subject_id=test_subject.id,
        curriculum_id=test_curriculum.id,
        teacher_id=teacher.id,
        name="Pending Class",
        academic_year="2026",
        is_active=True,
    )
    db_session.add(class_)
    await db_session.commit()

    enrollment = ClassEnrollment(
        class_id=class_.id,
        student_id=student_with_profile.id,
        is_active=True,
        onboarding_diagnostic_status="PENDING",
    )
    db_session.add(enrollment)
    await db_session.commit()

    return class_


@pytest_asyncio.fixture
async def student_with_no_classes(db_session: AsyncSession, school: School) -> User:
    """Create a student user not enrolled in any class."""
    student = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"student-{uuid.uuid4().hex[:8]}@example.com",
        first_name="NoClass",
        last_name="Student",
        role=UserRole.STUDENT,
    )
    db_session.add(student)
    await db_session.commit()

    profile = StudentProfile(
        id=uuid.uuid4(),
        user_id=student.id,
        is_learning_profile_complete=False,
    )
    db_session.add(profile)
    await db_session.commit()

    return student


def get_auth_headers(user: User) -> dict[str, str]:
    """Generate JWT auth headers for a user."""
    token = create_access_token(
        user_id=user.id,
        school_id=user.school_id,
        role=user.role,
    )
    return {"Authorization": f"Bearer {token}"}


# =============================================================================
# GET /api/v1/onboarding/status (current user) - Happy Path
# =============================================================================


@pytest.mark.asyncio
async def test_status_01_new_student_no_profile_returns_pending(
    client: AsyncClient,
    db_session: AsyncSession,
    student_no_profile: User,
) -> None:
    """STATUS-01: New student (no profile) → learning_profile_complete=false, overall=PENDING."""
    response = await client.get(
        "/api/v1/onboarding/status",
        headers=get_auth_headers(student_no_profile),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["learning_profile_complete"] is False
    assert data["overall"] == "PENDING"
    assert data["diagnostics_status"] == "PENDING"


@pytest.mark.asyncio
async def test_status_02_student_incomplete_profile_returns_pending(
    client: AsyncClient,
    db_session: AsyncSession,
    student_with_profile: User,
) -> None:
    """STATUS-02: Student with incomplete profile → learning_profile_complete=false."""
    response = await client.get(
        "/api/v1/onboarding/status",
        headers=get_auth_headers(student_with_profile),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["learning_profile_complete"] is False
    assert data["overall"] == "PENDING"


@pytest.mark.asyncio
async def test_status_03_student_complete_profile_returns_completed(
    client: AsyncClient,
    db_session: AsyncSession,
    student_with_complete_profile: User,
) -> None:
    """STATUS-03: Student with completed profile → learning_profile_complete=true, overall=COMPLETED."""
    response = await client.get(
        "/api/v1/onboarding/status",
        headers=get_auth_headers(student_with_complete_profile),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["learning_profile_complete"] is True
    assert data["overall"] == "COMPLETED"


@pytest.mark.asyncio
async def test_status_04_student_with_class_enrollments_includes_diagnostics(
    client: AsyncClient,
    db_session: AsyncSession,
    student_with_profile: User,
    class_with_enrollment: Class,
) -> None:
    """STATUS-04: Student with class enrollments → diagnostics_by_class included."""
    response = await client.get(
        "/api/v1/onboarding/status",
        headers=get_auth_headers(student_with_profile),
    )

    assert response.status_code == 200
    data = response.json()
    assert "diagnostics_by_class" in data
    assert len(data["diagnostics_by_class"]) == 1
    assert data["diagnostics_by_class"][0]["class_id"] == str(class_with_enrollment.id)
    assert data["diagnostics_by_class"][0]["class_name"] == "Test Class"


@pytest.mark.asyncio
async def test_status_05_teacher_checks_own_status_returns_200(
    client: AsyncClient,
    db_session: AsyncSession,
    teacher: User,
) -> None:
    """STATUS-05: Teacher checks own status → 200."""
    response = await client.get(
        "/api/v1/onboarding/status",
        headers=get_auth_headers(teacher),
    )

    assert response.status_code == 200
    data = response.json()
    assert "learning_profile_complete" in data
    assert "overall" in data


# =============================================================================
# GET /api/v1/onboarding/status (current user) - Bad Behavior
# =============================================================================


@pytest.mark.asyncio
async def test_status_06_unauthenticated_returns_401(
    client: AsyncClient,
) -> None:
    """STATUS-06: Unauthenticated → 401."""
    response = await client.get("/api/v1/onboarding/status")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_status_07_parent_role_returns_403(
    client: AsyncClient,
    db_session: AsyncSession,
    parent_user: User,
) -> None:
    """STATUS-07: PARENT role → 403."""
    response = await client.get(
        "/api/v1/onboarding/status",
        headers=get_auth_headers(parent_user),
    )

    assert response.status_code == 403


# =============================================================================
# GET /api/v1/onboarding/status/{student_id} - Happy Path
# =============================================================================


@pytest.mark.asyncio
async def test_status_08_teacher_views_student_in_class_returns_200(
    client: AsyncClient,
    db_session: AsyncSession,
    teacher: User,
    student_with_profile: User,
    class_with_enrollment: Class,
) -> None:
    """STATUS-08: Teacher views student in their class → 200 with diagnostics_by_class."""
    response = await client.get(
        f"/api/v1/onboarding/status/{student_with_profile.id}",
        headers=get_auth_headers(teacher),
    )

    assert response.status_code == 200
    data = response.json()
    assert "learning_profile_complete" in data
    assert "diagnostics_by_class" in data
    assert len(data["diagnostics_by_class"]) == 1


@pytest.mark.asyncio
async def test_status_09_kaihle_admin_views_any_student_returns_200(
    client: AsyncClient,
    db_session: AsyncSession,
    kaihle_admin: User,
    student_with_profile: User,
) -> None:
    """STATUS-09: KaihleAdmin views any student → 200."""
    response = await client.get(
        f"/api/v1/onboarding/status/{student_with_profile.id}",
        headers=get_auth_headers(kaihle_admin),
    )

    assert response.status_code == 200
    data = response.json()
    assert "learning_profile_complete" in data


@pytest.mark.asyncio
async def test_status_10_teacher_views_student_enrolled_no_diagnostics_returns_200(
    client: AsyncClient,
    db_session: AsyncSession,
    teacher: User,
    student_with_profile: User,
    test_grade: Grade,
    test_subject: Subject,
    test_curriculum: Curriculum,
) -> None:
    """STATUS-10: Teacher views student enrolled in their class but no diagnostics → 200, empty diagnostics_by_class."""
    class_ = Class(
        id=uuid.uuid4(),
        school_id=teacher.school_id,
        grade_id=test_grade.id,
        subject_id=test_subject.id,
        curriculum_id=test_curriculum.id,
        teacher_id=teacher.id,
        name="Empty Class",
        academic_year="2026",
        is_active=True,
    )
    db_session.add(class_)
    await db_session.commit()

    enrollment = ClassEnrollment(
        class_id=class_.id,
        student_id=student_with_profile.id,
        is_active=True,
        onboarding_diagnostic_status="PENDING",
    )
    db_session.add(enrollment)
    await db_session.commit()

    response = await client.get(
        f"/api/v1/onboarding/status/{student_with_profile.id}",
        headers=get_auth_headers(teacher),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["learning_profile_complete"] is False
    assert len(data["diagnostics_by_class"]) == 1
    assert data["diagnostics_by_class"][0]["status"] == "PENDING"


# =============================================================================
# GET /api/v1/onboarding/status/{student_id} - Bad Behavior
# =============================================================================


@pytest.mark.asyncio
async def test_status_11_student_tries_view_another_student_returns_403(
    client: AsyncClient,
    db_session: AsyncSession,
    student_with_profile: User,
    student_no_profile: User,
) -> None:
    """STATUS-11: Student tries to view another student → 403."""
    response = await client.get(
        f"/api/v1/onboarding/status/{student_no_profile.id}",
        headers=get_auth_headers(student_with_profile),
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_status_12_teacher_tries_view_student_not_in_classes_returns_403(
    client: AsyncClient,
    db_session: AsyncSession,
    teacher: User,
    student_no_profile: User,
) -> None:
    """STATUS-12: Teacher tries to view student NOT in their classes → 403."""
    response = await client.get(
        f"/api/v1/onboarding/status/{student_no_profile.id}",
        headers=get_auth_headers(teacher),
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_status_13_unauthenticated_returns_401(
    client: AsyncClient,
    student_with_profile: User,
) -> None:
    """STATUS-13: Unauthenticated → 401."""
    response = await client.get(f"/api/v1/onboarding/status/{student_with_profile.id}")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_status_14_invalid_uuid_format_returns_422(
    client: AsyncClient,
    teacher: User,
) -> None:
    """STATUS-14: Invalid UUID format → 422."""
    response = await client.get(
        "/api/v1/onboarding/status/not-a-valid-uuid",
        headers=get_auth_headers(teacher),
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_status_15_teacher_with_student_role_access_returns_403(
    client: AsyncClient,
    db_session: AsyncSession,
    teacher: User,
    student_with_profile: User,
) -> None:
    """STATUS-15: Teacher with STUDENT role tries to access → 403.

    Note: This tests a teacher user who would have role=TEACHER but somehow
    the role check fails. The endpoint allows only TEACHER and KAIHLE_ADMIN roles.
    """
    teacher_student = User(
        id=uuid.uuid4(),
        school_id=teacher.school_id,
        email=f"teacher-student-{uuid.uuid4().hex[:8]}@example.com",
        first_name="TeacherStudent",
        last_name="User",
        role=UserRole.STUDENT,
    )
    db_session.add(teacher_student)
    await db_session.commit()

    response = await client.get(
        f"/api/v1/onboarding/status/{student_with_profile.id}",
        headers=get_auth_headers(teacher_student),
    )

    assert response.status_code == 403
