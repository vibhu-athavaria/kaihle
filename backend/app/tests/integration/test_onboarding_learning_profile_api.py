"""Integration tests for learning profile retrieval API endpoints.

Tests cover:
- GET /api/v1/onboarding/learning-profile - Role-based profile retrieval
"""

import uuid
from datetime import UTC

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.curriculum import Curriculum, Grade, Subject
from app.models.onboarding import StudentLearningProfile
from app.models.school import Class, ClassEnrollment, School
from app.models.user import StudentProfile, User, UserRole


def get_auth_headers(user: User) -> dict[str, str]:
    """Generate JWT auth headers for a user."""
    token = create_access_token(
        user_id=user.id,
        school_id=user.school_id,
        role=user.role,
    )
    return {"Authorization": f"Bearer {token}"}


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
async def grade(db_session: AsyncSession) -> Grade:
    """Create a test grade."""
    grade = Grade(
        id=uuid.uuid4(),
        name="Grade 7",
        level=7,
        is_active=True,
    )
    db_session.add(grade)
    await db_session.commit()
    return grade


@pytest_asyncio.fixture
async def subject(db_session: AsyncSession) -> Subject:
    """Create a test subject."""
    subject = Subject(
        id=uuid.uuid4(),
        name="Math",
        code="MATH",
        is_active=True,
    )
    db_session.add(subject)
    await db_session.commit()
    return subject


@pytest_asyncio.fixture
async def curriculum(db_session: AsyncSession) -> Curriculum:
    """Create a test curriculum."""
    curriculum = Curriculum(
        id=uuid.uuid4(),
        name="Standard Curriculum",
        code="STD",
        description="Standard curriculum",
        is_active=True,
    )
    db_session.add(curriculum)
    await db_session.commit()
    return curriculum


@pytest_asyncio.fixture
async def student_with_profile(db_session: AsyncSession, school: School) -> User:
    """Create a student user with a learning profile."""
    student = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"student-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Test",
        last_name="Student",
        role=UserRole.STUDENT,
    )
    db_session.add(student)
    await db_session.commit()

    profile = StudentProfile(
        id=uuid.uuid4(),
        user_id=student.id,
    )
    db_session.add(profile)
    await db_session.commit()

    learning_profile = StudentLearningProfile(
        id=uuid.uuid4(),
        student_id=student.id,
        school_id=school.id,
        modality_scores={"visual": 0.8, "auditory": 0.3, "reading_writing": 0.6, "kinesthetic": 0.5},
        work_style={"prefers_solo": True, "short_sessions": False, "task_based": True},
        interests=["football", "music"],
        questionnaire_version="v1",
    )
    db_session.add(learning_profile)
    await db_session.commit()

    return student


@pytest_asyncio.fixture
async def student_with_complete_profile(db_session: AsyncSession, school: School) -> User:
    """Create a student user with a completed learning profile (after questionnaire submission)."""
    from datetime import datetime

    student = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"student-complete-{uuid.uuid4().hex[:8]}@example.com",
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
        modality_scores={"visual": 0.9, "auditory": 0.4, "reading_writing": 0.7, "kinesthetic": 0.3},
        work_style={"prefers_solo": True, "short_sessions": False, "task_based": True, "group_learning": False},
        interests=["gaming", "science"],
        questionnaire_version="v1",
        completed_at=datetime.now(UTC),
    )
    db_session.add(learning_profile)
    await db_session.commit()

    return student


@pytest_asyncio.fixture
async def student_without_profile(db_session: AsyncSession, school: School) -> User:
    """Create a student user without a learning profile."""
    student = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"student-noprofile-{uuid.uuid4().hex[:8]}@example.com",
        first_name="NoProfile",
        last_name="Student",
        role=UserRole.STUDENT,
    )
    db_session.add(student)
    await db_session.commit()

    profile = StudentProfile(
        id=uuid.uuid4(),
        user_id=student.id,
    )
    db_session.add(profile)
    await db_session.commit()

    return student


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
async def teacher_with_class(
    db_session: AsyncSession,
    school: School,
    grade: Grade,
    subject: Subject,
    curriculum: Curriculum,
    teacher: User,
    student_with_profile: User,
) -> tuple[User, Class]:
    """Create a teacher with a class that has the student enrolled."""
    class_ = Class(
        id=uuid.uuid4(),
        school_id=school.id,
        grade_id=grade.id,
        subject_id=subject.id,
        curriculum_id=curriculum.id,
        teacher_id=teacher.id,
        name="Math 7",
        academic_year="2025-2026",
        is_active=True,
    )
    db_session.add(class_)
    await db_session.commit()

    enrollment = ClassEnrollment(
        class_id=class_.id,
        student_id=student_with_profile.id,
        is_active=True,
    )
    db_session.add(enrollment)
    await db_session.commit()

    return teacher, class_


@pytest_asyncio.fixture
async def other_teacher(db_session: AsyncSession, school: School) -> User:
    """Create another teacher without the student in their classes."""
    teacher = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"other-teacher-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Other",
        last_name="Teacher",
        role=UserRole.TEACHER,
    )
    db_session.add(teacher)
    await db_session.commit()
    return teacher


@pytest_asyncio.fixture
async def kaihle_admin(db_session: AsyncSession, school: School) -> User:
    """Create a KaihleAdmin user."""
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
async def parent_user(db_session: AsyncSession, school: School) -> User:
    """Create a PARENT user."""
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


# =============================================================================
# Happy Path Tests
# =============================================================================


