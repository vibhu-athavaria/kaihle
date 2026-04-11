"""Integration tests for SubtopicContent API routes (M3-0-T2a).

Tests verify real service calls through HTTP endpoints using a live test DB.
Naming convention: test_<what>_when_<condition>_then_<expected>

Run with: pytest backend/app/tests/integration/test_subtopic_content_routes.py -v
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
from app.models.subtopic_content import SubtopicContent
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


async def _create_video_content_setup(
    db: AsyncSession,
) -> tuple[SubtopicContent, Subject, Grade, Curriculum, CurriculumTopic, Subtopic]:
    """Create a minimal curriculum + subtopic with video content for route tests."""
    subject = Subject(
        id=uuid.uuid4(), name=f"Math-{uuid.uuid4().hex[:4]}", code=f"M{uuid.uuid4().hex[:4]}", is_active=True
    )
    grade = Grade(id=uuid.uuid4(), name="Grade 8", level=8, is_active=True)
    curriculum = Curriculum(
        id=uuid.uuid4(), name=f"Curr-{uuid.uuid4().hex[:4]}", code=f"C{uuid.uuid4().hex[:4]}", is_active=True
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

    st = Subtopic(
        id=uuid.uuid4(),
        curriculum_topic_id=ct.id,
        name="Linear Equations",
        learning_objective="Solve linear equations",
        is_active=True,
    )
    db.add(st)
    await db.flush()

    content = SubtopicContent(
        id=uuid.uuid4(),
        subtopic_id=st.id,
        content_type="video",
        videos=[
            {
                "url": "https://youtube.com/watch?v=abc123",
                "title": "Introduction to Linear Equations",
                "channel": "MathWorld",
                "view_count": 10000,
                "status": "pending",
                "last_checked_at": None,
            },
            {
                "url": "https://youtube.com/watch?v=def456",
                "title": "Solving Linear Equations",
                "channel": "AlgebraHelp",
                "view_count": 5000,
                "status": "approved",
                "last_checked_at": None,
            },
        ],
        review_status="pending",
    )
    db.add(content)
    await db.commit()

    return content, subject, grade, curriculum, ct, st


# ---------------------------------------------------------------------------
# Tests: GET /subtopic-content/review-queue
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_review_queue_when_kaihle_admin_then_returns_queue(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """GET /review-queue returns paginated list of subtopics with video content."""
    content, subject, grade, curriculum, ct, st = await _create_video_content_setup(db_session)

    # Create a KAIHLE_ADMIN user for auth
    admin = User(
        id=uuid.uuid4(),
        school_id=None,
        email=f"admin-{uuid.uuid4().hex[:8]}@kaihle.ai",
        first_name="Kaihle",
        last_name="Admin",
        role=UserRole.KAIHLE_ADMIN,
        is_active=True,
    )
    db_session.add(admin)
    await db_session.commit()

    response = await client.get(
        "/api/v1/subtopic-content/review-queue",
        headers=make_auth_header(admin),
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "pending_total" in data
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_review_queue_when_teacher_role_then_403(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
) -> None:
    """GET /review-queue returns 403 for non-KAIHLE_ADMIN roles."""
    # Create a teacher user
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
        "/api/v1/subtopic-content/review-queue",
        headers=make_auth_header(teacher),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_review_queue_when_no_auth_then_401(
    client: AsyncClient,
) -> None:
    """GET /review-queue returns 401 without authentication."""
    response = await client.get("/api/v1/subtopic-content/review-queue")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Tests: GET /subtopic-content/{subtopic_id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_subtopic_content_when_valid_id_then_returns_detail(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """GET /{subtopic_id} returns full video content detail."""
    content, subject, grade, curriculum, ct, st = await _create_video_content_setup(db_session)

    admin = User(
        id=uuid.uuid4(),
        school_id=None,
        email=f"admin-{uuid.uuid4().hex[:8]}@kaihle.ai",
        first_name="Kaihle",
        last_name="Admin",
        role=UserRole.KAIHLE_ADMIN,
        is_active=True,
    )
    db_session.add(admin)
    await db_session.commit()

    response = await client.get(
        f"/api/v1/subtopic-content/{st.id}",
        headers=make_auth_header(admin),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["subtopic_id"] == str(st.id)
    assert data["subtopic_name"] == "Linear Equations"
    assert data["subject_code"] == subject.code
    assert data["grade_level"] == grade.level
    assert len(data["videos"]) == 2


@pytest.mark.asyncio
async def test_get_subtopic_content_when_invalid_id_then_404(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """GET /{subtopic_id} returns 404 for non-existent subtopic."""
    admin = User(
        id=uuid.uuid4(),
        school_id=None,
        email=f"admin-{uuid.uuid4().hex[:8]}@kaihle.ai",
        first_name="Kaihle",
        last_name="Admin",
        role=UserRole.KAIHLE_ADMIN,
        is_active=True,
    )
    db_session.add(admin)
    await db_session.commit()

    fake_id = uuid.uuid4()
    response = await client.get(
        f"/api/v1/subtopic-content/{fake_id}",
        headers=make_auth_header(admin),
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_subtopic_content_when_teacher_then_403(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
) -> None:
    """GET /{subtopic_id} returns 403 for non-KAIHLE_ADMIN roles."""
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

    fake_id = uuid.uuid4()
    response = await client.get(
        f"/api/v1/subtopic-content/{fake_id}",
        headers=make_auth_header(teacher),
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Tests: PATCH /subtopic-content/{subtopic_id}/videos/{video_index}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_video_status_when_valid_index_then_status_updated(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """PATCH updates video status and returns updated content."""
    content, subject, grade, curriculum, ct, st = await _create_video_content_setup(db_session)

    admin = User(
        id=uuid.uuid4(),
        school_id=None,
        email=f"admin-{uuid.uuid4().hex[:8]}@kaihle.ai",
        first_name="Kaihle",
        last_name="Admin",
        role=UserRole.KAIHLE_ADMIN,
        is_active=True,
    )
    db_session.add(admin)
    await db_session.commit()

    response = await client.patch(
        f"/api/v1/subtopic-content/{st.id}/videos/0",
        json={"status": "approved"},
        headers=make_auth_header(admin),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["videos"][0]["status"] == "approved"


@pytest.mark.asyncio
async def test_update_video_status_when_invalid_index_then_404(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """PATCH with invalid video index returns 404."""
    content, subject, grade, curriculum, ct, st = await _create_video_content_setup(db_session)

    admin = User(
        id=uuid.uuid4(),
        school_id=None,
        email=f"admin-{uuid.uuid4().hex[:8]}@kaihle.ai",
        first_name="Kaihle",
        last_name="Admin",
        role=UserRole.KAIHLE_ADMIN,
        is_active=True,
    )
    db_session.add(admin)
    await db_session.commit()

    response = await client.patch(
        f"/api/v1/subtopic-content/{st.id}/videos/999",
        json={"status": "approved"},
        headers=make_auth_header(admin),
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_video_status_when_teacher_then_403(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
) -> None:
    """PATCH returns 403 for non-KAIHLE_ADMIN roles."""
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

    fake_id = uuid.uuid4()
    response = await client.patch(
        f"/api/v1/subtopic-content/{fake_id}/videos/0",
        json={"status": "approved"},
        headers=make_auth_header(teacher),
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Tests: POST /subtopic-content/{subtopic_id}/videos
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_manual_video_when_valid_then_appended_to_array(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """POST adds a new manual video entry to the subtopic's video array."""
    content, subject, grade, curriculum, ct, st = await _create_video_content_setup(db_session)

    admin = User(
        id=uuid.uuid4(),
        school_id=None,
        email=f"admin-{uuid.uuid4().hex[:8]}@kaihle.ai",
        first_name="Kaihle",
        last_name="Admin",
        role=UserRole.KAIHLE_ADMIN,
        is_active=True,
    )
    db_session.add(admin)
    await db_session.commit()

    response = await client.post(
        f"/api/v1/subtopic-content/{st.id}/videos",
        json={
            "url": "https://youtube.com/watch?v=newvideo",
            "title": "New Video Title",
            "channel": "New Channel",
        },
        headers=make_auth_header(admin),
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["videos"]) == 3
    assert data["videos"][2]["url"] == "https://youtube.com/watch?v=newvideo"
    assert data["videos"][2]["status"] == "pending"


@pytest.mark.asyncio
async def test_add_manual_video_when_teacher_then_403(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
) -> None:
    """POST returns 403 for non-KAIHLE_ADMIN roles."""
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

    fake_id = uuid.uuid4()
    response = await client.post(
        f"/api/v1/subtopic-content/{fake_id}/videos",
        json={
            "url": "https://youtube.com/watch?v=newvideo",
            "title": "New Video Title",
            "channel": "New Channel",
        },
        headers=make_auth_header(teacher),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_add_manual_video_when_no_body_then_422(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """POST without request body returns 422."""
    content, subject, grade, curriculum, ct, st = await _create_video_content_setup(db_session)

    admin = User(
        id=uuid.uuid4(),
        school_id=None,
        email=f"admin-{uuid.uuid4().hex[:8]}@kaihle.ai",
        first_name="Kaihle",
        last_name="Admin",
        role=UserRole.KAIHLE_ADMIN,
        is_active=True,
    )
    db_session.add(admin)
    await db_session.commit()

    response = await client.post(
        f"/api/v1/subtopic-content/{st.id}/videos",
        headers=make_auth_header(admin),
    )
    assert response.status_code == 422
