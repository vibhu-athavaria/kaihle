"""Integration tests for curriculum read endpoints (M0-10-T2b).

Tests verify the acceptance criteria from M0-10-T2b_curriculum_read_endpoints.md:
1. GET /api/v1/curricula returns curricula list
2. GET /api/v1/curricula/{id} returns single curriculum
3. GET /api/v1/grades returns grades list with optional curriculum filter
4. GET /api/v1/subjects returns subjects list with optional curriculum filter
5. GET /api/v1/subjects/{id}/topics returns topics for a subject
6. GET /api/v1/topics/{id}/subtopics returns subtopics for a topic
7. All endpoints require authentication (401 without valid JWT)
8. GET /api/v1/curricula/{invalid_id} returns 404

Run with: pytest backend/app/tests/integration/test_curriculum_routes.py -v
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.curriculum import (
    Curriculum,
    CurriculumSubject,
    CurriculumTopic,
    Grade,
    Subject,
    Subtopic,
    Topic,
)
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
async def curriculum_graph(db_session: AsyncSession) -> dict:
    """Seed the full curriculum graph for testing.

    Creates:
    - 2 curricula: Cambridge Lower Secondary (lower), Cambridge IGCSE (igcse)
    - 7 grades: Grade 6 through Grade 12
    - 7 subjects: MATH, SCI, ENG, BIO, CHEM, PHY, ENGL
    - Topics and curriculum_topics linking them
    - Subtopics for some topics

    Returns dict with IDs for all created entities.
    """
    # Create curricula
    lower = Curriculum(
        id=uuid.uuid4(),
        name="Cambridge Lower Secondary",
        code="lower",
        is_active=True,
    )
    igcse = Curriculum(
        id=uuid.uuid4(),
        name="Cambridge IGCSE",
        code="igcse",
        is_active=True,
    )
    db_session.add_all([lower, igcse])

    # Create grades
    grades = {}
    for level in range(6, 13):  # Grade 6 through Grade 12
        g = Grade(
            id=uuid.uuid4(),
            name=f"Grade {level}",
            level=level,
            is_active=True,
        )
        grades[level] = g
        db_session.add(g)

    await db_session.flush()

    # Create subjects
    subjects = {}
    subject_data = [
        ("Mathematics", "MATH"),
        ("Science", "SCI"),
        ("English", "ENG"),
        ("Biology", "BIO"),
        ("Chemistry", "CHEM"),
        ("Physics", "PHY"),
        ("English Language", "ENGL"),
    ]
    for name, code in subject_data:
        s = Subject(
            id=uuid.uuid4(),
            name=name,
            code=code,
            is_active=True,
        )
        subjects[code] = s
        db_session.add(s)

    await db_session.flush()

    # Link subjects to curricula via CurriculumSubject
    # Lower Secondary: MATH, SCI, ENG
    # IGCSE: MATH, SCI, ENG, BIO, CHEM, PHY, ENGL
    curriculum_subjects = [
        CurriculumSubject(curriculum_id=lower.id, subject_id=subjects["MATH"].id, sort_order=1),
        CurriculumSubject(curriculum_id=lower.id, subject_id=subjects["SCI"].id, sort_order=2),
        CurriculumSubject(curriculum_id=lower.id, subject_id=subjects["ENG"].id, sort_order=3),
        CurriculumSubject(curriculum_id=igcse.id, subject_id=subjects["MATH"].id, sort_order=1),
        CurriculumSubject(curriculum_id=igcse.id, subject_id=subjects["SCI"].id, sort_order=2),
        CurriculumSubject(curriculum_id=igcse.id, subject_id=subjects["ENG"].id, sort_order=3),
        CurriculumSubject(curriculum_id=igcse.id, subject_id=subjects["BIO"].id, sort_order=4),
        CurriculumSubject(curriculum_id=igcse.id, subject_id=subjects["CHEM"].id, sort_order=5),
        CurriculumSubject(curriculum_id=igcse.id, subject_id=subjects["PHY"].id, sort_order=6),
        CurriculumSubject(curriculum_id=igcse.id, subject_id=subjects["ENGL"].id, sort_order=7),
    ]
    db_session.add_all(curriculum_subjects)

    # Create topics
    math_algebra = Topic(
        id=uuid.uuid4(),
        name="Algebra",
        is_active=True,
    )
    math_number = Topic(
        id=uuid.uuid4(),
        name="Number",
        is_active=True,
    )
    math_geometry = Topic(
        id=uuid.uuid4(),
        name="Geometry",
        is_active=True,
    )
    db_session.add_all([math_algebra, math_number, math_geometry])

    await db_session.flush()

    # Link topics to curriculum/subject/grade via CurriculumTopic
    # Lower Secondary Math Grade 6: Number (1), Algebra (2), Geometry (3)
    curriculum_topics_lower_math_g6 = [
        CurriculumTopic(
            id=uuid.uuid4(),
            curriculum_id=lower.id,
            subject_id=subjects["MATH"].id,
            topic_id=math_number.id,
            grade_id=grades[6].id,
            sequence_order=1,
        ),
        CurriculumTopic(
            id=uuid.uuid4(),
            curriculum_id=lower.id,
            subject_id=subjects["MATH"].id,
            topic_id=math_algebra.id,
            grade_id=grades[6].id,
            sequence_order=2,
        ),
        CurriculumTopic(
            id=uuid.uuid4(),
            curriculum_id=lower.id,
            subject_id=subjects["MATH"].id,
            topic_id=math_geometry.id,
            grade_id=grades[6].id,
            sequence_order=3,
        ),
    ]

    # Lower Secondary Math Grade 7: Number (1), Algebra (2), Geometry (3)
    curriculum_topics_lower_math_g7 = [
        CurriculumTopic(
            id=uuid.uuid4(),
            curriculum_id=lower.id,
            subject_id=subjects["MATH"].id,
            topic_id=math_number.id,
            grade_id=grades[7].id,
            sequence_order=1,
        ),
        CurriculumTopic(
            id=uuid.uuid4(),
            curriculum_id=lower.id,
            subject_id=subjects["MATH"].id,
            topic_id=math_algebra.id,
            grade_id=grades[7].id,
            sequence_order=2,
        ),
    ]

    # IGCSE Math Grade 9: Number, Algebra
    curriculum_topics_igcse_math_g9 = [
        CurriculumTopic(
            id=uuid.uuid4(),
            curriculum_id=igcse.id,
            subject_id=subjects["MATH"].id,
            topic_id=math_number.id,
            grade_id=grades[9].id,
            sequence_order=1,
        ),
        CurriculumTopic(
            id=uuid.uuid4(),
            curriculum_id=igcse.id,
            subject_id=subjects["MATH"].id,
            topic_id=math_algebra.id,
            grade_id=grades[9].id,
            sequence_order=2,
        ),
    ]

    db_session.add_all(
        curriculum_topics_lower_math_g6 + curriculum_topics_lower_math_g7 + curriculum_topics_igcse_math_g9
    )

    await db_session.flush()

    # Create subtopics for Algebra topic
    algebra_subtopics = [
        Subtopic(
            id=uuid.uuid4(),
            name="Basic Equations",
            curriculum_topic_id=curriculum_topics_lower_math_g6[1].id,
            learning_objective="Understand basic algebraic equations",
            sequence_order=1,
        ),
        Subtopic(
            id=uuid.uuid4(),
            name="Linear Equations",
            curriculum_topic_id=curriculum_topics_lower_math_g6[1].id,
            learning_objective="Solve linear equations",
            sequence_order=2,
        ),
        Subtopic(
            id=uuid.uuid4(),
            name="Quadratic Equations",
            curriculum_topic_id=curriculum_topics_lower_math_g6[1].id,
            learning_objective="Solve quadratic equations",
            sequence_order=3,
        ),
    ]
    db_session.add_all(algebra_subtopics)

    await db_session.commit()

    return {
        "lower": lower,
        "igcse": igcse,
        "grades": grades,
        "subjects": subjects,
        "topics": {
            "algebra": math_algebra,
            "number": math_number,
            "geometry": math_geometry,
        },
        "curriculum_topics": {
            "lower_math_g6": curriculum_topics_lower_math_g6,
            "lower_math_g7": curriculum_topics_lower_math_g7,
        },
        "algebra_subtopics": algebra_subtopics,
    }


# =============================================================================
# Test: list_curricula when seeded
# =============================================================================


class TestListCurricula:
    """Tests for GET /api/v1/curricula."""

    @pytest.mark.asyncio
    async def test_list_curricula_when_seeded_then_returns_two_curricula(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        curriculum_graph: dict,
    ) -> None:
        """GET /api/v1/curricula returns both seeded curricula with non-null fields."""
        # Create authenticated user
        school = School(
            id=uuid.uuid4(),
            name="Test School",
            slug=f"test-{uuid.uuid4().hex[:8]}",
            status="active",
        )
        db_session.add(school)
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

        headers = make_auth_header(user)

        response = await client.get("/api/v1/curricula", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

        # Both curricula have non-null id, name, code
        for curriculum in data:
            assert curriculum["id"] is not None
            assert curriculum["name"] is not None
            assert curriculum["code"] is not None


# =============================================================================
# Test: get_curriculum
# =============================================================================


class TestGetCurriculum:
    """Tests for GET /api/v1/curricula/{curriculum_id}."""

    @pytest.mark.asyncio
    async def test_get_curriculum_when_invalid_id_then_404(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """GET /api/v1/curricula/{random_uuid} returns 404."""
        # Create authenticated user
        school = School(
            id=uuid.uuid4(),
            name="Test School",
            slug=f"test-{uuid.uuid4().hex[:8]}",
            status="active",
        )
        db_session.add(school)
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

        headers = make_auth_header(user)
        random_id = uuid.uuid4()

        response = await client.get(
            f"/api/v1/curricula/{random_id}",
            headers=headers,
        )

        assert response.status_code == 404


# =============================================================================
# Test: list_grades with curriculum filter
# =============================================================================


class TestListGrades:
    """Tests for GET /api/v1/grades."""

    @pytest.mark.asyncio
    async def test_list_grades_when_curriculum_filter_then_only_correct_grades(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        curriculum_graph: dict,
    ) -> None:
        """GET /api/v1/grades?curriculum_id={igcse_id} returns only grades 9 and 10."""
        # Create authenticated user
        school = School(
            id=uuid.uuid4(),
            name="Test School",
            slug=f"test-{uuid.uuid4().hex[:8]}",
            status="active",
        )
        db_session.add(school)
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

        headers = make_auth_header(user)
        igcse_id = curriculum_graph["igcse"].id

        response = await client.get(
            f"/api/v1/grades?curriculum_id={igcse_id}",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        # IGCSE only has Grade 9 in our seed data
        assert len(data) == 1
        grade_levels = [g["level"] for g in data]
        assert 9 in grade_levels
        # Grade 6 should not be in IGCSE
        assert 6 not in grade_levels


# =============================================================================
# Test: list_subjects with curriculum filter
# =============================================================================


class TestListSubjects:
    """Tests for GET /api/v1/subjects."""

    @pytest.mark.asyncio
    async def test_list_subjects_when_curriculum_filter_then_only_correct_subjects(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        curriculum_graph: dict,
    ) -> None:
        """GET /api/v1/subjects?curriculum_id={lower_id} returns MATH, SCI, ENG only."""
        # Create authenticated user
        school = School(
            id=uuid.uuid4(),
            name="Test School",
            slug=f"test-{uuid.uuid4().hex[:8]}",
            status="active",
        )
        db_session.add(school)
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

        headers = make_auth_header(user)
        lower_id = curriculum_graph["lower"].id

        response = await client.get(
            f"/api/v1/subjects?curriculum_id={lower_id}",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        subject_codes = [s["code"] for s in data]

        # Lower Secondary has MATH, SCI, ENG
        assert "MATH" in subject_codes
        assert "SCI" in subject_codes
        assert "ENG" in subject_codes
        # But not BIO, CHEM, PHY, ENGL
        assert "BIO" not in subject_codes
        assert "CHEM" not in subject_codes
        assert "PHY" not in subject_codes
        assert "ENGL" not in subject_codes


# =============================================================================
# Test: list_subject_topics with filters
# =============================================================================


class TestListSubjectTopics:
    """Tests for GET /api/v1/subjects/{subject_id}/topics."""

    @pytest.mark.asyncio
    async def test_list_topics_when_grade_and_curriculum_filter_then_correct_topics(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        curriculum_graph: dict,
    ) -> None:
        """GET /api/v1/subjects/{math_id}/topics?curriculum_id={lower}&grade_id={g7}
        returns only Grade 7 Mathematics topics.
        """
        # Create authenticated user
        school = School(
            id=uuid.uuid4(),
            name="Test School",
            slug=f"test-{uuid.uuid4().hex[:8]}",
            status="active",
        )
        db_session.add(school)
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

        headers = make_auth_header(user)
        math_id = curriculum_graph["subjects"]["MATH"].id
        lower_id = curriculum_graph["lower"].id
        g7_id = curriculum_graph["grades"][7].id

        response = await client.get(
            f"/api/v1/subjects/{math_id}/topics?curriculum_id={lower_id}&grade_id={g7_id}",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        # Grade 7 Lower Secondary Math has Number and Algebra (2 topics)
        assert len(data) == 2
        topic_names = [t["name"] for t in data]
        assert "Number" in topic_names
        assert "Algebra" in topic_names
        assert "Geometry" not in topic_names

    @pytest.mark.asyncio
    async def test_list_topics_ordered_by_sequence_order(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        curriculum_graph: dict,
    ) -> None:
        """Topics are returned ordered by sequence_order, not alphabetically."""
        # Create authenticated user
        school = School(
            id=uuid.uuid4(),
            name="Test School",
            slug=f"test-{uuid.uuid4().hex[:8]}",
            status="active",
        )
        db_session.add(school)
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

        headers = make_auth_header(user)
        math_id = curriculum_graph["subjects"]["MATH"].id
        lower_id = curriculum_graph["lower"].id
        g6_id = curriculum_graph["grades"][6].id

        response = await client.get(
            f"/api/v1/subjects/{math_id}/topics?curriculum_id={lower_id}&grade_id={g6_id}",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        # Grade 6 Lower Secondary Math: Number (1), Algebra (2), Geometry (3)
        assert len(data) == 3
        # Verify order is by sequence_order
        assert data[0]["name"] == "Number"
        assert data[0]["sequence_order"] == 1
        assert data[1]["name"] == "Algebra"
        assert data[1]["sequence_order"] == 2
        assert data[2]["name"] == "Geometry"
        assert data[2]["sequence_order"] == 3


# =============================================================================
# Test: list_topic_subtopics
# =============================================================================


class TestListTopicSubtopics:
    """Tests for GET /api/v1/topics/{topic_id}/subtopics."""

    @pytest.mark.asyncio
    async def test_list_subtopics_when_topic_id_then_correct_subtopics_returned(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        curriculum_graph: dict,
    ) -> None:
        """GET /api/v1/topics/{algebra_id}/subtopics returns Algebra subtopics in order."""
        # Create authenticated user
        school = School(
            id=uuid.uuid4(),
            name="Test School",
            slug=f"test-{uuid.uuid4().hex[:8]}",
            status="active",
        )
        db_session.add(school)
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

        headers = make_auth_header(user)
        algebra_id = curriculum_graph["topics"]["algebra"].id

        response = await client.get(
            f"/api/v1/topics/{algebra_id}/subtopics",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        # Algebra has 3 subtopics: Basic Equations, Linear Equations, Quadratic Equations
        assert len(data) == 3
        # Verify correct subtopics
        subtopic_names = [s["name"] for s in data]
        assert "Basic Equations" in subtopic_names
        assert "Linear Equations" in subtopic_names
        assert "Quadratic Equations" in subtopic_names
        # Verify order by sequence_order
        assert data[0]["name"] == "Basic Equations"
        assert data[0]["sequence_order"] == 1
        assert data[1]["name"] == "Linear Equations"
        assert data[1]["sequence_order"] == 2
        assert data[2]["name"] == "Quadratic Equations"
        assert data[2]["sequence_order"] == 3


# =============================================================================
# Test: authentication required
# =============================================================================


class TestCurriculumAuthRequired:
    """Tests for authentication requirement on all curriculum endpoints."""

    @pytest.mark.asyncio
    async def test_all_curriculum_endpoints_when_no_auth_then_401(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        curriculum_graph: dict,
    ) -> None:
        """All curriculum endpoints return 401 without Authorization header."""
        math_id = curriculum_graph["subjects"]["MATH"].id
        algebra_id = curriculum_graph["topics"]["algebra"].id
        lower_id = curriculum_graph["lower"].id
        g6_id = curriculum_graph["grades"][6].id

        endpoints = [
            ("GET", "/api/v1/curricula"),
            ("GET", f"/api/v1/curricula/{uuid.uuid4()}"),
            ("GET", "/api/v1/grades"),
            ("GET", f"/api/v1/grades?curriculum_id={lower_id}"),
            ("GET", "/api/v1/subjects"),
            ("GET", f"/api/v1/subjects/{math_id}/topics"),
            ("GET", f"/api/v1/subjects/{math_id}/topics?curriculum_id={lower_id}&grade_id={g6_id}"),
            ("GET", f"/api/v1/topics/{algebra_id}/subtopics"),
        ]

        for method, url in endpoints:
            if method == "GET":
                response = await client.get(url)
            assert response.status_code == 401, f"Expected 401 for {url}, got {response.status_code}"


# =============================================================================
# Write Endpoint Tests (Admin Only)
# =============================================================================


@pytest.mark.asyncio
async def test_post_curricula_when_kaihle_admin_then_201(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test that KAIHLE_ADMIN can create curriculum."""
    # Arrange - Create KAIHLE_ADMIN
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

    headers = make_auth_header(admin)
    payload = {
        "name": f"Test Curriculum {uuid.uuid4().hex[:8]}",
        "code": f"TEST-{uuid.uuid4().hex[:6]}",
        "description": "Test description",
        "country": "UK",
        "is_active": True,
    }

    # Act
    response = await client.post("/api/v1/curricula", json=payload, headers=headers)

    # Assert
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == payload["name"]
    assert data["code"] == payload["code"]


