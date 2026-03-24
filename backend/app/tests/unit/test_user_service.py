"""Unit tests for UserService."""

import uuid
from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole
from app.schemas.user import UserInvite, UserSelfUpdate, UserUpdate
from app.services.user_service import UserService


@pytest.fixture
def mock_db() -> Generator[MagicMock, None, None]:
    """Create a mock database session."""
    session = MagicMock(spec=AsyncSession)
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.scalar = AsyncMock()
    session.get = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def user_service(mock_db: MagicMock) -> UserService:
    """Create a UserService with mock database."""
    return UserService(mock_db)


@pytest.fixture
def school_id() -> uuid.UUID:
    """Create a test school UUID."""
    return uuid.uuid4()


@pytest.fixture
def user_invite_data() -> UserInvite:
    """Create test UserInvite data."""
    return UserInvite(
        email="newteacher@school.com",
        role=UserRole.TEACHER,
        first_name="John",
        last_name="Doe",
        subjects=["Mathematics", "Science"],
    )


class TestInviteUser:
    """Tests for UserService.invite_user method."""

    @pytest.mark.asyncio
    async def test_invite_user_when_valid_teacher_then_user_created(
        self, user_service: UserService, mock_db: MagicMock, school_id: uuid.UUID, user_invite_data: UserInvite
    ) -> None:
        """Test inviting a valid teacher creates user and profile."""
        # Arrange
        mock_db.scalar = AsyncMock(return_value=None)  # No existing user

        # Act
        with (
            patch("app.services.user_service.create_magic_link_token") as mock_token,
            patch("app.services.user_service.hash_token") as mock_hash,
            patch("app.services.user_service.store_magic_link_token") as mock_store,
            patch("app.services.user_service.UserService._send_welcome_email"),
        ):
            mock_token.return_value = "test_token_123"
            mock_hash.return_value = "hashed_token"
            mock_store.return_value = MagicMock()

            result = await user_service.invite_user(school_id, user_invite_data, "https://app.kaihle.com")

        # Assert
        assert result is not None
        assert result.email == user_invite_data.email
        assert result.role == user_invite_data.role
        assert result.first_name == user_invite_data.first_name
        assert result.last_name == user_invite_data.last_name
        assert result.school_id == school_id
        assert result.is_active is True
        mock_db.add.assert_called()
        mock_db.flush.assert_called()

    @pytest.mark.asyncio
    async def test_invite_user_when_invalid_role_then_raises_value_error(
        self, user_service: UserService, mock_db: MagicMock, school_id: uuid.UUID
    ) -> None:
        """Test that inviting user with invalid role raises ValueError."""
        # Arrange
        invalid_data = UserInvite(
            email="user@school.com",
            role=UserRole.STUDENT,  # Not in allowed roles
            first_name="John",
            last_name="Doe",
        )

        # Act & Assert
        with pytest.raises(ValueError, match="Cannot invite user with role"):
            await user_service.invite_user(school_id, invalid_data, "https://app.kaihle.com")

    @pytest.mark.asyncio
    async def test_invite_user_when_duplicate_email_then_raises_value_error(
        self, user_service: UserService, mock_db: MagicMock, school_id: uuid.UUID, user_invite_data: UserInvite
    ) -> None:
        """Test that duplicate email in same school raises ValueError."""
        # Arrange
        existing_user = User(
            id=uuid.uuid4(),
            email=user_invite_data.email,
            school_id=school_id,
        )
        mock_db.scalar = AsyncMock(return_value=existing_user)

        # Act & Assert
        with pytest.raises(ValueError, match="already registered at this school"):
            await user_service.invite_user(school_id, user_invite_data, "https://app.kaihle.com")

    @pytest.mark.asyncio
    async def test_invite_user_when_school_admin_role_then_creates_user(
        self, user_service: UserService, mock_db: MagicMock, school_id: uuid.UUID
    ) -> None:
        """Test that school admin can be invited."""
        # Arrange
        admin_data = UserInvite(
            email="admin@school.com",
            role=UserRole.SCHOOL_ADMIN,
            first_name="Admin",
            last_name="User",
        )
        mock_db.scalar = AsyncMock(return_value=None)

        # Act
        with (
            patch("app.services.user_service.create_magic_link_token") as mock_token,
            patch("app.services.user_service.hash_token") as mock_hash,
            patch("app.services.user_service.store_magic_link_token") as mock_store,
            patch("app.services.user_service.UserService._send_welcome_email"),
        ):
            mock_token.return_value = "test_token_123"
            mock_hash.return_value = "hashed_token"
            mock_store.return_value = MagicMock()

            result = await user_service.invite_user(school_id, admin_data, "https://app.kaihle.com")

        # Assert
        assert result.role == UserRole.SCHOOL_ADMIN

    @pytest.mark.asyncio
    async def test_invite_user_when_parent_role_then_creates_user(
        self, user_service: UserService, mock_db: MagicMock, school_id: uuid.UUID
    ) -> None:
        """Test that parent can be invited."""
        # Arrange
        parent_data = UserInvite(
            email="parent@school.com",
            role=UserRole.PARENT,
            first_name="Parent",
            last_name="User",
        )
        mock_db.scalar = AsyncMock(return_value=None)

        # Act
        with (
            patch("app.services.user_service.create_magic_link_token") as mock_token,
            patch("app.services.user_service.hash_token") as mock_hash,
            patch("app.services.user_service.store_magic_link_token") as mock_store,
            patch("app.services.user_service.UserService._send_welcome_email"),
        ):
            mock_token.return_value = "test_token_123"
            mock_hash.return_value = "hashed_token"
            mock_store.return_value = MagicMock()

            result = await user_service.invite_user(school_id, parent_data, "https://app.kaihle.com")

        # Assert
        assert result.role == UserRole.PARENT

    @pytest.mark.asyncio
    async def test_invite_user_when_student_role_then_raises_value_error(
        self, user_service: UserService, mock_db: MagicMock, school_id: uuid.UUID
    ) -> None:
        """Test that student cannot be invited via user invitation (must use enrollment flow)."""
        # Arrange
        student_data = UserInvite(
            email="student@school.com",
            role=UserRole.STUDENT,  # Not in allowed roles for invitation
            first_name="Student",
            last_name="User",
        )

        # Act & Assert
        with pytest.raises(ValueError, match="Cannot invite user with role"):
            await user_service.invite_user(school_id, student_data, "https://app.kaihle.com")

    @pytest.mark.asyncio
    async def test_invite_user_when_teacher_with_subjects_then_creates_teacher_profile(
        self, user_service: UserService, mock_db: MagicMock, school_id: uuid.UUID
    ) -> None:
        """Test that teacher with subjects gets TeacherProfile created."""
        # Arrange
        teacher_data = UserInvite(
            email="teacher@school.com",
            role=UserRole.TEACHER,
            first_name="Teacher",
            last_name="User",
            subjects=["Mathematics", "Science"],
        )
        mock_db.scalar = AsyncMock(return_value=None)

        created_user: User | None = None

        def capture_add(obj: Any) -> None:
            nonlocal created_user
            if isinstance(obj, User):
                created_user = obj

        mock_db.add = MagicMock(side_effect=capture_add)

        # Act
        with (
            patch("app.services.user_service.create_magic_link_token") as mock_token,
            patch("app.services.user_service.hash_token") as mock_hash,
            patch("app.services.user_service.store_magic_link_token") as mock_store,
            patch("app.services.user_service.UserService._send_welcome_email"),
        ):
            mock_token.return_value = "test_token_123"
            mock_hash.return_value = "hashed_token"
            mock_store.return_value = MagicMock()

            await user_service.invite_user(school_id, teacher_data, "https://app.kaihle.com")

        # Assert - TeacherProfile should be added
        calls = mock_db.add.call_args_list
        assert len(calls) == 2  # User + TeacherProfile


