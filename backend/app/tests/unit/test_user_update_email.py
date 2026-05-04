"""Unit tests for UserService.update_user with email field."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.schemas.user import UserUpdate
from app.services.user_service import UserService


@pytest.fixture
def school_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.mark.asyncio
async def test_update_user_when_email_provided_and_unique_then_updates_email(
    user_id: uuid.UUID,
    school_id: uuid.UUID,
) -> None:
    """UserService.update_user must update email when it is unique in the school.

    Arrange: user with old email; new email not in use; UserUpdate with new email.
    Act:     call update_user(school_id, user_id, data).
    Assert:  user.email updated to new email; flush called.
    """
    fake_user = SimpleNamespace(
        id=user_id,
        school_id=school_id,
        email="old@school.edu",
        first_name="Amir",
        last_name="Karimi",
        is_active=True,
        hashed_password="hashed",
    )

    mock_db = AsyncMock()
    mock_db.scalar = AsyncMock(return_value=None)  # no conflict

    service = UserService(db=mock_db)

    # Patch get_user to return our fake user
    with patch.object(service, "get_user", return_value=fake_user):
        data = UserUpdate(email="new@school.edu")
        result = await service.update_user(school_id, user_id, data)

    assert result.email == "new@school.edu"
    mock_db.flush.assert_called_once()


@pytest.mark.asyncio
async def test_update_user_when_email_already_taken_then_raises_value_error(
    user_id: uuid.UUID,
    school_id: uuid.UUID,
) -> None:
    """UserService.update_user must raise ValueError when new email is taken.

    Arrange: another user already has the target email.
    Act:     call update_user with that email.
    Assert:  ValueError raised containing 'already registered'.
    """
    fake_user = SimpleNamespace(
        id=user_id,
        school_id=school_id,
        email="old@school.edu",
        first_name="Amir",
        last_name="Karimi",
        is_active=True,
        hashed_password="hashed",
    )

    other_user = SimpleNamespace(id=uuid.uuid4(), email="taken@school.edu")

    mock_db = AsyncMock()
    mock_db.scalar = AsyncMock(return_value=other_user)  # conflict found

    service = UserService(db=mock_db)

    # Patch get_user to return our fake user
    with patch.object(service, "get_user", return_value=fake_user):
        data = UserUpdate(email="taken@school.edu")

        with pytest.raises(ValueError, match="already registered"):
            await service.update_user(school_id, user_id, data)


@pytest.mark.asyncio
async def test_update_user_when_email_same_as_current_then_no_conflict_check(
    user_id: uuid.UUID,
    school_id: uuid.UUID,
) -> None:
    """UserService.update_user must skip uniqueness check when email is unchanged.

    Arrange: user with email@school.edu; UserUpdate with same email.
    Act:     call update_user.
    Assert:  db.execute NOT called for uniqueness check; flush called.
    """
    fake_user = SimpleNamespace(
        id=user_id,
        school_id=school_id,
        email="same@school.edu",
        first_name="Amir",
        last_name="Karimi",
        is_active=True,
        hashed_password="hashed",
    )

    mock_db = AsyncMock()

    service = UserService(db=mock_db)

    # Patch get_user to return our fake user
    with patch.object(service, "get_user", return_value=fake_user):
        data = UserUpdate(email="same@school.edu")
        result = await service.update_user(school_id, user_id, data)

    assert result.email == "same@school.edu"
    # scalar should NOT be called (no conflict check when email unchanged)
    mock_db.scalar.assert_not_called()
    mock_db.flush.assert_called_once()