@pytest.mark.asyncio
async def test_profile_01_student_retrieves_own_profile_returns_200(
    client: AsyncClient,
    student_with_profile: User,
) -> None:
    """PROFILE-01: Student retrieves own profile → 200 with full profile."""
    response = await client.get(
        "/api/v1/onboarding/learning-profile",
        headers=get_auth_headers(student_with_profile),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["student_id"] == str(student_with_profile.id)
    assert data["modality_scores"] == {"visual": 0.8, "auditory": 0.3, "reading_writing": 0.6, "kinesthetic": 0.5}
    assert data["work_style"] == {"prefers_solo": True, "short_sessions": False, "task_based": True}
    assert data["interests"] == ["football", "music"]


@pytest.mark.asyncio
async def test_profile_02_student_retrieves_own_profile_after_submission_returns_200(
    client: AsyncClient,
    student_with_complete_profile: User,
) -> None:
    """PROFILE-02: Student retrieves own profile after submission → 200 with scores populated."""
    response = await client.get(
        "/api/v1/onboarding/learning-profile",
        headers=get_auth_headers(student_with_complete_profile),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["student_id"] == str(student_with_complete_profile.id)
    assert data["modality_scores"]["visual"] == 0.9
    assert data["completed_at"] is not None


@pytest.mark.asyncio
async def test_profile_03_teacher_retrieves_student_in_class_returns_200(
    client: AsyncClient,
    teacher_with_class: tuple[User, Class],
    student_with_profile: User,
) -> None:
    """PROFILE-03: Teacher retrieves student in their class → 200."""
    teacher, _class = teacher_with_class

    response = await client.get(
        f"/api/v1/onboarding/learning-profile?student_id={student_with_profile.id}",
        headers=get_auth_headers(teacher),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["student_id"] == str(student_with_profile.id)
    assert data["modality_scores"]["visual"] == 0.8


@pytest.mark.asyncio
async def test_profile_04_kaihle_admin_retrieves_any_student_returns_200(
    client: AsyncClient,
    kaihle_admin: User,
    student_with_profile: User,
) -> None:
    """PROFILE-04: KaihleAdmin retrieves any student → 200."""
    response = await client.get(
        f"/api/v1/onboarding/learning-profile?student_id={student_with_profile.id}",
        headers=get_auth_headers(kaihle_admin),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["student_id"] == str(student_with_profile.id)


# =============================================================================
# Bad Behavior Tests
# =============================================================================


@pytest.mark.asyncio
async def test_profile_05_unauthenticated_returns_401(
    client: AsyncClient,
    student_with_profile: User,
) -> None:
    """PROFILE-05: Unauthenticated → 401."""
    response = await client.get("/api/v1/onboarding/learning-profile")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_profile_06_student_tries_to_view_other_student_profile_returns_403(
    client: AsyncClient,
    student_with_profile: User,
    student_without_profile: User,
) -> None:
    """PROFILE-06: Student tries to view another student's profile → 403."""
    response = await client.get(
        f"/api/v1/onboarding/learning-profile?student_id={student_without_profile.id}",
        headers=get_auth_headers(student_with_profile),
    )

    assert response.status_code == 403
    assert "only view their own" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_profile_07_teacher_tries_to_view_student_not_in_class_returns_403(
    client: AsyncClient,
    other_teacher: User,
    student_with_profile: User,
) -> None:
    """PROFILE-07: Teacher tries to view student NOT in their classes → 403."""
    response = await client.get(
        f"/api/v1/onboarding/learning-profile?student_id={student_with_profile.id}",
        headers=get_auth_headers(other_teacher),
    )

    assert response.status_code == 403
    assert "your classes" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_profile_08_teacher_without_student_id_returns_400(
    client: AsyncClient,
    teacher: User,
) -> None:
    """PROFILE-08: Teacher without student_id query param → 400."""
    response = await client.get(
        "/api/v1/onboarding/learning-profile",
        headers=get_auth_headers(teacher),
    )

    assert response.status_code == 400
    assert "student_id" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_profile_09_kaihle_admin_without_student_id_returns_400(
    client: AsyncClient,
    kaihle_admin: User,
) -> None:
    """PROFILE-09: KaihleAdmin without student_id query param → 400."""
    response = await client.get(
        "/api/v1/onboarding/learning-profile",
        headers=get_auth_headers(kaihle_admin),
    )

    assert response.status_code == 400
    assert "student_id" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_profile_10_query_for_student_with_no_profile_returns_404(
    client: AsyncClient,
    kaihle_admin: User,
    student_without_profile: User,
) -> None:
    """PROFILE-10: Query for student with no profile → 404."""
    response = await client.get(
        f"/api/v1/onboarding/learning-profile?student_id={student_without_profile.id}",
        headers=get_auth_headers(kaihle_admin),
    )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_profile_11_invalid_uuid_format_returns_422(
    client: AsyncClient,
    kaihle_admin: User,
) -> None:
    """PROFILE-11: Invalid UUID format → 422."""
    response = await client.get(
        "/api/v1/onboarding/learning-profile?student_id=not-a-valid-uuid",
        headers=get_auth_headers(kaihle_admin),
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_profile_12_parent_role_returns_403(
    client: AsyncClient,
    parent_user: User,
    student_with_profile: User,
) -> None:
    """PROFILE-12: PARENT role → 403."""
    response = await client.get(
        f"/api/v1/onboarding/learning-profile?student_id={student_with_profile.id}",
        headers=get_auth_headers(parent_user),
    )

    assert response.status_code == 403
