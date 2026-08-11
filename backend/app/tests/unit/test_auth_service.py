"""Unit tests for AuthService."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    InvalidTokenError,
    create_impersonation_handoff_token,
    create_magic_link_token,
    decode_token,
    hash_password,
    hash_token,
)
from app.models.user import AuthToken, AuthTokenType, User
from app.schemas.auth import LoginResponse, RegisterResponse, TokenResponse
from app.services.auth_service import (
    AuthService,
    ImpersonationNotAllowedError,
    UserNotFoundError,
)


@pytest.fixture
def mock_db() -> MagicMock:
    """Create a mock database session."""
    session = MagicMock(spec=AsyncSession)
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.scalar = AsyncMock()
    session.get = AsyncMock()

    def capture_add(obj: object) -> object:
        """Capture added object and set defaults."""
        if hasattr(obj, "id") and getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()
        return obj

    session.add.side_effect = capture_add
    return session


@pytest.fixture
def auth_service(mock_db: MagicMock) -> AuthService:
    """Create an AuthService with mock database."""
    return AuthService(mock_db)


@pytest.fixture
def sample_user() -> User:
    """Create a sample user for testing."""
    return User(
        id=uuid.uuid4(),
        school_id=uuid.uuid4(),
        email="test@example.com",
        hashed_password="hashed_password",
        first_name="John",
        last_name="Doe",
        role="TEACHER",
        is_active=True,
    )


@pytest.fixture
def sample_school_id() -> uuid.UUID:
    """Create a sample school ID."""
    return uuid.uuid4()


# ==============================================================================
# Tests for register()
# ==============================================================================


class TestRegister:
    """Tests for AuthService.register method."""

    @pytest.mark.asyncio
    async def test_register_when_valid_data_then_user_created(
        self, auth_service: AuthService, mock_db: MagicMock, sample_school_id: uuid.UUID
    ) -> None:
        """Test creating a user with valid data."""
        # Arrange
        mock_db.scalar = AsyncMock(return_value=None)  # No existing user

        # Act
        result = await auth_service.register(
            email="new@example.com",
            password="securepass123",
            role="TEACHER",
            school_id=sample_school_id,
            first_name="Jane",
            last_name="Smith",
        )

        # Assert
        assert isinstance(result, RegisterResponse)
        assert result.email == "new@example.com"
        assert result.role == "TEACHER"
        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_when_duplicate_email_raises_value_error(
        self, auth_service: AuthService, mock_db: MagicMock, sample_user: User
    ) -> None:
        """Test that duplicate email in same school raises ValueError."""
        # Arrange
        mock_db.scalar = AsyncMock(return_value=sample_user)

        # Act & Assert
        with pytest.raises(ValueError, match="Email already registered"):
            await auth_service.register(
                email=sample_user.email,
                password="securepass123",
                role="TEACHER",
                school_id=sample_user.school_id,
                first_name="Jane",
                last_name="Smith",
            )

    @pytest.mark.asyncio
    async def test_register_when_duplicate_email_different_school_then_succeeds(
        self, auth_service: AuthService, mock_db: MagicMock, sample_user: User
    ) -> None:
        """Test that same email in different school succeeds."""
        # Arrange
        different_school_id = uuid.uuid4()
        mock_db.scalar = AsyncMock(return_value=None)  # No conflict in different school

        # Act
        result = await auth_service.register(
            email=sample_user.email,  # Same email
            password="securepass123",
            role="TEACHER",
            school_id=different_school_id,  # Different school
            first_name="Jane",
            last_name="Smith",
        )

        # Assert
        assert result.email == sample_user.email
        mock_db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_when_no_school_then_global_check(
        self, auth_service: AuthService, mock_db: MagicMock
    ) -> None:
        """Test that no school_id means global email check."""
        # Arrange
        mock_db.scalar = AsyncMock(return_value=None)

        # Act
        result = await auth_service.register(
            email="admin@kaihle.com",
            password="securepass123",
            role="KAIHLE_ADMIN",
            school_id=None,
            first_name="Admin",
            last_name="User",
        )

        # Assert
        assert result.email == "admin@kaihle.com"
        # Verify scalar was called (would have been called with just email filter)
        mock_db.scalar.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_when_school_not_found_then_raises_error(
        self, auth_service: AuthService, mock_db: MagicMock, sample_school_id: uuid.UUID
    ) -> None:
        """Test that non-existent school raises SchoolNotFoundError."""
        # Arrange
        mock_db.scalar = AsyncMock(return_value=None)  # No existing user
        mock_db.get = AsyncMock(return_value=None)  # School not found

        # Act & Assert
        from app.services.auth_service import SchoolNotFoundError

        with pytest.raises(SchoolNotFoundError, match="School with id .* not found"):
            await auth_service.register(
                email="new@example.com",
                password="securepass123",
                role="TEACHER",
                school_id=sample_school_id,
                first_name="Jane",
                last_name="Smith",
            )


# ==============================================================================
# Tests for login()
# ==============================================================================


class TestLogin:
    """Tests for AuthService.login method."""

    @pytest.mark.asyncio
    async def test_login_when_valid_credentials_then_returns_tokens(
        self, auth_service: AuthService, mock_db: MagicMock, sample_user: User
    ) -> None:
        """Test login with valid credentials returns tokens."""
        # Arrange
        with (
            patch("app.services.auth_service.create_access_token") as mock_create_token,
            patch("app.services.auth_service.generate_refresh_token") as mock_gen_refresh,
            patch("app.services.auth_service.store_refresh_token") as mock_store_refresh,
            patch("app.services.auth_service.verify_password") as mock_verify,
        ):
            mock_verify.return_value = True
            mock_create_token.return_value = "access_token_123"
            mock_gen_refresh.return_value = ("raw_refresh_token", "hashed_refresh")
            mock_db.scalar = AsyncMock(return_value=sample_user)

            # Act
            result = await auth_service.login(email_or_username="test@example.com", password="correct_password")

            # Assert
            assert isinstance(result, LoginResponse)
            assert result.access_token == "access_token_123"
            assert result.refresh_token == "raw_refresh_token"
            assert result.token_type == "bearer"
            assert result.user["id"] == str(sample_user.id)
            assert result.user["email"] == sample_user.email
            assert result.user["role"] == sample_user.role
            assert result.user["school_id"] == str(sample_user.school_id)
            assert "permissions" in result.user
            assert result.user["permissions"] == sample_user.permissions
            mock_store_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_login_when_user_has_permissions_then_permissions_included_in_response(
        self, auth_service: AuthService, mock_db: MagicMock, sample_user: User
    ) -> None:
        """Permissions set on the user model must be present in the login response user dict."""
        # Arrange
        sample_user.permissions = {"billing": False, "user_management": False}
        with (
            patch("app.services.auth_service.create_access_token") as mock_create_token,
            patch("app.services.auth_service.generate_refresh_token") as mock_gen_refresh,
            patch("app.services.auth_service.store_refresh_token"),
            patch("app.services.auth_service.verify_password") as mock_verify,
        ):
            mock_verify.return_value = True
            mock_create_token.return_value = "access_token_123"
            mock_gen_refresh.return_value = ("raw_refresh_token", "hashed_refresh")
            mock_db.scalar = AsyncMock(return_value=sample_user)

            # Act
            result = await auth_service.login(email_or_username=sample_user.email, password="correct_password")

        # Assert — permissions must survive the serialization path
        assert result.user["permissions"] == {"billing": False, "user_management": False}

    @pytest.mark.asyncio
    async def test_login_when_invalid_password_raises_value_error(
        self, auth_service: AuthService, mock_db: MagicMock, sample_user: User
    ) -> None:
        """Test login with wrong password raises ValueError."""
        # Arrange
        with patch("app.services.auth_service.verify_password") as mock_verify:
            mock_verify.return_value = False
            mock_db.scalar = AsyncMock(return_value=sample_user)

            # Act & Assert
            with pytest.raises(ValueError, match="Invalid credentials"):
                await auth_service.login(email_or_username="test@example.com", password="wrong_password")

    @pytest.mark.asyncio
    async def test_login_when_user_not_found_raises_value_error(
        self, auth_service: AuthService, mock_db: MagicMock
    ) -> None:
        """Test login with non-existent email raises ValueError."""
        # Arrange
        mock_db.scalar = AsyncMock(return_value=None)

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid credentials"):
            await auth_service.login(email_or_username="nonexistent@example.com", password="any_password")

    @pytest.mark.asyncio
    async def test_login_when_inactive_user_raises_value_error(
        self, auth_service: AuthService, mock_db: MagicMock
    ) -> None:
        """Test login with inactive account raises ValueError."""
        # Arrange
        mock_db.scalar = AsyncMock(return_value=None)

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid credentials"):
            await auth_service.login(email_or_username="inactive@example.com", password="any_password")

    @pytest.mark.asyncio
    async def test_login_when_user_without_password_raises_value_error(
        self, auth_service: AuthService, mock_db: MagicMock
    ) -> None:
        """Test login when user has no password set raises ValueError."""
        # Arrange
        user_no_password = User(
            id=uuid.uuid4(),
            school_id=uuid.uuid4(),
            email="nopass@example.com",
            hashed_password=None,  # No password
            first_name="NoPass",
            last_name="User",
            role="TEACHER",
            is_active=True,
        )
        mock_db.scalar = AsyncMock(return_value=user_no_password)

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid credentials"):
            await auth_service.login(email_or_username="nopass@example.com", password="any_password")


# ==============================================================================
# Tests for send_magic_link()
# ==============================================================================


class TestSendMagicLink:
    """Tests for AuthService.send_magic_link method."""

    @pytest.mark.asyncio
    async def test_send_magic_link_when_valid_active_user_then_sends_email(
        self, auth_service: AuthService, mock_db: MagicMock, sample_user: User
    ) -> None:
        """Test sending magic link to active user."""
        # Arrange
        mock_db.scalar = AsyncMock(return_value=sample_user)

        with (
            patch("app.services.auth_service.create_magic_link_token") as mock_create,
            patch("app.services.auth_service.hash_token") as mock_hash,
            patch.object(auth_service, "_send_magic_link_email", new_callable=AsyncMock) as mock_send,
        ):
            mock_create.return_value = "magic_token_123"
            mock_hash.return_value = "hashed_token"

            # Act
            await auth_service.send_magic_link(email="test@example.com", base_url="https://kaihle.com")

            # Assert
            mock_send.assert_called_once()
            mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_magic_link_when_user_not_found_then_returns_silently(
        self, auth_service: AuthService, mock_db: MagicMock
    ) -> None:
        """Test that non-existent email returns silently (security)."""
        # Arrange
        mock_db.scalar = AsyncMock(return_value=None)

        # Act & Assert - should not raise
        await auth_service.send_magic_link(email="nonexistent@example.com", base_url="https://kaihle.com")

    @pytest.mark.asyncio
    async def test_send_magic_link_when_inactive_user_then_returns_silently(
        self, auth_service: AuthService, mock_db: MagicMock
    ) -> None:
        """Test that inactive user returns silently (security)."""
        # Arrange
        mock_db.scalar = AsyncMock(return_value=None)  # Query filters by is_active=True

        # Act & Assert - should not raise
        await auth_service.send_magic_link(email="inactive@example.com", base_url="https://kaihle.com")


# ==============================================================================
# Tests for verify_magic_link()
# ==============================================================================


class TestVerifyMagicLink:
    """Tests for AuthService.verify_magic_link method."""

    @pytest.mark.asyncio
    async def test_verify_magic_link_when_valid_token_then_returns_tokens(
        self, auth_service: AuthService, mock_db: MagicMock, sample_user: User
    ) -> None:
        """Test verifying valid magic link returns tokens."""
        # Arrange
        valid_token = "valid_magic_link_token"
        token_hash = "hashed_token"
        expires_at = datetime.now(UTC) + timedelta(minutes=10)

        auth_token = AuthToken(
            id=uuid.uuid4(),
            user_id=sample_user.id,
            token_hash=token_hash,
            type="MAGIC_LINK",
            expires_at=expires_at,
            used_at=None,
        )

        with (
            patch("app.services.auth_service.decode_token") as mock_decode,
            patch("app.services.auth_service.hash_token", return_value=token_hash),
            patch("app.services.auth_service.create_access_token") as mock_create_token,
            patch("app.services.auth_service.generate_refresh_token") as mock_gen_refresh,
            patch("app.services.auth_service.store_refresh_token"),
        ):
            mock_decode.return_value = {"sub": str(sample_user.id), "type": "magic_link"}
            mock_create_token.return_value = "access_token_123"
            mock_gen_refresh.return_value = ("raw_refresh", "hashed_refresh")
            mock_db.scalar = AsyncMock(return_value=auth_token)
            mock_db.get = AsyncMock(return_value=sample_user)

            # Act
            result = await auth_service.verify_magic_link(token=valid_token)

            # Assert
            assert isinstance(result, LoginResponse)
            assert result.access_token == "access_token_123"
            mock_db.flush.assert_called()

    @pytest.mark.asyncio
    async def test_verify_magic_link_when_invalid_token_raises_error(
        self, auth_service: AuthService, mock_db: MagicMock
    ) -> None:
        """Test that malformed token raises InvalidTokenError."""
        # Arrange
        with patch("app.services.auth_service.decode_token") as mock_decode:
            mock_decode.side_effect = InvalidTokenError("Invalid token")

            # Act & Assert
            with pytest.raises(InvalidTokenError):
                await auth_service.verify_magic_link(token="malformed_token")

    @pytest.mark.asyncio
    async def test_verify_magic_link_when_wrong_token_type_raises_error(
        self, auth_service: AuthService, mock_db: MagicMock, sample_user: User
    ) -> None:
        """Test that non-magic-link token raises InvalidTokenError."""
        # Arrange
        with patch("app.services.auth_service.decode_token") as mock_decode:
            mock_decode.return_value = {"sub": str(sample_user.id), "type": "refresh"}

            # Act & Assert
            with pytest.raises(InvalidTokenError, match="Not a magic link token"):
                await auth_service.verify_magic_link(token="some_refresh_token")

    @pytest.mark.asyncio
    async def test_verify_magic_link_when_token_already_used_raises_error(
        self, auth_service: AuthService, mock_db: MagicMock, sample_user: User
    ) -> None:
        """Test that used token raises InvalidTokenError."""
        # Arrange
        token_hash = "hashed_token"
        AuthToken(
            id=uuid.uuid4(),
            user_id=sample_user.id,
            token_hash=token_hash,
            type="MAGIC_LINK",
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
            used_at=datetime.now(UTC),  # Already used
        )

        with (
            patch("app.services.auth_service.decode_token") as mock_decode,
            patch("app.services.auth_service.hash_token", return_value=token_hash),
        ):
            mock_decode.return_value = {"sub": str(sample_user.id), "type": "magic_link"}
            mock_db.scalar = AsyncMock(return_value=None)  # Token not found (used)

            # Act & Assert
            with pytest.raises(InvalidTokenError, match="Token invalid or already used"):
                await auth_service.verify_magic_link(token="used_token")

    @pytest.mark.asyncio
    async def test_verify_magic_link_when_token_expired_raises_error(
        self, auth_service: AuthService, mock_db: MagicMock, sample_user: User
    ) -> None:
        """Test that expired token raises InvalidTokenError."""
        # Arrange
        token_hash = "hashed_token"
        AuthToken(
            id=uuid.uuid4(),
            user_id=sample_user.id,
            token_hash=token_hash,
            type="MAGIC_LINK",
            expires_at=datetime.now(UTC) - timedelta(minutes=1),  # Expired
            used_at=None,
        )

        with (
            patch("app.services.auth_service.decode_token") as mock_decode,
            patch("app.services.auth_service.hash_token", return_value=token_hash),
        ):
            mock_decode.return_value = {"sub": str(sample_user.id), "type": "magic_link"}
            mock_db.scalar = AsyncMock(return_value=None)  # Token not found (expired)

            # Act & Assert
            with pytest.raises(InvalidTokenError, match="Token invalid or already used"):
                await auth_service.verify_magic_link(token="expired_token")


# ==============================================================================
# Tests for refresh_access_token()
# ==============================================================================


class TestRefreshAccessToken:
    """Tests for AuthService.refresh_access_token method."""

    @pytest.mark.asyncio
    async def test_refresh_access_token_when_valid_token_then_returns_new_access(
        self, auth_service: AuthService, mock_db: MagicMock, sample_user: User
    ) -> None:
        """Test refreshing with valid token returns new access token."""
        # Arrange
        token_hash = "hashed_refresh_token"
        expires_at = datetime.now(UTC) + timedelta(days=7)

        auth_token = AuthToken(
            id=uuid.uuid4(),
            user_id=sample_user.id,
            token_hash=token_hash,
            type="REFRESH",
            expires_at=expires_at,
            used_at=None,
        )

        with (
            patch("app.services.auth_service.hash_token", return_value=token_hash),
            patch("app.services.auth_service.create_access_token") as mock_create_token,
        ):
            mock_create_token.return_value = "new_access_token_123"
            mock_db.scalar = AsyncMock(return_value=auth_token)
            mock_db.get = AsyncMock(return_value=sample_user)

            # Act
            result = await auth_service.refresh_access_token(raw_refresh_token="raw_refresh")

            # Assert
            assert isinstance(result, TokenResponse)
            assert result.access_token == "new_access_token_123"

    @pytest.mark.asyncio
    async def test_refresh_access_token_when_token_not_found_raises_error(
        self, auth_service: AuthService, mock_db: MagicMock
    ) -> None:
        """Test that invalid refresh token raises InvalidTokenError."""
        # Arrange
        with patch("app.services.auth_service.hash_token", return_value="unknown_hash"):
            mock_db.scalar = AsyncMock(return_value=None)

            # Act & Assert
            with pytest.raises(InvalidTokenError, match="Refresh token invalid or expired"):
                await auth_service.refresh_access_token(raw_refresh_token="invalid_token")

    @pytest.mark.asyncio
    async def test_refresh_access_token_when_token_already_used_raises_error(
        self, auth_service: AuthService, mock_db: MagicMock, sample_user: User
    ) -> None:
        """Test that used refresh token raises InvalidTokenError."""
        # Arrange
        token_hash = "hashed_token"
        AuthToken(
            id=uuid.uuid4(),
            user_id=sample_user.id,
            token_hash=token_hash,
            type="REFRESH",
            expires_at=datetime.now(UTC) + timedelta(days=7),
            used_at=datetime.now(UTC),  # Already used
        )

        with patch("app.services.auth_service.hash_token", return_value=token_hash):
            mock_db.scalar = AsyncMock(return_value=None)  # Not found (used)

            # Act & Assert
            with pytest.raises(InvalidTokenError, match="Refresh token invalid or expired"):
                await auth_service.refresh_access_token(raw_refresh_token="used_token")

    @pytest.mark.asyncio
    async def test_refresh_access_token_when_token_expired_raises_error(
        self, auth_service: AuthService, mock_db: MagicMock, sample_user: User
    ) -> None:
        """Test that expired refresh token raises InvalidTokenError."""
        # Arrange
        token_hash = "hashed_token"
        AuthToken(
            id=uuid.uuid4(),
            user_id=sample_user.id,
            token_hash=token_hash,
            type="REFRESH",
            expires_at=datetime.now(UTC) - timedelta(days=1),  # Expired
            used_at=None,
        )

        with patch("app.services.auth_service.hash_token", return_value=token_hash):
            mock_db.scalar = AsyncMock(return_value=None)  # Not found (expired)

            # Act & Assert
            with pytest.raises(InvalidTokenError, match="Refresh token invalid or expired"):
                await auth_service.refresh_access_token(raw_refresh_token="expired_token")

    @pytest.mark.asyncio
    async def test_refresh_access_token_when_user_not_found_raises_error(
        self, auth_service: AuthService, mock_db: MagicMock
    ) -> None:
        """Test that deleted user raises InvalidTokenError."""
        # Arrange
        token_hash = "hashed_token"
        expires_at = datetime.now(UTC) + timedelta(days=7)

        auth_token = AuthToken(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            token_hash=token_hash,
            type="REFRESH",
            expires_at=expires_at,
            used_at=None,
        )

        with patch("app.services.auth_service.hash_token", return_value=token_hash):
            mock_db.scalar = AsyncMock(return_value=auth_token)
            mock_db.get = AsyncMock(return_value=None)  # User deleted

            # Act & Assert
            with pytest.raises(InvalidTokenError, match="User not found"):
                await auth_service.refresh_access_token(raw_refresh_token="raw_token")


# ==============================================================================
# Tests for logout()
# ==============================================================================


class TestLogout:
    """Tests for AuthService.logout method."""

    @pytest.mark.asyncio
    async def test_logout_when_valid_token_then_marks_used(
        self, auth_service: AuthService, mock_db: MagicMock, sample_user: User
    ) -> None:
        """Test that logout marks token as used."""
        # Arrange
        token_hash = "hashed_token"
        auth_token = AuthToken(
            id=uuid.uuid4(),
            user_id=sample_user.id,
            token_hash=token_hash,
            type="REFRESH",
            expires_at=datetime.now(UTC) + timedelta(days=7),
            used_at=None,
        )

        with patch("app.services.auth_service.hash_token", return_value=token_hash):
            mock_db.scalar = AsyncMock(return_value=auth_token)

            # Act
            await auth_service.logout(raw_refresh_token="raw_token")

            # Assert
            assert auth_token.used_at is not None
            mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_logout_when_token_not_found_then_does_nothing(
        self, auth_service: AuthService, mock_db: MagicMock
    ) -> None:
        """Test that logout with invalid token does nothing."""
        # Arrange
        with patch("app.services.auth_service.hash_token", return_value="unknown_hash"):
            mock_db.scalar = AsyncMock(return_value=None)

            # Act - should not raise
            await auth_service.logout(raw_refresh_token="invalid_token")

            # Assert
            mock_db.flush.assert_not_called()


# ==============================================================================
# Tests for change_password()
# ==============================================================================


class TestChangePassword:
    """Tests for AuthService.change_password method."""

    @pytest.mark.asyncio
    async def test_change_password_when_correct_current_then_password_updated(
        self,
        auth_service: AuthService,
        mock_db: MagicMock,
        sample_user: User,
    ) -> None:
        """Test that change_password updates password when current is correct."""
        # Arrange
        current_password = "OldPass123!"
        new_password = "NewPass456!"
        original_hash = hash_password(current_password)
        sample_user.hashed_password = original_hash
        mock_db.get = AsyncMock(return_value=sample_user)

        with (
            patch(
                "app.services.auth_service.verify_password",
                return_value=True,
            ) as mock_verify,
            patch(
                "app.services.auth_service.hash_password",
                return_value="new_hashed_password",
            ) as mock_hash,
        ):
            # Act
            await auth_service.change_password(
                user_id=sample_user.id,
                current_password=current_password,
                new_password=new_password,
            )

            # Assert
            mock_verify.assert_called_once_with(current_password, original_hash)
            mock_hash.assert_called_once_with(new_password)
            assert sample_user.hashed_password == "new_hashed_password"
            mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_change_password_when_wrong_current_then_raises_error(
        self,
        auth_service: AuthService,
        mock_db: MagicMock,
        sample_user: User,
    ) -> None:
        """Test that change_password raises error when current password is wrong."""
        # Arrange
        wrong_current = "WrongPass123!"
        new_password = "NewPass456!"
        sample_user.hashed_password = hash_password("CorrectPass!")
        mock_db.get = AsyncMock(return_value=sample_user)

        with patch(
            "app.services.auth_service.verify_password",
            return_value=False,
        ):
            # Act & Assert
            with pytest.raises(ValueError, match="Current password is incorrect"):
                await auth_service.change_password(
                    user_id=sample_user.id,
                    current_password=wrong_current,
                    new_password=new_password,
                )

    @pytest.mark.asyncio
    async def test_change_password_when_user_not_found_then_raises_error(
        self,
        auth_service: AuthService,
        mock_db: MagicMock,
    ) -> None:
        """Test that change_password raises error when user not found."""
        # Arrange
        mock_db.get = AsyncMock(return_value=None)

        # Act & Assert
        with pytest.raises(ValueError, match="User not found"):
            await auth_service.change_password(
                user_id=uuid.uuid4(),
                current_password="old",
                new_password="new",
            )

    @pytest.mark.asyncio
    async def test_change_password_when_no_password_set_then_raises_error(
        self,
        auth_service: AuthService,
        mock_db: MagicMock,
        sample_user: User,
    ) -> None:
        """Test that change_password raises error when user has no password set."""
        # Arrange
        sample_user.hashed_password = None
        mock_db.get = AsyncMock(return_value=sample_user)

        # Act & Assert
        with pytest.raises(ValueError, match="User has no password set"):
            await auth_service.change_password(
                user_id=sample_user.id,
                current_password="old",
                new_password="new",
            )


# ==============================================================================
# Tests for verify_magic_link_get_token()
# ==============================================================================


class TestVerifyMagicLinkGetToken:
    """Tests for AuthService.verify_magic_link_get_token method."""

    @pytest.mark.asyncio
    async def test_verify_magic_link_get_token_when_valid_token_then_returns_scoped_token(
        self, auth_service: AuthService, mock_db: MagicMock, sample_user: User
    ) -> None:
        """Test verifying valid magic link token returns scoped JWT for password setup."""
        # Arrange
        valid_token = "valid_magic_link_token"
        token_hash = "hashed_token"
        expires_at = datetime.now(UTC) + timedelta(minutes=10)

        auth_token = AuthToken(
            id=uuid.uuid4(),
            user_id=sample_user.id,
            token_hash=token_hash,
            type="MAGIC_LINK",
            expires_at=expires_at,
            used_at=None,
        )

        with (
            patch("app.services.auth_service.decode_token") as mock_decode,
            patch("app.services.auth_service.hash_token", return_value=token_hash),
            patch("app.services.auth_service.create_magic_link_token") as mock_create_token,
        ):
            mock_decode.return_value = {"sub": str(sample_user.id), "type": "magic_link"}
            mock_create_token.return_value = "scoped_jwt_token_123"
            mock_db.scalar = AsyncMock(return_value=auth_token)
            mock_db.get = AsyncMock(return_value=sample_user)

            # Act
            result = await auth_service.verify_magic_link_get_token(token=valid_token)

            # Assert
            assert result == "scoped_jwt_token_123"
            mock_db.flush.assert_called()

    @pytest.mark.asyncio
    async def test_verify_magic_link_get_token_when_invalid_token_raises_error(
        self, auth_service: AuthService, mock_db: MagicMock
    ) -> None:
        """Test that malformed token raises InvalidTokenError."""
        # Arrange
        with patch("app.services.auth_service.decode_token") as mock_decode:
            mock_decode.side_effect = InvalidTokenError("Invalid token")

            # Act & Assert
            with pytest.raises(InvalidTokenError):
                await auth_service.verify_magic_link_get_token(token="malformed_token")

    @pytest.mark.asyncio
    async def test_verify_magic_link_get_token_when_wrong_token_type_raises_error(
        self, auth_service: AuthService, mock_db: MagicMock, sample_user: User
    ) -> None:
        """Test that non-magic-link token raises InvalidTokenError."""
        # Arrange
        with patch("app.services.auth_service.decode_token") as mock_decode:
            mock_decode.return_value = {"sub": str(sample_user.id), "type": "refresh"}

            # Act & Assert
            with pytest.raises(InvalidTokenError, match="Not a magic link token"):
                await auth_service.verify_magic_link_get_token(token="some_refresh_token")

    @pytest.mark.asyncio
    async def test_verify_magic_link_get_token_when_token_already_used_raises_error(
        self, auth_service: AuthService, mock_db: MagicMock, sample_user: User
    ) -> None:
        """Test that used token raises InvalidTokenError."""
        # Arrange
        token_hash = "hashed_token"

        with (
            patch("app.services.auth_service.decode_token") as mock_decode,
            patch("app.services.auth_service.hash_token", return_value=token_hash),
        ):
            mock_decode.return_value = {"sub": str(sample_user.id), "type": "magic_link"}
            mock_db.scalar = AsyncMock(return_value=None)  # Token not found (used)

            # Act & Assert
            with pytest.raises(InvalidTokenError, match="Token invalid or already used"):
                await auth_service.verify_magic_link_get_token(token="used_token")

    @pytest.mark.asyncio
    async def test_verify_magic_link_get_token_when_token_expired_raises_error(
        self, auth_service: AuthService, mock_db: MagicMock, sample_user: User
    ) -> None:
        """Test that expired token raises InvalidTokenError."""
        # Arrange
        token_hash = "hashed_token"

        with (
            patch("app.services.auth_service.decode_token") as mock_decode,
            patch("app.services.auth_service.hash_token", return_value=token_hash),
        ):
            mock_decode.return_value = {"sub": str(sample_user.id), "type": "magic_link"}
            mock_db.scalar = AsyncMock(return_value=None)  # Expired tokens don't match query

            # Act & Assert
            with pytest.raises(InvalidTokenError, match="Token invalid or already used"):
                await auth_service.verify_magic_link_get_token(token="expired_token")

    @pytest.mark.asyncio
    async def test_verify_magic_link_get_token_when_user_not_found_raises_error(
        self, auth_service: AuthService, mock_db: MagicMock, sample_user: User
    ) -> None:
        """Test that user not found raises InvalidTokenError."""
        # Arrange
        token_hash = "hashed_token"
        expires_at = datetime.now(UTC) + timedelta(minutes=10)

        auth_token = AuthToken(
            id=uuid.uuid4(),
            user_id=sample_user.id,
            token_hash=token_hash,
            type="MAGIC_LINK",
            expires_at=expires_at,
            used_at=None,
        )

        with (
            patch("app.services.auth_service.decode_token") as mock_decode,
            patch("app.services.auth_service.hash_token", return_value=token_hash),
        ):
            mock_decode.return_value = {"sub": str(sample_user.id), "type": "magic_link"}
            mock_db.scalar = AsyncMock(return_value=auth_token)
            mock_db.get = AsyncMock(return_value=None)  # User not found

            # Act & Assert
            with pytest.raises(InvalidTokenError, match="User not found"):
                await auth_service.verify_magic_link_get_token(token="valid_token")


# ==============================================================================
# Tests for set_password_from_scoped_token()
# ==============================================================================


class TestSetPasswordFromScopedToken:
    """Tests for AuthService.set_password_from_scoped_token method."""

    @pytest.mark.asyncio
    async def test_set_password_from_scoped_token_when_valid_then_sets_password_and_returns_tokens(
        self, auth_service: AuthService, mock_db: MagicMock, sample_user: User
    ) -> None:
        """Test setting password from scoped token returns full-access tokens."""
        # Arrange
        sample_user.hashed_password = None  # User has no password yet
        token_payload = {"sub": str(sample_user.id), "type": "magic_link", "scope": "password_setup"}

        with (
            patch("app.services.auth_service.create_access_token") as mock_access,
            patch("app.services.auth_service.generate_refresh_token") as mock_refresh,
            patch("app.services.auth_service.store_refresh_token"),
            patch("app.services.auth_service.hash_password") as mock_hash,
        ):
            mock_access.return_value = "access_token_123"
            mock_refresh.return_value = ("raw_refresh", "hashed_refresh")
            mock_hash.return_value = "hashed_new_password"
            mock_db.get = AsyncMock(return_value=sample_user)

            # Act
            result = await auth_service.set_password_from_scoped_token(
                token_payload=token_payload,
                new_password="SecurePass123!",
            )

            # Assert
            assert isinstance(result, LoginResponse)
            assert result.access_token == "access_token_123"
            assert result.refresh_token == "raw_refresh"
            assert sample_user.hashed_password == "hashed_new_password"
            mock_db.flush.assert_called()

    @pytest.mark.asyncio
    async def test_set_password_from_scoped_token_when_wrong_token_type_raises_error(
        self, auth_service: AuthService, mock_db: MagicMock
    ) -> None:
        """Test that non-magic-link token raises ValueError."""
        # Arrange
        token_payload = {"sub": str(uuid.uuid4()), "type": "refresh", "scope": "password_setup"}

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid token type"):
            await auth_service.set_password_from_scoped_token(
                token_payload=token_payload,
                new_password="SecurePass123!",
            )

    @pytest.mark.asyncio
    async def test_set_password_from_scoped_token_when_missing_scope_raises_error(
        self, auth_service: AuthService, mock_db: MagicMock
    ) -> None:
        """Test that token without password_setup scope raises ValueError."""
        # Arrange
        token_payload = {"sub": str(uuid.uuid4()), "type": "magic_link", "scope": "other"}

        # Act & Assert
        with pytest.raises(ValueError, match="Token does not have password_setup scope"):
            await auth_service.set_password_from_scoped_token(
                token_payload=token_payload,
                new_password="SecurePass123!",
            )

    @pytest.mark.asyncio
    async def test_set_password_from_scoped_token_when_user_not_found_raises_error(
        self, auth_service: AuthService, mock_db: MagicMock
    ) -> None:
        """Test that user not found raises InvalidTokenError."""
        # Arrange
        token_payload = {
            "sub": str(uuid.uuid4()),
            "type": "magic_link",
            "scope": "password_setup",
        }

        with patch("app.services.auth_service.create_access_token"):
            mock_db.get = AsyncMock(return_value=None)

            # Act & Assert
            with pytest.raises(InvalidTokenError, match="User not found"):
                await auth_service.set_password_from_scoped_token(
                    token_payload=token_payload,
                    new_password="SecurePass123!",
                )

    @pytest.mark.asyncio
    async def test_set_password_from_scoped_token_when_password_already_set_raises_error(
        self, auth_service: AuthService, mock_db: MagicMock, sample_user: User
    ) -> None:
        """Test that user with existing password raises ValueError."""
        # Arrange
        token_payload = {
            "sub": str(sample_user.id),
            "type": "magic_link",
            "scope": "password_setup",
        }
        sample_user.hashed_password = "existing_hash"  # User already has password

        with patch("app.services.auth_service.create_access_token"):
            mock_db.get = AsyncMock(return_value=sample_user)

            # Act & Assert
            with pytest.raises(ValueError, match="Password already set"):
                await auth_service.set_password_from_scoped_token(
                    token_payload=token_payload,
                    new_password="SecurePass123!",
                )


class TestMustChangePassword:
    """Tests for must_change_password flag in login and change_password."""

    @pytest.mark.asyncio
    async def test_login_when_must_change_password_true_then_flag_in_response(
        self, auth_service: AuthService, mock_db: MagicMock
    ) -> None:
        """login returns must_change_password=True when user.must_change_password is True."""
        user = User(
            id=uuid.uuid4(),
            email="a@b.com",
            first_name="A",
            last_name="B",
            role="TEACHER",
            school_id=uuid.uuid4(),
            is_active=True,
            hashed_password="hashed",
            must_change_password=True,
        )

        mock_db.scalar = AsyncMock(return_value=user)

        with (
            patch("app.services.auth_service.verify_password", return_value=True),
            patch("app.services.auth_service.create_access_token", return_value="access"),
            patch("app.services.auth_service.generate_refresh_token", return_value=("raw", "hashed")),
            patch("app.services.auth_service.store_refresh_token", new_callable=AsyncMock),
        ):
            response = await auth_service.login(email_or_username="a@b.com", password="pass")

        assert response.must_change_password is True

    @pytest.mark.asyncio
    async def test_login_when_must_change_password_false_then_flag_false_in_response(
        self, auth_service: AuthService, mock_db: MagicMock
    ) -> None:
        """login returns must_change_password=False when user.must_change_password is False."""
        user = User(
            id=uuid.uuid4(),
            email="a@b.com",
            first_name="A",
            last_name="B",
            role="TEACHER",
            school_id=uuid.uuid4(),
            is_active=True,
            hashed_password="hashed",
            must_change_password=False,
        )

        mock_db.scalar = AsyncMock(return_value=user)

        with (
            patch("app.services.auth_service.verify_password", return_value=True),
            patch("app.services.auth_service.create_access_token", return_value="access"),
            patch("app.services.auth_service.generate_refresh_token", return_value=("raw", "hashed")),
            patch("app.services.auth_service.store_refresh_token", new_callable=AsyncMock),
        ):
            response = await auth_service.login(email_or_username="a@b.com", password="pass")

        assert response.must_change_password is False

    @pytest.mark.asyncio
    async def test_change_password_clears_must_change_password_flag(
        self, auth_service: AuthService, mock_db: MagicMock
    ) -> None:
        """change_password sets must_change_password=False after successful change."""
        user = User(
            id=uuid.uuid4(),
            email="a@b.com",
            first_name="A",
            last_name="B",
            role="TEACHER",
            school_id=uuid.uuid4(),
            is_active=True,
            hashed_password="old_hash",
            must_change_password=True,
        )

        mock_db.get = AsyncMock(return_value=user)

        with (
            patch("app.services.auth_service.verify_password", return_value=True),
            patch("app.services.auth_service.hash_password", return_value="new_hash"),
        ):
            await auth_service.change_password(user_id=user.id, current_password="old", new_password="Newpass1!")

        assert user.must_change_password is False
        assert user.hashed_password == "new_hash"


class TestSendPasswordResetEmail:
    @pytest.mark.asyncio
    async def test_send_password_reset_email_when_valid_email_then_token_stored_and_email_sent(
        self, auth_service: AuthService, mock_db: MagicMock
    ) -> None:
        """send_password_reset_email stores a PASSWORD_RESET token and sends email for active users."""
        user = User(
            id=uuid.uuid4(),
            school_id=uuid.uuid4(),
            email="teacher@school.edu",
            first_name="Rachel",
            last_name="Morgan",
            role="TEACHER",
            is_active=True,
            hashed_password="hashed",
            must_change_password=False,
        )
        mock_db.scalar = AsyncMock(return_value=user)

        mock_email_send = AsyncMock()
        with (
            patch("app.services.auth_service.store_password_reset_token", new_callable=AsyncMock),
            patch("app.services.auth_service.EmailService") as MockEmailService,
        ):
            MockEmailService.return_value.send = mock_email_send
            await auth_service.send_password_reset_email("teacher@school.edu")

        mock_email_send.assert_called_once()
        call_kwargs = mock_email_send.call_args[1]
        assert call_kwargs["template"] == "password_reset.html.jinja2"
        assert call_kwargs["to"] == "teacher@school.edu"

    @pytest.mark.asyncio
    async def test_send_password_reset_email_when_unknown_email_then_returns_silently(
        self, auth_service: AuthService, mock_db: MagicMock
    ) -> None:
        """send_password_reset_email returns without error when email is not found."""
        mock_db.scalar = AsyncMock(return_value=None)

        with patch("app.services.auth_service.EmailService") as MockEmailService:
            await auth_service.send_password_reset_email("nobody@nowhere.com")

        MockEmailService.return_value.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_password_reset_email_when_inactive_user_then_returns_silently(
        self, auth_service: AuthService, mock_db: MagicMock
    ) -> None:
        """send_password_reset_email returns without error for inactive users."""
        mock_db.scalar = AsyncMock(return_value=None)  # active filter returns nothing

        with patch("app.services.auth_service.EmailService") as MockEmailService:
            await auth_service.send_password_reset_email("inactive@school.edu")

        MockEmailService.return_value.send.assert_not_called()


class TestResetPassword:
    @pytest.mark.asyncio
    async def test_reset_password_when_valid_token_then_password_updated_and_token_marked_used(
        self, auth_service: AuthService, mock_db: MagicMock
    ) -> None:
        """reset_password hashes new password and marks token as used on valid token."""
        user = User(
            id=uuid.uuid4(),
            email="user@school.edu",
            first_name="Alice",
            role="STUDENT",
            hashed_password="old_hash",
            must_change_password=True,
        )
        auth_token = AuthToken(
            user_id=user.id,
            token_hash="some_hash",
            type="PASSWORD_RESET",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            used_at=None,
        )
        mock_db.scalar = AsyncMock(return_value=auth_token)
        mock_db.get = AsyncMock(return_value=user)

        with patch("app.services.auth_service.hash_password", return_value="new_hash"):
            await auth_service.reset_password("raw_token", "NewPassword1!")

        assert user.hashed_password == "new_hash"
        assert user.must_change_password is False
        assert auth_token.used_at is not None

    @pytest.mark.asyncio
    async def test_reset_password_when_expired_token_then_raises_invalid_token_error(
        self, auth_service: AuthService, mock_db: MagicMock
    ) -> None:
        """reset_password raises InvalidTokenError when token is not found (expired or used)."""
        mock_db.scalar = AsyncMock(return_value=None)

        with pytest.raises(InvalidTokenError):
            await auth_service.reset_password("bad_token", "NewPassword1!")

    @pytest.mark.asyncio
    async def test_reset_password_when_used_token_then_raises_invalid_token_error(
        self, auth_service: AuthService, mock_db: MagicMock
    ) -> None:
        """reset_password raises InvalidTokenError when query finds no token (used tokens excluded by query)."""
        mock_db.scalar = AsyncMock(return_value=None)

        with pytest.raises(InvalidTokenError):
            await auth_service.reset_password("used_token", "NewPassword1!")

    @pytest.mark.asyncio
    async def test_reset_password_when_unknown_token_then_raises_invalid_token_error(
        self, auth_service: AuthService, mock_db: MagicMock
    ) -> None:
        """reset_password raises InvalidTokenError for completely unknown tokens."""
        mock_db.scalar = AsyncMock(return_value=None)

        with pytest.raises(InvalidTokenError):
            await auth_service.reset_password("unknown_token", "NewPassword1!")


# ---------------------------------------------------------------------------
# Impersonation — Kaihle Admin "log in as user"
# ---------------------------------------------------------------------------


@pytest.fixture
def admin_user() -> User:
    """An active KAIHLE_ADMIN — the only role permitted to impersonate."""
    return User(
        id=uuid.uuid4(),
        school_id=None,
        email="admin@kaihle.com",
        hashed_password="hashed_password",
        first_name="Ada",
        last_name="Admin",
        role="KAIHLE_ADMIN",
        is_active=True,
    )


@pytest.fixture
def student_user() -> User:
    """An active STUDENT — a valid impersonation target."""
    return User(
        id=uuid.uuid4(),
        school_id=uuid.uuid4(),
        email="student@example.com",
        hashed_password="hashed_password",
        first_name="Sam",
        last_name="Student",
        role="STUDENT",
        is_active=True,
    )


class TestStartImpersonation:
    """Tests for AuthService.start_impersonation."""

    @pytest.mark.asyncio
    async def test_start_impersonation_when_target_missing_then_raises_user_not_found(
        self, auth_service: AuthService, mock_db: MagicMock, admin_user: User
    ) -> None:
        mock_db.get = AsyncMock(return_value=None)

        with pytest.raises(UserNotFoundError):
            await auth_service.start_impersonation(admin_user, uuid.uuid4())

    @pytest.mark.asyncio
    async def test_start_impersonation_when_target_is_kaihle_admin_then_raises_not_allowed(
        self, auth_service: AuthService, mock_db: MagicMock, admin_user: User
    ) -> None:
        """One platform admin acting as another would be unattributable — refuse it."""
        other_admin = User(
            id=uuid.uuid4(),
            school_id=None,
            email="other@kaihle.com",
            hashed_password="x",
            first_name="Otto",
            last_name="Other",
            role="KAIHLE_ADMIN",
            is_active=True,
        )
        mock_db.get = AsyncMock(return_value=other_admin)

        with pytest.raises(ImpersonationNotAllowedError):
            await auth_service.start_impersonation(admin_user, other_admin.id)

    @pytest.mark.asyncio
    async def test_start_impersonation_when_target_inactive_then_raises_not_allowed(
        self, auth_service: AuthService, mock_db: MagicMock, admin_user: User, student_user: User
    ) -> None:
        student_user.is_active = False
        mock_db.get = AsyncMock(return_value=student_user)

        with pytest.raises(ImpersonationNotAllowedError):
            await auth_service.start_impersonation(admin_user, student_user.id)

    @pytest.mark.asyncio
    async def test_start_impersonation_when_target_is_self_then_raises_not_allowed(
        self, auth_service: AuthService, mock_db: MagicMock, admin_user: User
    ) -> None:
        mock_db.get = AsyncMock(return_value=admin_user)

        with pytest.raises(ImpersonationNotAllowedError):
            await auth_service.start_impersonation(admin_user, admin_user.id)

    @pytest.mark.asyncio
    async def test_start_impersonation_when_valid_target_then_returns_role_specific_url(
        self, auth_service: AuthService, mock_db: MagicMock, admin_user: User, student_user: User
    ) -> None:
        """The link must point at the app that serves the target's role, not the admin's."""
        mock_db.get = AsyncMock(return_value=student_user)

        result = await auth_service.start_impersonation(admin_user, student_user.id)

        assert result.target_app_url == settings.student_app_url
        assert result.redirect_url.startswith(f"{settings.student_app_url}/impersonate?token=")
        assert result.target_user_id == student_user.id
        assert result.target_role == "STUDENT"

    @pytest.mark.asyncio
    async def test_start_impersonation_when_valid_target_then_stores_single_use_token(
        self, auth_service: AuthService, mock_db: MagicMock, admin_user: User, student_user: User
    ) -> None:
        """The token hash is persisted so redemption can burn it exactly once."""
        mock_db.get = AsyncMock(return_value=student_user)

        result = await auth_service.start_impersonation(admin_user, student_user.id)

        stored = [c.args[0] for c in mock_db.add.call_args_list if isinstance(c.args[0], AuthToken)]
        assert len(stored) == 1
        assert stored[0].type == AuthTokenType.IMPERSONATION
        assert stored[0].user_id == student_user.id
        assert stored[0].used_at is None
        raw = result.redirect_url.split("token=")[1]
        assert stored[0].token_hash == hash_token(raw)

    @pytest.mark.asyncio
    async def test_start_impersonation_when_valid_target_then_token_carries_impersonator(
        self, auth_service: AuthService, mock_db: MagicMock, admin_user: User, student_user: User
    ) -> None:
        mock_db.get = AsyncMock(return_value=student_user)

        result = await auth_service.start_impersonation(admin_user, student_user.id)

        payload = decode_token(result.redirect_url.split("token=")[1])
        assert payload["sub"] == str(student_user.id)
        assert payload["act"] == str(admin_user.id)
        assert payload["type"] == "impersonation_handoff"


class TestRedeemImpersonation:
    """Tests for AuthService.redeem_impersonation."""

    @staticmethod
    def _valid_token(target: User, admin: User) -> str:
        return create_impersonation_handoff_token(target.id, admin.id)

    @staticmethod
    def _auth_token_row(target: User) -> AuthToken:
        return AuthToken(
            id=uuid.uuid4(),
            user_id=target.id,
            token_hash="hash",
            type=AuthTokenType.IMPERSONATION,
            expires_at=datetime.now(UTC) + timedelta(seconds=60),
            used_at=None,
        )

    @pytest.mark.asyncio
    async def test_redeem_impersonation_when_token_valid_then_access_token_carries_act_claim(
        self, auth_service: AuthService, mock_db: MagicMock, admin_user: User, student_user: User
    ) -> None:
        """The acting admin must remain visible on the session, or writes are unattributable."""
        token = self._valid_token(student_user, admin_user)
        mock_db.scalar = AsyncMock(return_value=self._auth_token_row(student_user))
        mock_db.get = AsyncMock(side_effect=[student_user, admin_user])

        result = await auth_service.redeem_impersonation(token)

        payload = decode_token(result.access_token)
        assert payload["sub"] == str(student_user.id)
        assert payload["act"] == str(admin_user.id)
        assert payload["impersonated"] is True
        assert payload["role"] == "STUDENT"

    @pytest.mark.asyncio
    async def test_redeem_impersonation_when_token_valid_then_returns_no_refresh_token(
        self, auth_service: AuthService, mock_db: MagicMock, admin_user: User, student_user: User
    ) -> None:
        """A refresh would rebuild the token from the User row and drop the act claim."""
        token = self._valid_token(student_user, admin_user)
        mock_db.scalar = AsyncMock(return_value=self._auth_token_row(student_user))
        mock_db.get = AsyncMock(side_effect=[student_user, admin_user])

        result = await auth_service.redeem_impersonation(token)

        assert result.refresh_token is None
        assert result.impersonator is not None
        assert result.impersonator["id"] == str(admin_user.id)

    @pytest.mark.asyncio
    async def test_redeem_impersonation_when_token_valid_then_marks_token_used(
        self, auth_service: AuthService, mock_db: MagicMock, admin_user: User, student_user: User
    ) -> None:
        token = self._valid_token(student_user, admin_user)
        row = self._auth_token_row(student_user)
        mock_db.scalar = AsyncMock(return_value=row)
        mock_db.get = AsyncMock(side_effect=[student_user, admin_user])

        await auth_service.redeem_impersonation(token)

        assert row.used_at is not None

    @pytest.mark.asyncio
    async def test_redeem_impersonation_when_called_then_last_login_at_unchanged(
        self, auth_service: AuthService, mock_db: MagicMock, admin_user: User, student_user: User
    ) -> None:
        """last_login_at reflects the real user's activity — support access must not pollute it."""
        student_user.last_login_at = None
        token = self._valid_token(student_user, admin_user)
        mock_db.scalar = AsyncMock(return_value=self._auth_token_row(student_user))
        mock_db.get = AsyncMock(side_effect=[student_user, admin_user])

        await auth_service.redeem_impersonation(token)

        assert student_user.last_login_at is None

    @pytest.mark.asyncio
    async def test_redeem_impersonation_when_token_reused_then_raises_invalid_token(
        self, auth_service: AuthService, mock_db: MagicMock, admin_user: User, student_user: User
    ) -> None:
        """Used tokens are excluded by the query, so the second redemption finds nothing."""
        token = self._valid_token(student_user, admin_user)
        mock_db.scalar = AsyncMock(return_value=None)

        with pytest.raises(InvalidTokenError):
            await auth_service.redeem_impersonation(token)

    @pytest.mark.asyncio
    async def test_redeem_impersonation_when_token_expired_then_raises_invalid_token(
        self, auth_service: AuthService, mock_db: MagicMock, admin_user: User, student_user: User
    ) -> None:
        expired = create_impersonation_handoff_token(student_user.id, admin_user.id, expires_in_seconds=-1)

        with pytest.raises(InvalidTokenError):
            await auth_service.redeem_impersonation(expired)

    @pytest.mark.asyncio
    async def test_redeem_impersonation_when_wrong_token_type_then_raises_invalid_token(
        self, auth_service: AuthService, mock_db: MagicMock, student_user: User
    ) -> None:
        """A password-setup magic link must not be redeemable as an impersonation grant."""
        magic = create_magic_link_token(student_user.id)

        with pytest.raises(InvalidTokenError):
            await auth_service.redeem_impersonation(magic)

    @pytest.mark.asyncio
    async def test_redeem_impersonation_when_target_deactivated_after_mint_then_raises_invalid_token(
        self, auth_service: AuthService, mock_db: MagicMock, admin_user: User, student_user: User
    ) -> None:
        """Authorisation is re-checked at redemption, not just at mint time."""
        token = self._valid_token(student_user, admin_user)
        student_user.is_active = False
        mock_db.scalar = AsyncMock(return_value=self._auth_token_row(student_user))
        mock_db.get = AsyncMock(side_effect=[student_user, admin_user])

        with pytest.raises(InvalidTokenError):
            await auth_service.redeem_impersonation(token)

    @pytest.mark.asyncio
    async def test_redeem_impersonation_when_impersonator_no_longer_admin_then_raises_invalid_token(
        self, auth_service: AuthService, mock_db: MagicMock, admin_user: User, student_user: User
    ) -> None:
        """A demoted admin's outstanding link must stop working."""
        token = self._valid_token(student_user, admin_user)
        admin_user.role = "TEACHER"
        mock_db.scalar = AsyncMock(return_value=self._auth_token_row(student_user))
        mock_db.get = AsyncMock(side_effect=[student_user, admin_user])

        with pytest.raises(InvalidTokenError):
            await auth_service.redeem_impersonation(token)

    @pytest.mark.asyncio
    async def test_redeem_impersonation_when_token_valid_then_commits_the_burn(
        self, auth_service: AuthService, mock_db: MagicMock, admin_user: User, student_user: User
    ) -> None:
        """The burn is committed, not merely flushed."""
        token = self._valid_token(student_user, admin_user)
        mock_db.scalar = AsyncMock(return_value=self._auth_token_row(student_user))
        mock_db.get = AsyncMock(side_effect=[student_user, admin_user])

        await auth_service.redeem_impersonation(token)

        mock_db.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_redeem_impersonation_when_post_burn_check_fails_then_burn_is_still_committed(
        self, auth_service: AuthService, mock_db: MagicMock, admin_user: User, student_user: User
    ) -> None:
        """A rejected redemption must still spend the token.

        get_db rolls back on exception, so a burn that was only flushed would be
        discarded and the link would stay redeemable for the rest of its TTL.
        One attempt spends the token whether or not it succeeds.
        """
        token = self._valid_token(student_user, admin_user)
        row = self._auth_token_row(student_user)
        student_user.is_active = False  # rejected AFTER the burn
        mock_db.scalar = AsyncMock(return_value=row)
        mock_db.get = AsyncMock(side_effect=[student_user, admin_user])

        with pytest.raises(InvalidTokenError):
            await auth_service.redeem_impersonation(token)

        assert row.used_at is not None
        mock_db.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_redeem_impersonation_when_impersonator_rejected_then_burn_is_still_committed(
        self, auth_service: AuthService, mock_db: MagicMock, admin_user: User, student_user: User
    ) -> None:
        """Same guarantee on the impersonator-authorisation path."""
        token = self._valid_token(student_user, admin_user)
        row = self._auth_token_row(student_user)
        admin_user.role = "TEACHER"
        mock_db.scalar = AsyncMock(return_value=row)
        mock_db.get = AsyncMock(side_effect=[student_user, admin_user])

        with pytest.raises(InvalidTokenError):
            await auth_service.redeem_impersonation(token)

        assert row.used_at is not None
        mock_db.commit.assert_awaited()
