"""Unit tests for UserService.list_platform_users.

Per Rule 20 (TDD): platform users functionality has named unit tests.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole
from app.services.user_service import UserService


@pytest.fixture
def mock_db() -> MagicMock:
    """Create a mock database session."""
    session = MagicMock(spec=AsyncSession)
    return session


@pytest.fixture
def user_service(mock_db: MagicMock) -> UserService:
    """Create a UserService with mock database."""
    return UserService(mock_db)


class TestListPlatformUsers:
    """Tests for UserService.list_platform_users."""

    @pytest.mark.asyncio
    async def test_list_platform_users_when_no_filter_then_returns_all_users(
        self,
        user_service: UserService,
        mock_db: MagicMock,
    ) -> None:
        """Test listing all users without filters."""
        # Arrange
        user1 = User(
            id=uuid.uuid4(),
            email="user1@test.com",
            first_name="User",
            last_name="One",
            role=UserRole.TEACHER,
            school_id=uuid.uuid4(),
        )
        user2 = User(
            id=uuid.uuid4(),
            email="user2@test.com",
            first_name="User",
            last_name="Two",
            role=UserRole.STUDENT,
            school_id=uuid.uuid4(),
        )

        # Mock the execute result
        mock_result = MagicMock()
        mock_result.all.return_value = [(user1, "School One"), (user2, "School Two")]
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.scalar = AsyncMock(return_value=2)  # total count

        # Act
        users, total = await user_service.list_platform_users()

        # Assert
        assert len(users) == 2
        assert total == 2
        assert users[0].email == "user1@test.com"
        assert users[1].email == "user2@test.com"

    @pytest.mark.asyncio
    async def test_list_platform_users_when_role_filter_then_returns_only_that_role(
        self,
        user_service: UserService,
        mock_db: MagicMock,
    ) -> None:
        """Test filtering users by role."""
        # Arrange
        teacher = User(
            id=uuid.uuid4(),
            email="teacher@test.com",
            first_name="Teach",
            last_name="Er",
            role=UserRole.TEACHER,
            school_id=uuid.uuid4(),
        )

        mock_result = MagicMock()
        mock_result.all.return_value = [(teacher, "Test School")]
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.scalar = AsyncMock(return_value=1)

        # Act
        users, total = await user_service.list_platform_users(role="TEACHER")

        # Assert
        assert len(users) == 1
        assert users[0].role == UserRole.TEACHER

    @pytest.mark.asyncio
    async def test_list_platform_users_when_q_filter_then_searches_name_and_email(
        self,
        user_service: UserService,
        mock_db: MagicMock,
    ) -> None:
        """Test searching users by query string."""
        # Arrange
        user = User(
            id=uuid.uuid4(),
            email="john.doe@test.com",
            first_name="John",
            last_name="Doe",
            role=UserRole.TEACHER,
        )

        mock_result = MagicMock()
        mock_result.all.return_value = [(user, None)]
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.scalar = AsyncMock(return_value=1)

        # Act
        users, total = await user_service.list_platform_users(q="john")

        # Assert
        assert len(users) == 1
        assert users[0].first_name == "John"

    @pytest.mark.asyncio
    async def test_list_platform_users_when_paginated_then_correct_page_returned(
        self,
        user_service: UserService,
        mock_db: MagicMock,
    ) -> None:
        """Test pagination returns correct page."""
        # Arrange
        users_data = [
            User(
                id=uuid.uuid4(),
                email=f"user{i}@test.com",
                first_name=f"User{i}",
                last_name="Test",
                role=UserRole.STUDENT,
            )
            for i in range(5)
        ]

        mock_result = MagicMock()
        mock_result.all.return_value = [(u, None) for u in users_data]
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.scalar = AsyncMock(return_value=25)  # total 25 users

        # Act
        users, total = await user_service.list_platform_users(page=2, page_size=5)

        # Assert
        assert len(users) == 5
        assert total == 25
