"""Integration tests for SubtopicContent API routes.

Tests verify real service calls through HTTP endpoints using a live test DB.
Naming convention: test_<what>_when_<condition>_then_<expected>

Run with: pytest backend/app/tests/integration/test_subtopic_content_routes.py -v
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.curriculum import (
    Curriculum,
    CurriculumTopic,
    Grade,
    QuestionBank,
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


async def _create_curriculum_tree(db: AsyncSession) -> tuple[Subject, Grade, Curriculum, CurriculumTopic, Subtopic]:
    """Create a minimal curriculum + subtopic."""
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

    return subject, grade, curriculum, ct, st


async def _create_video_content_setup(
    db: AsyncSession,
) -> tuple[SubtopicContent, Subject, Grade, Curriculum, CurriculumTopic, Subtopic]:
    """Create a subtopic with video content for route tests."""
    subject, grade, curriculum, ct, st = await _create_curriculum_tree(db)

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


async def _create_explanation_content(db: AsyncSession, subtopic_id: uuid.UUID) -> SubtopicContent:
    """Create an explanation content row for a subtopic."""
    content = SubtopicContent(
        id=uuid.uuid4(),
        subtopic_id=subtopic_id,
        content_type="explanation",
        explanation_text="Linear equations are equations with one variable. To solve, isolate the variable.",
        review_status="pending",
    )
    db.add(content)
    await db.commit()
    return content


async def _create_quiz_content(db: AsyncSession, subtopic_id: uuid.UUID) -> SubtopicContent:
    """Create a practice quiz content row for a subtopic."""
    content = SubtopicContent(
        id=uuid.uuid4(),
        subtopic_id=subtopic_id,
        content_type="practice",
        quiz_questions=[
            {
                "question_id": str(uuid.uuid4()),
                "question_text": "What is 2x = 8?",
                "options": ["A: 2", "B: 4", "C: 6", "D: 8"],
                "correct_answer": "B: 4",
                "explanation": "Divide both sides by 2.",
                "difficulty_level": 2,
            }
        ],
        quiz_questions_count=1,
        review_status="pending",
    )
    db.add(content)
    await db.commit()
    return content


async def _make_admin(db: AsyncSession) -> User:
    admin = User(
        id=uuid.uuid4(),
        school_id=None,
        email=f"admin-{uuid.uuid4().hex[:8]}@kaihle.ai",
        first_name="Kaihle",
        last_name="Admin",
        role=UserRole.KAIHLE_ADMIN,
        is_active=True,
    )
    db.add(admin)
    await db.commit()
    return admin


# ---------------------------------------------------------------------------
# Tests: GET /subtopic-content/review-queue
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_review_queue_when_kaihle_admin_then_returns_queue(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """GET /review-queue returns paginated list of subtopics with content."""
    content, subject, grade, curriculum, ct, st2 = await _create_video_content_setup(db_session)
    admin = await _make_admin(db_session)

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

    item = next((i for i in data["items"] if i["subtopic_id"] == str(st2.id)), None)
    assert item is not None
    assert "video_status" in item
    assert "explanation_status" in item
    assert "quiz_status" in item


@pytest.mark.asyncio
async def test_review_queue_when_teacher_role_then_403(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
) -> None:
    """GET /review-queue returns 403 for non-KAIHLE_ADMIN roles."""
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
    """GET /{subtopic_id} returns full content detail with video, explanation, quiz sections."""
    content, subject, grade, curriculum, ct, st = await _create_video_content_setup(db_session)
    admin = await _make_admin(db_session)

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
    # New nested shape: video section contains videos list
    assert data["video"] is not None
    assert len(data["video"]["videos"]) == 2
    assert data["explanation"] is None
    assert data["quiz"] is None


@pytest.mark.asyncio
async def test_get_subtopic_content_when_all_sections_present_then_returns_all(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """GET /{subtopic_id} returns all three content sections when all exist."""
    _, subject, grade, curriculum, ct, st = await _create_video_content_setup(db_session)
    await _create_explanation_content(db_session, st.id)
    await _create_quiz_content(db_session, st.id)
    admin = await _make_admin(db_session)

    response = await client.get(
        f"/api/v1/subtopic-content/{st.id}",
        headers=make_auth_header(admin),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["video"] is not None
    assert data["explanation"] is not None
    assert data["explanation"]["explanation_text"] is not None
    assert data["quiz"] is not None
    assert len(data["quiz"]["questions"]) == 1


@pytest.mark.asyncio
async def test_get_subtopic_content_when_invalid_id_then_404(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """GET /{subtopic_id} returns 404 for non-existent subtopic."""
    admin = await _make_admin(db_session)
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

    response = await client.get(
        f"/api/v1/subtopic-content/{uuid.uuid4()}",
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
    """PATCH /videos/0 approves a video and returns updated nested response."""
    content, subject, grade, curriculum, ct, st = await _create_video_content_setup(db_session)
    admin = await _make_admin(db_session)

    response = await client.patch(
        f"/api/v1/subtopic-content/{st.id}/videos/0",
        json={"status": "approved"},
        headers=make_auth_header(admin),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["video"]["videos"][0]["status"] == "approved"


@pytest.mark.asyncio
async def test_update_video_status_when_rejected_then_status_updated(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """PATCH /videos/1 rejects a video candidate."""
    content, subject, grade, curriculum, ct, st = await _create_video_content_setup(db_session)
    admin = await _make_admin(db_session)

    response = await client.patch(
        f"/api/v1/subtopic-content/{st.id}/videos/1",
        json={"status": "rejected"},
        headers=make_auth_header(admin),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["video"]["videos"][1]["status"] == "rejected"


@pytest.mark.asyncio
async def test_update_video_status_when_invalid_index_then_404(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """PATCH with out-of-bounds video index returns 404."""
    content, subject, grade, curriculum, ct, st = await _create_video_content_setup(db_session)
    admin = await _make_admin(db_session)

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

    response = await client.patch(
        f"/api/v1/subtopic-content/{uuid.uuid4()}/videos/0",
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
    """POST /videos appends a new manual video and returns updated nested response."""
    content, subject, grade, curriculum, ct, st = await _create_video_content_setup(db_session)
    admin = await _make_admin(db_session)

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
    videos = data["video"]["videos"]
    assert len(videos) == 3
    assert videos[2]["url"] == "https://youtube.com/watch?v=newvideo"
    assert videos[2]["status"] == "pending"


@pytest.mark.asyncio
async def test_add_manual_video_when_teacher_then_403(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
) -> None:
    """POST /videos returns 403 for non-KAIHLE_ADMIN roles."""
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

    response = await client.post(
        f"/api/v1/subtopic-content/{uuid.uuid4()}/videos",
        json={"url": "https://youtube.com/watch?v=newvideo", "title": "New Video Title"},
        headers=make_auth_header(teacher),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_add_manual_video_when_no_body_then_422(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """POST /videos without request body returns 422."""
    content, subject, grade, curriculum, ct, st = await _create_video_content_setup(db_session)
    admin = await _make_admin(db_session)

    response = await client.post(
        f"/api/v1/subtopic-content/{st.id}/videos",
        headers=make_auth_header(admin),
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Tests: PATCH /subtopic-content/{subtopic_id}/explanation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_explanation_when_approved_then_status_saved(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """PATCH /explanation approves the explanation text and persists it."""
    _, _, _, _, st = await _create_curriculum_tree(db_session)
    await _create_explanation_content(db_session, st.id)
    admin = await _make_admin(db_session)

    new_text = "A linear equation has the form ax + b = 0. Solve by isolating x on one side."
    response = await client.patch(
        f"/api/v1/subtopic-content/{st.id}/explanation",
        json={"explanation_text": new_text, "review_status": "approved"},
        headers=make_auth_header(admin),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["explanation"]["explanation_text"] == new_text
    assert data["explanation"]["review_status"] == "approved"


@pytest.mark.asyncio
async def test_update_explanation_when_rejected_then_status_saved(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """PATCH /explanation rejects with a reason and sets status to rejected."""
    _, _, _, _, st = await _create_curriculum_tree(db_session)
    await _create_explanation_content(db_session, st.id)
    admin = await _make_admin(db_session)

    response = await client.patch(
        f"/api/v1/subtopic-content/{st.id}/explanation",
        json={
            "explanation_text": "Some explanation text here for testing purposes.",
            "review_status": "rejected",
            "rejection_reason": "Too brief — needs more worked examples.",
        },
        headers=make_auth_header(admin),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["explanation"]["review_status"] == "rejected"


@pytest.mark.asyncio
async def test_update_explanation_when_no_content_row_then_404(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """PATCH /explanation returns 404 when no explanation row exists."""
    _, _, _, _, st = await _create_curriculum_tree(db_session)
    admin = await _make_admin(db_session)

    response = await client.patch(
        f"/api/v1/subtopic-content/{st.id}/explanation",
        json={"explanation_text": "Some text for testing.", "review_status": "approved"},
        headers=make_auth_header(admin),
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_explanation_when_teacher_then_403(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
) -> None:
    """PATCH /explanation returns 403 for non-KAIHLE_ADMIN roles."""
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

    response = await client.patch(
        f"/api/v1/subtopic-content/{uuid.uuid4()}/explanation",
        json={"explanation_text": "Some text here.", "review_status": "approved"},
        headers=make_auth_header(teacher),
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Tests: PATCH /subtopic-content/{subtopic_id}/quiz
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_quiz_when_approved_then_questions_and_status_saved(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """PATCH /quiz approves, saves to subtopic_content, and publishes to question_bank."""
    _, _, _, _, st = await _create_curriculum_tree(db_session)
    await _create_quiz_content(db_session, st.id)
    admin = await _make_admin(db_session)

    updated_questions = [
        {
            "question_id": str(uuid.uuid4()),
            "question_text": "What value of x satisfies 2x = 8?",
            "options": ["A: 2", "B: 4", "C: 6", "D: 8"],
            "correct_answer": "B: 4",
            "explanation": "Divide both sides of the equation by 2 to get x = 4.",
            "difficulty_level": 2,
        }
    ]
    response = await client.patch(
        f"/api/v1/subtopic-content/{st.id}/quiz",
        json={"questions": updated_questions, "review_status": "approved"},
        headers=make_auth_header(admin),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["quiz"]["review_status"] == "approved"
    assert data["quiz"]["questions"][0]["question_text"] == "What value of x satisfies 2x = 8?"

    # Approval must publish questions to question_bank so assessments and mini-courses can use them
    from sqlalchemy import select as sa_select

    qb_result = await db_session.execute(
        sa_select(QuestionBank).where(QuestionBank.subtopic_id == st.id, QuestionBank.source == "llm")
    )
    qb_rows = qb_result.scalars().all()
    assert len(qb_rows) == 1
    assert qb_rows[0].question_text == "What value of x satisfies 2x = 8?"
    assert qb_rows[0].correct_answer == "B: 4"
    assert qb_rows[0].is_active is True


@pytest.mark.asyncio
async def test_update_quiz_when_rejected_then_status_saved(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """PATCH /quiz rejects the quiz with a reason."""
    _, _, _, _, st = await _create_curriculum_tree(db_session)
    await _create_quiz_content(db_session, st.id)
    admin = await _make_admin(db_session)

    response = await client.patch(
        f"/api/v1/subtopic-content/{st.id}/quiz",
        json={
            "questions": [
                {
                    "question_id": str(uuid.uuid4()),
                    "question_text": "What is 2x = 8?",
                    "options": ["A: 2", "B: 4", "C: 6", "D: 8"],
                    "correct_answer": "B: 4",
                    "explanation": "Divide both sides by 2.",
                    "difficulty_level": 2,
                }
            ],
            "review_status": "rejected",
            "rejection_reason": "Questions are too trivial for Grade 8.",
        },
        headers=make_auth_header(admin),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["quiz"]["review_status"] == "rejected"


@pytest.mark.asyncio
async def test_update_quiz_when_no_content_row_then_404(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """PATCH /quiz returns 404 when no practice content row exists."""
    _, _, _, _, st = await _create_curriculum_tree(db_session)
    admin = await _make_admin(db_session)

    response = await client.patch(
        f"/api/v1/subtopic-content/{st.id}/quiz",
        json={
            "questions": [
                {
                    "question_id": str(uuid.uuid4()),
                    "question_text": "Test question text here",
                    "options": ["A: 1", "B: 2", "C: 3", "D: 4"],
                    "correct_answer": "A: 1",
                    "explanation": "Explanation here.",
                    "difficulty_level": 1,
                }
            ],
            "review_status": "approved",
        },
        headers=make_auth_header(admin),
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_quiz_when_teacher_then_403(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
) -> None:
    """PATCH /quiz returns 403 for non-KAIHLE_ADMIN roles."""
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

    response = await client.patch(
        f"/api/v1/subtopic-content/{uuid.uuid4()}/quiz",
        json={"questions": [], "review_status": "approved"},
        headers=make_auth_header(teacher),
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Tests: POST /subtopic-content/{subtopic_id}/quiz/generate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_quiz_when_llm_succeeds_then_creates_practice_row(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """POST /quiz/generate creates a practice row with LLM-generated questions."""
    _, _, _, _, st = await _create_curriculum_tree(db_session)
    admin = await _make_admin(db_session)

    mock_llm_response = json.dumps(
        {
            "questions": [
                {
                    "question_id": str(uuid.uuid4()),
                    "question_text": "What is x in 2x + 4 = 10?",
                    "options": ["A: 1", "B: 2", "C: 3", "D: 4"],
                    "correct_answer": "C: 3",
                    "explanation": "Subtract 4 from both sides: 2x = 6. Divide by 2: x = 3.",
                    "difficulty_level": 3,
                }
            ]
        }
    )

    with patch("app.ai.providers.router.complete", new_callable=AsyncMock) as mock_complete:
        mock_complete.return_value = mock_llm_response
        response = await client.post(
            f"/api/v1/subtopic-content/{st.id}/quiz/generate",
            headers=make_auth_header(admin),
        )

    assert response.status_code == 200
    data = response.json()
    assert data["quiz"] is not None
    assert len(data["quiz"]["questions"]) == 1
    assert data["quiz"]["review_status"] == "pending"
    assert data["quiz"]["questions"][0]["question_text"] == "What is x in 2x + 4 = 10?"


@pytest.mark.asyncio
async def test_generate_quiz_when_quiz_exists_then_overwrites_questions(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """POST /quiz/generate overwrites existing quiz questions with new LLM output."""
    _, _, _, _, st = await _create_curriculum_tree(db_session)
    await _create_quiz_content(db_session, st.id)
    admin = await _make_admin(db_session)

    new_question_text = "Solve: 3x - 6 = 9"
    mock_llm_response = json.dumps(
        {
            "questions": [
                {
                    "question_id": str(uuid.uuid4()),
                    "question_text": new_question_text,
                    "options": ["A: 3", "B: 4", "C: 5", "D: 6"],
                    "correct_answer": "C: 5",
                    "explanation": "Add 6 to both sides: 3x = 15. Divide by 3: x = 5.",
                    "difficulty_level": 3,
                }
            ]
        }
    )

    with patch("app.ai.providers.router.complete", new_callable=AsyncMock) as mock_complete:
        mock_complete.return_value = mock_llm_response
        response = await client.post(
            f"/api/v1/subtopic-content/{st.id}/quiz/generate",
            headers=make_auth_header(admin),
        )

    assert response.status_code == 200
    data = response.json()
    assert data["quiz"]["questions"][0]["question_text"] == new_question_text
    assert data["quiz"]["review_status"] == "pending"


@pytest.mark.asyncio
async def test_generate_quiz_when_llm_fails_then_502(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """POST /quiz/generate returns 502 when LLM call raises an exception."""
    _, _, _, _, st = await _create_curriculum_tree(db_session)
    admin = await _make_admin(db_session)

    with patch("app.ai.providers.router.complete", new_callable=AsyncMock) as mock_complete:
        mock_complete.side_effect = Exception("LLM timeout")
        response = await client.post(
            f"/api/v1/subtopic-content/{st.id}/quiz/generate",
            headers=make_auth_header(admin),
        )

    assert response.status_code == 502


@pytest.mark.asyncio
async def test_generate_quiz_when_teacher_then_403(
    client: AsyncClient,
    db_session: AsyncSession,
    school: School,
) -> None:
    """POST /quiz/generate returns 403 for non-KAIHLE_ADMIN roles."""
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

    response = await client.post(
        f"/api/v1/subtopic-content/{uuid.uuid4()}/quiz/generate",
        headers=make_auth_header(teacher),
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# T5 Integration Tests: teacher status, generate, approve; promotion queue
# ---------------------------------------------------------------------------


async def _setup_teacher_with_class(
    db: AsyncSession,
    subject: Subject,
    grade: Grade,
    curriculum: Curriculum,
) -> tuple[School, User]:
    """Create a school, teacher, and class linked to curriculum tree."""
    from app.models.school import Class, School

    school = School(
        id=uuid.uuid4(),
        name=f"School-{uuid.uuid4().hex[:6]}",
        slug=f"school-{uuid.uuid4().hex[:8]}",
        status="active",
    )
    db.add(school)
    await db.flush()

    teacher = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"teacher-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Jane",
        last_name="Teacher",
        role=UserRole.TEACHER,
        is_active=True,
    )
    db.add(teacher)
    await db.flush()

    klass = Class(
        id=uuid.uuid4(),
        school_id=school.id,
        grade_id=grade.id,
        subject_id=subject.id,
        curriculum_id=curriculum.id,
        teacher_id=teacher.id,
        name="8A Mathematics",
        academic_year="2025-2026",
        is_active=True,
    )
    db.add(klass)
    await db.flush()

    return school, teacher


@pytest.mark.asyncio
async def test_get_status_when_no_content_then_all_none(client: AsyncClient, db_session: AsyncSession) -> None:
    """GET /{subtopic_id}/status with no content rows returns status='none' for all types."""
    subject, grade, curriculum, ct, st = await _create_curriculum_tree(db_session)
    school, teacher = await _setup_teacher_with_class(db_session, subject, grade, curriculum)
    await db_session.commit()

    response = await client.get(
        f"/api/v1/subtopic-content/{st.id}/status",
        headers=make_auth_header(teacher),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["video"]["status"] == "none"
    assert data["explanation"]["status"] == "none"
    assert data["quiz"]["status"] == "none"


@pytest.mark.asyncio
async def test_get_status_when_school_scoped_own_school_then_shows_pending(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """GET /{subtopic_id}/status returns 'pending' for own school's pending content."""
    subject, grade, curriculum, ct, st = await _create_curriculum_tree(db_session)
    school, teacher = await _setup_teacher_with_class(db_session, subject, grade, curriculum)

    content = SubtopicContent(
        id=uuid.uuid4(),
        subtopic_id=st.id,
        content_type="video",
        scope="school",
        school_id=school.id,
        review_status="pending",
    )
    db_session.add(content)
    await db_session.commit()

    response = await client.get(
        f"/api/v1/subtopic-content/{st.id}/status",
        headers=make_auth_header(teacher),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["video"]["status"] == "pending"
    assert data["video"]["scope"] == "school"


@pytest.mark.asyncio
async def test_get_status_when_school_scoped_other_school_then_shows_other_school_pending(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """GET /{subtopic_id}/status shows 'other_school_pending' for another school's content."""
    subject, grade, curriculum, ct, st = await _create_curriculum_tree(db_session)
    school, teacher = await _setup_teacher_with_class(db_session, subject, grade, curriculum)
    other_school, _ = await _setup_teacher_with_class(db_session, subject, grade, curriculum)

    content = SubtopicContent(
        id=uuid.uuid4(),
        subtopic_id=st.id,
        content_type="quiz",
        scope="school",
        school_id=other_school.id,
        review_status="pending",
    )
    db_session.add(content)
    await db_session.commit()

    response = await client.get(
        f"/api/v1/subtopic-content/{st.id}/status",
        headers=make_auth_header(teacher),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["quiz"]["status"] == "other_school_pending"


@pytest.mark.asyncio
async def test_generate_when_content_exists_any_scope_then_409(client: AsyncClient, db_session: AsyncSession) -> None:
    """POST /{subtopic_id}/quiz/generate returns 409 if any row exists for that (subtopic, type)."""
    subject, grade, curriculum, ct, st = await _create_curriculum_tree(db_session)
    school, teacher = await _setup_teacher_with_class(db_session, subject, grade, curriculum)

    # Curriculum-scope row already exists
    content = SubtopicContent(
        id=uuid.uuid4(),
        subtopic_id=st.id,
        content_type="quiz",
        scope="curriculum",
        review_status="pending",
    )
    db_session.add(content)
    await db_session.commit()

    response = await client.post(
        f"/api/v1/subtopic-content/{st.id}/quiz/generate",
        headers=make_auth_header(teacher),
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_generate_when_no_content_then_creates_school_scoped_pending_row(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """POST /{subtopic_id}/video/generate creates school-scoped pending row when none exists."""
    subject, grade, curriculum, ct, st = await _create_curriculum_tree(db_session)
    school, teacher = await _setup_teacher_with_class(db_session, subject, grade, curriculum)
    await db_session.commit()

    response = await client.post(
        f"/api/v1/subtopic-content/{st.id}/video/generate",
        headers=make_auth_header(teacher),
    )
    assert response.status_code == 202

    from sqlalchemy import select as sa_select

    result = await db_session.execute(
        sa_select(SubtopicContent).where(
            SubtopicContent.subtopic_id == st.id,
            SubtopicContent.content_type == "video",
        )
    )
    row = result.scalar_one_or_none()
    assert row is not None
    assert row.scope == "school"
    assert row.school_id == school.id
    assert row.review_status == "pending"


@pytest.mark.asyncio
async def test_teacher_approve_when_own_school_content_then_sets_approved(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """PATCH /{subtopic_id}/video/approve sets review_status='approved' for own school's content."""
    subject, grade, curriculum, ct, st = await _create_curriculum_tree(db_session)
    school, teacher = await _setup_teacher_with_class(db_session, subject, grade, curriculum)

    content = SubtopicContent(
        id=uuid.uuid4(),
        subtopic_id=st.id,
        content_type="video",
        scope="school",
        school_id=school.id,
        review_status="pending",
    )
    db_session.add(content)
    await db_session.commit()

    response = await client.patch(
        f"/api/v1/subtopic-content/{st.id}/video/approve",
        headers=make_auth_header(teacher),
        json={"action": "approve"},
    )
    assert response.status_code == 200

    await db_session.refresh(content)
    assert content.review_status == "approved"
    assert content.is_active is True


@pytest.mark.asyncio
async def test_teacher_approve_when_other_school_content_then_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """PATCH /{subtopic_id}/video/approve returns 404 when the row belongs to another school."""
    subject, grade, curriculum, ct, st = await _create_curriculum_tree(db_session)
    school, teacher = await _setup_teacher_with_class(db_session, subject, grade, curriculum)
    other_school, _ = await _setup_teacher_with_class(db_session, subject, grade, curriculum)

    content = SubtopicContent(
        id=uuid.uuid4(),
        subtopic_id=st.id,
        content_type="video",
        scope="school",
        school_id=other_school.id,
        review_status="pending",
    )
    db_session.add(content)
    await db_session.commit()

    response = await client.patch(
        f"/api/v1/subtopic-content/{st.id}/video/approve",
        headers=make_auth_header(teacher),
        json={"action": "approve"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_promotion_queue_when_kaihle_admin_then_returns_school_scoped_approved(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """GET /promotion-queue returns school-scoped approved rows."""
    subject, grade, curriculum, ct, st = await _create_curriculum_tree(db_session)
    school, teacher = await _setup_teacher_with_class(db_session, subject, grade, curriculum)

    content = SubtopicContent(
        id=uuid.uuid4(),
        subtopic_id=st.id,
        content_type="quiz",
        scope="school",
        school_id=school.id,
        review_status="approved",
    )
    db_session.add(content)

    admin = User(
        id=uuid.uuid4(),
        email=f"admin-{uuid.uuid4().hex[:8]}@kaihle.ai",
        first_name="Admin",
        last_name="User",
        role=UserRole.KAIHLE_ADMIN,
        is_active=True,
    )
    db_session.add(admin)
    await db_session.commit()

    response = await client.get(
        "/api/v1/subtopic-content/promotion-queue",
        headers=make_auth_header(admin),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    ids = [item["subtopic_content_id"] for item in data["items"]]
    assert str(content.id) in ids


@pytest.mark.asyncio
async def test_promote_when_kaihle_admin_then_scope_becomes_curriculum(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """PATCH /{subtopic_id}/quiz/promote updates scope to 'curriculum' and clears school_id."""
    subject, grade, curriculum, ct, st = await _create_curriculum_tree(db_session)
    school, teacher = await _setup_teacher_with_class(db_session, subject, grade, curriculum)

    content = SubtopicContent(
        id=uuid.uuid4(),
        subtopic_id=st.id,
        content_type="quiz",
        scope="school",
        school_id=school.id,
        review_status="approved",
    )
    db_session.add(content)

    admin = User(
        id=uuid.uuid4(),
        email=f"admin2-{uuid.uuid4().hex[:8]}@kaihle.ai",
        first_name="Admin",
        last_name="Two",
        role=UserRole.KAIHLE_ADMIN,
        is_active=True,
    )
    db_session.add(admin)
    await db_session.commit()

    response = await client.patch(
        f"/api/v1/subtopic-content/{st.id}/quiz/promote",
        headers=make_auth_header(admin),
        json={"action": "promote"},
    )
    assert response.status_code == 200

    await db_session.refresh(content)
    assert content.scope == "curriculum"
    assert content.school_id is None


@pytest.mark.asyncio
async def test_promote_when_teacher_then_403(client: AsyncClient, db_session: AsyncSession) -> None:
    """PATCH /{subtopic_id}/quiz/promote returns 403 for teacher role."""
    subject, grade, curriculum, ct, st = await _create_curriculum_tree(db_session)
    school, teacher = await _setup_teacher_with_class(db_session, subject, grade, curriculum)
    await db_session.commit()

    response = await client.patch(
        f"/api/v1/subtopic-content/{st.id}/quiz/promote",
        headers=make_auth_header(teacher),
        json={"action": "promote"},
    )
    assert response.status_code == 403