class TestListUsers:
    """Tests for UserService.list_users method."""

    @pytest.mark.asyncio
    async def test_list_users_when_no_filter_then_returns_all_active_users(
        self, user_service: UserService, mock_db: MagicMock, school_id: uuid.UUID
    ) -> None:
        """Test listing all active users in a school."""
        # Arrange
        users = [
            User(
                id=uuid.uuid4(),
                email="user1@school.com",
                first_name="User",
                last_name="One",
                role=UserRole.TEACHER,
                school_id=school_id,
                is_active=True,
            ),
            User(
                id=uuid.uuid4(),
                email="user2@school.com",
                first_name="User",
                last_name="Two",
                role=UserRole.SCHOOL_ADMIN,
                school_id=school_id,
                is_active=True,
            ),
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = users
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.scalar = AsyncMock(return_value=2)

        # Act
        result_users, total = await user_service.list_users(school_id)

        # Assert
        assert len(result_users) == 2
        assert total == 2

    @pytest.mark.asyncio
    async def test_list_users_when_role_filter_then_returns_filtered_users(
        self, user_service: UserService, mock_db: MagicMock, school_id: uuid.UUID
    ) -> None:
        """Test listing users with role filter."""
        # Arrange
        teachers = [
            User(
                id=uuid.uuid4(),
                email="teacher1@school.com",
                first_name="Teacher",
                last_name="One",
                role=UserRole.TEACHER,
                school_id=school_id,
                is_active=True,
            ),
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = teachers
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.scalar = AsyncMock(return_value=1)

        # Act
        result_users, total = await user_service.list_users(school_id, role="TEACHER")

        # Assert
        assert len(result_users) == 1
        assert result_users[0].role == "TEACHER"

    @pytest.mark.asyncio
    async def test_list_users_when_pagination_then_returns_correct_page(
        self, user_service: UserService, mock_db: MagicMock, school_id: uuid.UUID
    ) -> None:
        """Test pagination parameters are applied correctly."""
        # Arrange
        users = [
            User(
                id=uuid.uuid4(),
                email=f"user{i}@school.com",
                first_name="User",
                last_name=str(i),
                role=UserRole.TEACHER,
                school_id=school_id,
                is_active=True,
            )
            for i in range(20)
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = users[10:20]  # page 2
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.scalar = AsyncMock(return_value=50)

        # Act
        result_users, total = await user_service.list_users(school_id, page=2, page_size=10)

        # Assert
        assert len(result_users) == 10
        assert total == 50


class TestGetUser:
    """Tests for UserService.get_user method."""

    @pytest.mark.asyncio
    async def test_get_user_when_exists_then_returns_user(
        self, user_service: UserService, mock_db: MagicMock, school_id: uuid.UUID
    ) -> None:
        """Test getting an existing user."""
        # Arrange
        user_id = uuid.uuid4()
        expected_user = User(
            id=user_id,
            email="user@school.com",
            first_name="User",
            last_name="Test",
            role=UserRole.TEACHER,
            school_id=school_id,
            is_active=True,
        )
        mock_db.scalar = AsyncMock(return_value=expected_user)

        # Act
        result = await user_service.get_user(school_id, user_id)

        # Assert
        assert result.id == user_id

    @pytest.mark.asyncio
    async def test_get_user_when_not_exists_then_raises_not_found(
        self, user_service: UserService, mock_db: MagicMock, school_id: uuid.UUID
    ) -> None:
        """Test getting non-existent user raises ValueError."""
        # Arrange
        user_id = uuid.uuid4()
        mock_db.scalar = AsyncMock(return_value=None)

        # Act & Assert
        with pytest.raises(ValueError, match="User not found"):
            await user_service.get_user(school_id, user_id)

    @pytest.mark.asyncio
    async def test_get_user_when_wrong_school_then_raises_not_found(
        self, user_service: UserService, mock_db: MagicMock, school_id: uuid.UUID
    ) -> None:
        """Test getting user from different school raises ValueError.

        Note: With the new query using both user_id and school_id, if the user
        belongs to a different school, the query returns None (not the user),
        so this correctly raises ValueError.
        """
        # Arrange - scalar returns None because query with wrong school returns nothing
        user_id = uuid.uuid4()
        mock_db.scalar = AsyncMock(return_value=None)

        # Act & Assert
        with pytest.raises(ValueError, match="User not found"):
            await user_service.get_user(school_id, user_id)


class TestUpdateUser:
    """Tests for UserService.update_user method."""

    @pytest.mark.asyncio
    async def test_update_user_when_valid_data_then_updates_user(
        self, user_service: UserService, mock_db: MagicMock, school_id: uuid.UUID
    ) -> None:
        """Test updating user with valid data."""
        # Arrange
        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            email="user@school.com",
            first_name="OldName",
            last_name="LastName",
            role=UserRole.TEACHER,
            school_id=school_id,
            is_active=True,
        )
        mock_db.scalar = AsyncMock(return_value=user)

        update_data = UserUpdate(first_name="NewName")

        # Act
        result = await user_service.update_user(school_id, user_id, update_data)

        # Assert
        assert result.first_name == "NewName"
        mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_user_when_not_exists_then_raises_not_found(
        self, user_service: UserService, mock_db: MagicMock, school_id: uuid.UUID
    ) -> None:
        """Test updating non-existent user raises ValueError."""
        # Arrange
        user_id = uuid.uuid4()
        mock_db.scalar = AsyncMock(return_value=None)

        update_data = UserUpdate(first_name="NewName")

        # Act & Assert
        with pytest.raises(ValueError, match="User not found"):
            await user_service.update_user(school_id, user_id, update_data)


class TestDeactivateUser:
    """Tests for UserService.deactivate_user method."""

    @pytest.mark.asyncio
    async def test_deactivate_user_when_active_then_sets_inactive(
        self, user_service: UserService, mock_db: MagicMock, school_id: uuid.UUID
    ) -> None:
        """Test deactivating a user sets is_active to False."""
        # Arrange
        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            email="user@school.com",
            first_name="User",
            last_name="Test",
            role=UserRole.TEACHER,
            school_id=school_id,
            is_active=True,
        )
        mock_db.scalar = AsyncMock(return_value=user)

        # Act
        await user_service.deactivate_user(school_id, user_id)

        # Assert
        assert user.is_active is False
        mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_deactivate_user_when_not_exists_then_raises_not_found(
        self, user_service: UserService, mock_db: MagicMock, school_id: uuid.UUID
    ) -> None:
        """Test deactivating non-existent user raises ValueError."""
        # Arrange
        user_id = uuid.uuid4()
        mock_db.scalar = AsyncMock(return_value=None)

        # Act & Assert
        with pytest.raises(ValueError, match="User not found"):
            await user_service.deactivate_user(school_id, user_id)


# ==============================================================================
# Tests for get_me()
# ==============================================================================


class TestGetMe:
    """Tests for UserService.get_me method."""

    @pytest.mark.asyncio
    async def test_get_me_when_user_exists_then_returns_user(
        self,
        user_service: UserService,
        mock_db: MagicMock,
        school_id: uuid.UUID,
    ) -> None:
        """Test get_me returns user when user exists."""
        # Arrange
        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            email="me@school.com",
            first_name="Me",
            last_name="User",
            role=UserRole.TEACHER,
            school_id=school_id,
            is_active=True,
        )
        mock_db.get = AsyncMock(return_value=user)

        # Act
        result = await user_service.get_me(user_id)

        # Assert
        assert result == user
        mock_db.get.assert_called_once_with(User, user_id)

    @pytest.mark.asyncio
    async def test_get_me_when_user_not_found_then_raises_error(
        self,
        user_service: UserService,
        mock_db: MagicMock,
    ) -> None:
        """Test get_me raises ValueError when user not found."""
        # Arrange
        user_id = uuid.uuid4()
        mock_db.get = AsyncMock(return_value=None)

        # Act & Assert
        with pytest.raises(ValueError, match="User not found"):
            await user_service.get_me(user_id)


