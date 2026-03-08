"""Unit tests for auth service."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole
from app.services.auth_service import AuthService


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = AsyncMock(spec=AsyncSession)
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.scalar = AsyncMock()
    db.get = AsyncMock()
    return db


@pytest.fixture
def auth_service(mock_db):
    """Create an AuthService with mock database."""
    return AuthService(mock_db)


class TestRegisterSchoolAdmin:
    """Tests for school admin registration."""

    @pytest.mark.asyncio
    async def test_register_school_admin_when_duplicate_email_raises_error(self, auth_service, mock_db):
        """Test that duplicate email raises ValueError."""
        # Arrange
        school_id = uuid.uuid4()
        mock_db.scalar.return_value = User(
            id=uuid.uuid4(),
            email="admin@school.com",
            school_id=school_id,
        )

        # Act & Assert
        with pytest.raises(ValueError, match="Email already registered"):
            await auth_service.register_school_admin(
                email="admin@school.com",
                password="password123",
                school_id=school_id,
                first_name="John",
                last_name="Admin",
            )


class TestRegisterTeacher:
    """Tests for teacher registration."""

    @pytest.mark.asyncio
    async def test_register_teacher_raises_on_duplicate(self, auth_service, mock_db):
        """Test that duplicate teacher email raises ValueError."""
        # Arrange
        school_id = uuid.uuid4()
        mock_db.scalar.return_value = User(
            id=uuid.uuid4(),
            email="teacher@school.com",
            school_id=school_id,
        )

        # Act & Assert
        with pytest.raises(ValueError, match="Email already registered"):
            await auth_service.register_teacher(
                email="teacher@school.com",
                password="password123",
                school_id=school_id,
                first_name="Jane",
                last_name="Teacher",
            )


class TestRegisterStudent:
    """Tests for student registration."""

    @pytest.mark.asyncio
    async def test_register_student_raises_on_duplicate(self, auth_service, mock_db):
        """Test that duplicate student email raises ValueError."""
        # Arrange
        school_id = uuid.uuid4()
        mock_db.scalar.return_value = User(
            id=uuid.uuid4(),
            email="student@school.com",
            school_id=school_id,
        )

        # Act & Assert
        with pytest.raises(ValueError, match="Email already registered"):
            await auth_service.register_student(
                email="student@school.com",
                password="password123",
                school_id=school_id,
                grade_id=None,
                first_name="Bob",
                last_name="Student",
            )


class TestRegisterParent:
    """Tests for parent registration."""

    @pytest.mark.asyncio
    async def test_register_parent_raises_on_duplicate(self, auth_service, mock_db):
        """Test that duplicate parent email raises ValueError."""
        # Arrange
        mock_db.scalar.return_value = User(
            id=uuid.uuid4(),
            email="parent@email.com",
        )

        # Act & Assert
        with pytest.raises(ValueError, match="Email already registered"):
            await auth_service.register_parent(
                email="parent@email.com",
                password="password123",
                first_name="Alice",
                last_name="Parent",
            )


class TestRegisterKaihleAdmin:
    """Tests for Kaihle admin registration."""

    @pytest.mark.asyncio
    async def test_register_kaihle_admin_raises_on_duplicate(self, auth_service, mock_db):
        """Test that duplicate Kaihle admin email raises ValueError."""
        # Arrange
        mock_db.scalar.return_value = User(
            id=uuid.uuid4(),
            email="admin@kaihle.ai",
        )

        # Act & Assert
        with pytest.raises(ValueError, match="Email already registered"):
            await auth_service.register_kaihle_admin(
                email="admin@kaihle.ai",
                password="password123",
                first_name="Super",
                last_name="Admin",
            )


class TestLogin:
    """Tests for login functionality."""

    @pytest.mark.asyncio
    async def test_login_with_invalid_email_raises_error(self, auth_service, mock_db):
        """Test that login with invalid email raises ValueError."""
        # Arrange
        mock_db.scalar.return_value = None

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid credentials"):
            await auth_service.login("wrong@email.com", "password123")

    @pytest.mark.asyncio
    async def test_login_with_inactive_account_raises_error(self, auth_service, mock_db):
        """Test that login with inactive account raises ValueError."""
        # Arrange
        user = User(
            id=uuid.uuid4(),
            email="user@school.com",
            hashed_password="hashed",
            role=UserRole.TEACHER,
            is_active=False,
            school_id=uuid.uuid4(),
        )
        mock_db.scalar.return_value = user

        # Act & Assert
        with pytest.raises(ValueError, match="Account is inactive"):
            await auth_service.login("user@school.com", "password123")


class TestSendMagicLink:
    """Tests for magic link functionality."""

    @pytest.mark.asyncio
    async def test_send_magic_link_returns_silently_for_unknown_email(self, auth_service, mock_db):
        """Test that sending magic link to unknown email returns silently."""
        # Arrange
        mock_db.scalar.return_value = None

        # Act
        await auth_service.send_magic_link("unknown@email.com", "http://localhost")

        # Assert - should not raise and should not send email
        mock_db.add.assert_not_called()


class TestLogout:
    """Tests for logout functionality."""

    @pytest.mark.asyncio
    async def test_logout_marks_token_as_used(self, auth_service, mock_db):
        """Test that logout marks refresh token as used."""
        # Arrange
        from app.models.user import AuthToken

        token = AuthToken(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            token_hash="hashed",
            type="REFRESH",
        )
        mock_db.scalar.return_value = token

        # Act
        await auth_service.logout("raw_token")

        # Assert
        assert token.used_at is not None
        mock_db.flush.assert_called_once()


class TestGetActiveUserByEmail:
    """Tests for internal _get_active_user_by_email method."""

    @pytest.mark.asyncio
    async def test_get_active_user_returns_user(self, auth_service, mock_db):
        """Test that method returns user when found."""
        # Arrange
        user = User(
            id=uuid.uuid4(),
            email="user@school.com",
            hashed_password="hashed",
            role=UserRole.TEACHER,
            is_active=True,
            school_id=uuid.uuid4(),
        )
        mock_db.scalar.return_value = user

        # Act
        result = await auth_service._get_active_user_by_email("user@school.com")

        # Assert
        assert result == user

    @pytest.mark.asyncio
    async def test_get_active_user_raises_when_not_found(self, auth_service, mock_db):
        """Test that method raises ValueError when user not found."""
        # Arrange
        mock_db.scalar.return_value = None

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid credentials"):
            await auth_service._get_active_user_by_email("notfound@email.com")


class TestLoginWithPassword:
    """Tests for login with password verification."""

    @pytest.mark.asyncio
    async def test_login_with_wrong_password_raises_error(self, auth_service, mock_db):
        """Test that login with wrong password raises ValueError."""
        # Arrange
        user = User(
            id=uuid.uuid4(),
            email="user@school.com",
            hashed_password="hashed_correct",
            role=UserRole.TEACHER,
            is_active=True,
            school_id=uuid.uuid4(),
        )
        mock_db.scalar.return_value = user

        with patch("app.services.auth_service.verify_password") as mock_verify:
            mock_verify.return_value = False

            # Act & Assert
            with pytest.raises(ValueError, match="Invalid credentials"):
                await auth_service.login("user@school.com", "wrong_password")


class TestRegisterStudentMethod:
    """Tests for register_student method."""

    @pytest.mark.asyncio
    async def test_register_student_raises_on_duplicate(self, auth_service, mock_db):
        """Test that duplicate student email raises ValueError."""
        # Arrange
        school_id = uuid.uuid4()
        mock_db.scalar.return_value = User(
            id=uuid.uuid4(),
            email="student@school.com",
            school_id=school_id,
        )

        # Act & Assert
        with pytest.raises(ValueError, match="Email already registered"):
            await auth_service.register_student(
                email="student@school.com",
                password="password123",
                school_id=school_id,
                grade_id=None,
                first_name="Bob",
                last_name="Student",
            )
