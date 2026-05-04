"""Unit tests for user grade_id update functionality."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import StudentProfile, User, UserRole
from app.schemas.user import UserUpdate
from app.services.user_service import UserService


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return MagicMock(spec=AsyncSession)


@pytest.fixture
def user_service(mock_db):
    """Create a UserService instance with mock db."""
    return UserService(db=mock_db)


@pytest.fixture
def sample_student_user():
    """Create a sample student user for testing."""
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.email = "student@example.com"
    user.first_name = "John"
    user.last_name = "Doe"
    user.role = UserRole.STUDENT
    user.school_id = uuid.uuid4()
    user.is_active = True
    user.hashed_password = "hashed_password"
    return user


@pytest.fixture
def sample_student_profile():
    """Create a sample student profile for testing."""
    profile = MagicMock(spec=StudentProfile)
    profile.id = uuid.uuid4()
    profile.user_id = uuid.uuid4()
    profile.grade_id = uuid.uuid4()
    profile.age = 12
    profile.is_learning_profile_complete = False
    return profile


@pytest.mark.asyncio
async def test_update_user_when_grade_id_provided_then_updates_student_profile(
    mock_db, user_service, sample_student_user, sample_student_profile
):
    """Test that update_user updates student profile grade_id when provided."""
    # Arrange
    school_id = sample_student_user.school_id
    user_id = sample_student_user.id
    new_grade_id = uuid.uuid4()

    update_data = UserUpdate(
        first_name="Jane",
        grade_id=new_grade_id,
    )

    # Mock get_user to return the student
    user_service.get_user = AsyncMock(return_value=sample_student_user)

    # Mock the scalar query for StudentProfile
    mock_db.scalar = AsyncMock(return_value=sample_student_profile)

    # Act
    result = await user_service.update_user(school_id, user_id, update_data)

    # Assert
    assert result.first_name == "Jane"
    assert sample_student_profile.grade_id == new_grade_id
    mock_db.flush.assert_called_once()


@pytest.mark.asyncio
async def test_update_user_when_grade_id_provided_and_no_profile_then_raises_value_error(
    mock_db, user_service, sample_student_user
):
    """Test that update_user raises ValueError when grade_id provided but no student profile."""
    # Arrange
    school_id = sample_student_user.school_id
    user_id = sample_student_user.id
    new_grade_id = uuid.uuid4()

    update_data = UserUpdate(
        first_name="Jane",
        grade_id=new_grade_id,
    )

    # Mock get_user to return the student
    user_service.get_user = AsyncMock(return_value=sample_student_user)

    # Mock the scalar query to return None (no profile found)
    mock_db.scalar = AsyncMock(return_value=None)

    # Act & Assert
    with pytest.raises(ValueError, match="Student profile not found"):
        await user_service.update_user(school_id, user_id, update_data)
