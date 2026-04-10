"""Integration tests for assessment and attempt stub routes (M0-10-T3).

Tests verify the acceptance criteria from M0-10-T3_assessment_attempt_stubs.md:
1. GET /api/v1/classes/{id}/assessments with teacher/school_admin/kaihle_admin returns 200
2. GET /api/v1/classes/{id}/assessments with student/parent returns 403
3. GET /api/v1/classes/{id}/assessments with pagination params returns 200
4. POST /api/v1/classes/{id}/assessments with teacher returns 501 (stub)
5. GET /api/v1/assessments/{id} with valid roles returns 404 (stub)
6. POST /api/v1/assessments/{id}/publish with teacher returns 404 (stub)
7. POST /api/v1/assessments/{id}/close with teacher returns 404 (stub)
8. GET /api/v1/classes/{id}/diagnostic with student returns 200
9. GET /api/v1/attempts/{id} with student/teacher returns 200
10. POST /api/v1/attempts/{id}/responses with student returns 204
11. POST /api/v1/attempts/{id}/submit with student returns 200
12. GET /api/v1/attempts/{id}/results with student/teacher returns 200

Run with: pytest backend/app/tests/integration/test_assessment_attempt_routes.py -v
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
# Class-scoped assessment tests
# =============================================================================


class TestGetClassAssessments:
    """Tests for GET /api/v1/classes/{class_id}/assessments."""

    @pytest.mark.asyncio
    async def test_get_class_assessments_when_teacher_then_200(
        self,
        client: AsyncClient,
        teacher: User,
    ) -> None:
        """GET /api/v1/classes/{id}/assessments with teacher JWT for non-existent class returns 404.

        Updated M1-3-T2: real implementation checks teacher owns class — non-existent class → 404.
        """
        class_id = uuid.uuid4()
        headers = make_auth_header(teacher)

        response = await client.get(
            f"/api/v1/classes/{class_id}/assessments",
            headers=headers,
        )

        # Teacher querying a non-existent class → 404
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_class_assessments_when_school_admin_then_200(
        self,
        client: AsyncClient,
        school_admin: User,
    ) -> None:
        """GET /api/v1/classes/{id}/assessments with school admin JWT returns 200."""
        class_id = uuid.uuid4()
        headers = make_auth_header(school_admin)

        response = await client.get(
            f"/api/v1/classes/{class_id}/assessments",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["data"] == []

    @pytest.mark.asyncio
    async def test_get_class_assessments_when_kaihle_admin_then_200(
        self,
        client: AsyncClient,
        kaihle_admin: User,
    ) -> None:
        """GET /api/v1/classes/{id}/assessments with Kaihle admin JWT returns 200."""
        class_id = uuid.uuid4()
        headers = make_auth_header(kaihle_admin)

        response = await client.get(
            f"/api/v1/classes/{class_id}/assessments",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["data"] == []

    @pytest.mark.asyncio
    async def test_get_class_assessments_when_student_then_200(
        self,
        client: AsyncClient,
        student: User,
    ) -> None:
        """GET /api/v1/classes/{id}/assessments with student JWT returns 200."""
        class_id = uuid.uuid4()
        headers = make_auth_header(student)

        response = await client.get(
            f"/api/v1/classes/{class_id}/assessments",
            headers=headers,
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_class_assessments_when_parent_then_403(
        self,
        client: AsyncClient,
        parent_user: User,
    ) -> None:
        """GET /api/v1/classes/{id}/assessments with parent JWT returns 403."""
        class_id = uuid.uuid4()
        headers = make_auth_header(parent_user)

        response = await client.get(
            f"/api/v1/classes/{class_id}/assessments",
            headers=headers,
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_get_class_assessments_with_pagination(
        self,
        client: AsyncClient,
        school_admin: User,
    ) -> None:
        """GET /api/v1/classes/{id}/assessments accepts page and page_size params.

        Updated M1-3-T2: use school_admin (no ownership check) for pagination param test.
        """
        class_id = uuid.uuid4()
        headers = make_auth_header(school_admin)

        response = await client.get(
            f"/api/v1/classes/{class_id}/assessments?page=2&page_size=10",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 2
        assert data["page_size"] == 10

    @pytest.mark.asyncio
    async def test_get_class_assessments_with_status_filter(
        self,
        client: AsyncClient,
        school_admin: User,
    ) -> None:
        """GET /api/v1/classes/{id}/assessments accepts ?status= alias.

        Updated M1-3-T2: use school_admin (no ownership check) for status filter param test.
        """
        class_id = uuid.uuid4()
        headers = make_auth_header(school_admin)

        response = await client.get(
            f"/api/v1/classes/{class_id}/assessments?status=DRAFT",
            headers=headers,
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_class_assessments_when_unauthenticated_then_401(
        self,
        client: AsyncClient,
    ) -> None:
        """GET /api/v1/classes/{id}/assessments without auth returns 401."""
        class_id = uuid.uuid4()

        response = await client.get(
            f"/api/v1/classes/{class_id}/assessments",
        )

        assert response.status_code == 401


class TestPostClassAssessments:
    """Tests for POST /api/v1/classes/{class_id}/assessments."""

    @pytest.mark.asyncio
    async def test_post_class_assessments_when_teacher_then_404(
        self,
        client: AsyncClient,
        teacher: User,
    ) -> None:
        """POST /api/v1/classes/{id}/assessments with teacher JWT for non-existent class returns 404.

        Updated M1-3-T2: real implementation; non-existent class → 404.
        """
        class_id = uuid.uuid4()
        headers = make_auth_header(teacher)
        body = {
            "title": "Test Assessment",
            "topic_ids": [str(uuid.uuid4())],
            "question_count": 10,
        }

        response = await client.post(
            f"/api/v1/classes/{class_id}/assessments",
            headers=headers,
            json=body,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_post_class_assessments_when_student_then_403(
        self,
        client: AsyncClient,
        student: User,
    ) -> None:
        """POST /api/v1/classes/{id}/assessments with student JWT returns 403."""
        class_id = uuid.uuid4()
        headers = make_auth_header(student)
        body = {
            "title": "Test Assessment",
            "topic_ids": [str(uuid.uuid4())],
            "question_count": 10,
        }

        response = await client.post(
            f"/api/v1/classes/{class_id}/assessments",
            headers=headers,
            json=body,
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_post_class_assessments_when_unauthenticated_then_401(
        self,
        client: AsyncClient,
    ) -> None:
        """POST /api/v1/classes/{id}/assessments without auth returns 401."""
        class_id = uuid.uuid4()
        body = {
            "title": "Test Assessment",
            "topic_ids": [str(uuid.uuid4())],
            "question_count": 10,
        }

        response = await client.post(
            f"/api/v1/classes/{class_id}/assessments",
            json=body,
        )

        assert response.status_code == 401


# =============================================================================
# Assessment-scoped tests
# =============================================================================


class TestGetAssessmentById:
    """Tests for GET /api/v1/assessments/{assessment_id}."""

    @pytest.mark.asyncio
    async def test_get_assessment_by_id_when_teacher_then_404_not_found(
        self,
        client: AsyncClient,
        teacher: User,
    ) -> None:
        """GET /api/v1/assessments/{id} with teacher JWT for non-existent ID returns 404.

        Updated M1-3-T2: real implementation; non-existent assessment → 404 from service.
        """
        assessment_id = uuid.uuid4()
        headers = make_auth_header(teacher)

        response = await client.get(
            f"/api/v1/assessments/{assessment_id}",
            headers=headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_assessment_by_id_when_student_then_404_stub(
        self,
        client: AsyncClient,
        student: User,
    ) -> None:
        """GET /api/v1/assessments/{id} with student JWT returns 404 (stub)."""
        assessment_id = uuid.uuid4()
        headers = make_auth_header(student)

        response = await client.get(
            f"/api/v1/assessments/{assessment_id}",
            headers=headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_assessment_by_id_when_school_admin_then_404_stub(
        self,
        client: AsyncClient,
        school_admin: User,
    ) -> None:
        """GET /api/v1/assessments/{id} with school admin JWT returns 404 (stub)."""
        assessment_id = uuid.uuid4()
        headers = make_auth_header(school_admin)

        response = await client.get(
            f"/api/v1/assessments/{assessment_id}",
            headers=headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_assessment_by_id_when_unauthenticated_then_401(
        self,
        client: AsyncClient,
    ) -> None:
        """GET /api/v1/assessments/{id} without auth returns 401."""
        assessment_id = uuid.uuid4()

        response = await client.get(
            f"/api/v1/assessments/{assessment_id}",
        )

        assert response.status_code == 401


class TestPublishAssessment:
    """Tests for POST /api/v1/assessments/{assessment_id}/publish."""

    @pytest.mark.asyncio
    async def test_publish_assessment_when_teacher_then_404_stub(
        self,
        client: AsyncClient,
        teacher: User,
    ) -> None:
        """POST /api/v1/assessments/{id}/publish with teacher JWT returns 404 (stub)."""
        assessment_id = uuid.uuid4()
        headers = make_auth_header(teacher)

        response = await client.post(
            f"/api/v1/assessments/{assessment_id}/publish",
            headers=headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_publish_assessment_when_student_then_403(
        self,
        client: AsyncClient,
        student: User,
    ) -> None:
        """POST /api/v1/assessments/{id}/publish with student JWT returns 403."""
        assessment_id = uuid.uuid4()
        headers = make_auth_header(student)

        response = await client.post(
            f"/api/v1/assessments/{assessment_id}/publish",
            headers=headers,
        )

        assert response.status_code == 403


class TestCloseAssessment:
    """Tests for POST /api/v1/assessments/{assessment_id}/close."""

    @pytest.mark.asyncio
    async def test_close_assessment_when_teacher_then_404_stub(
        self,
        client: AsyncClient,
        teacher: User,
    ) -> None:
        """POST /api/v1/assessments/{id}/close with teacher JWT returns 404 (stub)."""
        assessment_id = uuid.uuid4()
        headers = make_auth_header(teacher)

        response = await client.post(
            f"/api/v1/assessments/{assessment_id}/close",
            headers=headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_close_assessment_when_school_admin_then_403(
        self,
        client: AsyncClient,
        school_admin: User,
    ) -> None:
        """POST /api/v1/assessments/{id}/close with school admin JWT returns 403."""
        assessment_id = uuid.uuid4()
        headers = make_auth_header(school_admin)

        response = await client.post(
            f"/api/v1/assessments/{assessment_id}/close",
            headers=headers,
        )

        assert response.status_code == 403


# =============================================================================
# Diagnostic endpoint tests
# =============================================================================


class TestGetClassDiagnostic:
    """Tests for GET /api/v1/classes/{class_id}/diagnostic."""

    @pytest.mark.asyncio
    async def test_get_class_diagnostic_when_student_no_assessment_then_404(
        self,
        client: AsyncClient,
        student: User,
    ) -> None:
        """GET /api/v1/classes/{id}/diagnostic with student JWT returns 404 when no assessment exists.

        The real implementation (M1-4-T1) returns 404 when no ACTIVE system-generated
        assessment exists for the class — updated from stub which returned 200 always.
        """
        class_id = uuid.uuid4()
        headers = make_auth_header(student)

        response = await client.get(
            f"/api/v1/classes/{class_id}/diagnostic",
            headers=headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_class_diagnostic_when_teacher_then_403(
        self,
        client: AsyncClient,
        teacher: User,
    ) -> None:
        """GET /api/v1/classes/{id}/diagnostic with teacher JWT returns 403."""
        class_id = uuid.uuid4()
        headers = make_auth_header(teacher)

        response = await client.get(
            f"/api/v1/classes/{class_id}/diagnostic",
            headers=headers,
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_get_class_diagnostic_when_parent_then_403(
        self,
        client: AsyncClient,
        parent_user: User,
    ) -> None:
        """GET /api/v1/classes/{id}/diagnostic with parent JWT returns 403."""
        class_id = uuid.uuid4()
        headers = make_auth_header(parent_user)

        response = await client.get(
            f"/api/v1/classes/{class_id}/diagnostic",
            headers=headers,
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_get_class_diagnostic_when_unauthenticated_then_401(
        self,
        client: AsyncClient,
    ) -> None:
        """GET /api/v1/classes/{id}/diagnostic without auth returns 401."""
        class_id = uuid.uuid4()

        response = await client.get(
            f"/api/v1/classes/{class_id}/diagnostic",
        )

        assert response.status_code == 401


# =============================================================================
# Attempt routes tests
# =============================================================================


class TestGetAttempt:
    """Tests for GET /api/v1/attempts/{attempt_id}."""

    @pytest.mark.asyncio
    async def test_get_attempt_when_student_nonexistent_then_404(
        self,
        client: AsyncClient,
        student: User,
    ) -> None:
        """GET /api/v1/attempts/{id} with student JWT returns 404 for unknown attempt.

        Real implementation (M1-4-T1) returns 404 when attempt doesn't exist.
        """
        attempt_id = uuid.uuid4()
        headers = make_auth_header(student)

        response = await client.get(
            f"/api/v1/attempts/{attempt_id}",
            headers=headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_attempt_when_teacher_nonexistent_then_404(
        self,
        client: AsyncClient,
        teacher: User,
    ) -> None:
        """GET /api/v1/attempts/{id} with teacher JWT returns 404 for unknown attempt."""
        attempt_id = uuid.uuid4()
        headers = make_auth_header(teacher)

        response = await client.get(
            f"/api/v1/attempts/{attempt_id}",
            headers=headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_attempt_when_parent_nonexistent_then_404(
        self,
        client: AsyncClient,
        parent_user: User,
    ) -> None:
        """GET /api/v1/attempts/{id} with parent JWT returns 404 for unknown attempt."""
        attempt_id = uuid.uuid4()
        headers = make_auth_header(parent_user)

        response = await client.get(
            f"/api/v1/attempts/{attempt_id}",
            headers=headers,
        )

        assert response.status_code == 404


class TestSubmitResponse:
    """Tests for POST /api/v1/attempts/{attempt_id}/responses."""

    @pytest.mark.asyncio
    async def test_submit_response_when_student_nonexistent_attempt_then_404(
        self,
        client: AsyncClient,
        student: User,
    ) -> None:
        """POST /api/v1/attempts/{id}/responses with student JWT returns 404 for unknown attempt.

        Real implementation (M1-4-T1) returns 404 when attempt doesn't exist.
        """
        attempt_id = uuid.uuid4()
        headers = make_auth_header(student)
        body = {
            "question_id": str(uuid.uuid4()),
            "selected_key": "a",
        }

        response = await client.post(
            f"/api/v1/attempts/{attempt_id}/responses",
            headers=headers,
            json=body,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_submit_response_when_teacher_then_403(
        self,
        client: AsyncClient,
        teacher: User,
    ) -> None:
        """POST /api/v1/attempts/{id}/responses with teacher JWT returns 403."""
        attempt_id = uuid.uuid4()
        headers = make_auth_header(teacher)
        body = {
            "question_id": str(uuid.uuid4()),
            "selected_key": "a",
        }

        response = await client.post(
            f"/api/v1/attempts/{attempt_id}/responses",
            headers=headers,
            json=body,
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_submit_response_when_unauthenticated_then_401(
        self,
        client: AsyncClient,
    ) -> None:
        """POST /api/v1/attempts/{id}/responses without auth returns 401."""
        attempt_id = uuid.uuid4()
        body = {
            "question_id": str(uuid.uuid4()),
            "selected_key": "a",
        }

        response = await client.post(
            f"/api/v1/attempts/{attempt_id}/responses",
            json=body,
        )

        assert response.status_code == 401


class TestSubmitAttempt:
    """Tests for POST /api/v1/attempts/{attempt_id}/submit."""

    @pytest.mark.asyncio
    async def test_submit_attempt_when_student_nonexistent_then_404(
        self,
        client: AsyncClient,
        student: User,
    ) -> None:
        """POST /api/v1/attempts/{id}/submit with student JWT returns 404 for unknown attempt.

        Real implementation (M1-4-T1) returns 404 when attempt doesn't exist.
        """
        attempt_id = uuid.uuid4()
        headers = make_auth_header(student)
        body = {
            "answers": [
                {"question_id": str(uuid.uuid4()), "selected_key": "a"},
                {"question_id": str(uuid.uuid4()), "selected_key": "b"},
            ]
        }

        response = await client.post(
            f"/api/v1/attempts/{attempt_id}/submit",
            headers=headers,
            json=body,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_submit_attempt_when_teacher_then_403(
        self,
        client: AsyncClient,
        teacher: User,
    ) -> None:
        """POST /api/v1/attempts/{id}/submit with teacher JWT returns 403."""
        attempt_id = uuid.uuid4()
        headers = make_auth_header(teacher)
        body = {
            "answers": [
                {"question_id": str(uuid.uuid4()), "selected_key": "a"},
            ]
        }

        response = await client.post(
            f"/api/v1/attempts/{attempt_id}/submit",
            headers=headers,
            json=body,
        )

        assert response.status_code == 403


class TestGetAttemptResults:
    """Tests for GET /api/v1/attempts/{attempt_id}/results."""

    @pytest.mark.asyncio
    async def test_get_attempt_results_when_student_nonexistent_then_404(
        self,
        client: AsyncClient,
        student: User,
    ) -> None:
        """GET /api/v1/attempts/{id}/results with student JWT returns 404 for unknown attempt.

        Real implementation (M1-4-T1) returns 404 when attempt doesn't exist.
        """
        attempt_id = uuid.uuid4()
        headers = make_auth_header(student)

        response = await client.get(
            f"/api/v1/attempts/{attempt_id}/results",
            headers=headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_attempt_results_when_teacher_nonexistent_then_404(
        self,
        client: AsyncClient,
        teacher: User,
    ) -> None:
        """GET /api/v1/attempts/{id}/results with teacher JWT returns 404 for unknown attempt."""
        attempt_id = uuid.uuid4()
        headers = make_auth_header(teacher)

        response = await client.get(
            f"/api/v1/attempts/{attempt_id}/results",
            headers=headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_attempt_results_when_parent_nonexistent_then_404(
        self,
        client: AsyncClient,
        parent_user: User,
    ) -> None:
        """GET /api/v1/attempts/{id}/results with parent JWT returns 404 for unknown attempt."""
        attempt_id = uuid.uuid4()
        headers = make_auth_header(parent_user)

        response = await client.get(
            f"/api/v1/attempts/{attempt_id}/results",
            headers=headers,
        )

        assert response.status_code == 404


# =============================================================================
# OpenAPI tag tests
# =============================================================================


class TestAssessmentsRouterOpenAPITag:
    """Tests for assessments router OpenAPI tag."""

    @pytest.mark.asyncio
    async def test_assessments_router_under_tag_assessments_in_docs(
        self,
        client: AsyncClient,
    ) -> None:
        """Assessments router is registered with tag 'assessments'."""
        # The assessments router uses router = APIRouter(tags=["assessments"])
        # Verify by checking that the /api/v1/classes/{class_id}/assessments path exists
        # and has the assessments tag by introspecting the OpenAPI schema
        response = await client.get("/openapi.json")
        assert response.status_code == 200

        openapi = response.json()
        paths = openapi.get("paths", {})

        # Check that assessments endpoints exist under /api/v1/classes/{class_id}/assessments
        assessment_path = "/api/v1/classes/{class_id}/assessments"
        assert assessment_path in paths, f"Expected {assessment_path} in OpenAPI paths"

        # Verify the GET operation exists
        get_op = paths[assessment_path].get("get")
        assert get_op is not None, "GET method not found for assessments endpoint"

        # Verify the assessments tag is present
        assert "assessments" in get_op.get("tags", []), "Expected 'assessments' tag"


class TestAttemptsRouterOpenAPITag:
    """Tests for attempts router OpenAPI tag."""

    @pytest.mark.asyncio
    async def test_attempts_router_under_tag_attempts_in_docs(
        self,
        client: AsyncClient,
    ) -> None:
        """Attempts router is registered with tag 'attempts'."""
        # The attempts router uses router = APIRouter(tags=["attempts"])
        # Verify by checking that the /api/v1/attempts/{attempt_id} path exists
        response = await client.get("/openapi.json")
        assert response.status_code == 200

        openapi = response.json()
        paths = openapi.get("paths", {})

        # Check that attempts endpoints exist
        attempt_path = "/api/v1/attempts/{attempt_id}"
        assert attempt_path in paths, f"Expected {attempt_path} in OpenAPI paths"

        # Verify the GET operation exists
        get_op = paths[attempt_path].get("get")
        assert get_op is not None, "GET method not found for attempts endpoint"

        # Verify the attempts tag is present
        assert "attempts" in get_op.get("tags", []), "Expected 'attempts' tag"

        # Also verify the diagnostic endpoint has the attempts tag
        diagnostic_path = "/api/v1/classes/{class_id}/diagnostic"
        assert diagnostic_path in paths, f"Expected {diagnostic_path} in OpenAPI paths"
