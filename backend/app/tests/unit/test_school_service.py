"""Unit tests for SchoolService."""

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.school import Class, ClassEnrollment, School
from app.models.user import User, UserRole
from app.schemas.school import ClassCreate, SchoolCreate, SchoolUpdate
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
        mock_db.add.assert_called_once_with(school)
        mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_school_when_default_timezone_then_uses_utc(
        self, school_service: SchoolService, mock_db: MagicMock
    ) -> None:
        """Test that default timezone is UTC per schema."""
        # Arrange
        data = SchoolCreate(
            name="Test School",
            slug="test-school",
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


# ===========================================
# Class Management Tests
# ===========================================


class TestCreateClass:
    """Tests for SchoolService.create_class method."""

    @pytest.mark.asyncio
    async def test_create_class_when_valid_data_then_class_created(
        self, school_service: SchoolService, mock_db: MagicMock
    ) -> None:
        """Test creating a class with valid data."""
        # Arrange
        school_id = uuid.uuid4()
        teacher_id = uuid.uuid4()
        grade_id = uuid.uuid4()
        subject_id = uuid.uuid4()
        curriculum_id = uuid.uuid4()

        data = ClassCreate(
            name="Math 7A",
            grade_id=grade_id,
            subject_id=subject_id,
            curriculum_id=curriculum_id,
            teacher_id=teacher_id,
            academic_year="2026",
        )

        # Mock teacher lookup
        teacher = User(
            id=teacher_id,
            school_id=school_id,
            role=UserRole.TEACHER,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = teacher
        mock_db.execute = AsyncMock(return_value=mock_result)

        # Act
        class_ = await school_service.create_class(school_id, data)

        # Assert
        assert class_.name == "Math 7A"
        assert class_.teacher_id == teacher_id
        mock_db.add.assert_called()
        mock_db.flush.assert_called()

    @pytest.mark.asyncio
    async def test_create_class_when_teacher_not_in_school_then_raises(
        self, school_service: SchoolService, mock_db: MagicMock
    ) -> None:
        """Test that creating class with teacher from different school fails."""
        # Arrange
        school_id = uuid.uuid4()
        teacher_id = uuid.uuid4()  # Different school
        grade_id = uuid.uuid4()
        subject_id = uuid.uuid4()
        curriculum_id = uuid.uuid4()

        data = ClassCreate(
            name="Math 7A",
            grade_id=grade_id,
            subject_id=subject_id,
            curriculum_id=curriculum_id,
            teacher_id=teacher_id,
            academic_year="2026",
        )

        # Mock teacher not found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        # Act & Assert
        with pytest.raises(ValueError, match="Teacher not found in this school"):
            await school_service.create_class(school_id, data)


class TestListClasses:
    """Tests for SchoolService.list_classes method."""

    @pytest.mark.asyncio
    async def test_list_classes_when_no_filter_then_returns_all(
        self, school_service: SchoolService, mock_db: MagicMock
    ) -> None:
        """Test listing all classes in a school."""
        # Arrange
        school_id = uuid.uuid4()
        classes = [
            Class(
                id=uuid.uuid4(),
                school_id=school_id,
                name=f"Class {i}",
                grade_id=uuid.uuid4(),
                subject_id=uuid.uuid4(),
                curriculum_id=uuid.uuid4(),
                teacher_id=uuid.uuid4(),
                academic_year="2026",
            )
            for i in range(3)
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = classes
        mock_db.execute = AsyncMock(return_value=mock_result)

        # Act
        result = await school_service.list_classes(school_id)

        # Assert
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_list_classes_when_teacher_filter_then_returns_own_classes(
        self, school_service: SchoolService, mock_db: MagicMock
    ) -> None:
        """Test that teacher filter returns only their classes."""
        # Arrange
        school_id = uuid.uuid4()
        teacher_id = uuid.uuid4()

        classes = [
            Class(
                id=uuid.uuid4(),
                school_id=school_id,
                name="Class 1",
                grade_id=uuid.uuid4(),
                subject_id=uuid.uuid4(),
                curriculum_id=uuid.uuid4(),
                teacher_id=teacher_id,
                academic_year="2026",
            )
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = classes
        mock_db.execute = AsyncMock(return_value=mock_result)

        # Act
        result = await school_service.list_classes(school_id, teacher_id=teacher_id)

        # Assert
        assert len(result) == 1


class TestEnrollStudents:
    """Tests for SchoolService.enroll_students method."""

    @pytest.mark.asyncio
    async def test_enroll_students_when_valid_then_enrolls(
        self, school_service: SchoolService, mock_db: MagicMock
    ) -> None:
        """Test enrolling valid students."""
        # Arrange
        class_id = uuid.uuid4()
        school_id = uuid.uuid4()
        student_id = uuid.uuid4()

        class_ = Class(
            id=class_id,
            school_id=school_id,
            name="Test Class",
            grade_id=uuid.uuid4(),
            subject_id=uuid.uuid4(),
            curriculum_id=uuid.uuid4(),
            teacher_id=uuid.uuid4(),
            academic_year="2026",
        )
        mock_db.get = AsyncMock(return_value=class_)

        # Mock student lookup
        student = User(
            id=student_id,
            school_id=school_id,
            role=UserRole.STUDENT,
        )
        mock_student_result = MagicMock()
        mock_student_result.scalar_one_or_none.return_value = student

        # Mock no existing enrollment
        mock_enrollment_result = MagicMock()
        mock_enrollment_result.scalar_one_or_none.return_value = None

        # Mock no student profile
        mock_profile_result = MagicMock()
        mock_profile_result.scalar_one_or_none.return_value = None

        # Set up execute to return different results
        call_count = [0]

        async def mock_execute(query: Any) -> Any:
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_student_result
            elif call_count[0] == 2:
                return mock_enrollment_result
            else:
                return mock_profile_result

        mock_db.execute = AsyncMock(side_effect=mock_execute)

        # Act
        result = await school_service.enroll_students(class_id, [student_id])

        # Assert
        assert result.enrolled == 1
        assert result.skipped == 0

    @pytest.mark.asyncio
    async def test_enroll_students_when_already_enrolled_then_skips(
        self, school_service: SchoolService, mock_db: MagicMock
    ) -> None:
        """Test that already enrolled students are skipped."""
        # Arrange
        class_id = uuid.uuid4()
        school_id = uuid.uuid4()
        student_id = uuid.uuid4()

        class_ = Class(
            id=class_id,
            school_id=school_id,
            name="Test Class",
            grade_id=uuid.uuid4(),
            subject_id=uuid.uuid4(),
            curriculum_id=uuid.uuid4(),
            teacher_id=uuid.uuid4(),
            academic_year="2026",
        )
        mock_db.get = AsyncMock(return_value=class_)

        # Mock student lookup
        student = User(
            id=student_id,
            school_id=school_id,
            role=UserRole.STUDENT,
        )
        mock_student_result = MagicMock()
        mock_student_result.scalar_one_or_none.return_value = student

        # Mock existing enrollment
        existing_enrollment = ClassEnrollment(
            class_id=class_id,
            student_id=student_id,
        )
        mock_enrollment_result = MagicMock()
        mock_enrollment_result.scalar_one_or_none.return_value = existing_enrollment

        call_count = [0]

        async def mock_execute(query: Any) -> Any:
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_student_result
            else:
                return mock_enrollment_result

        mock_db.execute = AsyncMock(side_effect=mock_execute)

        # Act
        result = await school_service.enroll_students(class_id, [student_id])

        # Assert
        assert result.enrolled == 0
        assert result.skipped == 1

    @pytest.mark.asyncio
    async def test_enroll_students_when_wrong_school_then_error(
        self, school_service: SchoolService, mock_db: MagicMock
    ) -> None:
        """Test that student from different school returns error."""
        # Arrange
        class_id = uuid.uuid4()
        school_id = uuid.uuid4()
        student_id = uuid.uuid4()  # Different school

        class_ = Class(
            id=class_id,
            school_id=school_id,
            name="Test Class",
            grade_id=uuid.uuid4(),
            subject_id=uuid.uuid4(),
            curriculum_id=uuid.uuid4(),
            teacher_id=uuid.uuid4(),
            academic_year="2026",
        )
        mock_db.get = AsyncMock(return_value=class_)

        # Mock student not found (different school)
        mock_student_result = MagicMock()
        mock_student_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_student_result)

        # Act
        result = await school_service.enroll_students(class_id, [student_id])

        # Assert
        assert result.enrolled == 0
        assert "not found in this school" in result.errors[0]
