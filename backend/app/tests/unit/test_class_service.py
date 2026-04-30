"""Unit tests for ClassService."""

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

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

        # Mock teacher lookup then curriculum subscription check
        from app.models.school import SchoolCurriculum

        teacher = User(id=teacher_id, school_id=school_id, role=UserRole.TEACHER)
        sc = SchoolCurriculum(school_id=school_id, curriculum_id=curriculum_id)
        teacher_result = MagicMock()
        teacher_result.scalar_one_or_none.return_value = teacher
        subscription_result = MagicMock()
        subscription_result.scalar_one_or_none.return_value = sc
        mock_db.execute = AsyncMock(side_effect=[teacher_result, subscription_result])
        mock_db.flush = AsyncMock()

        # Act
        class_ = await class_service.create_class(school_id, data)

        # Assert
        assert class_.name == "Math 7A"
        assert class_.teacher_id == teacher_id
        mock_db.add.assert_called()

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

    @pytest.mark.asyncio
    async def test_create_class_when_curriculum_not_subscribed_then_raises(
        self, class_service: ClassService, mock_db: MagicMock
    ) -> None:
        """Raises ValueError when school is not subscribed to the curriculum."""
        school_id = uuid.uuid4()
        teacher_id = uuid.uuid4()
        curriculum_id = uuid.uuid4()
        data = ClassCreate(
            name="Math 7A",
            grade_id=uuid.uuid4(),
            subject_id=uuid.uuid4(),
            curriculum_id=curriculum_id,
            teacher_id=teacher_id,
            academic_year="2026",
        )
        teacher = User(id=teacher_id, school_id=school_id, role=UserRole.TEACHER)
        teacher_result = MagicMock()
        teacher_result.scalar_one_or_none.return_value = teacher
        subscription_result = MagicMock()
        subscription_result.scalar_one_or_none.return_value = None  # not subscribed
        mock_db.execute = AsyncMock(side_effect=[teacher_result, subscription_result])

        with pytest.raises(ValueError, match="not subscribed"):
            await class_service.create_class(school_id, data)

    @pytest.mark.asyncio
    async def test_create_class_when_curriculum_subscribed_then_class_created(
        self, class_service: ClassService, mock_db: MagicMock
    ) -> None:
        """Creates class when school is subscribed to the curriculum."""
        from app.models.school import SchoolCurriculum

        school_id = uuid.uuid4()
        teacher_id = uuid.uuid4()
        curriculum_id = uuid.uuid4()
        data = ClassCreate(
            name="Math 7A",
            grade_id=uuid.uuid4(),
            subject_id=uuid.uuid4(),
            curriculum_id=curriculum_id,
            teacher_id=teacher_id,
            academic_year="2026",
        )
        teacher = User(id=teacher_id, school_id=school_id, role=UserRole.TEACHER)
        sc = SchoolCurriculum(school_id=school_id, curriculum_id=curriculum_id)
        teacher_result = MagicMock()
        teacher_result.scalar_one_or_none.return_value = teacher
        subscription_result = MagicMock()
        subscription_result.scalar_one_or_none.return_value = sc
        mock_db.execute = AsyncMock(side_effect=[teacher_result, subscription_result])
        mock_db.flush = AsyncMock()

        class_ = await class_service.create_class(school_id, data)

        assert class_.name == "Math 7A"
        assert class_.curriculum_id == curriculum_id


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
    @patch("app.services.class_service.trigger_onboarding_diagnostics")
    async def test_enroll_students_when_valid_then_enrolls(
        self, mock_trigger: MagicMock, class_service: ClassService, mock_db: MagicMock
    ) -> None:
        """Test enrolling valid students using batch queries."""
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

        # Mock student lookup (batch query returns list)
        student = User(
            id=student_id,
            school_id=school_id,
            role=UserRole.STUDENT,
        )
        mock_student_result = MagicMock()
        mock_student_result.scalars.return_value.all.return_value = [student]

        # Mock no existing enrollments (batch query returns empty list)
        mock_enrollment_result = MagicMock()
        mock_enrollment_result.scalars.return_value.all.return_value = []

        # Set up execute to return different results for batch queries
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
        assert result.enrolled == 1
        assert result.skipped == 0

    @pytest.mark.asyncio
    @patch("app.services.class_service.trigger_onboarding_diagnostics")
    async def test_enroll_students_when_already_enrolled_then_skips(
        self, mock_trigger: MagicMock, class_service: ClassService, mock_db: MagicMock
    ) -> None:
        """Test that already enrolled students are skipped using batch queries."""
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

        # Mock student lookup (batch query returns list)
        student = User(
            id=student_id,
            school_id=school_id,
            role=UserRole.STUDENT,
        )
        mock_student_result = MagicMock()
        mock_student_result.scalars.return_value.all.return_value = [student]

        # Mock existing enrollment (batch query returns list of student_ids)
        mock_enrollment_result = MagicMock()
        # Return list of student_ids that are already enrolled
        mock_enrollment_result.scalars.return_value.all.return_value = [student_id]

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


