"""Unit tests for UserService."""

import uuid
from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole
from app.schemas.user import UserDirectCreate, UserInvite, UserSelfUpdate, UserUpdate
from app.services.user_service import CrossSchoolAccessError, UserNotFoundError, UserService


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
        result_users, total = await user_service.list_users(school_id, role=UserRole.TEACHER)

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

    @pytest.mark.asyncio
    async def test_update_user_when_password_changed_then_password_changed_email_sent(
        self, user_service: UserService, mock_db: MagicMock, school_id: uuid.UUID
    ) -> None:
        """Test that a password-changed email is sent when password is updated."""
        # Arrange
        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            email="teacher@school.com",
            first_name="Jane",
            last_name="Doe",
            role=UserRole.TEACHER,
            school_id=school_id,
            is_active=True,
        )
        mock_db.scalar = AsyncMock(return_value=user)

        update_data = UserUpdate(password="NewSecurePass123!")

        # Act
        with patch(
            "app.services.user_service.UserService._send_password_changed_email",
            new_callable=AsyncMock,
        ) as mock_send:
            await user_service.update_user(school_id, user_id, update_data)

        # Assert
        mock_send.assert_called_once_with(user, school_id)

    @pytest.mark.asyncio
    async def test_update_user_when_no_password_change_then_no_email_sent(
        self, user_service: UserService, mock_db: MagicMock, school_id: uuid.UUID
    ) -> None:
        """Test that no password-changed email is sent when password is not part of the update."""
        # Arrange
        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            email="teacher@school.com",
            first_name="OldName",
            last_name="Doe",
            role=UserRole.TEACHER,
            school_id=school_id,
            is_active=True,
        )
        mock_db.scalar = AsyncMock(return_value=user)

        update_data = UserUpdate(first_name="NewName")

        # Act
        with patch(
            "app.services.user_service.UserService._send_password_changed_email",
            new_callable=AsyncMock,
        ) as mock_send:
            await user_service.update_user(school_id, user_id, update_data)

        # Assert
        mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_user_when_email_send_fails_then_user_still_updated(
        self, user_service: UserService, mock_db: MagicMock, school_id: uuid.UUID
    ) -> None:
        """Test that a failure from EmailService.send does not block the user update (non-fatal guarantee)."""
        from app.models.school import School

        # Arrange
        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            email="teacher@school.com",
            first_name="Jane",
            last_name="Doe",
            role=UserRole.TEACHER,
            school_id=school_id,
            is_active=True,
        )
        mock_db.scalar = AsyncMock(return_value=user)

        school = School(id=school_id, name="Test School")
        mock_db.get = AsyncMock(return_value=school)

        update_data = UserUpdate(password="NewSecurePass123!")

        # Act — EmailService.send raises; _send_password_changed_email catches it; update proceeds
        with patch(
            "app.services.user_service.EmailService.send",
            new_callable=AsyncMock,
            side_effect=Exception("SMTP connection refused"),
        ):
            result = await user_service.update_user(school_id, user_id, update_data)

        # Assert — user object returned; DB flush was called
        assert result is user
        mock_db.flush.assert_called_once()


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


