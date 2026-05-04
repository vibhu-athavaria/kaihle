"""Integration tests for school curriculum subscription routes.

Tests cover:
- GET    /api/v1/schools/{school_id}/curricula        — list subscriptions
- POST   /api/v1/schools/{school_id}/curricula        — add subscription
- DELETE /api/v1/schools/{school_id}/curricula/{id}   — remove subscription
- PATCH  /api/v1/schools/{school_id}/curricula/{id}/primary — set primary

Run with: pytest app/tests/integration/test_school_curriculum_routes.py -v
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.curriculum import Curriculum
from app.models.school import Class, School, SchoolCurriculum
from app.models.user import User, UserRole


def make_auth_header(user: User) -> dict[str, str]:
    token = create_access_token(
        user_id=user.id,
        school_id=user.school_id,
        role=user.role,
        expires_in=3600,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def kaihle_admin(db_session: AsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        school_id=None,
        email=f"kadmin-{uuid.uuid4().hex[:8]}@kaihle.ai",
        first_name="Kaihle",
        last_name="Admin",
        role=UserRole.KAIHLE_ADMIN,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.fixture
async def school(db_session: AsyncSession) -> School:
    s = School(id=uuid.uuid4(), name="Test School", slug=f"ts-{uuid.uuid4().hex[:8]}", status="active")
    db_session.add(s)
    await db_session.commit()
    return s


@pytest.fixture
async def school_admin(db_session: AsyncSession, school: School) -> User:
    user = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"sadmin-{uuid.uuid4().hex[:8]}@test.com",
        first_name="School",
        last_name="Admin",
        role=UserRole.SCHOOL_ADMIN,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.fixture
async def teacher(db_session: AsyncSession, school: School) -> User:
    user = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"teacher-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Test",
        last_name="Teacher",
        role=UserRole.TEACHER,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.fixture
async def curriculum(db_session: AsyncSession) -> Curriculum:
    c = Curriculum(
        id=uuid.uuid4(),
        name=f"Cambridge LS {uuid.uuid4().hex[:6]}",
        code=f"CAM-LS-{uuid.uuid4().hex[:4]}",
        description="Cambridge Lower Secondary",
        is_active=True,
    )
    db_session.add(c)
    await db_session.commit()
    return c


@pytest.fixture
async def second_curriculum(db_session: AsyncSession) -> Curriculum:
    c = Curriculum(
        id=uuid.uuid4(),
        name=f"Cambridge IGCSE {uuid.uuid4().hex[:6]}",
        code=f"CAM-IGC-{uuid.uuid4().hex[:4]}",
        description="Cambridge IGCSE",
        is_active=True,
    )
    db_session.add(c)
    await db_session.commit()
    return c


@pytest.fixture
async def school_curriculum(db_session: AsyncSession, school: School, curriculum: Curriculum) -> SchoolCurriculum:
    sc = SchoolCurriculum(school_id=school.id, curriculum_id=curriculum.id, is_primary=True)
    db_session.add(sc)
    await db_session.commit()
    return sc


# =============================================================================
# GET /api/v1/schools/{school_id}/curricula
# =============================================================================


class TestListSchoolCurricula:
    """Tests for GET /api/v1/schools/{school_id}/curricula"""

    @pytest.mark.asyncio
    async def test_list_school_curricula_when_kaihle_admin_then_returns_200_with_list(
        self,
        client: AsyncClient,
        kaihle_admin: User,
        school: School,
        school_curriculum: SchoolCurriculum,
        curriculum: Curriculum,
    ) -> None:
        """KaihleAdmin can list curricula for any school."""
        headers = make_auth_header(kaihle_admin)

        response = await client.get(f"/api/v1/schools/{school.id}/curricula", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["curriculum_id"] == str(curriculum.id)
        assert data[0]["curriculum_name"] == curriculum.name
        assert data[0]["curriculum_code"] == curriculum.code
        assert data[0]["is_primary"] is True
        assert "adopted_at" in data[0]

    @pytest.mark.asyncio
    async def test_list_school_curricula_when_school_admin_own_school_then_200(
        self, client: AsyncClient, school_admin: User, school: School, school_curriculum: SchoolCurriculum
    ) -> None:
        """SchoolAdmin can view their own school's curricula."""
        headers = make_auth_header(school_admin)

        response = await client.get(f"/api/v1/schools/{school.id}/curricula", headers=headers)

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_list_school_curricula_when_school_admin_other_school_then_403(
        self, client: AsyncClient, db_session: AsyncSession, school_admin: User
    ) -> None:
        """SchoolAdmin cannot view another school's curricula."""
        other_school = School(id=uuid.uuid4(), name="Other", slug=f"other-{uuid.uuid4().hex[:8]}", status="active")
        db_session.add(other_school)
        await db_session.commit()
        headers = make_auth_header(school_admin)

        response = await client.get(f"/api/v1/schools/{other_school.id}/curricula", headers=headers)

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_list_school_curricula_when_teacher_then_403(
        self, client: AsyncClient, teacher: User, school: School
    ) -> None:
        """Teacher cannot list curricula."""
        headers = make_auth_header(teacher)

        response = await client.get(f"/api/v1/schools/{school.id}/curricula", headers=headers)

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_list_school_curricula_when_no_subscriptions_then_returns_empty_list(
        self, client: AsyncClient, kaihle_admin: User, school: School
    ) -> None:
        """Returns empty list when school has no curriculum subscriptions."""
        headers = make_auth_header(kaihle_admin)

        response = await client.get(f"/api/v1/schools/{school.id}/curricula", headers=headers)

        assert response.status_code == 200
        assert response.json() == []


