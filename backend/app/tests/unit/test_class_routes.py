"""Unit tests for class route handlers.

Verifies that the route handler delegates to ClassService and returns
the correct response. Diagnostics are now teacher-designed and NOT
auto-dispatched on class creation.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import get_db
from app.core.deps import get_current_user
from app.main import app
from app.models.user import UserRole


def _make_fake_class(school_id: uuid.UUID) -> SimpleNamespace:
    """Return a minimal object that satisfies _class_to_response."""
    # subject, grade, teacher must have .name / .first_name/.last_name
    # for _class_to_response which accesses class_.subject.name etc.
    subject = SimpleNamespace(name="Math")
    grade = SimpleNamespace(name="Grade 7")
    teacher = SimpleNamespace(first_name="John", last_name="Doe")
    return SimpleNamespace(
        id=uuid.uuid4(),
        school_id=school_id,
        grade_id=uuid.uuid4(),
        subject_id=uuid.uuid4(),
        curriculum_id=uuid.uuid4(),
        teacher_id=uuid.uuid4(),
        name="Math 7A",
        academic_year="2025-2026",
        is_active=True,
        subject=subject,
        grade=grade,
        teacher=teacher,
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
    Assert:  response is 201, service.create_class was called once with correct args.
             No diagnostic dispatch — diagnostics are now teacher-designed.
    """

    fake_admin = MagicMock()
    fake_admin.id = uuid.uuid4()
    fake_admin.school_id = school_id
    fake_admin.role = UserRole.SCHOOL_ADMIN
    fake_admin.is_active = True

    async def _fake_current_user() -> MagicMock:
        return fake_admin

    mock_db = AsyncMock()

    async def _fake_db():  # type: ignore[return]
        yield mock_db

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
                    "academic_year": "2025-2026",
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
    call_args = mock_service_create.call_args
    assert call_args is not None
    assert call_args.args[1].academic_year == "2025-2026"


@pytest.mark.asyncio
async def test_list_classes_route_when_include_inactive_true_then_calls_service_with_flag(
    school_id: uuid.UUID,
    fake_class: SimpleNamespace,
) -> None:
    """GET /schools/{school_id}/classes?include_inactive=true passes flag to service.

    Arrange: SCHOOL_ADMIN user; ClassService.list_classes mocked.
    Act:     GET with include_inactive=true.
    Assert:  service.list_classes called with include_inactive=True.
    """
    from app.core.database import get_db
    from app.core.deps import get_current_user
    from app.main import app

    fake_admin = MagicMock()
    fake_admin.id = uuid.uuid4()
    fake_admin.school_id = school_id
    fake_admin.role = UserRole.SCHOOL_ADMIN

    with (
        patch("app.api.v1.routes.classes.ClassService") as MockService,
        patch(
            "app.api.v1.routes.classes._class_to_response",
            return_value={
                "id": str(fake_class.id),
                "school_id": str(fake_class.school_id),
                "grade_id": str(fake_class.grade_id),
                "subject_id": str(fake_class.subject_id),
                "curriculum_id": str(fake_class.curriculum_id),
                "teacher_id": str(fake_class.teacher_id),
                "name": fake_class.name,
                "academic_year": fake_class.academic_year,
                "is_active": fake_class.is_active,
                "subject_name": "Math",
                "grade_name": "Grade 7",
                "teacher_name": "John Doe",
            },
        ),
    ):
        mock_instance = MockService.return_value
        mock_instance.list_classes = AsyncMock(return_value=[fake_class])

        app.dependency_overrides[get_current_user] = lambda: fake_admin
        app.dependency_overrides[get_db] = lambda: MagicMock()
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                response = await ac.get(
                    f"/api/v1/schools/{school_id}/classes?include_inactive=true",
                    headers={"Authorization": "Bearer fake-token"},
                )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200, response.text
    mock_instance.list_classes.assert_called_once_with(school_id, None, include_inactive=True)


@pytest.mark.asyncio
async def test_list_classes_route_when_teacher_role_then_include_inactive_ignored(
    school_id: uuid.UUID,
    fake_class: SimpleNamespace,
) -> None:
    """Teacher role always gets active-only even if include_inactive=true is sent.

    Arrange: TEACHER user; ClassService.list_classes mocked.
    Act:     GET with include_inactive=true.
    Assert:  service.list_classes called with include_inactive=False.
    """
    from app.core.database import get_db
    from app.core.deps import get_current_user
    from app.main import app

    fake_teacher = MagicMock()
    fake_teacher.id = uuid.uuid4()
    fake_teacher.school_id = school_id
    fake_teacher.role = UserRole.TEACHER

    with patch("app.api.v1.routes.classes.ClassService") as MockService:
        mock_instance = MockService.return_value
        mock_instance.list_classes = AsyncMock(return_value=[fake_class])

        app.dependency_overrides[get_current_user] = lambda: fake_teacher
        app.dependency_overrides[get_db] = lambda: MagicMock()
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                response = await ac.get(
                    f"/api/v1/schools/{school_id}/classes?include_inactive=true",
                    headers={"Authorization": "Bearer fake-token"},
                )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200, response.text
    mock_instance.list_classes.assert_called_once_with(school_id, fake_teacher.id, include_inactive=False)