class TestGetClass:
    """Tests for ClassService.get_class method."""

    @pytest.mark.asyncio
    async def test_get_class_when_class_exists_then_returns_class(
        self, class_service: ClassService, mock_db: MagicMock
    ) -> None:
        """Test that get_class returns the class when it exists."""
        class_id = uuid.uuid4()
        class_ = Class(
            id=class_id,
            school_id=uuid.uuid4(),
            name="Test Class",
            grade_id=uuid.uuid4(),
            subject_id=uuid.uuid4(),
            curriculum_id=uuid.uuid4(),
            teacher_id=uuid.uuid4(),
            academic_year="2026",
        )
        mock_db.get = AsyncMock(return_value=class_)

        result = await class_service.get_class(class_id)

        assert result.id == class_id
        assert result.name == "Test Class"
        mock_db.get.assert_called_once_with(Class, class_id)

    @pytest.mark.asyncio
    async def test_get_class_when_class_not_found_then_raises_value_error(
        self, class_service: ClassService, mock_db: MagicMock
    ) -> None:
        """Test that get_class raises ValueError when class doesn't exist."""
        class_id = uuid.uuid4()
        mock_db.get = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="Class not found"):
            await class_service.get_class(class_id)


class TestVerifyClassSchool:
    """Tests for ClassService.verify_class_school method."""

    @pytest.mark.asyncio
    async def test_verify_class_school_when_valid_then_returns_class(
        self, class_service: ClassService, mock_db: MagicMock
    ) -> None:
        """Test that verify_class_school returns class when school matches."""
        class_id = uuid.uuid4()
        school_id = uuid.uuid4()
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

        result = await class_service.verify_class_school(class_id, school_id)

        assert result.id == class_id

    @pytest.mark.asyncio
    async def test_verify_class_school_when_wrong_school_then_raises_value_error(
        self, class_service: ClassService, mock_db: MagicMock
    ) -> None:
        """Test that verify_class_school raises ValueError when school doesn't match."""
        class_id = uuid.uuid4()
        correct_school_id = uuid.uuid4()
        wrong_school_id = uuid.uuid4()
        class_ = Class(
            id=class_id,
            school_id=correct_school_id,
            name="Test Class",
            grade_id=uuid.uuid4(),
            subject_id=uuid.uuid4(),
            curriculum_id=uuid.uuid4(),
            teacher_id=uuid.uuid4(),
            academic_year="2026",
        )
        mock_db.get = AsyncMock(return_value=class_)

        with pytest.raises(ValueError, match="Class not found"):
            await class_service.verify_class_school(class_id, wrong_school_id)


class TestGetClassStudents:
    """Tests for ClassService.get_class_students method."""

    @pytest.mark.asyncio
    async def test_get_class_students_when_students_enrolled_then_returns_list(
        self, class_service: ClassService, mock_db: MagicMock
    ) -> None:
        """Test that get_class_students returns enrolled students ordered by name."""
        class_id = uuid.uuid4()
        school_id = uuid.uuid4()
        class_ = Class(
            id=class_id,
            school_id=school_id,
            name="Test",
            grade_id=uuid.uuid4(),
            subject_id=uuid.uuid4(),
            curriculum_id=uuid.uuid4(),
            teacher_id=uuid.uuid4(),
            academic_year="2026",
        )

        student1 = User(
            id=uuid.uuid4(),
            school_id=school_id,
            email="alice@test.com",
            first_name="Alice",
            last_name="Smith",
            role=UserRole.STUDENT,
        )
        student2 = User(
            id=uuid.uuid4(),
            school_id=school_id,
            email="bob@test.com",
            first_name="Bob",
            last_name="Jones",
            role=UserRole.STUDENT,
        )

        mock_db.get = AsyncMock(return_value=class_)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [student2, student1]
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await class_service.get_class_students(class_id)

        assert len(result) == 2
        assert result[0].first_name == "Bob"
        assert result[1].first_name == "Alice"

    @pytest.mark.asyncio
    async def test_get_class_students_when_no_students_then_returns_empty_list(
        self, class_service: ClassService, mock_db: MagicMock
    ) -> None:
        """Test that get_class_students returns empty list when no students enrolled."""
        class_id = uuid.uuid4()
        class_ = Class(
            id=class_id,
            school_id=uuid.uuid4(),
            name="Test",
            grade_id=uuid.uuid4(),
            subject_id=uuid.uuid4(),
            curriculum_id=uuid.uuid4(),
            teacher_id=uuid.uuid4(),
            academic_year="2026",
        )
        mock_db.get = AsyncMock(return_value=class_)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await class_service.get_class_students(class_id)

        assert result == []

    @pytest.mark.asyncio
    async def test_get_class_students_when_class_not_found_then_raises(
        self, class_service: ClassService, mock_db: MagicMock
    ) -> None:
        """Test that get_class_students raises ValueError when class doesn't exist."""
        class_id = uuid.uuid4()
        mock_db.get = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="Class not found"):
            await class_service.get_class_students(class_id)


