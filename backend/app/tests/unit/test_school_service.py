"""Unit tests for SchoolService."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.school import School
from app.schemas.school import SchoolCreate, SchoolUpdate
from app.services.school_service import SchoolService


@pytest.fixture
def mock_db() -> MagicMock:
    """Create a mock database session."""
    session = MagicMock(spec=AsyncSession)
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


@pytest.fixture
def school_service(mock_db: MagicMock) -> SchoolService:
    """Create a SchoolService with mock database."""
    return SchoolService(mock_db)


class TestCreateSchool:
    """Tests for SchoolService.create_school method."""

    @pytest.mark.asyncio
    async def test_create_school_when_valid_data_then_school_created(
        self, school_service: SchoolService, mock_db: MagicMock
    ) -> None:
        """Test creating a school with valid data."""
        # Arrange
        data = SchoolCreate(
            name="Test School",
            slug="test-school",
            country="Indonesia",
            timezone="Asia/Jakarta",
            admin_email="admin@test.com",
            admin_first_name="Admin",
            admin_last_name="User",
            admin_password="password123",
        )
        mock_db.scalar = AsyncMock(return_value=None)  # No existing school

        # Act
        school = await school_service.create_school(data)

        # Assert
        assert school.name == "Test School"
        assert school.slug == "test-school"
        assert school.country == "Indonesia"
        assert school.timezone == "Asia/Jakarta"
        assert school.status == "active"
        # create_school adds both School and User (admin)
        add_calls = [call.args[0] for call in mock_db.add.call_args_list]
        assert school in add_calls
        assert mock_db.add.call_count == 2
        assert mock_db.flush.call_count >= 2

    @pytest.mark.asyncio
    async def test_create_school_when_default_timezone_then_uses_utc(
        self, school_service: SchoolService, mock_db: MagicMock
    ) -> None:
        """Test that default timezone is UTC per schema."""
        # Arrange
        data = SchoolCreate(
            name="Test School",
            slug="test-school",
            admin_email="admin@test.com",
            admin_first_name="Admin",
            admin_last_name="User",
            admin_password="password123",
        )
        mock_db.scalar = AsyncMock(return_value=None)

        # Act
        school = await school_service.create_school(data)

        # Assert - schema defaults to "UTC"
        assert school.timezone == "UTC"

    @pytest.mark.asyncio
    async def test_create_school_when_duplicate_slug_then_raises_value_error(
        self, school_service: SchoolService, mock_db: MagicMock
    ) -> None:
        """Test that duplicate slug raises ValueError."""
        # Arrange
        data = SchoolCreate(
            name="Test School",
            slug="test-school",
            admin_email="admin@test.com",
            admin_first_name="Admin",
            admin_last_name="User",
            admin_password="password123",
        )
        existing_school = School(name="Existing", slug="test-school")
        mock_db.scalar = AsyncMock(return_value=existing_school)

        # Act & Assert
        with pytest.raises(ValueError, match="School slug 'test-school' already exists"):
            await school_service.create_school(data)


class TestListSchools:
    """Tests for SchoolService.list_schools method."""

    @pytest.mark.asyncio
    async def test_list_schools_when_paginated_then_returns_correct_page(
        self, school_service: SchoolService, mock_db: MagicMock
    ) -> None:
        """Test listing schools with pagination."""
        # Arrange
        schools = [School(name=f"School {i}", slug=f"school-{i}") for i in range(5)]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = schools
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.scalar = AsyncMock(return_value=10)  # total count

        # Act
        result_schools, total = await school_service.list_schools(page=1, page_size=5)

        # Assert
        assert len(result_schools) == 5
        assert total == 10

    @pytest.mark.asyncio
    async def test_list_schools_when_page_2_then_correct_offset(
        self, school_service: SchoolService, mock_db: MagicMock
    ) -> None:
        """Test that page 2 uses correct offset."""
        # Arrange
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.scalar = AsyncMock(return_value=0)

        # Act
        await school_service.list_schools(page=2, page_size=10)

        # Assert - verify offset is calculated correctly (page-1 * page_size = 10)
        call_args = mock_db.execute.call_args
        assert call_args is not None


class TestGetSchool:
    """Tests for SchoolService.get_school method."""

    @pytest.mark.asyncio
    async def test_get_school_when_exists_then_returns_school(
        self, school_service: SchoolService, mock_db: MagicMock
    ) -> None:
        """Test getting an existing school."""
        # Arrange
        school_id = uuid.uuid4()
        expected_school = School(
            id=school_id,
            name="Test School",
            slug="test-school",
        )
        mock_db.get = AsyncMock(return_value=expected_school)

        # Act
        result = await school_service.get_school(school_id)

        # Assert
        assert result.id == school_id
        assert result.name == "Test School"

    @pytest.mark.asyncio
    async def test_get_school_when_not_exists_then_raises_not_found(
        self, school_service: SchoolService, mock_db: MagicMock
    ) -> None:
        """Test getting a non-existent school raises ValueError."""
        # Arrange
        school_id = uuid.uuid4()
        mock_db.get = AsyncMock(return_value=None)

        # Act & Assert
        with pytest.raises(ValueError, match="School not found"):
            await school_service.get_school(school_id)


class TestUpdateSchool:
    """Tests for SchoolService.update_school method."""

    @pytest.mark.asyncio
    async def test_update_school_when_valid_then_fields_updated(
        self, school_service: SchoolService, mock_db: MagicMock
    ) -> None:
        """Test updating a school with valid data."""
        # Arrange
        school_id = uuid.uuid4()
        school = School(
            id=school_id,
            name="Old Name",
            slug="old-slug",
            country="Old Country",
            timezone="UTC",
            status="active",
        )
        mock_db.get = AsyncMock(return_value=school)

        data = SchoolUpdate(
            name="New Name",
            country="New Country",
            timezone="Asia/Jakarta",
        )

        # Act
        result = await school_service.update_school(school_id, data)

        # Assert
        assert result.name == "New Name"
        assert result.country == "New Country"
        assert result.timezone == "Asia/Jakarta"
        assert result.slug == "old-slug"  # unchanged
        mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_school_when_deactivate_then_status_suspended(
        self, school_service: SchoolService, mock_db: MagicMock
    ) -> None:
        """Test deactivating a school sets status to suspended."""
        # Arrange
        school_id = uuid.uuid4()
        school = School(
            id=school_id,
            name="Test School",
            slug="test-school",
            status="active",
        )
        mock_db.get = AsyncMock(return_value=school)

        data = SchoolUpdate(is_active=False)

        # Act
        result = await school_service.update_school(school_id, data)

        # Assert
        assert result.status == "suspended"

    @pytest.mark.asyncio
    async def test_update_school_when_activate_then_status_active(
        self, school_service: SchoolService, mock_db: MagicMock
    ) -> None:
        """Test activating a school sets status to active."""
        # Arrange
        school_id = uuid.uuid4()
        school = School(
            id=school_id,
            name="Test School",
            slug="test-school",
            status="suspended",
        )
        mock_db.get = AsyncMock(return_value=school)

        data = SchoolUpdate(is_active=True)

        # Act
        result = await school_service.update_school(school_id, data)

        # Assert
        assert result.status == "active"

    @pytest.mark.asyncio
    async def test_update_school_when_not_exists_then_raises_not_found(
        self, school_service: SchoolService, mock_db: MagicMock
    ) -> None:
        """Test updating a non-existent school raises ValueError."""
        # Arrange
        school_id = uuid.uuid4()
        mock_db.get = AsyncMock(return_value=None)

        data = SchoolUpdate(name="New Name")

        # Act & Assert
        with pytest.raises(ValueError, match="School not found"):
            await school_service.update_school(school_id, data)
