"""Integration tests for per-class diagnostic gate on student content routes.

Tests that verify:
- Students cannot access class content (topics, resources, etc.) until diagnostic is complete
- The diagnostic endpoint itself is NOT gated
- Teachers and admins bypass the diagnostic gate
- Non-enrolled students get 404

Run with: pytest backend/app/tests/integration/test_diagnostic_gate.py -v
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.school import Class, ClassEnrollment, School
from app.models.user import User, UserRole


def make_auth_header(user: User) -> dict[str, str]:
    """Create auth header for user."""
    token = create_access_token(
        user_id=user.id,
        school_id=user.school_id,
        role=user.role,
        expires_in=3600,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def student_with_enrollment(
    db_session: AsyncSession,
    school: School,
    test_class: Class,
) -> tuple[User, ClassEnrollment]:
    """Create a student with PENDING diagnostic enrollment in a class."""
    student = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"student-pending-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Test",
        last_name="Student",
        role=UserRole.STUDENT,
        is_active=True,
    )
    db_session.add(student)
    await db_session.flush()

    enrollment = ClassEnrollment(
        class_id=test_class.id,
        student_id=student.id,
        is_active=True,
        onboarding_diagnostic_status="PENDING",
    )
    db_session.add(enrollment)
    await db_session.commit()
    return student, enrollment


@pytest.fixture
async def student_with_in_progress_enrollment(
    db_session: AsyncSession,
    school: School,
    test_class: Class,
) -> tuple[User, ClassEnrollment]:
    """Create a student with IN_PROGRESS diagnostic enrollment in a class."""
    student = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"student-inprogress-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Test",
        last_name="Student",
        role=UserRole.STUDENT,
        is_active=True,
    )
    db_session.add(student)
    await db_session.flush()

    enrollment = ClassEnrollment(
        class_id=test_class.id,
        student_id=student.id,
        is_active=True,
        onboarding_diagnostic_status="IN_PROGRESS",
    )
    db_session.add(enrollment)
    await db_session.commit()
    return student, enrollment


@pytest.fixture
async def student_with_completed_enrollment(
    db_session: AsyncSession,
    school: School,
    test_class: Class,
) -> tuple[User, ClassEnrollment]:
    """Create a student with COMPLETED diagnostic enrollment in a class."""
    student = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"student-complete-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Test",
        last_name="Student",
        role=UserRole.STUDENT,
        is_active=True,
    )
    db_session.add(student)
    await db_session.flush()

    enrollment = ClassEnrollment(
        class_id=test_class.id,
        student_id=student.id,
        is_active=True,
        onboarding_diagnostic_status="COMPLETED",
    )
    db_session.add(enrollment)
    await db_session.commit()
    return student, enrollment


@pytest.mark.asyncio
async def test_class_topics_when_diagnostic_pending_then_returns_403(
    client: AsyncClient,
    db_session: AsyncSession,
    student_with_enrollment: tuple[User, ClassEnrollment],
    test_class: Class,
) -> None:
    """Student with PENDING diagnostic gets 403 when accessing class topics."""
    student, enrollment = student_with_enrollment
    headers = make_auth_header(student)

    response = await client.get(
        f"/api/v1/classes/{test_class.id}/topics",
        headers=headers,
    )

    assert response.status_code == 403
    data = response.json()
    assert data["detail"]["code"] == "DIAGNOSTIC_INCOMPLETE"
    assert data["detail"]["diagnostic_status"] == "PENDING"


@pytest.mark.asyncio
async def test_class_topics_when_diagnostic_in_progress_then_returns_403(
    client: AsyncClient,
    db_session: AsyncSession,
    student_with_in_progress_enrollment: tuple[User, ClassEnrollment],
    test_class: Class,
) -> None:
    """Student with IN_PROGRESS diagnostic gets 403 when accessing class topics."""
    student, enrollment = student_with_in_progress_enrollment
    headers = make_auth_header(student)

    response = await client.get(
        f"/api/v1/classes/{test_class.id}/topics",
        headers=headers,
    )

    assert response.status_code == 403
    data = response.json()
    assert data["detail"]["code"] == "DIAGNOSTIC_INCOMPLETE"
    assert data["detail"]["diagnostic_status"] == "IN_PROGRESS"


@pytest.mark.asyncio
async def test_class_topics_when_diagnostic_completed_then_returns_200(
    client: AsyncClient,
    db_session: AsyncSession,
    student_with_completed_enrollment: tuple[User, ClassEnrollment],
    test_class: Class,
) -> None:
    """Student with COMPLETED diagnostic can access class topics."""
    student, enrollment = student_with_completed_enrollment
    headers = make_auth_header(student)

    response = await client.get(
        f"/api/v1/classes/{test_class.id}/topics",
        headers=headers,
    )

    assert response.status_code == 200
    # Returns empty list because routes are stubs (no actual topics data)
    assert response.json() == []


@pytest.mark.asyncio
async def test_diagnostic_endpoint_when_diagnostic_pending_then_returns_200(
    client: AsyncClient,
    db_session: AsyncSession,
    student_with_enrollment: tuple[User, ClassEnrollment],
    test_class: Class,
) -> None:
    """Diagnostic endpoint is NOT gated - student can always access it."""
    student, enrollment = student_with_enrollment
    headers = make_auth_header(student)

    response = await client.get(
        f"/api/v1/classes/{test_class.id}/diagnostic",
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "PENDING"


@pytest.mark.asyncio
async def test_class_topics_when_teacher_role_then_bypasses_gate(
    client: AsyncClient,
    db_session: AsyncSession,
    test_teacher: User,
    test_class: Class,
) -> None:
    """Teachers bypass the diagnostic gate and can access class topics."""
    headers = make_auth_header(test_teacher)

    response = await client.get(
        f"/api/v1/classes/{test_class.id}/topics",
        headers=headers,
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_class_topics_when_school_admin_role_then_bypasses_gate(
    client: AsyncClient,
    db_session: AsyncSession,
    school_admin: User,
    test_class: Class,
) -> None:
    """School admins bypass the diagnostic gate and can access class topics."""
    headers = make_auth_header(school_admin)

    response = await client.get(
        f"/api/v1/classes/{test_class.id}/topics",
        headers=headers,
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_class_topics_when_student_not_enrolled_then_returns_404(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
    test_class: Class,
) -> None:
    """Student who is not enrolled in the class gets 404."""
    # Create a student without enrollment
    student = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"not-enrolled-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Not",
        last_name="Enrolled",
        role=UserRole.STUDENT,
        is_active=True,
    )
    db_session.add(student)
    await db_session.commit()

    headers = make_auth_header(student)

    response = await client.get(
        f"/api/v1/classes/{test_class.id}/topics",
        headers=headers,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_class_resources_when_diagnostic_pending_then_returns_403(
    client: AsyncClient,
    db_session: AsyncSession,
    student_with_enrollment: tuple[User, ClassEnrollment],
    test_class: Class,
) -> None:
    """Student with PENDING diagnostic gets 403 when accessing topic resources."""
    student, enrollment = student_with_enrollment
    headers = make_auth_header(student)
    topic_id = uuid.uuid4()

    response = await client.get(
        f"/api/v1/classes/{test_class.id}/topics/{topic_id}/resources",
        headers=headers,
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_class_lesson_plan_when_diagnostic_pending_then_returns_403(
    client: AsyncClient,
    db_session: AsyncSession,
    student_with_enrollment: tuple[User, ClassEnrollment],
    test_class: Class,
) -> None:
    """Student with PENDING diagnostic gets 403 when accessing lesson plan."""
    student, enrollment = student_with_enrollment
    headers = make_auth_header(student)
    topic_id = uuid.uuid4()

    response = await client.get(
        f"/api/v1/classes/{test_class.id}/topics/{topic_id}/lesson-plan",
        headers=headers,
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_class_quizzes_when_diagnostic_pending_then_returns_403(
    client: AsyncClient,
    db_session: AsyncSession,
    student_with_enrollment: tuple[User, ClassEnrollment],
    test_class: Class,
) -> None:
    """Student with PENDING diagnostic gets 403 when accessing topic quizzes."""
    student, enrollment = student_with_enrollment
    headers = make_auth_header(student)
    topic_id = uuid.uuid4()

    response = await client.get(
        f"/api/v1/classes/{test_class.id}/topics/{topic_id}/quizzes",
        headers=headers,
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_diagnostic_endpoint_always_accessible_for_in_progress_student(
    client: AsyncClient,
    db_session: AsyncSession,
    student_with_in_progress_enrollment: tuple[User, ClassEnrollment],
    test_class: Class,
) -> None:
    """Student with IN_PROGRESS diagnostic can still access the diagnostic endpoint."""
    student, enrollment = student_with_in_progress_enrollment
    headers = make_auth_header(student)

    response = await client.get(
        f"/api/v1/classes/{test_class.id}/diagnostic",
        headers=headers,
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_class_topics_when_kaihle_admin_role_then_bypasses_gate(
    client: AsyncClient,
    db_session: AsyncSession,
    kaihle_admin: User,
    test_class: Class,
) -> None:
    """Kaihle admins bypass the diagnostic gate and can access class topics."""
    headers = make_auth_header(kaihle_admin)

    response = await client.get(
        f"/api/v1/classes/{test_class.id}/topics",
        headers=headers,
    )

    assert response.status_code == 200
