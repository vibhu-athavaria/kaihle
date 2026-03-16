"""Integration tests for GET /api/v1/onboarding/students/pending

Tests cover:
- GET /api/v1/onboarding/students/pending

Role permissions:
- KAIHLE_ADMIN: sees ALL pending students from all schools
- SCHOOL_ADMIN: sees only pending students from their own school
- TEACHER/STUDENT: 403 Forbidden
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.school import School
from app.models.user import StudentProfile, User, UserRole


def auth_header(user: User) -> dict[str, str]:
    """Create auth header for user."""
    from app.core.security import create_access_token

    token = create_access_token(
        user_id=user.id,
        school_id=user.school_id,
        role=user.role,
        expires_in=3600,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def kaihle_admin(db_session: AsyncSession, test_school: School) -> User:
    """Create a KaihleAdmin user."""
    admin = User(
        id=uuid.uuid4(),
        school_id=test_school.id,
        email=f"kaihle-admin-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Kaihle",
        last_name="Admin",
        role=UserRole.KAIHLE_ADMIN,
        is_active=True,
    )
    db_session.add(admin)
    await db_session.commit()
    return admin


@pytest.fixture
async def school_admin(db_session: AsyncSession, test_school: School) -> User:
    """Create a school admin user."""
    admin = User(
        id=uuid.uuid4(),
        school_id=test_school.id,
        email=f"school-admin-{uuid.uuid4().hex[:8]}@example.com",
        first_name="School",
        last_name="Admin",
        role=UserRole.SCHOOL_ADMIN,
        is_active=True,
    )
    db_session.add(admin)
    await db_session.commit()
    return admin


@pytest.fixture
async def teacher(db_session: AsyncSession, test_school: School) -> User:
    """Create a teacher user."""
    teacher = User(
        id=uuid.uuid4(),
        school_id=test_school.id,
        email=f"teacher-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Test",
        last_name="Teacher",
        role=UserRole.TEACHER,
        is_active=True,
    )
    db_session.add(teacher)
    await db_session.commit()
    return teacher


@pytest.fixture
async def student_with_pending_onboarding(db_session: AsyncSession, test_school: School) -> User:
    """Create a student with pending onboarding (learning profile not complete)."""
    student = User(
        id=uuid.uuid4(),
        school_id=test_school.id,
        email=f"pending-student-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Pending",
        last_name="Student",
        role=UserRole.STUDENT,
        is_active=True,
    )
    db_session.add(student)
    await db_session.commit()

    profile = StudentProfile(
        id=uuid.uuid4(),
        user_id=student.id,
        is_learning_profile_complete=False,
    )
    db_session.add(profile)
    await db_session.commit()

    return student


@pytest.fixture
async def student_with_completed_onboarding(db_session: AsyncSession, test_school: School) -> User:
    """Create a student with completed onboarding (learning profile complete)."""
    student = User(
        id=uuid.uuid4(),
        school_id=test_school.id,
        email=f"completed-student-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Completed",
        last_name="Student",
        role=UserRole.STUDENT,
        is_active=True,
    )
    db_session.add(student)
    await db_session.commit()

    profile = StudentProfile(
        id=uuid.uuid4(),
        user_id=student.id,
        is_learning_profile_complete=True,
    )
    db_session.add(profile)
    await db_session.commit()

    return student


@pytest.fixture
async def other_school(db_session: AsyncSession) -> School:
    """Create another school for cross-school tests."""
    school = School(
        id=uuid.uuid4(),
        name="Other School",
        slug=f"other-school-{uuid.uuid4().hex[:8]}",
        status="active",
    )
    db_session.add(school)
    await db_session.commit()
    return school


@pytest.fixture
async def other_school_admin(db_session: AsyncSession, other_school: School) -> User:
    """Create a school admin for another school."""
    admin = User(
        id=uuid.uuid4(),
        school_id=other_school.id,
        email=f"other-admin-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Other",
        last_name="Admin",
        role=UserRole.SCHOOL_ADMIN,
        is_active=True,
    )
    db_session.add(admin)
    await db_session.commit()
    return admin


@pytest.fixture
async def student_in_other_school(db_session: AsyncSession, other_school: School) -> User:
    """Create a student with pending onboarding in another school."""
    student = User(
        id=uuid.uuid4(),
        school_id=other_school.id,
        email=f"other-school-student-{uuid.uuid4().hex[:8]}@example.com",
        first_name="OtherSchool",
        last_name="Student",
        role=UserRole.STUDENT,
        is_active=True,
    )
    db_session.add(student)
    await db_session.commit()

    profile = StudentProfile(
        id=uuid.uuid4(),
        user_id=student.id,
        is_learning_profile_complete=False,
    )
    db_session.add(profile)
    await db_session.commit()

    return student


@pytest.fixture
async def student_with_completed_onboarding_in_other_school(db_session: AsyncSession, other_school: School) -> User:
    """Create a student with completed onboarding in another school."""
    student = User(
        id=uuid.uuid4(),
        school_id=other_school.id,
        email=f"other-school-completed-{uuid.uuid4().hex[:8]}@example.com",
        first_name="OtherSchoolCompleted",
        last_name="Student",
        role=UserRole.STUDENT,
        is_active=True,
    )
    db_session.add(student)
    await db_session.commit()

    profile = StudentProfile(
        id=uuid.uuid4(),
        user_id=student.id,
        is_learning_profile_complete=True,
    )
    db_session.add(profile)
    await db_session.commit()

    return student


# =============================================================================
# Happy Path Tests
# =============================================================================


class TestGetPendingOnboardingStudentsHappyPath:
    """Tests for successful retrieval of pending onboarding students."""

    @pytest.mark.asyncio
    async def test_kaihle_admin_sees_all_pending_students_from_all_schools(
        self,
        client: AsyncClient,
        kaihle_admin: User,
        student_with_pending_onboarding: User,
        student_in_other_school: User,
    ) -> None:
        """P01: KaihleAdmin retrieves ALL pending students from all schools -> 200."""
        headers = auth_header(kaihle_admin)

        response = await client.get(
            "/api/v1/onboarding/students/pending",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2

        # Verify both students from both schools are present
        student_ids = {item["student_id"] for item in data}
        assert str(student_with_pending_onboarding.id) in student_ids
        assert str(student_in_other_school.id) in student_ids

        # Verify student names are present and correct
        student_names = {item["student_name"] for item in data}
        assert (
            f"{student_with_pending_onboarding.first_name} {student_with_pending_onboarding.last_name}" in student_names
        )
        assert f"{student_in_other_school.first_name} {student_in_other_school.last_name}" in student_names

    @pytest.mark.asyncio
    async def test_school_admin_sees_only_their_school_students(
        self,
        client: AsyncClient,
        school_admin: User,
        student_with_pending_onboarding: User,
    ) -> None:
        """P02: SchoolAdmin retrieves only pending students from their school -> 200."""
        headers = auth_header(school_admin)

        response = await client.get(
            "/api/v1/onboarding/students/pending",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1

        # Verify correct student is returned
        assert data[0]["student_id"] == str(student_with_pending_onboarding.id)
        assert (
            data[0]["student_name"]
            == f"{student_with_pending_onboarding.first_name} {student_with_pending_onboarding.last_name}"
        )
        assert data[0]["learning_profile_complete"] is False

    @pytest.mark.asyncio
    async def test_school_admin_does_not_see_other_school_students(
        self,
        client: AsyncClient,
        school_admin: User,
        student_in_other_school: User,
    ) -> None:
        """P03: SchoolAdmin does NOT see pending students from other schools -> 200, empty."""
        headers = auth_header(school_admin)

        response = await client.get(
            "/api/v1/onboarding/students/pending",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

        # Verify the other school student is NOT in response
        student_ids = {item["student_id"] for item in data}
        assert str(student_in_other_school.id) not in student_ids

    @pytest.mark.asyncio
    async def test_empty_list_when_no_pending_students(
        self,
        client: AsyncClient,
        kaihle_admin: User,
        student_with_completed_onboarding: User,
    ) -> None:
        """P04: Returns empty list when no students have pending onboarding -> 200."""
        headers = auth_header(kaihle_admin)

        response = await client.get(
            "/api/v1/onboarding/students/pending",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    @pytest.mark.asyncio
    async def test_pagination_limit_parameter_respects_limit(
        self,
        client: AsyncClient,
        kaihle_admin: User,
        db_session: AsyncSession,
        test_school: School,
    ) -> None:
        """P05: Pagination limit parameter is respected -> returns up to limit items."""
        # Create 5 pending students
        created_students = []
        for i in range(5):
            student = User(
                id=uuid.uuid4(),
                school_id=test_school.id,
                email=f"limit-test-{i}-{uuid.uuid4().hex[:8]}@example.com",
                first_name=f"Student{i}",
                last_name="Test",
                role=UserRole.STUDENT,
                is_active=True,
            )
            db_session.add(student)
            await db_session.commit()

            profile = StudentProfile(
                id=uuid.uuid4(),
                user_id=student.id,
                is_learning_profile_complete=False,
            )
            db_session.add(profile)
            await db_session.commit()
            created_students.append(student)

        headers = auth_header(kaihle_admin)

        response = await client.get(
            "/api/v1/onboarding/students/pending?limit=2",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2

        # Verify returned students have correct structure
        for item in data:
            assert "student_id" in item
            assert "student_name" in item
            assert "learning_profile_complete" in item
            assert item["learning_profile_complete"] is False

    @pytest.mark.asyncio
    async def test_pagination_offset_parameter_skips_results(
        self,
        client: AsyncClient,
        kaihle_admin: User,
        db_session: AsyncSession,
        test_school: School,
    ) -> None:
        """P06: Pagination offset parameter skips correct number of results."""
        # Create 5 pending students
        for i in range(5):
            student = User(
                id=uuid.uuid4(),
                school_id=test_school.id,
                email=f"offset-test-{i}-{uuid.uuid4().hex[:8]}@example.com",
                first_name=f"OffsetStudent{i}",
                last_name="Test",
                role=UserRole.STUDENT,
                is_active=True,
            )
            db_session.add(student)
            await db_session.commit()

            profile = StudentProfile(
                id=uuid.uuid4(),
                user_id=student.id,
                is_learning_profile_complete=False,
            )
            db_session.add(profile)
            await db_session.commit()

        headers = auth_header(kaihle_admin)

        # First page
        response1 = await client.get(
            "/api/v1/onboarding/students/pending?limit=2&offset=0",
            headers=headers,
        )
        # Second page
        response2 = await client.get(
            "/api/v1/onboarding/students/pending?limit=2&offset=2",
            headers=headers,
        )

        assert response1.status_code == 200
        assert response2.status_code == 200

        data1 = response1.json()
        data2 = response2.json()

        assert len(data1) == 2
        assert len(data2) == 2

        # Verify names are present and correct
        for item in data1:
            assert "OffsetStudent" in item["student_name"]
            assert item["learning_profile_complete"] is False
        for item in data2:
            assert "OffsetStudent" in item["student_name"]
            assert item["learning_profile_complete"] is False

        # Ensure no overlap between pages
        ids1 = {item["student_id"] for item in data1}
        ids2 = {item["student_id"] for item in data2}
        assert ids1.isdisjoint(ids2)

    @pytest.mark.asyncio
    async def test_returns_correct_response_schema(
        self,
        client: AsyncClient,
        kaihle_admin: User,
        student_with_pending_onboarding: User,
    ) -> None:
        """P07: Response contains correct schema fields."""
        headers = auth_header(kaihle_admin)

        response = await client.get(
            "/api/v1/onboarding/students/pending",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1

        item = data[0]
        # Verify required fields from OnboardingPendingResponse
        assert "student_id" in item
        assert "student_name" in item
        assert "learning_profile_complete" in item
        # Verify values
        assert item["student_id"] == str(student_with_pending_onboarding.id)
        assert item["learning_profile_complete"] is False

    @pytest.mark.asyncio
    async def test_completed_students_not_included(
        self,
        client: AsyncClient,
        kaihle_admin: User,
        student_with_pending_onboarding: User,
        student_with_completed_onboarding: User,
    ) -> None:
        """P08: Students with completed onboarding are NOT included."""
        headers = auth_header(kaihle_admin)

        response = await client.get(
            "/api/v1/onboarding/students/pending",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

        # Only pending student should be returned
        assert len(data) == 1
        assert data[0]["student_id"] == str(student_with_pending_onboarding.id)
        assert (
            data[0]["student_name"]
            == f"{student_with_pending_onboarding.first_name} {student_with_pending_onboarding.last_name}"
        )
        assert data[0]["learning_profile_complete"] is False

        # Verify completed student is NOT in response
        returned_ids = {item["student_id"] for item in data}
        assert str(student_with_completed_onboarding.id) not in returned_ids


# =============================================================================
# Authentication & Authorization Tests
# =============================================================================


class TestGetPendingOnboardingStudentsAuth:
    """Tests for authentication and authorization."""

    @pytest.mark.asyncio
    async def test_unauthenticated_request_returns_401(
        self,
        client: AsyncClient,
    ) -> None:
        """A01: Unauthenticated request -> 401."""
        response = await client.get("/api/v1/onboarding/students/pending")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_teacher_returns_403(
        self,
        client: AsyncClient,
        teacher: User,
    ) -> None:
        """A02: Teacher tries to access -> 403 Forbidden."""
        headers = auth_header(teacher)

        response = await client.get(
            "/api/v1/onboarding/students/pending",
            headers=headers,
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_student_returns_403(
        self,
        client: AsyncClient,
        student_with_pending_onboarding: User,
    ) -> None:
        """A03: Student tries to access -> 403 Forbidden."""
        headers = auth_header(student_with_pending_onboarding)

        response = await client.get(
            "/api/v1/onboarding/students/pending",
            headers=headers,
        )

        assert response.status_code == 403


# =============================================================================
# Validation Tests
# =============================================================================


class TestGetPendingOnboardingStudentsValidation:
    """Tests for query parameter validation."""

    @pytest.mark.asyncio
    async def test_limit_zero_returns_422(
        self,
        client: AsyncClient,
        kaihle_admin: User,
    ) -> None:
        """V01: limit=0 -> 422 Unprocessable Entity."""
        headers = auth_header(kaihle_admin)

        response = await client.get(
            "/api/v1/onboarding/students/pending?limit=0",
            headers=headers,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_limit_over_100_returns_422(
        self,
        client: AsyncClient,
        kaihle_admin: User,
    ) -> None:
        """V02: limit=101 -> 422 Unprocessable Entity."""
        headers = auth_header(kaihle_admin)

        response = await client.get(
            "/api/v1/onboarding/students/pending?limit=101",
            headers=headers,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_negative_offset_returns_422(
        self,
        client: AsyncClient,
        kaihle_admin: User,
    ) -> None:
        """V03: offset=-1 -> 422 Unprocessable Entity."""
        headers = auth_header(kaihle_admin)

        response = await client.get(
            "/api/v1/onboarding/students/pending?offset=-1",
            headers=headers,
        )

        assert response.status_code == 422
