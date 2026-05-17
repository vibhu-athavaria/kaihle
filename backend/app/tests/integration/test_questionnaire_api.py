"""Integration tests for questionnaire API endpoints.

Tests cover:
- GET /api/v1/onboarding/questionnaire - Questionnaire retrieval
- POST /api/v1/onboarding/questionnaire/submit - Questionnaire submission
"""

import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token
from app.main import app
from app.models.school import School
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
async def student(db_session: AsyncSession, school: School) -> User:
    """Create a test student user."""
    student = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"student-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Test",
        last_name="Student",
        role=UserRole.STUDENT,
        is_active=True,
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
        is_active=True,
    )
    db_session.add(teacher)
    await db_session.commit()
    return teacher


@pytest_asyncio.fixture
async def kaihle_admin(db_session: AsyncSession, school: School) -> User:
    """Create a test Kaihle admin user."""
    admin = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"admin-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Kaihle",
        last_name="Admin",
        role=UserRole.KAIHLE_ADMIN,
        is_active=True,
    )
    db_session.add(admin)
    await db_session.commit()
    return admin


@pytest_asyncio.fixture
async def parent(db_session: AsyncSession, school: School) -> User:
    """Create a test parent user."""
    parent_user = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"parent-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Test",
        last_name="Parent",
        role=UserRole.PARENT,
        is_active=True,
    )
    db_session.add(parent_user)
    await db_session.commit()
    return parent_user


