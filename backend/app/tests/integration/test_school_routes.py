"""Integration tests for school routes — KaihleAdmin bypass + school CRUD (M0-9-T6).

Tests verify:
1. KaihleAdmin can access any school's data via the schools router (Fix 1)
2. SchoolAdmin is properly restricted to their own school
3. Full CRUD operations on schools (KaihleAdmin only)
4. Class operations from any school (KaihleAdmin bypass)

Run with: pytest backend/app/tests/integration/test_school_routes.py -v
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.curriculum import Curriculum, Grade, Subject
from app.models.school import Class, School
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
async def kaihle_admin(db_session: AsyncSession) -> User:
    """Create a KaihleAdmin with school_id=None."""
    user = User(
        id=uuid.uuid4(),
        school_id=None,  # KaihleAdmin has no school
        email=f"kaihle-admin-{uuid.uuid4().hex[:8]}@kaihle.ai",
        first_name="Kaihle",
        last_name="Admin",
        role=UserRole.KAIHLE_ADMIN,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.fixture
async def school_admin_other(db_session: AsyncSession, other_school: School) -> User:
    """Create a SchoolAdmin for the other school."""
    user = User(
        id=uuid.uuid4(),
        school_id=other_school.id,
        email=f"other-admin-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Other",
        last_name="Admin",
        role=UserRole.SCHOOL_ADMIN,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


# =============================================================================
# School CRUD Tests (restored from original test file)
# =============================================================================


class TestCreateSchool:
    """Tests for POST /api/v1/schools"""

    @pytest.mark.asyncio
    async def test_create_school_when_kaihle_admin_then_201(self, client: AsyncClient, kaihle_admin: User) -> None:
        """Test that KaihleAdmin can create a school."""
        headers = make_auth_header(kaihle_admin)
        payload = {
            "name": "New School",
            "slug": f"new-school-{uuid.uuid4().hex[:8]}",
            "country": "Indonesia",
            "timezone": "Asia/Jakarta",
        }

        response = await client.post("/api/v1/schools", json=payload, headers=headers)

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["name"] == "New School"
        assert data["slug"] == payload["slug"]
        assert data["country"] == "Indonesia"
        assert data["is_active"] is True

    @pytest.mark.asyncio
    async def test_create_school_with_password_when_valid_then_admin_user_has_hashed_password(
        self, client: AsyncClient, kaihle_admin: User, db_session: AsyncSession
    ) -> None:
        """Test that creating a school with password creates admin user with hashed password."""
        headers = make_auth_header(kaihle_admin)
        plain_password = "securepass123"
        payload = {
            "name": "School With Password",
            "slug": f"school-with-pw-{uuid.uuid4().hex[:8]}",
            "country": "Indonesia",
            "timezone": "Asia/Jakarta",
            "admin_email": f"admin-{uuid.uuid4().hex[:8]}@test.com",
            "admin_first_name": "Admin",
            "admin_last_name": "User",
            "admin_password": plain_password,
        }

        response = await client.post("/api/v1/schools", json=payload, headers=headers)

        assert response.status_code == 201
        data = response.json()
        assert "id" in data

        # Verify user was created with hashed password
        from sqlalchemy import select

        from app.core.security import verify_password

        result = await db_session.execute(
            select(User).where(User.school_id == data["id"], User.role == UserRole.SCHOOL_ADMIN)
        )
        admin_user = result.scalar_one_or_none()
        assert admin_user is not None
        assert admin_user.hashed_password is not None
        assert verify_password(plain_password, admin_user.hashed_password)
        assert admin_user.hashed_password != plain_password  # Not plaintext

    @pytest.mark.asyncio
    async def test_create_school_without_password_when_valid_then_admin_user_has_null_password(
        self, client: AsyncClient, kaihle_admin: User, db_session: AsyncSession
    ) -> None:
        """Test that creating a school without password creates admin user with null password."""
        headers = make_auth_header(kaihle_admin)
        payload = {
            "name": "School No Password",
            "slug": f"school-no-pw-{uuid.uuid4().hex[:8]}",
            "country": "Indonesia",
            "timezone": "Asia/Jakarta",
            "admin_email": f"admin-{uuid.uuid4().hex[:8]}@test.com",
            "admin_first_name": "Admin",
            "admin_last_name": "User",
            # No admin_password
        }

        response = await client.post("/api/v1/schools", json=payload, headers=headers)

        assert response.status_code == 201
        data = response.json()

        # Verify user was created with null password (magic-link only)
        result = await db_session.execute(
            select(User).where(User.school_id == data["id"], User.role == UserRole.SCHOOL_ADMIN)
        )
        admin_user = result.scalar_one_or_none()
        assert admin_user is not None
        assert admin_user.hashed_password is None

    @pytest.mark.asyncio
    async def test_create_school_when_duplicate_admin_email_then_returns_409(
        self, client: AsyncClient, kaihle_admin: User, db_session: AsyncSession, test_school: School
    ) -> None:
        """Test that duplicate admin email returns 409."""
        # Create a user with the same email first
        duplicate_email = f"existing-{uuid.uuid4().hex[:8]}@test.com"
        existing_user = User(
            id=uuid.uuid4(),
            school_id=test_school.id,
            email=duplicate_email,
            first_name="Existing",
            last_name="User",
            role=UserRole.TEACHER,
            is_active=True,
        )
        db_session.add(existing_user)
        await db_session.commit()

        headers = make_auth_header(kaihle_admin)
        payload = {
            "name": "School Duplicate Email",
            "slug": f"school-dup-{uuid.uuid4().hex[:8]}",
            "admin_email": duplicate_email,
            "admin_first_name": "Admin",
            "admin_last_name": "User",
        }

        response = await client.post("/api/v1/schools", json=payload, headers=headers)

        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_school_when_teacher_then_403(self, client: AsyncClient, test_teacher: User) -> None:
        """Test that Teacher cannot create a school."""
        headers = make_auth_header(test_teacher)
        payload = {
            "name": "New School",
            "slug": f"new-school-{uuid.uuid4().hex[:8]}",
        }

        response = await client.post("/api/v1/schools", json=payload, headers=headers)

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_create_school_when_duplicate_slug_then_409(
        self, client: AsyncClient, kaihle_admin: User, test_school: School
    ) -> None:
        """Test that duplicate slug returns 409."""
        headers = make_auth_header(kaihle_admin)
        payload = {
            "name": "Another School",
            "slug": test_school.slug,
        }

        response = await client.post("/api/v1/schools", json=payload, headers=headers)

        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_school_when_unauthenticated_then_401(self, client: AsyncClient) -> None:
        """Test that unauthenticated request returns 401."""
        payload = {
            "name": "New School",
            "slug": f"new-school-{uuid.uuid4().hex[:8]}",
        }

        response = await client.post("/api/v1/schools", json=payload)

        assert response.status_code == 401


class TestListSchools:
    """Tests for GET /api/v1/schools"""

    @pytest.mark.asyncio
    async def test_list_schools_when_kaihle_admin_then_returns_paginated_list(
        self, client: AsyncClient, kaihle_admin: User, db_session: AsyncSession
    ) -> None:
        """Test that KaihleAdmin can list schools with pagination."""
        # Create some schools
        for i in range(5):
            school = School(
                id=uuid.uuid4(),
                name=f"School {i}",
                slug=f"school-{i}-{uuid.uuid4().hex[:8]}",
                status="active",
            )
            db_session.add(school)
        await db_session.commit()

        headers = make_auth_header(kaihle_admin)

        response = await client.get("/api/v1/schools?page=1&page_size=3", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert "schools" in data
        assert "total" in data
        assert data["page"] == 1
        assert data["page_size"] == 3
        assert len(data["schools"]) <= 3
        assert data["total"] >= 5

    @pytest.mark.asyncio
    async def test_list_schools_when_teacher_then_403(self, client: AsyncClient, test_teacher: User) -> None:
        """Test that Teacher cannot list schools."""
        headers = make_auth_header(test_teacher)

        response = await client.get("/api/v1/schools", headers=headers)

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_list_schools_when_school_admin_then_403(self, client: AsyncClient, school_admin_other: User) -> None:
        """Test that SchoolAdmin cannot list all schools."""
        headers = make_auth_header(school_admin_other)

        response = await client.get("/api/v1/schools", headers=headers)

        assert response.status_code == 403


class TestGetSchool:
    """Tests for GET /api/v1/schools/{school_id}"""

    @pytest.mark.asyncio
    async def test_get_school_when_kaihle_admin_then_200(
        self, client: AsyncClient, kaihle_admin: User, test_school: School
    ) -> None:
        """Test that KaihleAdmin can get any school."""
        headers = make_auth_header(kaihle_admin)

        response = await client.get(f"/api/v1/schools/{test_school.id}", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_school.id)
        assert data["name"] == test_school.name

    @pytest.mark.asyncio
    async def test_get_school_when_school_admin_own_school_then_200(
        self, client: AsyncClient, school_admin_other: User, other_school: School
    ) -> None:
        """Test that SchoolAdmin can get their own school."""
        headers = make_auth_header(school_admin_other)

        response = await client.get(f"/api/v1/schools/{other_school.id}", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(other_school.id)

    @pytest.mark.asyncio
    async def test_get_school_when_school_admin_other_school_then_403(
        self,
        client: AsyncClient,
        school_admin_other: User,
        test_school: School,
    ) -> None:
        """Test that SchoolAdmin cannot get other schools."""
        headers = make_auth_header(school_admin_other)

        response = await client.get(f"/api/v1/schools/{test_school.id}", headers=headers)

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_get_school_when_teacher_then_403(
        self, client: AsyncClient, test_teacher: User, test_school: School
    ) -> None:
        """Test that Teacher cannot get school details."""
        headers = make_auth_header(test_teacher)

        response = await client.get(f"/api/v1/schools/{test_school.id}", headers=headers)

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_get_school_when_not_exists_then_404(self, client: AsyncClient, kaihle_admin: User) -> None:
        """Test that getting non-existent school returns 404."""
        headers = make_auth_header(kaihle_admin)
        non_existent_id = uuid.uuid4()

        response = await client.get(f"/api/v1/schools/{non_existent_id}", headers=headers)

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_school_when_admin_exists_then_returns_admin_user_id_and_email(
        self, client: AsyncClient, kaihle_admin: User, db_session: AsyncSession
    ) -> None:
        """Test that getting a school with admin returns admin_user_id and admin_email."""
        # Create a school with admin

        school_payload = {
            "name": "School With Admin",
            "slug": f"school-admin-{uuid.uuid4().hex[:8]}",
            "country": "Indonesia",
            "timezone": "Asia/Jakarta",
            "admin_email": f"admin-{uuid.uuid4().hex[:8]}@test.com",
            "admin_first_name": "Admin",
            "admin_last_name": "User",
            "admin_password": "securepass123",
        }

        create_response = await client.post(
            "/api/v1/schools", json=school_payload, headers=make_auth_header(kaihle_admin)
        )
        assert create_response.status_code == 201
        school_id = create_response.json()["id"]

        # Get the school
        headers = make_auth_header(kaihle_admin)
        response = await client.get(f"/api/v1/schools/{school_id}", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["admin_user_id"] is not None
        assert data["admin_email"] == school_payload["admin_email"]

    @pytest.mark.asyncio
    async def test_get_school_when_no_admin_then_admin_fields_are_null(
        self, client: AsyncClient, kaihle_admin: User, test_school: School
    ) -> None:
        """Test that getting a school with no admin returns null admin fields."""
        headers = make_auth_header(kaihle_admin)

        response = await client.get(f"/api/v1/schools/{test_school.id}", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["admin_user_id"] is None
        assert data["admin_email"] is None


class TestUpdateSchool:
    """Tests for PATCH /api/v1/schools/{school_id}"""

    @pytest.mark.asyncio
    async def test_update_school_when_kaihle_admin_then_200(
        self, client: AsyncClient, kaihle_admin: User, test_school: School
    ) -> None:
        """Test that KaihleAdmin can update a school."""
        headers = make_auth_header(kaihle_admin)
        payload = {
            "name": "Updated School Name",
            "country": "Singapore",
        }

        response = await client.patch(
            f"/api/v1/schools/{test_school.id}",
            json=payload,
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated School Name"
        assert data["country"] == "Singapore"
        assert data["slug"] == test_school.slug  # unchanged

    @pytest.mark.asyncio
    async def test_update_school_when_school_admin_then_403(
        self, client: AsyncClient, school_admin_other: User, other_school: School
    ) -> None:
        """Test that SchoolAdmin cannot update a school."""
        headers = make_auth_header(school_admin_other)
        payload = {"name": "Updated Name"}

        response = await client.patch(
            f"/api/v1/schools/{other_school.id}",
            json=payload,
            headers=headers,
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_update_school_when_teacher_then_403(
        self, client: AsyncClient, test_teacher: User, test_school: School
    ) -> None:
        """Test that Teacher cannot update a school."""
        headers = make_auth_header(test_teacher)
        payload = {"name": "Updated Name"}

        response = await client.patch(
            f"/api/v1/schools/{test_school.id}",
            json=payload,
            headers=headers,
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_update_school_when_not_exists_then_404(self, client: AsyncClient, kaihle_admin: User) -> None:
        """Test that updating non-existent school returns 404."""
        headers = make_auth_header(kaihle_admin)
        non_existent_id = uuid.uuid4()
        payload = {"name": "Updated Name"}

        response = await client.patch(
            f"/api/v1/schools/{non_existent_id}",
            json=payload,
            headers=headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_school_when_deactivate_then_status_updated(
        self, client: AsyncClient, kaihle_admin: User, test_school: School
    ) -> None:
        """Test that deactivating a school updates is_active."""
        headers = make_auth_header(kaihle_admin)
        payload = {"is_active": False}

        response = await client.patch(
            f"/api/v1/schools/{test_school.id}",
            json=payload,
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is False


# =============================================================================
# KaihleAdmin Bypass Tests for Class Operations (Fix 1)
# =============================================================================


@pytest.mark.asyncio
async def test_kaihle_admin_can_create_class_in_any_school(
    client: AsyncClient,
    db_session: AsyncSession,
    kaihle_admin: User,
    other_school: School,
    test_curriculum: Curriculum,
    test_grade: Grade,
    test_subject: Subject,
) -> None:
    """KaihleAdmin can POST to /api/v1/schools/{any_school_id}/classes and get 201."""
    headers = make_auth_header(kaihle_admin)

    # Create a teacher that belongs to other_school
    teacher = User(
        id=uuid.uuid4(),
        school_id=other_school.id,
        email=f"teacher-other-{uuid.uuid4().hex[:8]}@test.com",
        first_name="OtherSchool",
        last_name="Teacher",
        role=UserRole.TEACHER,
        is_active=True,
    )
    db_session.add(teacher)
    await db_session.flush()

    response = await client.post(
        f"/api/v1/schools/{other_school.id}/classes",
        headers=headers,
        json={
            "name": "Test Class",
            "grade_id": str(test_grade.id),
            "subject_id": str(test_subject.id),
            "curriculum_id": str(test_curriculum.id),
            "teacher_id": str(teacher.id),
            "academic_year": "2026",
        },
    )

    assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.json()}"
    data = response.json()
    assert data["school_id"] == str(other_school.id)
    assert data["name"] == "Test Class"


@pytest.mark.asyncio
async def test_kaihle_admin_can_list_classes_in_any_school(
    client: AsyncClient,
    db_session: AsyncSession,
    kaihle_admin: User,
    other_school: School,
    test_curriculum: Curriculum,
    test_grade: Grade,
    test_subject: Subject,
) -> None:
    """KaihleAdmin can GET /api/v1/schools/{any_school_id}/classes and get 200."""
    headers = make_auth_header(kaihle_admin)

    # Create a teacher that belongs to other_school
    teacher = User(
        id=uuid.uuid4(),
        school_id=other_school.id,
        email=f"list-teacher-{uuid.uuid4().hex[:8]}@test.com",
        first_name="ListTest",
        last_name="Teacher",
        role=UserRole.TEACHER,
        is_active=True,
    )
    db_session.add(teacher)
    await db_session.flush()

    class_ = Class(
        id=uuid.uuid4(),
        school_id=other_school.id,
        grade_id=test_grade.id,
        subject_id=test_subject.id,
        curriculum_id=test_curriculum.id,
        teacher_id=teacher.id,
        name="Kaihle Test Class",
        academic_year="2026",
        is_active=True,
    )
    db_session.add(class_)
    await db_session.commit()

    response = await client.get(
        f"/api/v1/schools/{other_school.id}/classes",
        headers=headers,
    )

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.json()}"
    data = response.json()
    assert isinstance(data, list)
    assert any(c["name"] == "Kaihle Test Class" for c in data)


@pytest.mark.asyncio
async def test_kaihle_admin_can_enroll_students_in_any_school(
    client: AsyncClient,
    db_session: AsyncSession,
    kaihle_admin: User,
    other_school: School,
    test_curriculum: Curriculum,
    test_grade: Grade,
    test_subject: Subject,
) -> None:
    """KaihleAdmin can POST to /api/v1/classes/{class_id}/enrollments."""
    headers = make_auth_header(kaihle_admin)

    # Create a teacher that belongs to other_school
    teacher = User(
        id=uuid.uuid4(),
        school_id=other_school.id,
        email=f"enroll-teacher-{uuid.uuid4().hex[:8]}@test.com",
        first_name="EnrollTest",
        last_name="Teacher",
        role=UserRole.TEACHER,
        is_active=True,
    )
    db_session.add(teacher)
    await db_session.flush()

    class_ = Class(
        id=uuid.uuid4(),
        school_id=other_school.id,
        grade_id=test_grade.id,
        subject_id=test_subject.id,
        curriculum_id=test_curriculum.id,
        teacher_id=teacher.id,
        name="Enrollment Test Class",
        academic_year="2026",
        is_active=True,
    )
    db_session.add(class_)
    await db_session.flush()

    # Create a student in the other school
    student = User(
        id=uuid.uuid4(),
        school_id=other_school.id,
        email=f"enroll-student-{uuid.uuid4().hex[:8]}@test.com",
        first_name="Enroll",
        last_name="Student",
        role=UserRole.STUDENT,
        is_active=True,
    )
    db_session.add(student)
    await db_session.flush()

    response = await client.post(
        f"/api/v1/classes/{class_.id}/enrollments",
        headers=headers,
        json={"student_ids": [str(student.id)]},
    )

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.json()}"
    data = response.json()
    assert data["enrolled"] == 1


@pytest.mark.asyncio
async def test_school_admin_cannot_access_different_school_classes(
    client: AsyncClient,
    db_session: AsyncSession,
    school_admin_other: User,
    test_school: School,
) -> None:
    """SchoolAdmin from school A cannot access classes in school B — returns 403."""
    headers = make_auth_header(school_admin_other)

    # Try to list classes in the other school (school, not other_school)
    response = await client.get(
        f"/api/v1/schools/{test_school.id}/classes",
        headers=headers,
    )

    assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.json()}"
    data = response.json()
    assert "Access denied" in data["detail"]
