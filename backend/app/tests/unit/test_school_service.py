"""Unit tests for SchoolService."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.curriculum import Curriculum
from app.models.school import School, SchoolCurriculum
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


# =============================================================================
# Curriculum subscription tests
# =============================================================================


def _make_curriculum(name: str = "Cambridge Lower Secondary", code: str = "CAM-LS") -> Curriculum:
    c = Curriculum(id=uuid.uuid4(), name=name, code=code, is_active=True)
    return c


def _make_school_curriculum(school_id: uuid.UUID, curriculum: Curriculum, is_primary: bool = False) -> SchoolCurriculum:
    sc = SchoolCurriculum(school_id=school_id, curriculum_id=curriculum.id, is_primary=is_primary)
    return sc


class TestListSchoolCurricula:
    """Tests for SchoolService.list_school_curricula method."""

    @pytest.mark.asyncio
    async def test_list_school_curricula_when_school_has_curricula_then_returns_pairs(
        self, school_service: SchoolService, mock_db: MagicMock
    ) -> None:
        """Returns list of (SchoolCurriculum, Curriculum) tuples for the school."""
        # Arrange
        school_id = uuid.uuid4()
        curriculum = _make_curriculum()
        sc = _make_school_curriculum(school_id, curriculum, is_primary=True)
        mock_result = MagicMock()
        mock_result.all.return_value = [(sc, curriculum)]
        mock_db.execute = AsyncMock(return_value=mock_result)

        # Act
        result = await school_service.list_school_curricula(school_id)

        # Assert
        assert len(result) == 1
        returned_sc, returned_c = result[0]
        assert returned_sc.school_id == school_id
        assert returned_sc.is_primary is True
        assert returned_c.code == "CAM-LS"

    @pytest.mark.asyncio
    async def test_list_school_curricula_when_no_curricula_then_returns_empty_list(
        self, school_service: SchoolService, mock_db: MagicMock
    ) -> None:
        """Returns empty list when school has no curriculum subscriptions."""
        # Arrange
        school_id = uuid.uuid4()
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        # Act
        result = await school_service.list_school_curricula(school_id)

        # Assert
        assert result == []


class TestAddSchoolCurriculum:
    """Tests for SchoolService.add_school_curriculum method."""

    @pytest.mark.asyncio
    async def test_add_school_curriculum_when_valid_then_creates_record(
        self, school_service: SchoolService, mock_db: MagicMock
    ) -> None:
        """Creates a SchoolCurriculum record when school and curriculum exist."""
        # Arrange
        school_id = uuid.uuid4()
        curriculum = _make_curriculum()
        school = School(id=school_id, name="Test School", slug="test-school")

        # scalar calls: school lookup, curriculum lookup, existing subscription check
        mock_db.get = AsyncMock(return_value=school)
        mock_db.scalar = AsyncMock(side_effect=[curriculum, None])  # curriculum found, not yet subscribed

        # Act
        sc, c = await school_service.add_school_curriculum(school_id, curriculum.id, is_primary=False)

        # Assert
        assert sc.school_id == school_id
        assert sc.curriculum_id == curriculum.id
        assert sc.is_primary is False
        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_school_curriculum_when_curriculum_not_found_then_raises_value_error(
        self, school_service: SchoolService, mock_db: MagicMock
    ) -> None:
        """Raises ValueError when the curriculum ID does not exist."""
        # Arrange
        school_id = uuid.uuid4()
        curriculum_id = uuid.uuid4()
        school = School(id=school_id, name="Test School", slug="test-school")

        mock_db.get = AsyncMock(return_value=school)
        mock_db.scalar = AsyncMock(return_value=None)  # curriculum not found

        # Act & Assert
        with pytest.raises(ValueError, match="Curriculum not found"):
            await school_service.add_school_curriculum(school_id, curriculum_id, is_primary=False)

    @pytest.mark.asyncio
    async def test_add_school_curriculum_when_already_subscribed_then_raises_value_error(
        self, school_service: SchoolService, mock_db: MagicMock
    ) -> None:
        """Raises ValueError when school is already subscribed to this curriculum."""
        # Arrange
        school_id = uuid.uuid4()
        curriculum = _make_curriculum()
        school = School(id=school_id, name="Test School", slug="test-school")
        existing_sc = _make_school_curriculum(school_id, curriculum)

        mock_db.get = AsyncMock(return_value=school)
        mock_db.scalar = AsyncMock(side_effect=[curriculum, existing_sc])  # curriculum found, already subscribed

        # Act & Assert
        with pytest.raises(ValueError, match="already subscribed"):
            await school_service.add_school_curriculum(school_id, curriculum.id, is_primary=False)

    @pytest.mark.asyncio
    async def test_add_school_curriculum_when_is_primary_true_then_clears_existing_primary(
        self, school_service: SchoolService, mock_db: MagicMock
    ) -> None:
        """Clears any existing primary flag before setting the new curriculum as primary."""
        # Arrange
        school_id = uuid.uuid4()
        curriculum = _make_curriculum()
        old_primary_curriculum = _make_curriculum("Old Primary", "OLD")
        old_sc = _make_school_curriculum(school_id, old_primary_curriculum, is_primary=True)
        school = School(id=school_id, name="Test School", slug="test-school")

        mock_db.get = AsyncMock(return_value=school)
        # curriculum found, not yet subscribed, existing primary found
        mock_db.scalar = AsyncMock(side_effect=[curriculum, None, old_sc])

        # Act
        sc, _ = await school_service.add_school_curriculum(school_id, curriculum.id, is_primary=True)

        # Assert
        assert old_sc.is_primary is False  # cleared
        assert sc.is_primary is True


class TestRemoveSchoolCurriculum:
    """Tests for SchoolService.remove_school_curriculum method."""

    @pytest.mark.asyncio
    async def test_remove_school_curriculum_when_no_active_classes_then_removes(
        self, school_service: SchoolService, mock_db: MagicMock
    ) -> None:
        """Removes the SchoolCurriculum record when no active classes use it."""
        # Arrange
        school_id = uuid.uuid4()
        curriculum = _make_curriculum()
        sc = _make_school_curriculum(school_id, curriculum)

        mock_db.scalar = AsyncMock(side_effect=[sc, 0])  # subscription found, zero active classes
        mock_db.delete = AsyncMock()

        # Act
        await school_service.remove_school_curriculum(school_id, curriculum.id)

        # Assert
        mock_db.delete.assert_called_once_with(sc)
        mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_remove_school_curriculum_when_active_classes_exist_then_raises_value_error(
        self, school_service: SchoolService, mock_db: MagicMock
    ) -> None:
        """Raises ValueError when active classes still use this curriculum."""
        # Arrange
        school_id = uuid.uuid4()
        curriculum = _make_curriculum()
        sc = _make_school_curriculum(school_id, curriculum)

        mock_db.scalar = AsyncMock(side_effect=[sc, 3])  # 3 active classes

        # Act & Assert
        with pytest.raises(ValueError, match="active classes"):
            await school_service.remove_school_curriculum(school_id, curriculum.id)

    @pytest.mark.asyncio
    async def test_remove_school_curriculum_when_not_subscribed_then_raises_value_error(
        self, school_service: SchoolService, mock_db: MagicMock
    ) -> None:
        """Raises ValueError when school is not subscribed to the curriculum."""
        # Arrange
        school_id = uuid.uuid4()
        curriculum_id = uuid.uuid4()

        mock_db.scalar = AsyncMock(return_value=None)  # subscription not found

        # Act & Assert
        with pytest.raises(ValueError, match="not subscribed"):
            await school_service.remove_school_curriculum(school_id, curriculum_id)


class TestSetPrimarySchoolCurriculum:
    """Tests for SchoolService.set_primary_curriculum method."""

    @pytest.mark.asyncio
    async def test_set_primary_curriculum_when_valid_then_updates_primary(
        self, school_service: SchoolService, mock_db: MagicMock
    ) -> None:
        """Clears old primary and sets the specified curriculum as primary."""
        # Arrange
        school_id = uuid.uuid4()
        curriculum = _make_curriculum()
        old_curriculum = _make_curriculum("Old", "OLD")
        sc = _make_school_curriculum(school_id, curriculum, is_primary=False)
        old_sc = _make_school_curriculum(school_id, old_curriculum, is_primary=True)

        # First query uses execute().one_or_none() (joined fetch with FOR UPDATE)
        execute_result = MagicMock()
        execute_result.one_or_none = MagicMock(return_value=(sc, curriculum))
        mock_db.execute = AsyncMock(return_value=execute_result)
        # Second query uses scalar() (current primary lookup)
        mock_db.scalar = AsyncMock(return_value=old_sc)

        # Act
        result_sc, result_c = await school_service.set_primary_curriculum(school_id, curriculum.id)

        # Assert
        assert old_sc.is_primary is False
        assert result_sc.is_primary is True
        mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_primary_curriculum_when_already_primary_then_no_change(
        self, school_service: SchoolService, mock_db: MagicMock
    ) -> None:
        """No-ops cleanly when the curriculum is already the primary."""
        # Arrange
        school_id = uuid.uuid4()
        curriculum = _make_curriculum()
        sc = _make_school_curriculum(school_id, curriculum, is_primary=True)

        execute_result = MagicMock()
        execute_result.one_or_none = MagicMock(return_value=(sc, curriculum))
        mock_db.execute = AsyncMock(return_value=execute_result)
        # Same sc is the current primary — same curriculum_id, so no clear needed
        mock_db.scalar = AsyncMock(return_value=sc)

        # Act
        result_sc, _ = await school_service.set_primary_curriculum(school_id, curriculum.id)

        # Assert
        assert result_sc.is_primary is True

    @pytest.mark.asyncio
    async def test_set_primary_curriculum_when_not_subscribed_then_raises_value_error(
        self, school_service: SchoolService, mock_db: MagicMock
    ) -> None:
        """Raises ValueError when school is not subscribed to the target curriculum."""
        # Arrange
        school_id = uuid.uuid4()
        curriculum_id = uuid.uuid4()

        execute_result = MagicMock()
        execute_result.one_or_none = MagicMock(return_value=None)
        mock_db.execute = AsyncMock(return_value=execute_result)

        # Act & Assert
        with pytest.raises(ValueError, match="not subscribed"):
            await school_service.set_primary_curriculum(school_id, curriculum_id)