@pytest_asyncio.fixture
def auth_headers_student(student: User) -> dict[str, str]:
    # type: ignore[return-value]
    # type: ignore[return-value]
    """Generate Authorization header with valid JWT for a student."""
    token = create_access_token(
        user_id=student.id,
        school_id=student.school_id,
        role=student.role,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
def auth_headers_teacher(teacher: User) -> dict[str, str]:
    # type: ignore[return-value]
    token = create_access_token(
        user_id=teacher.id,
        school_id=teacher.school_id,
        role=teacher.role,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
def auth_headers_kaihle_admin(kaihle_admin: User) -> dict[str, str]:
    # type: ignore[return-value]
    token = create_access_token(
        user_id=kaihle_admin.id,
        school_id=kaihle_admin.school_id,
        role=kaihle_admin.role,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
def auth_headers_parent(parent: User) -> dict[str, str]:
    # type: ignore[return-value]
    token = create_access_token(
        user_id=parent.id,
        school_id=parent.school_id,
        role=parent.role,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


class TestGetQuestionnaire:
    """Tests for GET /api/v1/onboarding/questionnaire."""

    @pytest.mark.asyncio
    async def test_quest_01_authenticated_student_retrieves_questionnaire(
        self,
        client: AsyncClient,
        auth_headers_student: dict[str, str],
    ) -> None:
        """QUEST-01: Authenticated student retrieves questionnaire → 200 with full questionnaire."""
        response = await client.get(
            "/api/v1/onboarding/questionnaire",
            headers=auth_headers_student,
        )

        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert "questions" in data
        assert data["version"] == "v2"
        assert len(data["questions"]) == 7

    @pytest.mark.asyncio
    async def test_quest_03_authenticated_kaihle_admin_retrieves_questionnaire(
        self,
        client: AsyncClient,
        auth_headers_kaihle_admin: dict[str, str],
    ) -> None:
        """QUEST-03: Authenticated KaihleAdmin retrieves questionnaire → 200."""
        response = await client.get(
            "/api/v1/onboarding/questionnaire",
            headers=auth_headers_kaihle_admin,
        )

        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert "questions" in data

    @pytest.mark.asyncio
    async def test_quest_04_verify_questionnaire_structure(
        self,
        client: AsyncClient,
        auth_headers_student: dict[str, str],
    ) -> None:
        """QUEST-04: Verify questionnaire structure (version, questions, options, mappings) → all fields present."""
        response = await client.get(
            "/api/v1/onboarding/questionnaire",
            headers=auth_headers_student,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["version"] == "v2"
        assert len(data["questions"]) == 7

        for question in data["questions"]:
            assert "id" in question
            assert "text" in question
            assert "type" in question
            assert "options" in question
            assert len(question["options"]) > 0

            for option in question["options"]:
                assert "key" in option
                assert "text" in option

                # q6 (interest) and q7 (challenge_response) options don't have maps_to
                if question["id"] not in ("q6", "q7"):
                    assert "maps_to" in option

    @pytest.mark.asyncio
    async def test_quest_05_unauthenticated_request(
        self,
        client: AsyncClient,
    ) -> None:
        """QUEST-05: Unauthenticated request → 401."""
        response = await client.get("/api/v1/onboarding/questionnaire")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_quest_06_invalid_jwt_token(
        self,
        client: AsyncClient,
    ) -> None:
        """QUEST-06: Invalid JWT token → 401."""
        response = await client.get(
            "/api/v1/onboarding/questionnaire",
            headers={"Authorization": "Bearer invalid-token"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_quest_07_malformed_authorization_header(
        self,
        client: AsyncClient,
    ) -> None:
        """QUEST-07: Malformed Authorization header → 401."""
        response = await client.get(
            "/api/v1/onboarding/questionnaire",
            headers={"Authorization": "NotBearer token"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_quest_08_parent_role_not_allowed(
        self,
        client: AsyncClient,
        auth_headers_parent: dict[str, str],
    ) -> None:
        """QUEST-08: PARENT role (not allowed) → 403."""
        response = await client.get(
            "/api/v1/onboarding/questionnaire",
            headers=auth_headers_parent,
        )

        assert response.status_code == 403


class TestSubmitQuestionnaire:
    """Tests for POST /api/v1/onboarding/questionnaire/submit."""

    @pytest.mark.asyncio
    async def test_sub_01_student_submits_valid_responses(
        self,
        client: AsyncClient,
        auth_headers_student: dict[str, str],
    ) -> None:
        """SUB-01: Student submits valid responses (7 questions) → 200 with scores."""
        submit_data = {
            "responses": [
                {"question_id": "q1", "answer_key": "see_diagram"},
                {"question_id": "q2", "answer_key": "draw_it"},
                {"question_id": "q3", "answer_key": "find_example"},
                {"question_id": "q4", "answer_key": "solo_quiet"},
                {"question_id": "q5", "answer_key": "big_picture"},
                {"question_id": "q6", "answer_key": "sports_movement"},
                {"question_id": "q7", "answer_key": "persists"},
            ]
        }

        response = await client.post(
            "/api/v1/onboarding/questionnaire/submit",
            headers=auth_headers_student,
            json=submit_data,
        )

        assert response.status_code == 200
        data = response.json()
        assert "student_id" in data
        assert "modality_scores" in data
        assert "work_style" in data
        assert "interests" in data
        assert data["interests"] == ["sports_movement"]

    @pytest.mark.asyncio
    async def test_sub_02_student_submits_with_all_modality_types(
        self,
        client: AsyncClient,
        auth_headers_student: dict[str, str],
    ) -> None:
        """SUB-02: Student submits kinesthetic answers → 200, dominant=kinesthetic."""
        submit_data = {
            "responses": [
                {"question_id": "q1", "answer_key": "try_problems"},
                {"question_id": "q2", "answer_key": "show_example"},
                {"question_id": "q3", "answer_key": "try_different"},
                {"question_id": "q4", "answer_key": "with_friends"},
                {"question_id": "q5", "answer_key": "dive_in"},
                {"question_id": "q6", "answer_key": "tech_gaming"},
                {"question_id": "q7", "answer_key": "paces"},
            ]
        }

        response = await client.post(
            "/api/v1/onboarding/questionnaire/submit",
            headers=auth_headers_student,
            json=submit_data,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["modality_scores"]["kinesthetic"] == 1.0
        assert data["work_style"]["prefers_solo"] is False
        assert data["work_style"]["concept_first"] is False
        assert data["work_style"]["task_based"] is True

    @pytest.mark.asyncio
    async def test_sub_03_student_submits_with_all_interests_selected(
        self,
        client: AsyncClient,
        auth_headers_student: dict[str, str],
    ) -> None:
        """SUB-03: Student submits with interest selected → 200, single interest returned."""
        submit_data = {
            "responses": [
                {"question_id": "q1", "answer_key": "see_diagram"},
                {"question_id": "q2", "answer_key": "draw_it"},
                {"question_id": "q3", "answer_key": "find_example"},
                {"question_id": "q4", "answer_key": "solo_quiet"},
                {"question_id": "q5", "answer_key": "big_picture"},
                {"question_id": "q6", "answer_key": "nature_animals"},
                {"question_id": "q7", "answer_key": "persists"},
            ]
        }

        response = await client.post(
            "/api/v1/onboarding/questionnaire/submit",
            headers=auth_headers_student,
            json=submit_data,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["interests"]) == 1
        assert data["interests"] == ["nature_animals"]

    @pytest.mark.asyncio
    async def test_sub_04_student_resubmits_idempotent(
        self,
        client: AsyncClient,
        auth_headers_student: dict[str, str],
    ) -> None:
        """SUB-04: Student re-submits (idempotent) → 200, same profile ID."""
        submit_data = {
            "responses": [
                {"question_id": "q1", "answer_key": "see_diagram"},
                {"question_id": "q2", "answer_key": "draw_it"},
                {"question_id": "q3", "answer_key": "find_example"},
                {"question_id": "q4", "answer_key": "solo_quiet"},
                {"question_id": "q5", "answer_key": "big_picture"},
                {"question_id": "q6", "answer_key": "arts_culture"},
                {"question_id": "q7", "answer_key": "persists"},
            ]
        }

        response1 = await client.post(
            "/api/v1/onboarding/questionnaire/submit",
            headers=auth_headers_student,
            json=submit_data,
        )

        assert response1.status_code == 200
        data1 = response1.json()
        profile_id1 = data1["id"]

        response2 = await client.post(
            "/api/v1/onboarding/questionnaire/submit",
            headers=auth_headers_student,
            json=submit_data,
        )

        assert response2.status_code == 200
        data2 = response2.json()
        profile_id2 = data2["id"]

        assert profile_id1 == profile_id2

    @pytest.mark.asyncio
    async def test_sub_05_student_submits_with_partial_interests(
        self,
        client: AsyncClient,
        auth_headers_student: dict[str, str],
    ) -> None:
        """SUB-05: Student submits with one interest selected → 200."""
        submit_data = {
            "responses": [
                {"question_id": "q1", "answer_key": "see_diagram"},
                {"question_id": "q2", "answer_key": "draw_it"},
                {"question_id": "q3", "answer_key": "find_example"},
                {"question_id": "q4", "answer_key": "solo_quiet"},
                {"question_id": "q5", "answer_key": "big_picture"},
                {"question_id": "q6", "answer_key": "sports_movement"},
                {"question_id": "q7", "answer_key": "paces"},
            ]
        }

        response = await client.post(
            "/api/v1/onboarding/questionnaire/submit",
            headers=auth_headers_student,
            json=submit_data,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["interests"] == ["sports_movement"]

    @pytest.mark.asyncio
    async def test_sub_06_unauthenticated(
        self,
        client: AsyncClient,
    ) -> None:
        """SUB-06: Unauthenticated → 401."""
        submit_data = {
            "responses": [
                {"question_id": "q1", "answer_key": "see_diagram"},
                {"question_id": "q2", "answer_key": "draw_it"},
                {"question_id": "q3", "answer_key": "find_example"},
                {"question_id": "q4", "answer_key": "solo_quiet"},
                {"question_id": "q5", "answer_key": "big_picture"},
                {"question_id": "q6", "answer_key": "sports_movement"},
                {"question_id": "q7", "answer_key": "persists"},
            ]
        }

        response = await client.post(
            "/api/v1/onboarding/questionnaire/submit",
            json=submit_data,
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_sub_07_teacher_submits(
        self,
        client: AsyncClient,
        auth_headers_teacher: dict[str, str],
    ) -> None:
        """SUB-07: Teacher submits → 403."""
        submit_data = {
            "responses": [
                {"question_id": "q1", "answer_key": "see_diagram"},
                {"question_id": "q2", "answer_key": "draw_it"},
                {"question_id": "q3", "answer_key": "find_example"},
                {"question_id": "q4", "answer_key": "solo_quiet"},
                {"question_id": "q5", "answer_key": "big_picture"},
                {"question_id": "q6", "answer_key": "sports_movement"},
                {"question_id": "q7", "answer_key": "persists"},
            ]
        }

        response = await client.post(
            "/api/v1/onboarding/questionnaire/submit",
            headers=auth_headers_teacher,
            json=submit_data,
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_sub_08_empty_responses(
        self,
        client: AsyncClient,
        auth_headers_student: dict[str, str],
    ) -> None:
        """SUB-08: Empty responses → 422."""
        submit_data: dict = {"responses": []}

        response = await client.post(
            "/api/v1/onboarding/questionnaire/submit",
            headers=auth_headers_student,
            json=submit_data,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_sub_09_invalid_question_id(
        self,
        client: AsyncClient,
        auth_headers_student: dict[str, str],
    ) -> None:
        """SUB-09: Invalid question_id → 422/400."""
        submit_data = {
            "responses": [
                {"question_id": "invalid_question", "answer_key": "watch_video"},
                {"question_id": "q2", "answer_key": "see_diagrams"},
                {"question_id": "q3", "answer_key": "solo"},
                {"question_id": "q4", "answer_key": "short"},
                {"question_id": "q5", "answer_key": "concept_first"},
                {"question_id": "q6_to_q10", "answer_keys": ["sports"]},
            ]
        }

        response = await client.post(
            "/api/v1/onboarding/questionnaire/submit",
            headers=auth_headers_student,
            json=submit_data,
        )

        assert response.status_code in (400, 422)

    @pytest.mark.asyncio
    async def test_sub_10_invalid_answer_key(
        self,
        client: AsyncClient,
        auth_headers_student: dict[str, str],
    ) -> None:
        """SUB-10: Invalid answer_key → 422/400."""
        submit_data = {
            "responses": [
                {"question_id": "q1", "answer_key": "invalid_option"},
                {"question_id": "q2", "answer_key": "see_diagrams"},
                {"question_id": "q3", "answer_key": "solo"},
                {"question_id": "q4", "answer_key": "short"},
                {"question_id": "q5", "answer_key": "concept_first"},
                {"question_id": "q6_to_q10", "answer_keys": ["sports"]},
            ]
        }

        response = await client.post(
            "/api/v1/onboarding/questionnaire/submit",
            headers=auth_headers_student,
            json=submit_data,
        )

        assert response.status_code in (400, 422)

    @pytest.mark.asyncio
    async def test_sub_11_missing_answer_key_for_single_select(
        self,
        client: AsyncClient,
        auth_headers_student: dict[str, str],
    ) -> None:
        """SUB-11: Missing answer_key for single-select → 422."""
        submit_data = {
            "responses": [
                {"question_id": "q1"},
                {"question_id": "q2", "answer_key": "see_diagrams"},
                {"question_id": "q3", "answer_key": "solo"},
                {"question_id": "q4", "answer_key": "short"},
                {"question_id": "q5", "answer_key": "concept_first"},
                {"question_id": "q6_to_q10", "answer_keys": ["sports"]},
            ]
        }

        response = await client.post(
            "/api/v1/onboarding/questionnaire/submit",
            headers=auth_headers_student,
            json=submit_data,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_sub_12_both_answer_key_and_answer_keys(
        self,
        client: AsyncClient,
        auth_headers_student: dict[str, str],
    ) -> None:
        """SUB-12: Both answer_key AND answer_keys → 422."""
        submit_data = {
            "responses": [
                {
                    "question_id": "q1",
                    "answer_key": "watch_video",
                    "answer_keys": ["sports"],
                },
                {"question_id": "q2", "answer_key": "see_diagrams"},
                {"question_id": "q3", "answer_key": "solo"},
                {"question_id": "q4", "answer_key": "short"},
                {"question_id": "q5", "answer_key": "concept_first"},
                {"question_id": "q6_to_q10", "answer_keys": ["sports"]},
            ]
        }

        response = await client.post(
            "/api/v1/onboarding/questionnaire/submit",
            headers=auth_headers_student,
            json=submit_data,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_sub_13_extra_unknown_fields(
        self,
        client: AsyncClient,
        auth_headers_student: dict[str, str],
    ) -> None:
        """SUB-13: Extra/unknown fields → 422."""
        submit_data = {
            "responses": [
                {"question_id": "q1", "answer_key": "watch_video", "extra_field": "bad"},
                {"question_id": "q2", "answer_key": "see_diagrams"},
                {"question_id": "q3", "answer_key": "solo"},
                {"question_id": "q4", "answer_key": "short"},
                {"question_id": "q5", "answer_key": "concept_first"},
                {"question_id": "q6_to_q10", "answer_keys": ["sports"]},
            ]
        }

        response = await client.post(
            "/api/v1/onboarding/questionnaire/submit",
            headers=auth_headers_student,
            json=submit_data,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_sub_14_answer_keys_for_single_select(
        self,
        client: AsyncClient,
        auth_headers_student: dict[str, str],
    ) -> None:
        """SUB-14: answer_keys for single-select → 422."""
        submit_data = {
            "responses": [
                {"question_id": "q1", "answer_keys": ["watch_video"]},
                {"question_id": "q2", "answer_key": "see_diagrams"},
                {"question_id": "q3", "answer_key": "solo"},
                {"question_id": "q4", "answer_key": "short"},
                {"question_id": "q5", "answer_key": "concept_first"},
                {"question_id": "q6_to_q10", "answer_keys": ["sports"]},
            ]
        }

        response = await client.post(
            "/api/v1/onboarding/questionnaire/submit",
            headers=auth_headers_student,
            json=submit_data,
        )

        assert response.status_code == 422