class TestGetTeacherStudents:
    """Tests for ClassService.get_teacher_students method."""

    @pytest.mark.asyncio
    async def test_get_teacher_students_when_multiple_classes_with_students(
        self, class_service: ClassService, mock_db: MagicMock
    ) -> None:
        """Test aggregating students across multiple classes."""
        teacher_id = uuid.uuid4()
        school_id = uuid.uuid4()

        class1 = Class(
            id=uuid.uuid4(),
            teacher_id=teacher_id,
            school_id=school_id,
            name="Math 8A",
            grade_id=uuid.uuid4(),
            subject_id=uuid.uuid4(),
            curriculum_id=uuid.uuid4(),
            academic_year="2026",
        )
        class2 = Class(
            id=uuid.uuid4(),
            teacher_id=teacher_id,
            school_id=school_id,
            name="Science 8B",
            grade_id=uuid.uuid4(),
            subject_id=uuid.uuid4(),
            curriculum_id=uuid.uuid4(),
            academic_year="2026",
        )

        student1 = User(
            id=uuid.uuid4(),
            school_id=school_id,
            first_name="Alice",
            last_name="A",
            email="alice@test.com",
            role=UserRole.STUDENT,
        )

        enrollment1 = ClassEnrollment(class_id=class1.id, student_id=student1.id, is_active=True)
        enrollment2 = ClassEnrollment(class_id=class2.id, student_id=student1.id, is_active=True)

        mock_classes_result = MagicMock()
        mock_classes_result.scalars.return_value.all.return_value = [class1, class2]
        mock_enrollments_result = MagicMock()
        mock_enrollments_result.scalars.return_value.all.return_value = [enrollment1, enrollment2]
        mock_students_result = MagicMock()
        mock_students_result.scalars.return_value.all.return_value = [student1]

        call_count = [0]

        async def mock_execute(q: Any) -> Any:
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_classes_result
            elif call_count[0] == 2:
                return mock_enrollments_result
            else:
                return mock_students_result

        mock_db.execute = AsyncMock(side_effect=mock_execute)

        result = await class_service.get_teacher_students(teacher_id, school_id)

        assert len(result) == 1
        assert result[0].id == student1.id
        assert len(result[0].class_ids) == 2
        assert "Math 8A" in result[0].class_names
        assert "Science 8B" in result[0].class_names

    @pytest.mark.asyncio
    async def test_get_teacher_students_when_no_classes_then_returns_empty(
        self, class_service: ClassService, mock_db: MagicMock
    ) -> None:
        """Test that get_teacher_students returns empty when teacher has no classes."""
        teacher_id = uuid.uuid4()
        school_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await class_service.get_teacher_students(teacher_id, school_id)

        assert result == []

    @pytest.mark.asyncio
    async def test_get_teacher_students_when_classes_have_no_enrollments_then_returns_empty(
        self, class_service: ClassService, mock_db: MagicMock
    ) -> None:
        """Test that get_teacher_students returns empty when classes have no enrollments."""
        teacher_id = uuid.uuid4()
        school_id = uuid.uuid4()
        class1 = Class(
            id=uuid.uuid4(),
            teacher_id=teacher_id,
            school_id=school_id,
            name="Math 8A",
            grade_id=uuid.uuid4(),
            subject_id=uuid.uuid4(),
            curriculum_id=uuid.uuid4(),
            academic_year="2026",
        )

        mock_classes_result = MagicMock()
        mock_classes_result.scalars.return_value.all.return_value = [class1]
        mock_enrollments_result = MagicMock()
        mock_enrollments_result.scalars.return_value.all.return_value = []

        call_count = [0]

        async def mock_execute(q: Any) -> Any:
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_classes_result
            else:
                return mock_enrollments_result

        mock_db.execute = AsyncMock(side_effect=mock_execute)

        result = await class_service.get_teacher_students(teacher_id, school_id)

        assert result == []