# =============================================================================
# POST /api/v1/schools/{school_id}/curricula
# =============================================================================


class TestAddSchoolCurriculum:
    """Tests for POST /api/v1/schools/{school_id}/curricula"""

    @pytest.mark.asyncio
    async def test_add_school_curriculum_when_kaihle_admin_then_201(
        self, client: AsyncClient, kaihle_admin: User, school: School, curriculum: Curriculum
    ) -> None:
        """KaihleAdmin can subscribe a school to a curriculum."""
        headers = make_auth_header(kaihle_admin)
        payload = {"curriculum_id": str(curriculum.id), "is_primary": True}

        response = await client.post(f"/api/v1/schools/{school.id}/curricula", json=payload, headers=headers)

        assert response.status_code == 201
        data = response.json()
        assert data["curriculum_id"] == str(curriculum.id)
        assert data["is_primary"] is True
        assert data["curriculum_name"] == curriculum.name

    @pytest.mark.asyncio
    async def test_add_school_curriculum_when_already_subscribed_then_409(
        self,
        client: AsyncClient,
        kaihle_admin: User,
        school: School,
        curriculum: Curriculum,
        school_curriculum: SchoolCurriculum,
    ) -> None:
        """Returns 409 when school is already subscribed to the curriculum."""
        headers = make_auth_header(kaihle_admin)
        payload = {"curriculum_id": str(curriculum.id), "is_primary": False}

        response = await client.post(f"/api/v1/schools/{school.id}/curricula", json=payload, headers=headers)

        assert response.status_code == 409
        assert "already subscribed" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_add_school_curriculum_when_curriculum_not_found_then_404(
        self, client: AsyncClient, kaihle_admin: User, school: School
    ) -> None:
        """Returns 404 when curriculum does not exist."""
        headers = make_auth_header(kaihle_admin)
        payload = {"curriculum_id": str(uuid.uuid4()), "is_primary": False}

        response = await client.post(f"/api/v1/schools/{school.id}/curricula", json=payload, headers=headers)

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_add_school_curriculum_when_school_admin_then_403(
        self, client: AsyncClient, school_admin: User, school: School, curriculum: Curriculum
    ) -> None:
        """SchoolAdmin cannot add curriculum subscriptions."""
        headers = make_auth_header(school_admin)
        payload = {"curriculum_id": str(curriculum.id), "is_primary": False}

        response = await client.post(f"/api/v1/schools/{school.id}/curricula", json=payload, headers=headers)

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_add_school_curriculum_when_is_primary_then_clears_existing_primary(
        self,
        client: AsyncClient,
        kaihle_admin: User,
        school: School,
        curriculum: Curriculum,
        second_curriculum: Curriculum,
        school_curriculum: SchoolCurriculum,
        db_session: AsyncSession,
    ) -> None:
        """Setting new curriculum as primary clears the previous primary."""
        headers = make_auth_header(kaihle_admin)
        payload = {"curriculum_id": str(second_curriculum.id), "is_primary": True}

        response = await client.post(f"/api/v1/schools/{school.id}/curricula", json=payload, headers=headers)

        assert response.status_code == 201
        # Verify the old primary was cleared
        await db_session.refresh(school_curriculum)
        assert school_curriculum.is_primary is False


# =============================================================================
# DELETE /api/v1/schools/{school_id}/curricula/{curriculum_id}
# =============================================================================