class TestCreateUserDirect:
    """Tests for UserService.create_user_direct method."""

    @pytest.mark.asyncio
    async def test_create_user_direct_student_creates_profile_when_student_role(
        self, user_service: UserService, mock_db: MagicMock, school_id: uuid.UUID
    ) -> None:
        """create_user_direct creates StudentProfile with age and grade when role=STUDENT."""
        grade_id = uuid.uuid4()

        # No existing user with that email
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

        from app.schemas.user import UserDirectCreate

        data = UserDirectCreate(
            first_name="Aisha",
            last_name="Al-Rashid",
            email="aisha@school.edu",
            password="Secure123!",
            role=UserRole.STUDENT,
            age=13,
            grade_id=grade_id,
        )

        with patch("app.services.user_service.hash_password", return_value="hashed") as mock_hash:
            await user_service.create_user_direct(school_id=school_id, data=data)

        mock_hash.assert_called_once_with("Secure123!")
        # db.add called twice: once for User, once for StudentProfile
        assert mock_db.add.call_count == 2
        # User created with must_change_password=True
        created_user = mock_db.add.call_args_list[0][0][0]
        assert created_user.must_change_password is True
        assert created_user.hashed_password == "hashed"

    @pytest.mark.asyncio
    async def test_create_user_direct_teacher_assigns_classes(
        self, user_service: UserService, mock_db: MagicMock, school_id: uuid.UUID
    ) -> None:
        """create_user_direct calls update_teacher on ClassService when class_ids provided."""
        class_id = uuid.uuid4()

        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

        from app.schemas.user import UserDirectCreate

        data = UserDirectCreate(
            first_name="Rachel",
            last_name="Morgan",
            email="r@school.edu",
            password="Secure123!",
            role=UserRole.TEACHER,
            class_ids=[class_id],
        )

        with (
            patch("app.services.user_service.hash_password", return_value="hashed"),
            patch("app.services.user_service.ClassService") as MockClassService,
        ):
            mock_cs_instance = AsyncMock()
            MockClassService.return_value = mock_cs_instance
            await user_service.create_user_direct(school_id=school_id, data=data)

        mock_cs_instance.update_teacher.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_user_direct_raises_if_email_taken(
        self, user_service: UserService, mock_db: MagicMock, school_id: uuid.UUID
    ) -> None:
        """create_user_direct raises ValueError when email already exists in school."""
        existing_user = MagicMock()
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=existing_user)))

        from app.schemas.user import UserDirectCreate

        data = UserDirectCreate(
            first_name="A",
            last_name="B",
            email="existing@school.edu",
            password="Secure123!",
            role=UserRole.TEACHER,
        )

        with pytest.raises(ValueError, match="already exists"):
            await user_service.create_user_direct(school_id=school_id, data=data)

    @pytest.mark.asyncio
    async def test_create_user_direct_parent_creates_parent_student_links(
        self, user_service: UserService, mock_db: MagicMock, school_id: uuid.UUID
    ) -> None:
        """create_user_direct creates ParentStudent rows when student_ids provided."""
        student_id = uuid.uuid4()

        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

        from app.schemas.user import UserDirectCreate

        data = UserDirectCreate(
            first_name="James",
            last_name="Smith",
            email="j@gmail.com",
            password="Secure123!",
            role=UserRole.PARENT,
            student_ids=[student_id],
        )

        with patch("app.services.user_service.hash_password", return_value="hashed"):
            await user_service.create_user_direct(school_id=school_id, data=data)

        # db.add called twice: User + ParentStudent
        assert mock_db.add.call_count == 2


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


# ==============================================================================
# Tests for invite_user — parent-student link path
# ==============================================================================


