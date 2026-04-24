"""Unit tests for class route handlers.

Verifies that the route handler delegates to ClassService and returns
the correct response. Task dispatch is now owned by the service layer
and tested in test_class_service.py.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.models.user import UserRole


def _make_fake_class(school_id: uuid.UUID) -> SimpleNamespace:
    """Return a minimal object that satisfies _class_to_response."""
    return SimpleNamespace(
        id=uuid.uuid4(),
        school_id=school_id,
        grade_id=uuid.uuid4(),
        subject_id=uuid.uuid4(),
        curriculum_id=uuid.uuid4(),
        teacher_id=uuid.uuid4(),
        name="Math 7A",
        academic_year="2026",
        is_active=True,
    )


@pytest.fixture
def school_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def fake_class(school_id: uuid.UUID) -> SimpleNamespace:
    return _make_fake_class(school_id)


@pytest.mark.asyncio
async def test_create_class_when_valid_payload_then_delegates_to_service_and_returns_201(
    school_id: uuid.UUID,
    fake_class: SimpleNamespace,
) -> None:
    """POST /schools/{school_id}/classes must return 201 and delegate to ClassService.

    Arrange: get_current_user overridden to return a SCHOOL_ADMIN for this school.
             ClassService.create_class mocked to return fake_class.
    Act:     POST to /api/v1/schools/{school_id}/classes with valid payload.
    Assert:  response is 201, service.create_class was called once.
             (Diagnostic task dispatch is tested in test_class_service.py, not here.)
    """
    from app.core.database import get_db
    from app.core.deps import get_current_user
    from app.main import app

    # Build a fake SCHOOL_ADMIN user object (real User model not needed — route only checks role/school_id)
    fake_admin = MagicMock()
    fake_admin.id = uuid.uuid4()
    fake_admin.school_id = school_id
    fake_admin.role = UserRole.SCHOOL_ADMIN
    fake_admin.is_active = True

    # Override auth dependency so no DB lookup happens
    async def _fake_current_user() -> MagicMock:
        return fake_admin

    # Override DB — provide an AsyncMock so any awaited call succeeds
    mock_db = AsyncMock()

    async def _fake_db():  # type: ignore[return]
        yield mock_db

    # Mock ClassService.create_class to return our fake class
    mock_service_create = AsyncMock(return_value=fake_class)

    with patch("app.api.v1.routes.classes.ClassService") as MockService:
        MockService.return_value.create_class = mock_service_create

        app.dependency_overrides[get_db] = _fake_db
        app.dependency_overrides[get_current_user] = _fake_current_user
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                payload = {
                    "name": "Math 7A",
                    "grade_id": str(uuid.uuid4()),
                    "subject_id": str(uuid.uuid4()),
                    "curriculum_id": str(uuid.uuid4()),
                    "teacher_id": str(uuid.uuid4()),
                    "academic_year": "2026",
                }
                response = await ac.post(
                    f"/api/v1/schools/{school_id}/classes",
                    json=payload,
                    headers={"Authorization": "Bearer fake-token"},
                )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 201, response.text
    mock_service_create.assert_called_once()
    # Task dispatch is now in ClassService.create_class — verified in test_class_service.py
