"""Unit tests for ClassService.update_class."""

import uuid
from collections.abc import Generator
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import get_db
from app.core.deps import get_current_user
from app.main import app
from app.models.user import UserRole
from app.schemas.class_enrollment import ClassUpdate
from app.services.class_service import ClassService
from app.services.workspace_service import WorkspaceRestrictionError


@pytest.fixture(autouse=True)
def allow_any_class_teacher() -> Generator[AsyncMock, None, None]:
    """Treat every school as a real school. Workspace rules are tested in test_workspace_service.py."""
    with patch("app.services.class_service.assert_class_teacher_allowed", new=AsyncMock()) as guard:
        yield guard


@pytest.fixture
def school_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def class_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def teacher_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.mark.asyncio
async def test_update_class_when_valid_data_then_updates_fields_and_returns_class(
    class_id: uuid.UUID,
    school_id: uuid.UUID,
    teacher_id: uuid.UUID,
) -> None:
    """ClassService.update_class must apply only the provided fields and return the class.

    Arrange: fake Class with original values; ClassUpdate with new name + teacher_id.
    Act:     call update_class(class_id, school_id, data).
    Assert:  class.name updated, class.teacher_id updated, academic_year unchanged,
             db.flush called once.
    """
    fake_class = SimpleNamespace(
        id=class_id,
        school_id=school_id,
        name="Old Name",
        teacher_id=uuid.uuid4(),
        academic_year="2024/2025",
        is_active=True,
    )

    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=fake_class)
    # The new teacher is an active TEACHER in the same school.
    mock_db.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=SimpleNamespace(id=teacher_id)))
    )

    service = ClassService(db=mock_db)
    data = ClassUpdate(name="New Name", teacher_id=teacher_id)

    result = await service.update_class(class_id, school_id, data)

    assert result.name == "New Name"
    assert result.teacher_id == teacher_id
    assert result.academic_year == "2024/2025"  # unchanged
    mock_db.flush.assert_called_once()


@pytest.mark.asyncio
async def test_update_class_when_class_not_found_then_raises_value_error(
    class_id: uuid.UUID,
    school_id: uuid.UUID,
) -> None:
    """ClassService.update_class must raise ValueError when class_id not found.

    Arrange: db.get returns None.
    Act:     call update_class with unknown class_id.
    Assert:  ValueError raised.
    """
    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=None)

    service = ClassService(db=mock_db)
    data = ClassUpdate(name="Anything")

    with pytest.raises(ValueError, match="Class not found"):
        await service.update_class(class_id, school_id, data)


@pytest.mark.asyncio
async def test_update_class_when_wrong_school_then_raises_value_error(
    class_id: uuid.UUID,
    school_id: uuid.UUID,
) -> None:
    """ClassService.update_class must raise ValueError when class belongs to a different school.

    Arrange: class_.school_id != school_id passed in.
    Act:     call update_class.
    Assert:  ValueError raised (403-equivalent — cross-school access denied).
    """
    fake_class = SimpleNamespace(
        id=class_id,
        school_id=uuid.uuid4(),  # different school
        name="Name",
        teacher_id=uuid.uuid4(),
        academic_year="2024/2025",
        is_active=True,
    )

    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=fake_class)

    service = ClassService(db=mock_db)

    with pytest.raises(ValueError, match="Class not found"):
        await service.update_class(class_id, school_id, ClassUpdate(name="X"))


@pytest.mark.asyncio
async def test_patch_class_route_when_valid_then_returns_200(
    class_id: uuid.UUID,
    school_id: uuid.UUID,
    teacher_id: uuid.UUID,
) -> None:
    """PATCH /classes/{class_id} must return 200 and delegate to ClassService.update_class.

    Arrange: SCHOOL_ADMIN user; ClassService.update_class mocked.
    Act:     PATCH /api/v1/classes/{class_id} with { name: "New Name" }.
    Assert:  200 response, service.update_class called once.
    """
    fake_admin = MagicMock()
    fake_admin.id = uuid.uuid4()
    fake_admin.school_id = school_id
    fake_admin.role = UserRole.SCHOOL_ADMIN
    fake_admin.is_active = True

    fake_class = SimpleNamespace(
        id=class_id,
        school_id=school_id,
        grade_id=uuid.uuid4(),
        subject_id=uuid.uuid4(),
        curriculum_id=uuid.uuid4(),
        teacher_id=teacher_id,
        name="New Name",
        academic_year="2024/2025",
        is_active=True,
        subject=SimpleNamespace(name="Math"),
        grade=SimpleNamespace(name="Grade 7"),
        teacher=SimpleNamespace(first_name="John", last_name="Doe"),
    )

    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()

    async def _fake_db():
        yield mock_db

    async def _fake_user():
        return fake_admin

    mock_update = AsyncMock(return_value=fake_class)

    with patch("app.api.v1.routes.classes.ClassService") as MockService:
        MockService.return_value.update_class = mock_update

        app.dependency_overrides[get_db] = _fake_db
        app.dependency_overrides[get_current_user] = _fake_user

        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.patch(
                    f"/api/v1/classes/{class_id}",
                    json={"name": "New Name"},
                )
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"
    mock_update.assert_called_once()


@pytest.mark.asyncio
async def test_update_class_when_teacher_not_in_school_then_raises_value_error(
    class_id: uuid.UUID,
    school_id: uuid.UUID,
    teacher_id: uuid.UUID,
) -> None:
    """update_class must refuse a teacher_id that is not an active TEACHER in the class's school.

    Arrange: class in school_id; the teacher lookup finds nothing (teacher from another school).
    Act:     call update_class with that teacher_id.
    Assert:  ValueError, teacher_id unchanged, no flush.
    """
    original_teacher = uuid.uuid4()
    fake_class = SimpleNamespace(id=class_id, school_id=school_id, name="Maths", teacher_id=original_teacher)
    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=fake_class)
    mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

    service = ClassService(db=mock_db)

    with pytest.raises(ValueError, match="Teacher not found"):
        await service.update_class(class_id, school_id, ClassUpdate(teacher_id=teacher_id))

    assert fake_class.teacher_id == original_teacher
    mock_db.flush.assert_not_called()


@pytest.mark.asyncio
async def test_update_class_when_workspace_rejects_teacher_then_raises_restriction_and_keeps_teacher(
    class_id: uuid.UUID,
    school_id: uuid.UUID,
    teacher_id: uuid.UUID,
    allow_any_class_teacher: AsyncMock,
) -> None:
    """update_class applies the workspace class-teacher rule (rule tested in test_workspace_service.py)."""
    original_teacher = uuid.uuid4()
    fake_class = SimpleNamespace(id=class_id, school_id=school_id, name="Maths", teacher_id=original_teacher)
    teacher = SimpleNamespace(id=teacher_id, school_id=school_id, role=UserRole.TEACHER)
    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=fake_class)
    mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=teacher)))
    allow_any_class_teacher.side_effect = WorkspaceRestrictionError("not the owner")

    service = ClassService(db=mock_db)

    with pytest.raises(WorkspaceRestrictionError):
        await service.update_class(class_id, school_id, ClassUpdate(teacher_id=teacher_id))

    allow_any_class_teacher.assert_awaited_once_with(mock_db, school_id, teacher_id)
    assert fake_class.teacher_id == original_teacher
    mock_db.flush.assert_not_called()