class TestInviteUserParentLink:
    """Tests for invite_user parent-student link validation."""

    def _patch_invite(self) -> tuple:
        return (
            patch("app.services.user_service.create_magic_link_token", return_value="tok"),
            patch("app.services.user_service.hash_token", return_value="h"),
            patch("app.services.user_service.store_magic_link_token"),
            patch("app.services.user_service.UserService._send_welcome_email"),
        )

    @pytest.mark.asyncio
    async def test_invite_user_when_parent_with_valid_student_ids_then_creates_links(
        self, user_service: UserService, mock_db: MagicMock, school_id: uuid.UUID
    ) -> None:
        """invite_user creates ParentStudent rows when student_ids are valid school members."""
        student_id = uuid.uuid4()
        data = UserInvite(
            email="parent@school.com",
            role=UserRole.PARENT,
            first_name="Parent",
            last_name="One",
            student_ids=[student_id],
        )

        # First scalar call: email uniqueness check → None (no duplicate)
        # scalars call: validate student_ids → returns the valid student id
        mock_db.scalar = AsyncMock(return_value=None)
        scalars_result = MagicMock()
        scalars_result.all = MagicMock(return_value=[student_id])
        mock_db.scalars = AsyncMock(return_value=scalars_result)

        with (
            patch("app.services.user_service.create_magic_link_token", return_value="tok"),
            patch("app.services.user_service.hash_token", return_value="h"),
            patch("app.services.user_service.store_magic_link_token"),
            patch("app.services.user_service.UserService._send_welcome_email"),
        ):
            result = await user_service.invite_user(school_id, data, "https://app.kaihle.com")

        # Arrange — ParentStudent row should have been added
        assert result.role == UserRole.PARENT
        add_calls = mock_db.add.call_args_list
        from app.models.user import ParentStudent

        parent_student_calls = [c for c in add_calls if isinstance(c.args[0], ParentStudent)]
        assert len(parent_student_calls) == 1
        assert parent_student_calls[0].args[0].student_id == student_id

    @pytest.mark.asyncio
    async def test_invite_user_when_parent_with_cross_school_student_ids_then_raises(
        self, user_service: UserService, mock_db: MagicMock, school_id: uuid.UUID
    ) -> None:
        """invite_user raises ValueError when student_ids belong to a different school."""
        foreign_student_id = uuid.uuid4()
        data = UserInvite(
            email="parent2@school.com",
            role=UserRole.PARENT,
            first_name="Parent",
            last_name="Two",
            student_ids=[foreign_student_id],
        )

        mock_db.scalar = AsyncMock(return_value=None)
        # scalars returns empty — student not found in this school
        scalars_result = MagicMock()
        scalars_result.all = MagicMock(return_value=[])
        mock_db.scalars = AsyncMock(return_value=scalars_result)

        with (
            patch("app.services.user_service.create_magic_link_token", return_value="tok"),
            patch("app.services.user_service.hash_token", return_value="h"),
            patch("app.services.user_service.store_magic_link_token"),
            patch("app.services.user_service.UserService._send_welcome_email"),
        ):
            with pytest.raises(ValueError, match="Student IDs not found in this school"):
                await user_service.invite_user(school_id, data, "https://app.kaihle.com")

    @pytest.mark.asyncio
    async def test_invite_user_when_parent_with_no_student_ids_then_no_links_created(
        self, user_service: UserService, mock_db: MagicMock, school_id: uuid.UUID
    ) -> None:
        """invite_user creates no ParentStudent rows when student_ids is None."""
        data = UserInvite(
            email="parent3@school.com",
            role=UserRole.PARENT,
            first_name="Parent",
            last_name="Three",
        )
        mock_db.scalar = AsyncMock(return_value=None)

        with (
            patch("app.services.user_service.create_magic_link_token", return_value="tok"),
            patch("app.services.user_service.hash_token", return_value="h"),
            patch("app.services.user_service.store_magic_link_token"),
            patch("app.services.user_service.UserService._send_welcome_email"),
        ):
            await user_service.invite_user(school_id, data, "https://app.kaihle.com")

        from app.models.user import ParentStudent

        parent_student_calls = [c for c in mock_db.add.call_args_list if isinstance(c.args[0], ParentStudent)]
        assert len(parent_student_calls) == 0


# ==============================================================================
# Tests for get_student_detail
# ==============================================================================


class TestGetStudentDetail:
    """Tests for UserService.get_student_detail."""

    @pytest.mark.asyncio
    async def test_get_student_detail_when_not_found_then_raises_user_not_found_error(
        self, user_service: UserService, mock_db: MagicMock
    ) -> None:
        """get_student_detail raises UserNotFoundError when student doesn't exist."""
        mock_db.scalar = AsyncMock(return_value=None)

        with pytest.raises(UserNotFoundError, match="Student not found"):
            await user_service.get_student_detail(uuid.uuid4(), caller_school_id=None)

    @pytest.mark.asyncio
    async def test_get_student_detail_when_cross_school_then_raises_cross_school_error(
        self, user_service: UserService, mock_db: MagicMock, school_id: uuid.UUID
    ) -> None:
        """get_student_detail raises CrossSchoolAccessError when schools don't match."""
        other_school = uuid.uuid4()
        student = User(
            id=uuid.uuid4(),
            school_id=other_school,
            role=UserRole.STUDENT,
            email="s@school.com",
            first_name="S",
            last_name="T",
            is_active=True,
        )
        mock_db.scalar = AsyncMock(return_value=student)

        with pytest.raises(CrossSchoolAccessError):
            await user_service.get_student_detail(student.id, caller_school_id=school_id)

    @pytest.mark.asyncio
    async def test_get_student_detail_when_same_school_then_returns_response(
        self, user_service: UserService, mock_db: MagicMock, school_id: uuid.UUID
    ) -> None:
        """get_student_detail returns StudentDetailResponse for valid same-school caller."""
        student = User(
            id=uuid.uuid4(),
            school_id=school_id,
            role=UserRole.STUDENT,
            email="s@school.com",
            first_name="Sam",
            last_name="Lee",
            is_active=True,
            last_login_at=None,
        )
        mock_db.scalar = AsyncMock(return_value=student)
        # First execute: grade query — returns no row via one_or_none()
        grade_result = MagicMock()
        grade_result.one_or_none = MagicMock(return_value=None)
        # Subsequent execute calls (enrollments + gap states) return empty results
        empty_result = MagicMock()
        empty_result.all = MagicMock(return_value=[])
        mock_db.execute = AsyncMock(side_effect=[grade_result, empty_result, empty_result])

        from app.schemas.user_detail import StudentDetailResponse

        result = await user_service.get_student_detail(student.id, caller_school_id=school_id)
        assert isinstance(result, StudentDetailResponse)
        assert result.first_name == "Sam"
        assert result.class_enrollments == []


