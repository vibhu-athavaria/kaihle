"""Unit tests for AuthService."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import InvalidTokenError, hash_password
from app.models.user import AuthToken, User
from app.schemas.auth import LoginResponse, RegisterResponse, TokenResponse
from app.services.auth_service import AuthService


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
            result = await auth_service.login(email="test@example.com", password="correct_password")

            # Assert
            assert isinstance(result, LoginResponse)
            assert result.access_token == "access_token_123"
            assert result.refresh_token == "raw_refresh_token"
            assert result.token_type == "bearer"
            mock_store_refresh.assert_called_once()

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
                await auth_service.login(email="test@example.com", password="wrong_password")

    @pytest.mark.asyncio
    async def test_login_when_user_not_found_raises_value_error(
        self, auth_service: AuthService, mock_db: MagicMock
    ) -> None:
        """Test login with non-existent email raises ValueError."""
        # Arrange
        mock_db.scalar = AsyncMock(return_value=None)

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid credentials"):
            await auth_service.login(email="nonexistent@example.com", password="any_password")

    @pytest.mark.asyncio
    async def test_login_when_inactive_user_raises_value_error(
        self, auth_service: AuthService, mock_db: MagicMock
    ) -> None:
        """Test login with inactive account raises ValueError."""
        # Arrange
        inactive_user = User(
            id=uuid.uuid4(),
            school_id=uuid.uuid4(),
            email="inactive@example.com",
            hashed_password="hashed",
            first_name="Inactive",
            last_name="User",
            role="TEACHER",
            is_active=False,
        )
        mock_db.scalar = AsyncMock(return_value=inactive_user)

        # Act & Assert
        with pytest.raises(ValueError, match="Account is inactive"):
            await auth_service.login(email="inactive@example.com", password="any_password")

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
            await auth_service.login(email="nopass@example.com", password="any_password")


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
