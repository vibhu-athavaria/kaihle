"""Integration tests for authentication middleware and route guards.

Fixtures provided by conftest.py.
"""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

import pytest
import pytest_asyncio
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import (
    CurrentUser,
    get_current_user,
    require_onboarding_complete,
    require_role,
    require_school_match,
)
from app.core.security import create_access_token
from app.models.onboarding import StudentLearningProfile
from app.models.school import School
from app.models.user import StudentProfile, User, UserRole

# Set test JWT secret
settings.jwt_secret_key = "test-secret-key-for-testing"


@pytest_asyncio.fixture
async def student_user(db_session: AsyncSession, school: School) -> User:
    """Create a test student user."""
    user = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"student-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Test",
        last_name="Student",
        role=UserRole.STUDENT,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def teacher_user(db_session: AsyncSession, school: School) -> User:
    """Create a test teacher user."""
    user = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"teacher-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Test",
        last_name="Teacher",
        role=UserRole.TEACHER,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def school_admin_user(db_session: AsyncSession, school: School) -> User:
    """Create a test school admin user."""
    user = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"admin-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Test",
        last_name="Admin",
        role=UserRole.SCHOOL_ADMIN,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def kaihle_admin_user(db_session: AsyncSession, school: School) -> User:
    """Create a test Kaihle admin user."""
    user = User(
        id=uuid.uuid4(),
        school_id=school.id,  # Use existing school for FK constraint
        email=f"kaihle-admin-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Kaihle",
        last_name="Admin",
        role=UserRole.KAIHLE_ADMIN,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def inactive_user(db_session: AsyncSession, school: School) -> User:
    """Create an inactive test user."""
    user = User(
        id=uuid.uuid4(),
        school_id=school.id,
        email=f"inactive-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Inactive",
        last_name="User",
        role=UserRole.TEACHER,
        is_active=False,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def student_profile_pending(db_session: AsyncSession, student_user: User) -> StudentProfile:
    """Create a student profile.

    Note: v2.1 - onboarding_diagnostic_status moved to class_enrollments.
    """
    profile = StudentProfile(
        id=uuid.uuid4(),
        user_id=student_user.id,
    )
    db_session.add(profile)
    await db_session.commit()
    return profile


@pytest_asyncio.fixture
async def student_profile_completed(db_session: AsyncSession, student_user: User, school: School) -> StudentProfile:
    """Create a student profile.

    Note: v2.1 - onboarding_diagnostic_status moved to class_enrollments.
    """
    profile = StudentProfile(
        id=uuid.uuid4(),
        user_id=student_user.id,
        is_learning_profile_complete=True,
    )
    db_session.add(profile)
    await db_session.commit()
    return profile


@pytest_asyncio.fixture
async def learning_profile_incomplete(
    db_session: AsyncSession, student_user: User, school: School
) -> StudentLearningProfile:
    """Create an incomplete learning profile (completed_at is NULL)."""
    profile = StudentLearningProfile(
        id=uuid.uuid4(),
        student_id=student_user.id,
        school_id=school.id,
        modality_scores={"visual": 0.8},
        work_style={"prefers_solo": True},
        questionnaire_version="v1",
        completed_at=None,  # Not completed
    )
    db_session.add(profile)
    await db_session.commit()
    return profile


@pytest_asyncio.fixture
async def learning_profile_completed(
    db_session: AsyncSession, student_user: User, school: School
) -> StudentLearningProfile:
    """Create a completed learning profile."""
    profile = StudentLearningProfile(
        id=uuid.uuid4(),
        student_id=student_user.id,
        school_id=school.id,
        modality_scores={"visual": 0.8},
        work_style={"prefers_solo": True},
        questionnaire_version="v1",
        completed_at=datetime.now(UTC),  # Completed
    )
    db_session.add(profile)
    await db_session.commit()
    return profile


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client."""

    # Override the get_db dependency
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# Create a minimal test app with protected endpoints
app = FastAPI(title="Test API")


@app.get("/protected")
async def protected_endpoint(user: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    """A protected endpoint that requires authentication."""
    return {"user_id": str(user.id), "email": user.email, "role": user.role}


@app.get("/teacher-only")
async def teacher_only_endpoint(
    user: CurrentUser = Depends(require_role(UserRole.TEACHER)),
) -> dict[str, Any]:
    """An endpoint that only teachers can access."""
    return {"user_id": str(user.id), "role": user.role}


# For testing require_school_match, we use a fixed school_id since the factory pattern
# requires the school_id to be available at route definition time
# This tests the factory pattern - in production, you'd use a different approach
TEST_SCHOOL_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


@app.get("/school/{school_id}/resource")
async def school_resource_endpoint(
    school_id: uuid.UUID,
    user: CurrentUser = Depends(require_school_match(TEST_SCHOOL_ID)),
) -> dict[str, Any]:
    """An endpoint that requires school match."""
    return {"user_id": str(user.id), "school_id": str(user.school_id)}


@app.get("/student-onboarding")
async def student_onboarding_endpoint(
    user: CurrentUser = Depends(require_onboarding_complete),
) -> dict[str, Any]:
    """An endpoint that requires student onboarding completion."""
    return {"user_id": str(user.id), "onboarding": "complete"}


# =============================================================================
# get_current_user Tests
# =============================================================================


@pytest.mark.asyncio
async def test_request_without_authorization_header_then_401(
    client: AsyncClient,
) -> None:
    """Test that request without Authorization header returns 401."""
    response = await client.get("/protected")
    assert response.status_code == 401  # HTTPBearer returns 401 when no credentials


@pytest.mark.asyncio
async def test_request_with_expired_token_then_401(
    client: AsyncClient,
    teacher_user: User,
) -> None:
    """Test that request with expired token returns 401."""
    # Create an expired token
    expired_token = create_access_token(
        user_id=teacher_user.id,
        school_id=teacher_user.school_id,
        role=teacher_user.role,
        expires_in=-10,  # Already expired
    )
    response = await client.get(
        "/protected",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_request_with_invalid_token_then_401(
    client: AsyncClient,
) -> None:
    """Test that request with invalid token returns 401."""
    response = await client.get(
        "/protected",
        headers={"Authorization": "Bearer invalid-token"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_request_with_valid_token_then_returns_user(
    client: AsyncClient,
    teacher_user: User,
) -> None:
    """Test that request with valid token returns user data."""
    valid_token = create_access_token(
        user_id=teacher_user.id,
        school_id=teacher_user.school_id,
        role=teacher_user.role,
        expires_in=30,
    )
    response = await client.get(
        "/protected",
        headers={"Authorization": f"Bearer {valid_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == str(teacher_user.id)
    assert data["email"] == teacher_user.email


@pytest.mark.asyncio
async def test_request_with_inactive_user_then_401(
    client: AsyncClient,
    inactive_user: User,
) -> None:
    """Test that request with inactive user returns 401."""
    valid_token = create_access_token(
        user_id=inactive_user.id,
        school_id=inactive_user.school_id,
        role=inactive_user.role,
        expires_in=30,
    )
    response = await client.get(
        "/protected",
        headers={"Authorization": f"Bearer {valid_token}"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_request_for_nonexistent_user_then_401(
    client: AsyncClient,
) -> None:
    """Test that request for nonexistent user returns 401."""
    nonexistent_user_id = uuid.uuid4()
    valid_token = create_access_token(
        user_id=nonexistent_user_id,
        school_id=uuid.uuid4(),
        role=UserRole.TEACHER,
        expires_in=30,
    )
    response = await client.get(
        "/protected",
        headers={"Authorization": f"Bearer {valid_token}"},
    )
    assert response.status_code == 401


# =============================================================================
# require_role Tests
# =============================================================================


@pytest.mark.asyncio
async def test_student_calling_teacher_only_route_then_403(
    client: AsyncClient,
    student_user: User,
) -> None:
    """Test that student calling teacher-only route returns 403."""
    valid_token = create_access_token(
        user_id=student_user.id,
        school_id=student_user.school_id,
        role=student_user.role,
        expires_in=30,
    )
    response = await client.get(
        "/teacher-only",
        headers={"Authorization": f"Bearer {valid_token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_teacher_calling_teacher_only_route_then_passes(
    client: AsyncClient,
    teacher_user: User,
) -> None:
    """Test that teacher calling teacher-only route passes."""
    valid_token = create_access_token(
        user_id=teacher_user.id,
        school_id=teacher_user.school_id,
        role=teacher_user.role,
        expires_in=30,
    )
    response = await client.get(
        "/teacher-only",
        headers={"Authorization": f"Bearer {valid_token}"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_school_admin_calling_teacher_only_route_then_403(
    client: AsyncClient,
    school_admin_user: User,
) -> None:
    """Test that school admin calling teacher-only route returns 403."""
    valid_token = create_access_token(
        user_id=school_admin_user.id,
        school_id=school_admin_user.school_id,
        role=school_admin_user.role,
        expires_in=30,
    )
    response = await client.get(
        "/teacher-only",
        headers={"Authorization": f"Bearer {valid_token}"},
    )
    assert response.status_code == 403


# =============================================================================
# require_school_match Tests
# =============================================================================
# Note: require_school_match takes school_id at route definition time, so positive tests
# require the user's school_id to match the hardcoded TEST_SCHOOL_ID used in the route.
# This design limitation means we can only test 403 cases and KAIHLE_ADMIN bypass.
# For proper dynamic school matching, a different pattern would be needed.


@pytest.mark.asyncio
async def test_teacher_accessing_different_school_data_then_403(
    client: AsyncClient,
    teacher_user: User,
    school: School,
) -> None:
    """Test that teacher accessing different school's data returns 403."""
    valid_token = create_access_token(
        user_id=teacher_user.id,
        school_id=teacher_user.school_id,
        role=teacher_user.role,
        expires_in=30,
    )
    # Use a different school ID than the teacher's school
    different_school_id = uuid.uuid4()
    response = await client.get(
        f"/school/{different_school_id}/resource",
        headers={"Authorization": f"Bearer {valid_token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_kaihle_admin_accessing_any_schools_data_then_passes(
    client: AsyncClient,
    kaihle_admin_user: User,
    school: School,
) -> None:
    """Test that KAIHLE_ADMIN can access any school's data."""
    valid_token = create_access_token(
        user_id=kaihle_admin_user.id,
        school_id=kaihle_admin_user.school_id,
        role=kaihle_admin_user.role,
        expires_in=30,
    )
    # Use a completely different school ID
    different_school_id = uuid.uuid4()
    response = await client.get(
        f"/school/{different_school_id}/resource",
        headers={"Authorization": f"Bearer {valid_token}"},
    )
    assert response.status_code == 200


# =============================================================================
# require_onboarding_complete Tests
# =============================================================================


@pytest.mark.asyncio
async def test_student_with_pending_onboarding_then_403(
    client: AsyncClient,
    student_user: User,
    student_profile_pending: StudentProfile,
    school: School,
) -> None:
    """Test that student with PENDING onboarding returns 403."""
    valid_token = create_access_token(
        user_id=student_user.id,
        school_id=student_user.school_id,
        role=student_user.role,
        expires_in=30,
    )
    response = await client.get(
        "/student-onboarding",
        headers={"Authorization": f"Bearer {valid_token}"},
    )
    assert response.status_code == 403
    data = response.json()
    assert "redirect" in data["detail"]


@pytest.mark.asyncio
async def test_student_with_incomplete_learning_profile_then_403(
    client: AsyncClient,
    student_user: User,
    student_profile_pending: StudentProfile,
    learning_profile_incomplete: StudentLearningProfile,
) -> None:
    """Test that student with incomplete learning profile returns 403."""
    valid_token = create_access_token(
        user_id=student_user.id,
        school_id=student_user.school_id,
        role=student_user.role,
        expires_in=30,
    )
    response = await client.get(
        "/student-onboarding",
        headers={"Authorization": f"Bearer {valid_token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_student_with_completed_onboarding_then_passes(
    client: AsyncClient,
    student_user: User,
    student_profile_completed: StudentProfile,
    learning_profile_completed: StudentLearningProfile,
) -> None:
    """Test that student with completed onboarding passes."""
    valid_token = create_access_token(
        user_id=student_user.id,
        school_id=student_user.school_id,
        role=student_user.role,
        expires_in=30,
    )
    response = await client.get(
        "/student-onboarding",
        headers={"Authorization": f"Bearer {valid_token}"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_teacher_calling_student_route_then_passes_without_check(
    client: AsyncClient,
    teacher_user: User,
) -> None:
    """Test that teacher calling student route passes without onboarding check."""
    valid_token = create_access_token(
        user_id=teacher_user.id,
        school_id=teacher_user.school_id,
        role=teacher_user.role,
        expires_in=30,
    )
    response = await client.get(
        "/student-onboarding",
        headers={"Authorization": f"Bearer {valid_token}"},
    )
    # Teacher should pass through without any onboarding check
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_school_admin_calling_student_route_then_passes_without_check(
    client: AsyncClient,
    school_admin_user: User,
) -> None:
    """Test that school admin calling student route passes without onboarding check."""
    valid_token = create_access_token(
        user_id=school_admin_user.id,
        school_id=school_admin_user.school_id,
        role=school_admin_user.role,
        expires_in=30,
    )
    response = await client.get(
        "/student-onboarding",
        headers={"Authorization": f"Bearer {valid_token}"},
    )
    # School admin should pass through without any onboarding check
    assert response.status_code == 200