# ==============================================================================
# Tests for get_teacher_detail
# ==============================================================================


class TestGetTeacherDetail:
    """Tests for UserService.get_teacher_detail."""

    @pytest.mark.asyncio
    async def test_get_teacher_detail_when_not_found_then_raises_user_not_found_error(
        self, user_service: UserService, mock_db: MagicMock
    ) -> None:
        """get_teacher_detail raises UserNotFoundError when teacher doesn't exist."""
        mock_db.scalar = AsyncMock(return_value=None)

        with pytest.raises(UserNotFoundError, match="Teacher not found"):
            await user_service.get_teacher_detail(uuid.uuid4(), caller_school_id=None)

    @pytest.mark.asyncio
    async def test_get_teacher_detail_when_cross_school_then_raises_cross_school_error(
        self, user_service: UserService, mock_db: MagicMock, school_id: uuid.UUID
    ) -> None:
        """get_teacher_detail raises CrossSchoolAccessError when schools don't match."""
        teacher = User(
            id=uuid.uuid4(),
            school_id=uuid.uuid4(),
            role=UserRole.TEACHER,
            email="t@school.com",
            first_name="T",
            last_name="E",
            is_active=True,
        )
        mock_db.scalar = AsyncMock(return_value=teacher)

        with pytest.raises(CrossSchoolAccessError):
            await user_service.get_teacher_detail(teacher.id, caller_school_id=school_id)

    @pytest.mark.asyncio
    async def test_get_teacher_detail_when_same_school_then_returns_response(
        self, user_service: UserService, mock_db: MagicMock, school_id: uuid.UUID
    ) -> None:
        """get_teacher_detail returns TeacherDetailResponse for valid same-school caller."""
        teacher = User(
            id=uuid.uuid4(),
            school_id=school_id,
            role=UserRole.TEACHER,
            email="t@school.com",
            first_name="Jane",
            last_name="Smith",
            is_active=True,
        )
        mock_db.scalar = AsyncMock(return_value=teacher)
        empty_result = MagicMock()
        empty_result.all = MagicMock(return_value=[])
        mock_db.execute = AsyncMock(return_value=empty_result)

        from app.schemas.user_detail import TeacherDetailResponse

        result = await user_service.get_teacher_detail(teacher.id, caller_school_id=school_id)
        assert isinstance(result, TeacherDetailResponse)
        assert result.email == "t@school.com"
        assert result.assigned_classes == []


# ==============================================================================
# Tests for get_parent_detail
# ==============================================================================


class TestGetParentDetail:
    """Tests for UserService.get_parent_detail."""

    @pytest.mark.asyncio
    async def test_get_parent_detail_when_not_found_then_raises_user_not_found_error(
        self, user_service: UserService, mock_db: MagicMock
    ) -> None:
        """get_parent_detail raises UserNotFoundError when parent doesn't exist."""
        mock_db.scalar = AsyncMock(return_value=None)

        with pytest.raises(UserNotFoundError, match="Parent not found"):
            await user_service.get_parent_detail(uuid.uuid4(), caller_school_id=None)

    @pytest.mark.asyncio
    async def test_get_parent_detail_when_cross_school_then_raises_cross_school_error(
        self, user_service: UserService, mock_db: MagicMock, school_id: uuid.UUID
    ) -> None:
        """get_parent_detail raises CrossSchoolAccessError when schools don't match."""
        parent = User(
            id=uuid.uuid4(),
            school_id=uuid.uuid4(),
            role=UserRole.PARENT,
            email="p@school.com",
            first_name="P",
            last_name="Q",
            is_active=True,
        )
        mock_db.scalar = AsyncMock(return_value=parent)

        with pytest.raises(CrossSchoolAccessError):
            await user_service.get_parent_detail(parent.id, caller_school_id=school_id)

    @pytest.mark.asyncio
    async def test_get_parent_detail_when_same_school_then_returns_response(
        self, user_service: UserService, mock_db: MagicMock, school_id: uuid.UUID
    ) -> None:
        """get_parent_detail returns ParentDetailResponse for valid same-school caller."""
        parent = User(
            id=uuid.uuid4(),
            school_id=school_id,
            role=UserRole.PARENT,
            email="p@school.com",
            first_name="Paul",
            last_name="Lee",
            is_active=True,
        )
        mock_db.scalar = AsyncMock(return_value=parent)
        empty_result = MagicMock()
        empty_result.all = MagicMock(return_value=[])
        mock_db.execute = AsyncMock(return_value=empty_result)

        from app.schemas.user_detail import ParentDetailResponse

        result = await user_service.get_parent_detail(parent.id, caller_school_id=school_id)
        assert isinstance(result, ParentDetailResponse)
        assert result.first_name == "Paul"
        assert result.linked_students == []


