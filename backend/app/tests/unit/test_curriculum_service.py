"""Unit tests for CurriculumService.

These tests mock the database layer to test business logic in isolation.
Per Rule 20 (TDD): each service method has named unit tests.
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pydantic
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.curriculum import (
    Curriculum,
    CurriculumSubject,
    CurriculumTopic,
    Grade,
    Subject,
    Subtopic,
    Topic,
)
from app.schemas.curriculum import (
    CurriculumCreate,
    CurriculumTopicCreate,
    CurriculumTopicUpdate,
    CurriculumUpdate,
    GradeCreate,
    GradeUpdate,
    LinkSubjectRequest,
    SubjectCreate,
    SubtopicCreate,
    SubtopicUpdate,
    TopicIdentityCreate,
)
from app.services.curriculum_service import (
    CurriculumService,
    DuplicateError,
    NotFoundError,
    ValidationError,
)


@pytest.fixture
def mock_db() -> MagicMock:
    """Create a mock database session."""
    session = MagicMock(spec=AsyncSession)

    def _simulate_db_insert(obj: object) -> None:
        """Simulate server-side defaults that the DB sets on INSERT."""
        if hasattr(obj, "id") and getattr(obj, "id") is None:
            object.__setattr__(obj, "id", uuid.uuid4())
        if hasattr(obj, "created_at") and getattr(obj, "created_at") is None:
            object.__setattr__(obj, "created_at", datetime.now(UTC))

    session.add = MagicMock(side_effect=_simulate_db_insert)
    session.flush = AsyncMock()
    session.delete = AsyncMock()
    return session


@pytest.fixture
def curriculum_service(mock_db: MagicMock) -> CurriculumService:
    """Create a CurriculumService with mock database."""
    return CurriculumService(mock_db)


# =============================================================================
# Curriculum Tests
# =============================================================================


class TestCreateCurriculum:
    """Tests for CurriculumService.create_curriculum."""

    @pytest.mark.asyncio
    async def test_create_curriculum_when_valid_data_then_returns_curriculum(
        self,
        curriculum_service: CurriculumService,
        mock_db: MagicMock,
    ) -> None:
        """Test creating a curriculum with valid data."""
        # Arrange
        data = CurriculumCreate(
            name="Cambridge IGCSE",
            code="igcse",
            description="International curriculum",
            country="UK",
            is_active=True,
        )

        # Mock no existing curriculum with same name/code
        mock_db.scalar = AsyncMock(return_value=None)

        # Act
        result = await curriculum_service.create_curriculum(data)

        # Assert
        assert result.name == "Cambridge IGCSE"
        assert result.code == "igcse"
        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_curriculum_when_duplicate_name_then_raises_value_error(
        self,
        curriculum_service: CurriculumService,
        mock_db: MagicMock,
    ) -> None:
        """Test that duplicate name raises DuplicateError."""
        # Arrange
        data = CurriculumCreate(
            name="Existing Curriculum",
            code="unique-code",
            is_active=True,
        )

        existing = Curriculum(id=uuid.uuid4(), name="Existing Curriculum", code="existing")
        mock_db.scalar = AsyncMock(return_value=existing)

        # Act & Assert
        with pytest.raises(DuplicateError, match="Curriculum name already exists"):
            await curriculum_service.create_curriculum(data)

    @pytest.mark.asyncio
    async def test_create_curriculum_when_duplicate_code_then_raises_value_error(
        self,
        curriculum_service: CurriculumService,
        mock_db: MagicMock,
    ) -> None:
        """Test that duplicate code raises DuplicateError."""
        # Arrange
        data = CurriculumCreate(
            name="Unique Name",
            code="duplicate-code",
            is_active=True,
        )

        # First call returns None (name check passes), second returns existing (code check fails)
        existing = Curriculum(id=uuid.uuid4(), name="Other", code="duplicate-code")
        mock_db.scalar = AsyncMock(side_effect=[None, existing])

        # Act & Assert
        with pytest.raises(DuplicateError, match="Curriculum code already exists"):
            await curriculum_service.create_curriculum(data)


class TestUpdateCurriculum:
    """Tests for CurriculumService.update_curriculum."""

    @pytest.mark.asyncio
    async def test_update_curriculum_when_valid_then_returns_updated(
        self,
        curriculum_service: CurriculumService,
        mock_db: MagicMock,
    ) -> None:
        """Test updating a curriculum with valid data."""
        # Arrange
        curriculum_id = uuid.uuid4()
        existing = Curriculum(
            id=curriculum_id,
            name="Old Name",
            code="old-code",
            is_active=True,
            created_at=datetime.now(UTC),
        )
        mock_db.get = AsyncMock(return_value=existing)
        mock_db.scalar = AsyncMock(return_value=None)  # No duplicates

        data = CurriculumUpdate(name="New Name")

        # Act
        result = await curriculum_service.update_curriculum(curriculum_id, data)

        # Assert
        assert result.name == "New Name"
        assert existing.name == "New Name"
        mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_curriculum_when_not_found_then_raises_not_found(
        self,
        curriculum_service: CurriculumService,
        mock_db: MagicMock,
    ) -> None:
        """Test updating non-existent curriculum raises NotFoundError."""
        # Arrange
        mock_db.get = AsyncMock(return_value=None)
        data = CurriculumUpdate(name="New Name")

        # Act & Assert
        with pytest.raises(NotFoundError, match="Curriculum not found"):
            await curriculum_service.update_curriculum(uuid.uuid4(), data)


# =============================================================================
# Grade Tests
# =============================================================================


class TestCreateGrade:
    """Tests for CurriculumService.create_grade."""

    @pytest.mark.asyncio
    async def test_create_grade_when_valid_data_then_returns_grade(
        self,
        curriculum_service: CurriculumService,
        mock_db: MagicMock,
    ) -> None:
        """Test creating a grade with valid data."""
        # Arrange
        data = GradeCreate(
            name="Grade 7",
            level=7,
            description="Seventh grade",
            is_active=True,
        )
        mock_db.scalar = AsyncMock(return_value=None)  # No duplicate level

        # Act
        result = await curriculum_service.create_grade(data)

        # Assert
        assert result.name == "Grade 7"
        assert result.level == 7
        mock_db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_grade_when_level_out_of_range_then_raises_value_error(
        self,
        curriculum_service: CurriculumService,
        mock_db: MagicMock,
    ) -> None:
        """Test that level outside 1-13 is rejected (enforced by schema ge/le constraints)."""
        # GradeCreate.level has ge=1, le=13 — Pydantic rejects at construction time
        with pytest.raises(pydantic.ValidationError):
            GradeCreate(name="Invalid Grade", level=14, is_active=True)

    @pytest.mark.asyncio
    async def test_create_grade_when_duplicate_level_then_raises_value_error(
        self,
        curriculum_service: CurriculumService,
        mock_db: MagicMock,
    ) -> None:
        """Test that duplicate level raises DuplicateError."""
        # Arrange
        data = GradeCreate(name="Grade 7", level=7, is_active=True)
        existing = Grade(id=uuid.uuid4(), name="Year 7", level=7)
        mock_db.scalar = AsyncMock(return_value=existing)

        # Act & Assert
        with pytest.raises(DuplicateError, match="Level 7 already taken"):
            await curriculum_service.create_grade(data)


class TestUpdateGrade:
    """Tests for CurriculumService.update_grade."""

    @pytest.mark.asyncio
    async def test_update_grade_when_level_out_of_range_then_raises_value_error(
        self,
        curriculum_service: CurriculumService,
        mock_db: MagicMock,
    ) -> None:
        """Test that updating to invalid level is rejected (enforced by schema ge/le constraints)."""
        # GradeUpdate.level has ge=1, le=13 — Pydantic rejects at construction time
        with pytest.raises(pydantic.ValidationError):
            GradeUpdate(level=14)


# =============================================================================
# Subject Tests
# =============================================================================


class TestCreateSubject:
    """Tests for CurriculumService.create_subject."""

    @pytest.mark.asyncio
    async def test_create_subject_when_valid_data_then_returns_subject(
        self,
        curriculum_service: CurriculumService,
        mock_db: MagicMock,
    ) -> None:
        """Test creating a subject with valid data."""
        # Arrange
        data = SubjectCreate(
            name="Mathematics",
            code="MATH",
            description="Math subject",
            icon="calculator",
            color="#FF0000",
            is_active=True,
        )
        mock_db.scalar = AsyncMock(return_value=None)

        # Act
        result = await curriculum_service.create_subject(data)

        # Assert
        assert result.name == "Mathematics"
        assert result.code == "MATH"
        assert result.icon == "calculator"
        mock_db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_subject_when_duplicate_code_then_raises_value_error(
        self,
        curriculum_service: CurriculumService,
        mock_db: MagicMock,
    ) -> None:
        """Test that duplicate code raises DuplicateError."""
        # Arrange
        data = SubjectCreate(name="New Math", code="MATH", is_active=True)
        existing = Subject(id=uuid.uuid4(), name="Mathematics", code="MATH")
        mock_db.scalar = AsyncMock(side_effect=[None, existing])

        # Act & Assert
        with pytest.raises(DuplicateError, match="Subject code already exists"):
            await curriculum_service.create_subject(data)


# =============================================================================
# CurriculumSubject Link Tests
# =============================================================================


class TestLinkSubjectToCurriculum:
    """Tests for CurriculumService.link_subject_to_curriculum."""

    @pytest.mark.asyncio
    async def test_link_subject_when_valid_then_returns_link(
        self,
        curriculum_service: CurriculumService,
        mock_db: MagicMock,
    ) -> None:
        """Test linking subject to curriculum."""
        # Arrange
        curriculum_id = uuid.uuid4()
        subject_id = uuid.uuid4()

        curriculum = Curriculum(id=curriculum_id, name="Test", code="TST")
        subject = Subject(id=subject_id, name="Math", code="MATH")

        mock_db.get = AsyncMock(side_effect=[curriculum, subject])
        mock_db.scalar = AsyncMock(return_value=None)  # Not already linked

        data = LinkSubjectRequest(subject_id=subject_id, is_core=True, sort_order=1)

        # Act
        result = await curriculum_service.link_subject_to_curriculum(curriculum_id, data)

        # Assert
        assert result.curriculum_id == curriculum_id
        assert result.subject_id == subject_id
        assert result.is_core is True
        mock_db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_link_subject_when_already_linked_then_raises_value_error(
        self,
        curriculum_service: CurriculumService,
        mock_db: MagicMock,
    ) -> None:
        """Test that linking already-linked subject raises DuplicateError."""
        # Arrange
        curriculum_id = uuid.uuid4()
        subject_id = uuid.uuid4()

        curriculum = Curriculum(id=curriculum_id, name="Test", code="TST")
        subject = Subject(id=subject_id, name="Math", code="MATH")
        existing_link = CurriculumSubject(curriculum_id=curriculum_id, subject_id=subject_id, is_core=True)

        mock_db.get = AsyncMock(side_effect=[curriculum, subject])
        mock_db.scalar = AsyncMock(return_value=existing_link)

        data = LinkSubjectRequest(subject_id=subject_id)

        # Act & Assert
        with pytest.raises(DuplicateError, match="already linked"):
            await curriculum_service.link_subject_to_curriculum(curriculum_id, data)


# =============================================================================
# CurriculumTopic Tests
# =============================================================================


class TestAddTopicToCurriculum:
    """Tests for CurriculumService.add_topic_to_curriculum."""

    @pytest.mark.asyncio
    async def test_add_topic_when_existing_topic_id_then_creates_curriculum_topic(
        self,
        curriculum_service: CurriculumService,
        mock_db: MagicMock,
    ) -> None:
        """Test adding existing topic to curriculum."""
        # Arrange
        curriculum_id = uuid.uuid4()
        grade_id = uuid.uuid4()
        subject_id = uuid.uuid4()
        topic_id = uuid.uuid4()

        curriculum = Curriculum(id=curriculum_id, name="Test", code="TST")
        grade = Grade(id=grade_id, name="Grade 7", level=7)
        subject = Subject(id=subject_id, name="Math", code="MATH")
        topic = Topic(id=topic_id, name="Algebra")

        mock_db.get = AsyncMock(side_effect=[curriculum, grade, subject, topic])
        mock_db.scalar = AsyncMock(return_value=None)  # No duplicate placement

        data = CurriculumTopicCreate(topic_id=topic_id, standard_code="7Ma1")

        # Act
        result = await curriculum_service.add_topic_to_curriculum(curriculum_id, grade_id, subject_id, data)

        # Assert
        assert result.topic_id == topic_id
        assert result.name == "Algebra"
        assert result.standard_code == "7Ma1"

    @pytest.mark.asyncio
    async def test_add_topic_when_new_topic_data_then_creates_topic_and_curriculum_topic(
        self,
        curriculum_service: CurriculumService,
        mock_db: MagicMock,
    ) -> None:
        """Test creating new topic and adding to curriculum."""
        # Arrange
        curriculum_id = uuid.uuid4()
        grade_id = uuid.uuid4()
        subject_id = uuid.uuid4()

        curriculum = Curriculum(id=curriculum_id, name="Test", code="TST")
        grade = Grade(id=grade_id, name="Grade 7", level=7)
        subject = Subject(id=subject_id, name="Math", code="MATH")

        mock_db.get = AsyncMock(side_effect=[curriculum, grade, subject])
        mock_db.scalar = AsyncMock(return_value=None)

        topic_data = TopicIdentityCreate(name="Geometry", canonical_code="MATH-GEO")
        data = CurriculumTopicCreate(topic_data=topic_data)

        # Act
        result = await curriculum_service.add_topic_to_curriculum(curriculum_id, grade_id, subject_id, data)

        # Assert
        assert result.name == "Geometry"
        mock_db.add.assert_called()

    @pytest.mark.asyncio
    async def test_add_topic_when_duplicate_placement_then_raises_value_error(
        self,
        curriculum_service: CurriculumService,
        mock_db: MagicMock,
    ) -> None:
        """Test that duplicate placement raises DuplicateError."""
        # Arrange
        curriculum_id = uuid.uuid4()
        grade_id = uuid.uuid4()
        subject_id = uuid.uuid4()
        topic_id = uuid.uuid4()

        curriculum = Curriculum(id=curriculum_id, name="Test", code="TST")
        grade = Grade(id=grade_id, name="Grade 7", level=7)
        subject = Subject(id=subject_id, name="Math", code="MATH")
        topic = Topic(id=topic_id, name="Algebra")
        existing_placement = CurriculumTopic(
            id=uuid.uuid4(),
            curriculum_id=curriculum_id,
            grade_id=grade_id,
            subject_id=subject_id,
            topic_id=topic_id,
        )

        mock_db.get = AsyncMock(side_effect=[curriculum, grade, subject, topic])
        mock_db.scalar = AsyncMock(return_value=existing_placement)

        data = CurriculumTopicCreate(topic_id=topic_id)

        # Act & Assert
        with pytest.raises(DuplicateError, match="already placed"):
            await curriculum_service.add_topic_to_curriculum(curriculum_id, grade_id, subject_id, data)

    @pytest.mark.asyncio
    async def test_add_topic_when_neither_id_nor_data_then_raises_validation_error(
        self,
        curriculum_service: CurriculumService,
        mock_db: MagicMock,
    ) -> None:
        """Test that missing both topic_id and topic_data raises ValidationError."""
        # Arrange
        curriculum_id = uuid.uuid4()
        grade_id = uuid.uuid4()
        subject_id = uuid.uuid4()

        curriculum = Curriculum(id=curriculum_id, name="Test", code="TST")
        grade = Grade(id=grade_id, name="Grade 7", level=7)
        subject = Subject(id=subject_id, name="Math", code="MATH")

        mock_db.get = AsyncMock(side_effect=[curriculum, grade, subject])

        data = CurriculumTopicCreate()  # Neither topic_id nor topic_data

        # Act & Assert
        with pytest.raises(ValidationError, match="exactly one"):
            await curriculum_service.add_topic_to_curriculum(curriculum_id, grade_id, subject_id, data)


class TestUpdateCurriculumTopic:
    """Tests for CurriculumService.update_curriculum_topic."""

    @pytest.mark.asyncio
    async def test_update_curriculum_topic_when_valid_then_returns_updated(
        self,
        curriculum_service: CurriculumService,
        mock_db: MagicMock,
    ) -> None:
        """Test updating curriculum topic placement."""
        # Arrange
        ct_id = uuid.uuid4()
        topic_id = uuid.uuid4()

        ct = CurriculumTopic(
            id=ct_id,
            curriculum_id=uuid.uuid4(),
            grade_id=uuid.uuid4(),
            subject_id=uuid.uuid4(),
            topic_id=topic_id,
            standard_code="OLD",
            sequence_order=1,
            is_required=True,
            is_active=True,
        )
        topic = Topic(id=topic_id, name="Test Topic")

        mock_db.get = AsyncMock(side_effect=[ct, topic])
        mock_db.scalar = AsyncMock(return_value=0)  # subtopic_count

        data = CurriculumTopicUpdate(standard_code="NEW", sequence_order=2)

        # Act
        result = await curriculum_service.update_curriculum_topic(ct_id, data)

        # Assert
        assert result.standard_code == "NEW"
        assert result.sequence_order == 2


# =============================================================================
# Subtopic Tests
# =============================================================================


class TestCreateSubtopic:
    """Tests for CurriculumService.create_subtopic."""

    @pytest.mark.asyncio
    async def test_create_subtopic_when_valid_data_then_returns_subtopic(
        self,
        curriculum_service: CurriculumService,
        mock_db: MagicMock,
    ) -> None:
        """Test creating a subtopic with valid data."""
        # Arrange
        ct_id = uuid.uuid4()
        ct = CurriculumTopic(
            id=ct_id,
            curriculum_id=uuid.uuid4(),
            grade_id=uuid.uuid4(),
            subject_id=uuid.uuid4(),
            topic_id=uuid.uuid4(),
        )
        mock_db.get = AsyncMock(return_value=ct)
        mock_db.scalar = AsyncMock(return_value=None)

        data = SubtopicCreate(
            name="Linear Equations",
            learning_objective="Students will be able to solve linear equations with one variable",
            difficulty_level=3,
            estimated_minutes=45,
        )

        # Act
        result = await curriculum_service.create_subtopic(ct_id, data)

        # Assert
        assert result.name == "Linear Equations"
        assert result.learning_objective == data.learning_objective
        assert result.difficulty_level == 3
        assert not hasattr(result, "embedding")  # embedding is never in the API response
        mock_db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_subtopic_when_learning_objective_blank_then_raises_value_error(
        self,
        curriculum_service: CurriculumService,
        mock_db: MagicMock,
    ) -> None:
        """Test that blank learning_objective is rejected (schema min_length=10)."""
        # SubtopicCreate.learning_objective has min_length=10 — Pydantic rejects at construction
        with pytest.raises(pydantic.ValidationError):
            SubtopicCreate(name="Bad Subtopic", learning_objective="")

    @pytest.mark.asyncio
    async def test_create_subtopic_when_difficulty_level_out_of_range_then_raises_value_error(
        self,
        curriculum_service: CurriculumService,
        mock_db: MagicMock,
    ) -> None:
        """Test that difficulty outside 1-5 is rejected (schema ge=1, le=5)."""
        # SubtopicCreate.difficulty_level has ge=1, le=5 — Pydantic rejects at construction
        with pytest.raises(pydantic.ValidationError):
            SubtopicCreate(
                name="Hard Topic",
                learning_objective="Students will be able to do something very complex indeed",
                difficulty_level=7,
            )

    @pytest.mark.asyncio
    async def test_create_subtopic_when_valid_data_then_embedding_field_is_none(
        self,
        curriculum_service: CurriculumService,
        mock_db: MagicMock,
    ) -> None:
        """Test that embedding is never returned (populated by backend ingest)."""
        # Arrange
        ct_id = uuid.uuid4()
        ct = CurriculumTopic(
            id=ct_id,
            curriculum_id=uuid.uuid4(),
            grade_id=uuid.uuid4(),
            subject_id=uuid.uuid4(),
            topic_id=uuid.uuid4(),
        )
        mock_db.get = AsyncMock(return_value=ct)
        mock_db.scalar = AsyncMock(return_value=None)

        data = SubtopicCreate(
            name="Test",
            learning_objective="Students will be able to demonstrate understanding",
        )

        # Act
        result = await curriculum_service.create_subtopic(ct_id, data)

        # Assert - embedding is not in the response schema at all
        assert hasattr(result, "id")
        assert not hasattr(result, "embedding")


class TestUpdateSubtopic:
    """Tests for CurriculumService.update_subtopic."""

    @pytest.mark.asyncio
    async def test_update_subtopic_when_valid_then_returns_updated(
        self,
        curriculum_service: CurriculumService,
        mock_db: MagicMock,
    ) -> None:
        """Test updating a subtopic."""
        # Arrange
        subtopic_id = uuid.uuid4()
        ct_id = uuid.uuid4()

        subtopic = Subtopic(
            id=subtopic_id,
            curriculum_topic_id=ct_id,
            name="Old Name",
            learning_objective="Old objective that is long enough",
            difficulty_level=2,
            is_active=True,
        )
        mock_db.get = AsyncMock(return_value=subtopic)

        data = SubtopicUpdate(name="New Name", difficulty_level=4)

        # Act
        result = await curriculum_service.update_subtopic(subtopic_id, data)

        # Assert
        assert result.name == "New Name"
        assert result.difficulty_level == 4

    @pytest.mark.asyncio
    async def test_update_subtopic_when_difficulty_out_of_range_then_raises(
        self,
        curriculum_service: CurriculumService,
        mock_db: MagicMock,
    ) -> None:
        """Test that invalid difficulty is rejected (schema ge=1, le=5)."""
        # SubtopicUpdate.difficulty_level has ge=1, le=5 — Pydantic rejects at construction
        with pytest.raises(pydantic.ValidationError):
            SubtopicUpdate(difficulty_level=10)


# =============================================================================
# Unlink Tests
# =============================================================================


class TestUnlinkSubjectFromCurriculum:
    """Tests for CurriculumService.unlink_subject_from_curriculum."""

    @pytest.mark.asyncio
    async def test_unlink_subject_when_valid_then_deletes_link(
        self,
        curriculum_service: CurriculumService,
        mock_db: MagicMock,
    ) -> None:
        """Test unlinking subject from curriculum."""
        # Arrange
        curriculum_id = uuid.uuid4()
        subject_id = uuid.uuid4()

        link = CurriculumSubject(curriculum_id=curriculum_id, subject_id=subject_id, is_core=True)
        mock_db.scalar = AsyncMock(return_value=link)

        # Act
        await curriculum_service.unlink_subject_from_curriculum(curriculum_id, subject_id)

        # Assert
        mock_db.delete.assert_called_once_with(link)

    @pytest.mark.asyncio
    async def test_unlink_subject_when_not_linked_then_raises_not_found(
        self,
        curriculum_service: CurriculumService,
        mock_db: MagicMock,
    ) -> None:
        """Test unlinking non-linked subject raises NotFoundError."""
        # Arrange
        mock_db.scalar = AsyncMock(return_value=None)

        # Act & Assert
        with pytest.raises(NotFoundError, match="not linked"):
            await curriculum_service.unlink_subject_from_curriculum(uuid.uuid4(), uuid.uuid4())
