"""Unit tests for ClassService.unenroll_students."""

import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import get_db
from app.core.deps import get_current_user
from app.main import app
from app.models.user import UserRole
from app.services.class_service import ClassService


@pytest.fixture
def school_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def class_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.mark.asyncio
async def test_unenroll_students_when_valid_then_sets_is_active_false(
    class_id: uuid.UUID,
    school_id: uuid.UUID,
) -> None:
    """ClassService.unenroll_students must soft-delete the matching enrollments.

    Arrange: two enrollments, one matching student_id passed in.
    Act:     call unenroll_students(class_id, school_id, [student_id]).
    Assert:  matching enrollment.is_active = False; non-matching unchanged; flush called.
    """
    student_to_remove = uuid.uuid4()
    student_to_keep = uuid.uuid4()

    enrollment_remove = SimpleNamespace(class_id=class_id, student_id=student_to_remove, is_active=True)
    enrollment_keep = SimpleNamespace(class_id=class_id, student_id=student_to_keep, is_active=True)

    fake_class = SimpleNamespace(id=class_id, school_id=school_id)

    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=fake_class)

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [enrollment_remove]
    mock_db.execute = AsyncMock(return_value=mock_result)

    service = ClassService(db=mock_db)
    await service.unenroll_students(class_id, school_id, [student_to_remove])

    assert enrollment_remove.is_active is False
    assert enrollment_keep.is_active is True
    mock_db.flush.assert_called_once()


@pytest.mark.asyncio
async def test_unenroll_students_when_class_not_found_then_raises_value_error(
    class_id: uuid.UUID,
    school_id: uuid.UUID,
) -> None:
    """ClassService.unenroll_students must raise ValueError when class not found.

    Arrange: db.get returns None.
    Act:     call unenroll_students.
    Assert:  ValueError raised with 'Class not found'.
    """
    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=None)

    service = ClassService(db=mock_db)

    with pytest.raises(ValueError, match="Class not found"):
        await service.unenroll_students(class_id, school_id, [uuid.uuid4()])


@pytest.mark.asyncio
async def test_unenroll_students_when_wrong_school_then_raises_value_error(
    class_id: uuid.UUID,
    school_id: uuid.UUID,
) -> None:
    """ClassService.unenroll_students must raise ValueError when class belongs to different school.

    Arrange: class_.school_id != school_id.
    Act:     call unenroll_students.
    Assert:  ValueError raised with 'Class not found'.
    """
    fake_class = SimpleNamespace(id=class_id, school_id=uuid.uuid4())  # different school

    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=fake_class)

    service = ClassService(db=mock_db)

    with pytest.raises(ValueError, match="Class not found"):
        await service.unenroll_students(class_id, school_id, [uuid.uuid4()])


@pytest.mark.asyncio
async def test_delete_enrollments_route_when_valid_then_returns_204(
    class_id: uuid.UUID,
    school_id: uuid.UUID,
) -> None:
    """DELETE /classes/{class_id}/enrollments must return 204 and delegate to ClassService.

    Arrange: SCHOOL_ADMIN user; ClassService.unenroll_students mocked.
    Act:     DELETE /api/v1/classes/{class_id}/enrollments with { student_ids: [...] }.
    Assert:  204 response, service.unenroll_students called once.
    """
    student_id = uuid.uuid4()

    fake_admin = MagicMock()
    fake_admin.id = uuid.uuid4()
    fake_admin.school_id = school_id
    fake_admin.role = UserRole.SCHOOL_ADMIN
    fake_admin.is_active = True

    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()

    async def _fake_db():
        yield mock_db

    async def _fake_user():
        return fake_admin

    mock_unenroll = AsyncMock(return_value=None)

    with patch("app.api.v1.routes.classes.ClassService") as MockService:
        MockService.return_value.unenroll_students = mock_unenroll

        app.dependency_overrides[get_db] = _fake_db
        app.dependency_overrides[get_current_user] = _fake_user

        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.request(
                    "DELETE",
                    f"/api/v1/classes/{class_id}/enrollments",
                    content=json.dumps({"student_ids": [str(student_id)]}),
                    headers={"Content-Type": "application/json"},
                )
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 204
    mock_unenroll.assert_called_once()