class TestCreateUserDirectCredentialsEmail:
    """Tests that create_user_direct sends credentials email for each role."""

    def _make_direct_create_data(self, role: UserRole) -> UserDirectCreate:
        from app.schemas.user import UserDirectCreate

        return UserDirectCreate(
            first_name="New",
            last_name="User",
            email="newuser@school.edu",
            password="TempPass1!",
            role=role,
        )

    @pytest.mark.asyncio
    async def test_create_user_direct_when_teacher_then_credentials_email_sent(
        self, user_service: UserService, mock_db: MagicMock, school_id: uuid.UUID
    ) -> None:
        """create_user_direct sends welcome_credentials email to a new teacher."""
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        mock_db.get = AsyncMock(return_value=MagicMock(name="Greenhill International"))

        mock_email_send = AsyncMock()
        with (
            patch("app.services.user_service.hash_password", return_value="hashed"),
            patch("app.services.user_service.EmailService") as MockEmailService,
        ):
            MockEmailService.return_value.send = mock_email_send
            await user_service.create_user_direct(
                school_id=school_id, data=self._make_direct_create_data(UserRole.TEACHER)
            )

        mock_email_send.assert_called_once()
        call_kwargs = mock_email_send.call_args[1]
        assert call_kwargs["template"] == "welcome_credentials.html.jinja2"
        assert call_kwargs["ctx"]["temp_password"] == "TempPass1!"

    @pytest.mark.asyncio
    async def test_create_user_direct_when_student_then_credentials_email_sent(
        self, user_service: UserService, mock_db: MagicMock, school_id: uuid.UUID
    ) -> None:
        """create_user_direct sends welcome_credentials email to a new student."""
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        mock_db.get = AsyncMock(return_value=MagicMock(name="Greenhill International"))

        from app.schemas.user import UserDirectCreate

        data = UserDirectCreate(
            first_name="Student",
            last_name="One",
            email="student@school.edu",
            password="TempPass1!",
            role=UserRole.STUDENT,
            age=14,
            grade_id=uuid.uuid4(),
        )

        mock_email_send = AsyncMock()
        with (
            patch("app.services.user_service.hash_password", return_value="hashed"),
            patch("app.services.user_service.EmailService") as MockEmailService,
        ):
            MockEmailService.return_value.send = mock_email_send
            await user_service.create_user_direct(school_id=school_id, data=data)

        mock_email_send.assert_called_once()
        call_kwargs = mock_email_send.call_args[1]
        assert call_kwargs["template"] == "welcome_credentials.html.jinja2"

    @pytest.mark.asyncio
    async def test_create_user_direct_when_parent_then_credentials_email_sent(
        self, user_service: UserService, mock_db: MagicMock, school_id: uuid.UUID
    ) -> None:
        """create_user_direct sends welcome_credentials email to a new parent."""
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        mock_db.get = AsyncMock(return_value=MagicMock(name="Greenhill International"))

        mock_email_send = AsyncMock()
        with (
            patch("app.services.user_service.hash_password", return_value="hashed"),
            patch("app.services.user_service.EmailService") as MockEmailService,
        ):
            MockEmailService.return_value.send = mock_email_send
            await user_service.create_user_direct(
                school_id=school_id, data=self._make_direct_create_data(UserRole.PARENT)
            )

        mock_email_send.assert_called_once()
        call_kwargs = mock_email_send.call_args[1]
        assert call_kwargs["template"] == "welcome_credentials.html.jinja2"

    @pytest.mark.asyncio
    async def test_create_user_direct_when_email_send_fails_then_user_still_created(
        self, user_service: UserService, mock_db: MagicMock, school_id: uuid.UUID
    ) -> None:
        """create_user_direct completes user creation even if the credentials email fails."""
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        mock_db.get = AsyncMock(return_value=MagicMock(name="School"))

        with (
            patch("app.services.user_service.hash_password", return_value="hashed"),
            patch("app.services.user_service.EmailService") as MockEmailService,
        ):
            MockEmailService.return_value.send = AsyncMock(side_effect=Exception("Resend down"))
            user = await user_service.create_user_direct(
                school_id=school_id, data=self._make_direct_create_data(UserRole.TEACHER)
            )

        assert user is not None
        assert user.email == "newuser@school.edu"


