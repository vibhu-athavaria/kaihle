"""Integration tests for mini-course API routes (M5-1-T2).

Tests verify real service calls through HTTP endpoints using a live test DB.
Naming convention: test_<what>_when_<condition>_then_<expected>

Run with: pytest backend/app/tests/integration/test_mini_course_route.py -v
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.curriculum import (
    Curriculum,
    CurriculumTopic,
    Grade,
    Subject,
    Subtopic,
    Topic,
)
from app.models.school import School
from app.models.user import User, UserRole

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_auth_header(user: User) -> dict[str, str]:
    """Generate Authorization header with a real JWT."""
    token = create_access_token(
        user_id=user.id,
        school_id=user.school_id,
        role=user.role,
    )
    return {"Authorization": f"Bearer {token}"}


async def _create_curriculum_subtopic(db: AsyncSession) -> tuple[Subtopic, Topic]:
    """Create a minimal curriculum chain and return (subtopic, topic)."""
    subject = Subject(
        id=uuid.uuid4(),
        name=f"Math-{uuid.uuid4().hex[:4]}",
        code=f"M{uuid.uuid4().hex[:4]}",
        is_active=True,
    )
    grade = Grade(id=uuid.uuid4(), name="Grade 7", level=7, is_active=True)
    curriculum = Curriculum(
        id=uuid.uuid4(),
        name=f"Curr-{uuid.uuid4().hex[:4]}",
        code=f"C{uuid.uuid4().hex[:4]}",
        is_active=True,
    )
    topic = Topic(id=uuid.uuid4(), name="Algebra", is_active=True)
    db.add_all([subject, grade, curriculum, topic])
    await db.flush()

    ct = CurriculumTopic(
        id=uuid.uuid4(),
        curriculum_id=curriculum.id,
        subject_id=subject.id,
        grade_id=grade.id,
        topic_id=topic.id,
        is_active=True,
    )
    db.add(ct)
    await db.flush()

    subtopic = Subtopic(
        id=uuid.uuid4(),
        curriculum_topic_id=ct.id,
        name="Linear Equations",
        learning_objective="Solve linear equations",
        is_active=True,
    )
    db.add(subtopic)
    await db.commit()

    return subtopic, topic


# ---------------------------------------------------------------------------
# Tests: GET /api/v1/students/me/subtopics/{subtopic_id}/course
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_course_route_when_authenticated_student_then_returns_200(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
) -> None:
    """GET course endpoint returns 200 with the expected payload shape for a student."""
    subtopic, topic = await _create_curriculum_subtopic(db_session)

    student = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"student-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Test",
        last_name="Student",
        role=UserRole.STUDENT,
        is_active=True,
    )
    db_session.add(student)
    await db_session.commit()

    response = await client.get(
        f"/api/v1/students/me/subtopics/{subtopic.id}/course",
        headers=make_auth_header(student),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["subtopic_id"] == str(subtopic.id)
    assert data["subtopic_name"] == "Linear Equations"
    assert data["topic_name"] == "Algebra"
    assert data["content_status"] in ("ready", "unavailable")
    assert "progress" in data
    assert "check_questions" in data


@pytest.mark.asyncio
async def test_get_course_route_when_unauthenticated_then_returns_401(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """GET course endpoint returns 401 when no auth token is provided."""
    response = await client.get(
        f"/api/v1/students/me/subtopics/{uuid.uuid4()}/course",
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_post_progress_route_when_valid_payload_then_returns_200(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
) -> None:
    """POST progress endpoint returns 200 {"ok": true} when student marks progress."""
    subtopic, _ = await _create_curriculum_subtopic(db_session)

    student = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"student-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Test",
        last_name="Student",
        role=UserRole.STUDENT,
        is_active=True,
    )
    db_session.add(student)
    await db_session.commit()

    # First visit to create the progress row
    await client.get(
        f"/api/v1/students/me/subtopics/{subtopic.id}/course",
        headers=make_auth_header(student),
    )

    response = await client.post(
        f"/api/v1/students/me/subtopics/{subtopic.id}/course/progress",
        headers=make_auth_header(student),
        json={"explanation_accessed": True, "video_accessed": False},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True


@pytest.mark.asyncio
async def test_get_course_route_when_teacher_role_then_returns_403(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
) -> None:
    """GET course endpoint returns 403 for non-student roles."""
    subtopic, _ = await _create_curriculum_subtopic(db_session)

    teacher = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"teacher-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Test",
        last_name="Teacher",
        role=UserRole.TEACHER,
        is_active=True,
    )
    db_session.add(teacher)
    await db_session.commit()

    response = await client.get(
        f"/api/v1/students/me/subtopics/{subtopic.id}/course",
        headers=make_auth_header(teacher),
    )

    assert response.status_code == 403
