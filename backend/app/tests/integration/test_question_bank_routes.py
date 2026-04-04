"""
Integration tests for question_bank routes.
Tests GET /api/v1/question-bank (paginated list) and PATCH /api/v1/question-bank/{id}.
Requires KAIHLE_ADMIN role.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.curriculum import (
    Curriculum,
    CurriculumTopic,
    Grade,
    QuestionBank,
    Subject,
    Subtopic,
    Topic,
)
from app.models.user import User, UserRole

# Import make_auth_header from conftest (auto-discovered by pytest)
from app.tests.integration.conftest import make_auth_header

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def curriculum_graph(db_session: AsyncSession):
    """Create a minimal curriculum graph for testing."""
    curriculum = Curriculum(name="Test Curriculum")
    db_session.add(curriculum)
    await db_session.flush()

    subject = Subject(name="Test Subject")
    db_session.add(subject)
    await db_session.flush()

    grade = Grade(name="Test Grade")
    db_session.add(grade)
    await db_session.flush()

    topic = Topic(name="Test Topic")
    db_session.add(topic)
    await db_session.flush()

    curriculum_topic = CurriculumTopic(
        curriculum_id=curriculum.id,
        subject_id=subject.id,
        grade_id=grade.id,
        topic_id=topic.id,
    )
    db_session.add(curriculum_topic)
    await db_session.flush()

    subtopic = Subtopic(
        name="Test Subtopic",
        curriculum_topic_id=curriculum_topic.id,
    )
    db_session.add(subtopic)
    await db_session.flush()

    await db_session.commit()

    return {
        "curriculum": curriculum,
        "subject": subject,
        "grade": grade,
        "topic": topic,
        "curriculum_topic": curriculum_topic,
        "subtopic": subtopic,
    }


@pytest.fixture
async def student_user(db_session: AsyncSession) -> User:
    """Create a STUDENT user for access control testing."""
    user = User(
        id=uuid.uuid4(),
        email=f"student-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Test",
        last_name="Student",
        role=UserRole.STUDENT,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.fixture
async def sample_questions(db_session: AsyncSession, curriculum_graph) -> list[QuestionBank]:
    """Create sample questions for testing."""
    questions = [
        QuestionBank(
            question_text="What is 2 + 2?",
            question_type="MCQ",
            correct_answer="4",
            explanation="Basic addition.",
            difficulty_level=0.3,
            is_active=True,
            subtopic_id=curriculum_graph["subtopic"].id,
        ),
        QuestionBank(
            question_text="What is 3 + 3?",
            question_type="MCQ",
            correct_answer="6",
            explanation=None,
            difficulty_level=0.4,
            is_active=True,
            subtopic_id=curriculum_graph["subtopic"].id,
        ),
        QuestionBank(
            question_text="Is the sky blue?",
            question_type="TRUE_FALSE",
            correct_answer="True",
            explanation="The sky appears blue due to Rayleigh scattering.",
            difficulty_level=0.2,
            is_active=False,
            subtopic_id=curriculum_graph["subtopic"].id,
        ),
    ]
    for q in questions:
        db_session.add(q)
    await db_session.commit()
    for q in questions:
        await db_session.refresh(q)
    return questions


# ── GET /api/v1/question-bank ─────────────────────────────────────────────────


class TestListQuestions:
    """Tests for GET /api/v1/question-bank endpoint."""

    @pytest.mark.asyncio
    async def test_list_requires_auth(self, client: AsyncClient, sample_questions):
        """Unauthenticated requests should be rejected."""
        response = await client.get("/api/v1/question-bank")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_requires_admin_role(self, client: AsyncClient, student_user, sample_questions):
        """Non-admin users should be forbidden."""
        headers = make_auth_header(student_user)
        response = await client.get("/api/v1/question-bank", headers=headers)
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_list_returns_paginated_questions(self, client: AsyncClient, kaihle_admin, sample_questions):
        """Admin can list questions with pagination."""
        headers = make_auth_header(kaihle_admin)
        response = await client.get("/api/v1/question-bank", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "questions" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert data["total"] == 3
        assert len(data["questions"]) == 3

    @pytest.mark.asyncio
    async def test_list_includes_curriculum_context(self, client: AsyncClient, kaihle_admin, sample_questions):
        """Questions should include curriculum context from joins."""
        headers = make_auth_header(kaihle_admin)
        response = await client.get("/api/v1/question-bank", headers=headers)
        assert response.status_code == 200
        data = response.json()
        question = data["questions"][0]
        assert "curriculum_name" in question
        assert "subject_name" in question
        assert "grade_name" in question
        assert "topic_name" in question
        assert "subtopic_name" in question
        assert question["curriculum_name"] == "Test Curriculum"
        assert question["subject_name"] == "Test Subject"

    @pytest.mark.asyncio
    async def test_list_pagination(self, client: AsyncClient, kaihle_admin, sample_questions):
        """Pagination parameters should work correctly."""
        headers = make_auth_header(kaihle_admin)
        response = await client.get("/api/v1/question-bank?page=1&page_size=2", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data["questions"]) == 2
        assert data["total"] == 3
        assert data["page"] == 1
        assert data["page_size"] == 2

    @pytest.mark.asyncio
    async def test_list_filter_by_question_type(self, client: AsyncClient, kaihle_admin, sample_questions):
        """Filtering by question_type should work."""
        headers = make_auth_header(kaihle_admin)
        response = await client.get(
            "/api/v1/question-bank?question_type=TRUE_FALSE",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["questions"][0]["question_type"] == "TRUE_FALSE"

    @pytest.mark.asyncio
    async def test_list_filter_by_search(self, client: AsyncClient, kaihle_admin, sample_questions):
        """Search by question_text should work."""
        headers = make_auth_header(kaihle_admin)
        response = await client.get(
            "/api/v1/question-bank?search=2%20%2B%202",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert "2 + 2" in data["questions"][0]["question_text"]

    @pytest.mark.asyncio
    async def test_list_filter_by_curriculum(self, client: AsyncClient, kaihle_admin, sample_questions):
        """Filtering by curriculum_id should work."""
        headers = make_auth_header(kaihle_admin)
        curriculum = sample_questions[0].subtopic.curriculum_topic.curriculum
        response = await client.get(
            f"/api/v1/question-bank?curriculum_id={curriculum.id}",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3

    @pytest.mark.asyncio
    async def test_list_orders_by_created_at_desc(self, client: AsyncClient, kaihle_admin, sample_questions):
        """Questions should be ordered by created_at descending for stable pagination."""
        headers = make_auth_header(kaihle_admin)
        response = await client.get("/api/v1/question-bank", headers=headers)
        assert response.status_code == 200
        data = response.json()
        questions = data["questions"]
        # Verify descending order (most recent first)
        for i in range(len(questions) - 1):
            current = questions[i]["created_at"]
            next_q = questions[i + 1]["created_at"]
            assert current >= next_q


# ── PATCH /api/v1/question-bank/{id} ────────────────────────────────────────


class TestUpdateQuestion:
    """Tests for PATCH /api/v1/question-bank/{id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_requires_auth(self, client: AsyncClient, sample_questions):
        """Unauthenticated requests should be rejected."""
        q_id = str(sample_questions[0].id)
        response = await client.patch(
            f"/api/v1/question-bank/{q_id}",
            json={"question_text": "Updated text"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_update_requires_admin_role(self, client: AsyncClient, student_user, sample_questions):
        """Non-admin users should be forbidden."""
        headers = make_auth_header(student_user)
        q_id = str(sample_questions[0].id)
        response = await client.patch(
            f"/api/v1/question-bank/{q_id}",
            headers=headers,
            json={"question_text": "Updated text"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_update_question_text(self, client: AsyncClient, kaihle_admin, sample_questions):
        """Admin can update question_text."""
        headers = make_auth_header(kaihle_admin)
        q_id = str(sample_questions[0].id)
        new_text = "What is 2 + 3?"
        response = await client.patch(
            f"/api/v1/question-bank/{q_id}",
            headers=headers,
            json={"question_text": new_text},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["question_text"] == new_text

    @pytest.mark.asyncio
    async def test_update_multiple_fields(self, client: AsyncClient, kaihle_admin, sample_questions):
        """Admin can update multiple fields in one request."""
        headers = make_auth_header(kaihle_admin)
        q_id = str(sample_questions[0].id)
        response = await client.patch(
            f"/api/v1/question-bank/{q_id}",
            headers=headers,
            json={
                "question_text": "Updated question",
                "correct_answer": "5",
                "difficulty_level": 0.8,
                "is_active": False,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["question_text"] == "Updated question"
        assert data["correct_answer"] == "5"
        assert data["difficulty_level"] == 0.8
        assert data["is_active"] is False

    @pytest.mark.asyncio
    async def test_update_omitted_fields_unchanged(self, client: AsyncClient, kaihle_admin, sample_questions):
        """Omitted fields should remain unchanged."""
        headers = make_auth_header(kaihle_admin)
        q_id = str(sample_questions[0].id)
        original = sample_questions[0]
        response = await client.patch(
            f"/api/v1/question-bank/{q_id}",
            headers=headers,
            json={"question_text": "Only this changes"},
        )
        assert response.status_code == 200
        data = response.json()
        # Unchanged fields should retain original values
        assert data["correct_answer"] == original.correct_answer
        assert data["question_type"] == original.question_type

    @pytest.mark.asyncio
    async def test_update_nonexistent_question(self, client: AsyncClient, kaihle_admin):
        """Updating non-existent question should return 404."""
        headers = make_auth_header(kaihle_admin)
        fake_id = uuid.uuid4()
        response = await client.patch(
            f"/api/v1/question-bank/{fake_id}",
            headers=headers,
            json={"question_text": "Test"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_invalid_subtopic(self, client: AsyncClient, kaihle_admin, sample_questions):
        """Updating with invalid subtopic_id should return 422."""
        headers = make_auth_header(kaihle_admin)
        q_id = str(sample_questions[0].id)
        fake_subtopic_id = uuid.uuid4()
        response = await client.patch(
            f"/api/v1/question-bank/{q_id}",
            headers=headers,
            json={"subtopic_id": str(fake_subtopic_id)},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_difficulty_level_out_of_range(self, client: AsyncClient, kaihle_admin, sample_questions):
        """Difficulty level outside 0.0-1.0 should return 422."""
        headers = make_auth_header(kaihle_admin)
        q_id = str(sample_questions[0].id)
        response = await client.patch(
            f"/api/v1/question-bank/{q_id}",
            headers=headers,
            json={"difficulty_level": 1.5},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_returns_curriculum_context(self, client: AsyncClient, kaihle_admin, sample_questions):
        """Response should include curriculum context."""
        headers = make_auth_header(kaihle_admin)
        q_id = str(sample_questions[0].id)
        response = await client.patch(
            f"/api/v1/question-bank/{q_id}",
            headers=headers,
            json={"question_text": "Updated"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "curriculum_name" in data
        assert "subtopic_name" in data