class TestGetStudentInfo:
    """Tests for UserService.get_student_info."""

    def _make_student(self) -> User:
        student = MagicMock(spec=User)
        student.id = uuid.uuid4()
        student.first_name = "Josua"
        student.last_name = "Tan"
        student.email = "josua@school.edu"
        student.school_id = uuid.uuid4()
        return student

    @pytest.mark.asyncio
    async def test_get_student_info_when_enrolled_then_returns_id(
        self, user_service: UserService, mock_db: MagicMock
    ) -> None:
        """get_student_info includes student.id in the response."""
        student = self._make_student()
        mock_db.execute = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=[])))

        result = await user_service.get_student_info(student)

        assert result.id == student.id

    @pytest.mark.asyncio
    async def test_get_student_info_when_no_enrollments_then_not_enrolled(
        self, user_service: UserService, mock_db: MagicMock
    ) -> None:
        """get_student_info returns is_enrolled=False when no active class enrollments exist."""
        student = self._make_student()
        mock_db.execute = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=[])))

        result = await user_service.get_student_info(student)

        assert result.is_enrolled is False
        assert result.enrolled_classes == []


class TestGetMyAssessments:
    """Tests for UserService.get_my_assessments."""

    def _make_student(self) -> User:
        student = MagicMock(spec=User)
        student.id = uuid.uuid4()
        student.school_id = uuid.uuid4()
        return student

    def _make_row(
        self,
        *,
        attempt_id: uuid.UUID | None = None,
        attempt_status_raw: Any = None,
        score: float | None = None,
    ) -> MagicMock:
        from app.models.assessment import AssessmentStatus, AssessmentType, AttemptStatus

        row = MagicMock()
        row.id = uuid.uuid4()
        row.class_id = uuid.uuid4()
        row.class_name = "Mathematics 9B"
        row.title = "Algebra Quiz"
        row.assessment_type = AssessmentType.PROGRESS_CHECK
        row.status = AssessmentStatus.ACTIVE
        row.question_count = 10
        row.deadline = None
        row.published_at = None
        row.attempt_id = attempt_id
        row.attempt_status_raw = attempt_status_raw or (AttemptStatus.COMPLETED if attempt_id else None)
        row.score = score
        return row

    @pytest.mark.asyncio
    async def test_get_my_assessments_when_no_attempt_then_not_started(
        self, user_service: UserService, mock_db: MagicMock
    ) -> None:
        """get_my_assessments returns NOT_STARTED when no attempt row exists."""
        student = self._make_student()
        row = self._make_row(attempt_id=None)
        mock_db.execute = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=[row])))

        result = await user_service.get_my_assessments(student)

        assert len(result) == 1
        assert result[0].attempt_status == "NOT_STARTED"
        assert result[0].attempt_id is None

    @pytest.mark.asyncio
    async def test_get_my_assessments_when_attempt_completed_then_completed(
        self, user_service: UserService, mock_db: MagicMock
    ) -> None:
        """get_my_assessments returns COMPLETED when attempt row has status COMPLETED."""
        from app.models.assessment import AttemptStatus

        student = self._make_student()
        attempt_id = uuid.uuid4()
        row = self._make_row(
            attempt_id=attempt_id,
            attempt_status_raw=AttemptStatus.COMPLETED,
            score=0.85,
        )
        mock_db.execute = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=[row])))

        result = await user_service.get_my_assessments(student)

        assert result[0].attempt_status == "COMPLETED"
        assert result[0].attempt_id == attempt_id
        assert result[0].score == 0.85

    @pytest.mark.asyncio
    async def test_get_my_assessments_when_no_enrollments_then_empty(
        self, user_service: UserService, mock_db: MagicMock
    ) -> None:
        """get_my_assessments returns an empty list when the student has no active enrollments."""
        student = self._make_student()
        mock_db.execute = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=[])))

        result = await user_service.get_my_assessments(student)

        assert result == []
