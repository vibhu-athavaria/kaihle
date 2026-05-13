"""Integration tests for student content access routes.

Tests that verify:
- Students can access class content (topics, resources, etc.) regardless of diagnostic status
- The diagnostic endpoint itself is always accessible
- Teachers and admins can access class content
- Non-enrolled students get 404

This reflects the soft-gate design per spec:
2026-05-02-class-curriculum-teacher-control-design Section 5.

Run with: pytest backend/app/tests/integration/test_diagnostic_gate.py -v
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.assessment import Assessment, AssessmentStatus, AttemptStatus, StudentAttempt
from app.models.curriculum import Curriculum, Grade, Subject
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
async def test_class_topics_when_diagnostic_pending_then_returns_200(
    client: AsyncClient,
    db_session: AsyncSession,
    student_with_enrollment: tuple[User, ClassEnrollment],
    test_class: Class,
) -> None:
    """Student with PENDING diagnostic can access class topics (soft gate)."""
    student, enrollment = student_with_enrollment
    headers = make_auth_header(student)

    response = await client.get(
        f"/api/v1/classes/{test_class.id}/topics",
        headers=headers,
    )

    assert response.status_code == 200
    # Returns empty list because routes are stubs (no actual topics data)
    assert response.json() == []


@pytest.mark.asyncio
async def test_class_topics_when_diagnostic_in_progress_then_returns_200(
    client: AsyncClient,
    db_session: AsyncSession,
    student_with_in_progress_enrollment: tuple[User, ClassEnrollment],
    test_class: Class,
) -> None:
    """Student with IN_PROGRESS diagnostic can access class topics (soft gate)."""
    student, enrollment = student_with_in_progress_enrollment
    headers = make_auth_header(student)

    response = await client.get(
        f"/api/v1/classes/{test_class.id}/topics",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json() == []


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
    assert response.json() == []


@pytest.mark.asyncio
async def test_diagnostic_endpoint_when_diagnostic_pending_then_returns_200(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Diagnostic endpoint is always accessible - student can always access it.

    Real implementation (M1-4-T1) requires an active system-generated assessment
    and a corresponding student attempt row. This test creates a self-contained
    scenario with matching school_id across all objects.
    """
    # Create self-contained school, teacher, class, assessment, student, attempt
    diag_school = School(
        id=uuid.uuid4(),
        name="Diag Test School",
        slug=f"diag-{uuid.uuid4().hex[:8]}",
        status="active",
    )
    db_session.add(diag_school)
    await db_session.flush()

    diag_teacher = User(
        id=uuid.uuid4(),
        school_id=diag_school.id,
        email=f"diag-teacher-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Diag",
        last_name="Teacher",
        role=UserRole.TEACHER,
        is_active=True,
    )
    db_session.add(diag_teacher)
    await db_session.flush()

    diag_grade = Grade(id=uuid.uuid4(), name="Grade 7", level=7, is_active=True)
    diag_subject = Subject(
        id=uuid.uuid4(),
        name=f"Diag Math {uuid.uuid4().hex[:4]}",
        code=f"DM{uuid.uuid4().hex[:4]}",
        is_active=True,
    )
    diag_curriculum = Curriculum(
        id=uuid.uuid4(),
        name=f"Diag Curriculum {uuid.uuid4().hex[:4]}",
        code=f"DC{uuid.uuid4().hex[:4]}",
        is_active=True,
    )
    db_session.add_all([diag_grade, diag_subject, diag_curriculum])
    await db_session.flush()

    diag_class = Class(
        id=uuid.uuid4(),
        school_id=diag_school.id,
        grade_id=diag_grade.id,
        subject_id=diag_subject.id,
        curriculum_id=diag_curriculum.id,
        teacher_id=diag_teacher.id,
        name="Diag Test Class",
        academic_year="2025-2026",
        is_active=True,
    )
    db_session.add(diag_class)
    await db_session.flush()

    diag_assessment = Assessment(
        id=uuid.uuid4(),
        school_id=diag_school.id,
        class_id=diag_class.id,
        created_by=diag_teacher.id,
        title="Diagnostic Assessment",
        assessment_type="DIAGNOSTIC",
        status=AssessmentStatus.ACTIVE,
    )
    db_session.add(diag_assessment)
    await db_session.flush()

    diag_student = User(
        id=uuid.uuid4(),
        school_id=diag_school.id,
        email=f"diag-student-pending-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Diag",
        last_name="Student",
        role=UserRole.STUDENT,
        is_active=True,
    )
    db_session.add(diag_student)
    await db_session.flush()

    enrollment = ClassEnrollment(
        class_id=diag_class.id,
        student_id=diag_student.id,
        is_active=True,
        onboarding_diagnostic_status="PENDING",
    )
    diag_attempt = StudentAttempt(
        id=uuid.uuid4(),
        assessment_id=diag_assessment.id,
        student_id=diag_student.id,
        status=AttemptStatus.NOT_STARTED,
    )
    db_session.add_all([enrollment, diag_attempt])
    await db_session.commit()

    headers = make_auth_header(diag_student)
    response = await client.get(
        f"/api/v1/classes/{diag_class.id}/diagnostic",
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == AttemptStatus.NOT_STARTED


@pytest.mark.asyncio
async def test_class_topics_when_teacher_role_then_returns_200(
    client: AsyncClient,
    db_session: AsyncSession,
    test_teacher: User,
    test_class: Class,
) -> None:
    """Teachers can access class topics."""
    headers = make_auth_header(test_teacher)

    response = await client.get(
        f"/api/v1/classes/{test_class.id}/topics",
        headers=headers,
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_class_topics_when_school_admin_role_then_returns_200(
    client: AsyncClient,
    db_session: AsyncSession,
    school_admin: User,
    test_class: Class,
) -> None:
    """School admins can access class topics."""
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
async def test_class_resources_when_diagnostic_pending_then_returns_200(
    client: AsyncClient,
    db_session: AsyncSession,
    student_with_enrollment: tuple[User, ClassEnrollment],
    test_class: Class,
) -> None:
    """Student with PENDING diagnostic can access topic resources (soft gate)."""
    student, enrollment = student_with_enrollment
    headers = make_auth_header(student)
    topic_id = uuid.uuid4()

    response = await client.get(
        f"/api/v1/classes/{test_class.id}/topics/{topic_id}/resources",
        headers=headers,
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_class_lesson_plan_when_diagnostic_pending_then_returns_200(
    client: AsyncClient,
    db_session: AsyncSession,
    student_with_enrollment: tuple[User, ClassEnrollment],
    test_class: Class,
) -> None:
    """Student with PENDING diagnostic can access lesson plan (soft gate)."""
    student, enrollment = student_with_enrollment
    headers = make_auth_header(student)
    topic_id = uuid.uuid4()

    response = await client.get(
        f"/api/v1/classes/{test_class.id}/topics/{topic_id}/lesson-plan",
        headers=headers,
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_class_quizzes_when_diagnostic_pending_then_returns_200(
    client: AsyncClient,
    db_session: AsyncSession,
    student_with_enrollment: tuple[User, ClassEnrollment],
    test_class: Class,
) -> None:
    """Student with PENDING diagnostic can access topic quizzes (soft gate)."""
    student, enrollment = student_with_enrollment
    headers = make_auth_header(student)
    topic_id = uuid.uuid4()

    response = await client.get(
        f"/api/v1/classes/{test_class.id}/topics/{topic_id}/quizzes",
        headers=headers,
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_diagnostic_endpoint_always_accessible_for_in_progress_student(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Student with IN_PROGRESS diagnostic can access the diagnostic endpoint.

    Real implementation (M1-4-T1) requires an active system-generated assessment
    and a corresponding student attempt row. This test creates a self-contained
    scenario with matching school_id across all objects.
    """
    # Create self-contained school, teacher, class, assessment, student, attempt
    diag_school = School(
        id=uuid.uuid4(),
        name="Diag InProgress School",
        slug=f"diag-ip-{uuid.uuid4().hex[:8]}",
        status="active",
    )
    db_session.add(diag_school)
    await db_session.flush()

    diag_teacher = User(
        id=uuid.uuid4(),
        school_id=diag_school.id,
        email=f"diag-ip-teacher-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Diag",
        last_name="Teacher",
        role=UserRole.TEACHER,
        is_active=True,
    )
    db_session.add(diag_teacher)
    await db_session.flush()

    diag_grade = Grade(id=uuid.uuid4(), name="Grade 8", level=8, is_active=True)
    diag_subject = Subject(
        id=uuid.uuid4(),
        name=f"Diag Sci {uuid.uuid4().hex[:4]}",
        code=f"DS{uuid.uuid4().hex[:4]}",
        is_active=True,
    )
    diag_curriculum = Curriculum(
        id=uuid.uuid4(),
        name=f"Diag Curr {uuid.uuid4().hex[:4]}",
        code=f"DCC{uuid.uuid4().hex[:4]}",
        is_active=True,
    )
    db_session.add_all([diag_grade, diag_subject, diag_curriculum])
    await db_session.flush()

    diag_class = Class(
        id=uuid.uuid4(),
        school_id=diag_school.id,
        grade_id=diag_grade.id,
        subject_id=diag_subject.id,
        curriculum_id=diag_curriculum.id,
        teacher_id=diag_teacher.id,
        name="Diag InProgress Class",
        academic_year="2025-2026",
        is_active=True,
    )
    db_session.add(diag_class)
    await db_session.flush()

    diag_assessment = Assessment(
        id=uuid.uuid4(),
        school_id=diag_school.id,
        class_id=diag_class.id,
        created_by=diag_teacher.id,
        title="Diagnostic Assessment InProgress",
        assessment_type="DIAGNOSTIC",
        status=AssessmentStatus.ACTIVE,
    )
    db_session.add(diag_assessment)
    await db_session.flush()

    diag_student = User(
        id=uuid.uuid4(),
        school_id=diag_school.id,
        email=f"diag-student-ip-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Diag",
        last_name="StudentIP",
        role=UserRole.STUDENT,
        is_active=True,
    )
    db_session.add(diag_student)
    await db_session.flush()

    enrollment = ClassEnrollment(
        class_id=diag_class.id,
        student_id=diag_student.id,
        is_active=True,
        onboarding_diagnostic_status="IN_PROGRESS",
    )
    diag_attempt = StudentAttempt(
        id=uuid.uuid4(),
        assessment_id=diag_assessment.id,
        student_id=diag_student.id,
        status=AttemptStatus.IN_PROGRESS,
    )
    db_session.add_all([enrollment, diag_attempt])
    await db_session.commit()

    headers = make_auth_header(diag_student)
    response = await client.get(
        f"/api/v1/classes/{diag_class.id}/diagnostic",
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == AttemptStatus.IN_PROGRESS


@pytest.mark.asyncio
async def test_class_topics_when_kaihle_admin_role_then_returns_200(
    client: AsyncClient,
    db_session: AsyncSession,
    kaihle_admin: User,
    test_class: Class,
) -> None:
    """Kaihle admins can access class topics."""
    headers = make_auth_header(kaihle_admin)

    response = await client.get(
        f"/api/v1/classes/{test_class.id}/topics",
        headers=headers,
    )

    assert response.status_code == 200