class TestRemoveSchoolCurriculum:
    """Tests for DELETE /api/v1/schools/{school_id}/curricula/{curriculum_id}"""

    @pytest.mark.asyncio
    async def test_remove_school_curriculum_when_no_active_classes_then_204(
        self,
        client: AsyncClient,
        kaihle_admin: User,
        school: School,
        curriculum: Curriculum,
        school_curriculum: SchoolCurriculum,
    ) -> None:
        """KaihleAdmin can remove a curriculum subscription with no active classes."""
        headers = make_auth_header(kaihle_admin)

        response = await client.delete(f"/api/v1/schools/{school.id}/curricula/{curriculum.id}", headers=headers)

        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_remove_school_curriculum_when_has_active_classes_then_409(
        self,
        client: AsyncClient,
        kaihle_admin: User,
        school: School,
        curriculum: Curriculum,
        school_curriculum: SchoolCurriculum,
        db_session: AsyncSession,
        test_grade,
        test_subject,
        teacher: User,
    ) -> None:
        """Returns 409 when active classes use this curriculum."""
        # Create an active class using this curriculum
        cls = Class(
            id=uuid.uuid4(),
            school_id=school.id,
            grade_id=test_grade.id,
            subject_id=test_subject.id,
            curriculum_id=curriculum.id,
            teacher_id=teacher.id,
            name="Active Class",
            academic_year="2025-2026",
            is_active=True,
        )
        db_session.add(cls)
        await db_session.commit()

        headers = make_auth_header(kaihle_admin)

        response = await client.delete(f"/api/v1/schools/{school.id}/curricula/{curriculum.id}", headers=headers)

        assert response.status_code == 409
        assert "active classes" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_remove_school_curriculum_when_not_subscribed_then_404(
        self, client: AsyncClient, kaihle_admin: User, school: School, curriculum: Curriculum
    ) -> None:
        """Returns 404 when school is not subscribed to the curriculum."""
        headers = make_auth_header(kaihle_admin)

        response = await client.delete(f"/api/v1/schools/{school.id}/curricula/{curriculum.id}", headers=headers)

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_remove_school_curriculum_when_school_admin_then_403(
        self,
        client: AsyncClient,
        school_admin: User,
        school: School,
        curriculum: Curriculum,
        school_curriculum: SchoolCurriculum,
    ) -> None:
        """SchoolAdmin cannot remove curriculum subscriptions."""
        headers = make_auth_header(school_admin)

        response = await client.delete(f"/api/v1/schools/{school.id}/curricula/{curriculum.id}", headers=headers)

        assert response.status_code == 403


# =============================================================================
# PATCH /api/v1/schools/{school_id}/curricula/{curriculum_id}/primary
# =============================================================================


class TestSetPrimarySchoolCurriculum:
    """Tests for PATCH /api/v1/schools/{school_id}/curricula/{curriculum_id}/primary"""

    @pytest.mark.asyncio
    async def test_set_primary_curriculum_when_kaihle_admin_then_200(
        self,
        client: AsyncClient,
        kaihle_admin: User,
        school: School,
        curriculum: Curriculum,
        second_curriculum: Curriculum,
        db_session: AsyncSession,
    ) -> None:
        """KaihleAdmin can change the primary curriculum."""
        # Subscribe to both curricula
        sc1 = SchoolCurriculum(school_id=school.id, curriculum_id=curriculum.id, is_primary=True)
        sc2 = SchoolCurriculum(school_id=school.id, curriculum_id=second_curriculum.id, is_primary=False)
        db_session.add(sc1)
        db_session.add(sc2)
        await db_session.commit()

        headers = make_auth_header(kaihle_admin)

        response = await client.patch(
            f"/api/v1/schools/{school.id}/curricula/{second_curriculum.id}/primary", headers=headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["curriculum_id"] == str(second_curriculum.id)
        assert data["is_primary"] is True
        # Old primary must be cleared
        await db_session.refresh(sc1)
        assert sc1.is_primary is False

    @pytest.mark.asyncio
    async def test_set_primary_curriculum_when_not_subscribed_then_404(
        self, client: AsyncClient, kaihle_admin: User, school: School, curriculum: Curriculum
    ) -> None:
        """Returns 404 when school is not subscribed to the target curriculum."""
        headers = make_auth_header(kaihle_admin)

        response = await client.patch(f"/api/v1/schools/{school.id}/curricula/{curriculum.id}/primary", headers=headers)

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_set_primary_curriculum_when_school_admin_then_403(
        self,
        client: AsyncClient,
        school_admin: User,
        school: School,
        curriculum: Curriculum,
        school_curriculum: SchoolCurriculum,
    ) -> None:
        """SchoolAdmin cannot change the primary curriculum."""
        headers = make_auth_header(school_admin)

        response = await client.patch(f"/api/v1/schools/{school.id}/curricula/{curriculum.id}/primary", headers=headers)

        assert response.status_code == 403
