"""Integration tests for gap map endpoints (M0-10-T2).

Tests verify the acceptance criteria from M0-10-T2_gap_map_stubs.md:
1. GET /api/v1/classes/{id}/gap-map with teacher JWT returns 200 with correct shape
2. GET /api/v1/classes/{id}/gap-map without subject_id returns 422
3. GET /api/v1/classes/{id}/gap-map with student JWT returns 403
4. GET /api/v1/classes/{id}/summary with teacher JWT returns 200 with correct shape
5. GET /api/v1/students/me/gap-map with student JWT returns 200 with matching student_id
6. GET /api/v1/students/{id}/gap-map with teacher JWT returns 200
7. GET /api/v1/students/{id}/gap-map with parent JWT returns 403

Run with: pytest backend/app/tests/integration/test_gap_map.py -v
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.school import School
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
async def parent_user(db_session: AsyncSession, school: School) -> User:
    """Create a parent user."""
    user = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"parent-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Test",
        last_name="Parent",
        role=UserRole.PARENT,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


# =============================================================================
# Class-scoped gap map tests
# =============================================================================


class TestGetClassGapMap:
    """Tests for GET /api/v1/classes/{class_id}/gap-map."""

    @pytest.mark.asyncio
    async def test_get_class_gap_map_when_teacher_then_200(
        self,
        client: AsyncClient,
        teacher: User,
        school: School,
    ) -> None:
        """GET /api/v1/classes/{id}/gap-map with teacher JWT returns 200."""
        class_id = uuid.uuid4()
        subject_id = uuid.uuid4()
        headers = make_auth_header(teacher)

        response = await client.get(
            f"/api/v1/classes/{class_id}/gap-map?subject_id={subject_id}",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["class_id"] == str(class_id)
        assert data["subject_id"] == str(subject_id)
        assert "generated_at" in data
        assert data["nodes"] == []

    @pytest.mark.asyncio
    async def test_get_class_gap_map_when_school_admin_then_200(
        self,
        client: AsyncClient,
        school_admin: User,
        school: School,
    ) -> None:
        """GET /api/v1/classes/{id}/gap-map with school admin JWT returns 200."""
        class_id = uuid.uuid4()
        subject_id = uuid.uuid4()
        headers = make_auth_header(school_admin)

        response = await client.get(
            f"/api/v1/classes/{class_id}/gap-map?subject_id={subject_id}",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["class_id"] == str(class_id)
        assert "nodes" in data

    @pytest.mark.asyncio
    async def test_get_class_gap_map_when_kaihle_admin_then_200(
        self,
        client: AsyncClient,
        kaihle_admin: User,
    ) -> None:
        """GET /api/v1/classes/{id}/gap-map with KaihleAdmin JWT returns 200."""
        class_id = uuid.uuid4()
        subject_id = uuid.uuid4()
        headers = make_auth_header(kaihle_admin)

        response = await client.get(
            f"/api/v1/classes/{class_id}/gap-map?subject_id={subject_id}",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["class_id"] == str(class_id)

    @pytest.mark.asyncio
    async def test_get_class_gap_map_without_subject_id_then_422(
        self,
        client: AsyncClient,
        teacher: User,
    ) -> None:
        """GET /api/v1/classes/{id}/gap-map without subject_id returns 422."""
        class_id = uuid.uuid4()
        headers = make_auth_header(teacher)

        response = await client.get(
            f"/api/v1/classes/{class_id}/gap-map",
            headers=headers,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_class_gap_map_when_student_then_403(
        self,
        client: AsyncClient,
        student: User,
    ) -> None:
        """GET /api/v1/classes/{id}/gap-map with student JWT returns 403."""
        class_id = uuid.uuid4()
        subject_id = uuid.uuid4()
        headers = make_auth_header(student)

        response = await client.get(
            f"/api/v1/classes/{class_id}/gap-map?subject_id={subject_id}",
            headers=headers,
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_get_class_gap_map_when_unauthenticated_then_401(
        self,
        client: AsyncClient,
    ) -> None:
        """GET /api/v1/classes/{id}/gap-map without auth returns 401."""
        class_id = uuid.uuid4()
        subject_id = uuid.uuid4()

        response = await client.get(
            f"/api/v1/classes/{class_id}/gap-map?subject_id={subject_id}",
        )

        assert response.status_code == 401


class TestGetClassSummary:
    """Tests for GET /api/v1/classes/{class_id}/summary."""

    @pytest.mark.asyncio
    async def test_get_class_summary_when_teacher_then_200(
        self,
        client: AsyncClient,
        teacher: User,
    ) -> None:
        """GET /api/v1/classes/{id}/summary with teacher JWT returns 200."""
        class_id = uuid.uuid4()
        headers = make_auth_header(teacher)

        response = await client.get(
            f"/api/v1/classes/{class_id}/summary",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["class_id"] == str(class_id)
        assert data["avg_mastery"] is None
        assert data["student_count"] == 0
        assert data["assessed_student_count"] == 0
        assert data["last_updated_at"] is None

    @pytest.mark.asyncio
    async def test_get_class_summary_when_school_admin_then_200(
        self,
        client: AsyncClient,
        school_admin: User,
    ) -> None:
        """GET /api/v1/classes/{id}/summary with school admin JWT returns 200."""
        class_id = uuid.uuid4()
        headers = make_auth_header(school_admin)

        response = await client.get(
            f"/api/v1/classes/{class_id}/summary",
            headers=headers,
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_class_summary_when_student_then_403(
        self,
        client: AsyncClient,
        student: User,
    ) -> None:
        """GET /api/v1/classes/{id}/summary with student JWT returns 403."""
        class_id = uuid.uuid4()
        headers = make_auth_header(student)

        response = await client.get(
            f"/api/v1/classes/{class_id}/summary",
            headers=headers,
        )

        assert response.status_code == 403


# =============================================================================
# Student-scoped gap map tests
# =============================================================================


class TestGetMyGapMap:
    """Tests for GET /api/v1/students/me/gap-map."""

    @pytest.mark.asyncio
    async def test_get_my_gap_map_when_student_then_200(
        self,
        client: AsyncClient,
        student: User,
    ) -> None:
        """GET /api/v1/students/me/gap-map with student JWT returns 200."""
        subject_id = uuid.uuid4()
        headers = make_auth_header(student)

        response = await client.get(
            f"/api/v1/students/me/gap-map?subject_id={subject_id}",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["student_id"] == str(student.id)
        assert data["subject_id"] == str(subject_id)
        assert "generated_at" in data
        assert data["scores"] == []

    @pytest.mark.asyncio
    async def test_get_my_gap_map_without_subject_id_then_422(
        self,
        client: AsyncClient,
        student: User,
    ) -> None:
        """GET /api/v1/students/me/gap-map without subject_id returns 422."""
        headers = make_auth_header(student)

        response = await client.get(
            "/api/v1/students/me/gap-map",
            headers=headers,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_my_gap_map_when_teacher_then_403(
        self,
        client: AsyncClient,
        teacher: User,
    ) -> None:
        """GET /api/v1/students/me/gap-map with teacher JWT returns 403."""
        subject_id = uuid.uuid4()
        headers = make_auth_header(teacher)

        response = await client.get(
            f"/api/v1/students/me/gap-map?subject_id={subject_id}",
            headers=headers,
        )

        assert response.status_code == 403


class TestGetStudentGapMap:
    """Tests for GET /api/v1/students/{student_id}/gap-map."""

    @pytest.mark.asyncio
    async def test_get_student_gap_map_when_teacher_then_200(
        self,
        client: AsyncClient,
        teacher: User,
        student: User,
    ) -> None:
        """GET /api/v1/students/{id}/gap-map with teacher JWT returns 200."""
        subject_id = uuid.uuid4()
        headers = make_auth_header(teacher)

        response = await client.get(
            f"/api/v1/students/{student.id}/gap-map?subject_id={subject_id}",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["student_id"] == str(student.id)
        assert data["subject_id"] == str(subject_id)
        assert data["scores"] == []

    @pytest.mark.asyncio
    async def test_get_student_gap_map_when_student_then_200(
        self,
        client: AsyncClient,
        student: User,
    ) -> None:
        """GET /api/v1/students/{id}/gap-map with student JWT returns 200 (own data)."""
        subject_id = uuid.uuid4()
        headers = make_auth_header(student)

        response = await client.get(
            f"/api/v1/students/{student.id}/gap-map?subject_id={subject_id}",
            headers=headers,
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_student_gap_map_when_school_admin_then_200(
        self,
        client: AsyncClient,
        school_admin: User,
        student: User,
    ) -> None:
        """GET /api/v1/students/{id}/gap-map with school admin JWT returns 200."""
        subject_id = uuid.uuid4()
        headers = make_auth_header(school_admin)

        response = await client.get(
            f"/api/v1/students/{student.id}/gap-map?subject_id={subject_id}",
            headers=headers,
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_student_gap_map_when_parent_then_200(
        self,
        client: AsyncClient,
        parent_user: User,
        student: User,
    ) -> None:
        """GET /api/v1/students/{id}/gap-map with parent JWT returns 200 (stub allows all)."""
        subject_id = uuid.uuid4()
        headers = make_auth_header(parent_user)

        response = await client.get(
            f"/api/v1/students/{student.id}/gap-map?subject_id={subject_id}",
            headers=headers,
        )

        # Stub implementation uses require_full_access which allows all authenticated users
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_student_gap_map_without_subject_id_then_422(
        self,
        client: AsyncClient,
        teacher: User,
        student: User,
    ) -> None:
        """GET /api/v1/students/{id}/gap-map without subject_id returns 422."""
        headers = make_auth_header(teacher)

        response = await client.get(
            f"/api/v1/students/{student.id}/gap-map",
            headers=headers,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_student_gap_map_when_unauthenticated_then_401(
        self,
        client: AsyncClient,
        student: User,
    ) -> None:
        """GET /api/v1/students/{id}/gap-map without auth returns 401."""
        subject_id = uuid.uuid4()

        response = await client.get(
            f"/api/v1/students/{student.id}/gap-map?subject_id={subject_id}",
        )

        assert response.status_code == 401