# ==============================================================================
# Tests for update_me()
# ==============================================================================


class TestUpdateMe:
    """Tests for UserService.update_me method."""

    @pytest.mark.asyncio
    async def test_update_me_when_valid_first_name_then_updates(
        self,
        user_service: UserService,
        mock_db: MagicMock,
        school_id: uuid.UUID,
    ) -> None:
        """Test update_me updates first_name when valid."""
        # Arrange
        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            email="me@school.com",
            first_name="OldFirst",
            last_name="LastName",
            role=UserRole.TEACHER,
            school_id=school_id,
            is_active=True,
        )
        mock_db.get = AsyncMock(return_value=user)
        data = UserSelfUpdate(first_name="NewFirst")

        # Act
        result = await user_service.update_me(
            user_id=user_id,
            data=data,
        )

        # Assert
        assert result.first_name == "NewFirst"
        assert result.last_name == "LastName"
        mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_me_when_valid_last_name_then_updates(
        self,
        user_service: UserService,
        mock_db: MagicMock,
        school_id: uuid.UUID,
    ) -> None:
        """Test update_me updates last_name when valid."""
        # Arrange
        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            email="me@school.com",
            first_name="FirstName",
            last_name="OldLast",
            role=UserRole.TEACHER,
            school_id=school_id,
            is_active=True,
        )
        mock_db.get = AsyncMock(return_value=user)
        data = UserSelfUpdate(last_name="NewLast")

        # Act
        result = await user_service.update_me(
            user_id=user_id,
            data=data,
        )

        # Assert
        assert result.first_name == "FirstName"
        assert result.last_name == "NewLast"
        mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_me_when_user_not_found_then_raises_error(
        self,
        user_service: UserService,
        mock_db: MagicMock,
    ) -> None:
        """Test update_me raises ValueError when user not found."""
        # Arrange
        user_id = uuid.uuid4()
        mock_db.get.return_value = None
        data = UserSelfUpdate(first_name="New")

        # Act & Assert
        with pytest.raises(ValueError, match="User not found"):
            await user_service.update_me(
                user_id=user_id,
                data=data,
            )
