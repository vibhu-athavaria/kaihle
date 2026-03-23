"""Unit tests for ClassService."""

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.school import Class, ClassEnrollment
from app.models.user import User, UserRole
from app.schemas.class_enrollment import ClassCreate
from app.services.class_service import ClassService


@pytest.fixture
def mock_db() -> MagicMock:
    """Create a mock database session."""
    session = MagicMock(spec=AsyncSession)
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


@pytest.fixture
def class_service(mock_db: MagicMock) -> ClassService:
    """Create a ClassService with mock database."""
    return ClassService(mock_db)


class TestCreateClass:
    """Tests for ClassService.create_class method."""

    @pytest.mark.asyncio
    async def test_create_class_when_valid_data_then_class_created(
        self, class_service: ClassService, mock_db: MagicMock
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
        class_ = await class_service.create_class(school_id, data)

        # Assert
        assert class_.name == "Math 7A"
        assert class_.teacher_id == teacher_id
        mock_db.add.assert_called()
        mock_db.flush.assert_called()

    @pytest.mark.asyncio
    async def test_create_class_when_teacher_not_in_school_then_raises(
        self, class_service: ClassService, mock_db: MagicMock
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
            await class_service.create_class(school_id, data)


class TestListClasses:
    """Tests for ClassService.list_classes method."""

    @pytest.mark.asyncio
    async def test_list_classes_when_no_filter_then_returns_all(
        self, class_service: ClassService, mock_db: MagicMock
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
        result = await class_service.list_classes(school_id)

        # Assert
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_list_classes_when_teacher_filter_then_returns_own_classes(
        self, class_service: ClassService, mock_db: MagicMock
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
        result = await class_service.list_classes(school_id, teacher_id=teacher_id)

        # Assert
        assert len(result) == 1


class TestEnrollStudents:
    """Tests for ClassService.enroll_students method."""

    @pytest.mark.asyncio
    async def test_enroll_students_when_valid_then_enrolls(
        self, class_service: ClassService, mock_db: MagicMock
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
        result = await class_service.enroll_students(class_id, [student_id])

        # Assert
        assert result.enrolled == 1
        assert result.skipped == 0

    @pytest.mark.asyncio
    async def test_enroll_students_when_already_enrolled_then_skips(
        self, class_service: ClassService, mock_db: MagicMock
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
        result = await class_service.enroll_students(class_id, [student_id])

        # Assert
        assert result.enrolled == 0
        assert result.skipped == 1

    @pytest.mark.asyncio
    async def test_enroll_students_when_wrong_school_then_error(
        self, class_service: ClassService, mock_db: MagicMock
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
        result = await class_service.enroll_students(class_id, [student_id])

        # Assert
        assert result.enrolled == 0
        assert "not found in this school" in result.errors[0]