@pytest.mark.asyncio
async def test_post_curricula_when_school_admin_then_403(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test that SCHOOL_ADMIN cannot create curriculum."""
    # Arrange
    school = School(
        id=uuid.uuid4(),
        name="Test School",
        slug=f"test-{uuid.uuid4().hex[:8]}",
        status="active",
    )
    db_session.add(school)

    school_admin = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"sadmin-{uuid.uuid4().hex[:8]}@test.com",
        first_name="School",
        last_name="Admin",
        role=UserRole.SCHOOL_ADMIN,
        is_active=True,
    )
    db_session.add(school_admin)
    await db_session.commit()

    headers = make_auth_header(school_admin)
    payload = {
        "name": "Test Curriculum",
        "code": f"TEST-{uuid.uuid4().hex[:6]}",
        "is_active": True,
    }

    # Act
    response = await client.post("/api/v1/curricula", json=payload, headers=headers)

    # Assert
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_post_curricula_when_duplicate_code_then_409(
    client: AsyncClient,
    db_session: AsyncSession,
    curriculum_graph: dict,
) -> None:
    """Test that duplicate code returns 409."""
    # Arrange
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

    headers = make_auth_header(admin)
    existing_code = curriculum_graph["lower"].code
    payload = {
        "name": "New Name",
        "code": existing_code,
        "is_active": True,
    }

    # Act
    response = await client.post("/api/v1/curricula", json=payload, headers=headers)

    # Assert
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_patch_curriculum_when_valid_then_200(
    client: AsyncClient,
    db_session: AsyncSession,
    curriculum_graph: dict,
) -> None:
    """Test updating a curriculum."""
    # Arrange
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

    headers = make_auth_header(admin)
    payload = {"name": "Updated Curriculum Name"}

    # Act
    response = await client.patch(
        f"/api/v1/curricula/{curriculum_graph['lower'].id}",
        json=payload,
        headers=headers,
    )

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Curriculum Name"


@pytest.mark.asyncio
async def test_post_grades_when_level_14_then_422(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test that level outside 1-13 returns 422."""
    # Arrange
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

    headers = make_auth_header(admin)
    payload = {
        "name": "Invalid Grade",
        "level": 14,
        "is_active": True,
    }

    # Act
    response = await client.post("/api/v1/grades", json=payload, headers=headers)

    # Assert
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_post_subjects_when_valid_then_201(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test creating a subject."""
    # Arrange
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

    headers = make_auth_header(admin)
    unique_suffix = uuid.uuid4().hex[:8]
    payload = {
        "name": f"Test Subject {unique_suffix}",
        "code": f"TS{unique_suffix[:4].upper()}",
        "description": "Test subject description",
        "icon": "book",
        "color": "#1a5c38",
        "is_active": True,
    }

    # Act
    response = await client.post("/api/v1/subjects", json=payload, headers=headers)

    # Assert
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == payload["name"]
    assert data["icon"] == "book"
    assert data["color"] == "#1a5c38"


@pytest.mark.asyncio
async def test_post_curriculum_subjects_when_valid_then_201(
    client: AsyncClient,
    db_session: AsyncSession,
    curriculum_graph: dict,
) -> None:
    """Test linking subject to curriculum."""
    # Arrange
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

    headers = make_auth_header(admin)
    lower_id = curriculum_graph["lower"].id
    math_id = curriculum_graph["subjects"]["MATH"].id

    # First unlink existing
    await client.delete(
        f"/api/v1/curricula/{lower_id}/subjects/{math_id}",
        headers=headers,
    )

    payload = {
        "subject_id": str(math_id),
        "is_core": True,
        "sort_order": 1,
    }

    # Act
    response = await client.post(
        f"/api/v1/curricula/{lower_id}/subjects",
        json=payload,
        headers=headers,
    )

    # Assert
    assert response.status_code == 201
    data = response.json()
    assert data["curriculum_id"] == str(lower_id)
    assert data["subject_id"] == str(math_id)


@pytest.mark.asyncio
async def test_delete_curriculum_subjects_when_valid_then_204(
    client: AsyncClient,
    db_session: AsyncSession,
    curriculum_graph: dict,
) -> None:
    """Test unlinking subject from curriculum."""
    # Arrange
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

    headers = make_auth_header(admin)
    lower_id = curriculum_graph["lower"].id
    math_id = curriculum_graph["subjects"]["MATH"].id

    # Act
    response = await client.delete(
        f"/api/v1/curricula/{lower_id}/subjects/{math_id}",
        headers=headers,
    )

    # Assert
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_post_curriculum_topics_when_new_topic_data_then_201_and_topic_created(
    client: AsyncClient,
    db_session: AsyncSession,
    curriculum_graph: dict,
) -> None:
    """Test creating new topic and adding to curriculum."""
    # Arrange
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

    headers = make_auth_header(admin)
    lower_id = curriculum_graph["lower"].id
    g6_id = curriculum_graph["grades"][6].id
    math_id = curriculum_graph["subjects"]["MATH"].id

    payload = {
        "topic_data": {
            "name": "New Integration Test Topic",
            "canonical_code": "INT-TEST-01",
            "description": "Test topic",
            "keywords": ["test", "integration"],
        },
        "standard_code": "6Ma1",
        "sequence_order": 1,
        "learning_objectives": ["Learn integration testing"],
        "recommended_weeks": 2,
        "is_required": True,
    }

    # Act
    response = await client.post(
        f"/api/v1/curricula/{lower_id}/grades/{g6_id}/subjects/{math_id}/topics",
        json=payload,
        headers=headers,
    )

    # Assert
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "New Integration Test Topic"
    assert data["standard_code"] == "6Ma1"


@pytest.mark.asyncio
async def test_post_curriculum_topics_when_existing_topic_id_then_201(
    client: AsyncClient,
    db_session: AsyncSession,
    curriculum_graph: dict,
) -> None:
    """Test adding existing topic to curriculum placement."""
    # Arrange
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

    headers = make_auth_header(admin)
    igcse_id = curriculum_graph["igcse"].id
    g9_id = curriculum_graph["grades"][9].id
    math_id = curriculum_graph["subjects"]["MATH"].id
    geometry_id = curriculum_graph["topics"]["geometry"].id

    payload = {
        "topic_id": str(geometry_id),
        "standard_code": "9Ma3",
        "is_required": True,
    }

    # Act
    response = await client.post(
        f"/api/v1/curricula/{igcse_id}/grades/{g9_id}/subjects/{math_id}/topics",
        json=payload,
        headers=headers,
    )

    # Assert
    assert response.status_code == 201
    data = response.json()
    assert data["topic_id"] == str(geometry_id)
    assert data["name"] == "Geometry"


@pytest.mark.asyncio
async def test_post_curriculum_topics_when_duplicate_placement_then_409(
    client: AsyncClient,
    db_session: AsyncSession,
    curriculum_graph: dict,
) -> None:
    """Test that duplicate placement returns 409."""
    # Arrange
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

    headers = make_auth_header(admin)
    lower_id = curriculum_graph["lower"].id
    g6_id = curriculum_graph["grades"][6].id
    math_id = curriculum_graph["subjects"]["MATH"].id
    algebra_id = curriculum_graph["topics"]["algebra"].id

    payload = {
        "topic_id": str(algebra_id),
        "is_required": True,
    }

    # Act
    response = await client.post(
        f"/api/v1/curricula/{lower_id}/grades/{g6_id}/subjects/{math_id}/topics",
        json=payload,
        headers=headers,
    )

    # Assert - Algebra is already placed in Grade 6 Lower Secondary Math
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_patch_curriculum_topics_when_valid_then_200(
    client: AsyncClient,
    db_session: AsyncSession,
    curriculum_graph: dict,
) -> None:
    """Test updating curriculum topic placement."""
    # Arrange
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

    headers = make_auth_header(admin)
    ct_id = curriculum_graph["curriculum_topics"]["lower_math_g6"][0].id

    payload = {
        "standard_code": "6Ma-UPDATED",
        "sequence_order": 99,
        "is_required": False,
    }

    # Act
    response = await client.patch(
        f"/api/v1/curriculum-topics/{ct_id}",
        json=payload,
        headers=headers,
    )

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["standard_code"] == "6Ma-UPDATED"
    assert data["sequence_order"] == 99
    assert data["is_required"] is False


@pytest.mark.asyncio
async def test_post_subtopics_when_missing_learning_objective_then_422(
    client: AsyncClient,
    db_session: AsyncSession,
    curriculum_graph: dict,
) -> None:
    """Test that missing learning_objective returns 422."""
    # Arrange
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

    headers = make_auth_header(admin)
    ct_id = curriculum_graph["curriculum_topics"]["lower_math_g6"][0].id

    payload = {
        "name": "Subtopic without LO",
        # Missing learning_objective
    }

    # Act
    response = await client.post(
        f"/api/v1/curriculum-topics/{ct_id}/subtopics",
        json=payload,
        headers=headers,
    )

    # Assert
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_post_subtopics_when_valid_then_201(
    client: AsyncClient,
    db_session: AsyncSession,
    curriculum_graph: dict,
) -> None:
    """Test creating a subtopic."""
    # Arrange
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

    headers = make_auth_header(admin)
    ct_id = curriculum_graph["curriculum_topics"]["lower_math_g6"][0].id

    payload = {
        "name": "Linear Equations",
        "learning_objective": "Students will be able to solve linear equations with one variable using algebraic methods",
        "canonical_code": "6Ma1.1",
        "bloom_taxonomy_level": "Apply",
        "difficulty_level": 3,
        "estimated_minutes": 45,
        "keywords": ["algebra", "equations"],
    }

    # Act
    response = await client.post(
        f"/api/v1/curriculum-topics/{ct_id}/subtopics",
        json=payload,
        headers=headers,
    )

    # Assert
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Linear Equations"
    assert data["bloom_taxonomy_level"] == "Apply"
    assert data["difficulty_level"] == 3


@pytest.mark.asyncio
async def test_patch_subtopics_when_valid_then_200(
    client: AsyncClient,
    db_session: AsyncSession,
    curriculum_graph: dict,
) -> None:
    """Test updating a subtopic."""
    # Arrange
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

    # Create a subtopic to update
    ct_id = curriculum_graph["curriculum_topics"]["lower_math_g6"][1].id  # Algebra
    subtopic = Subtopic(
        id=uuid.uuid4(),
        curriculum_topic_id=ct_id,
        name="Old Name",
        learning_objective="Students will be able to demonstrate understanding of old content",
        difficulty_level=2,
        is_active=True,
    )
    db_session.add(subtopic)
    await db_session.commit()

    headers = make_auth_header(admin)
    payload = {
        "name": "Updated Subtopic Name",
        "difficulty_level": 4,
    }

    # Act
    response = await client.patch(
        f"/api/v1/subtopics/{subtopic.id}",
        json=payload,
        headers=headers,
    )

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Subtopic Name"
    assert data["difficulty_level"] == 4
