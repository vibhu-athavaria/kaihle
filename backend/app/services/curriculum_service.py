"""Curriculum management service layer for Kaihle Admin.

All curriculum CRUD operations are centralized here following Rule 1:
routes remain thin handlers that delegate to this service.
"""

import uuid
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import func, select
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
    SubjectUpdate,
    SubtopicCreate,
    SubtopicUpdate,
    TopicIdentityCreate,
)

if TYPE_CHECKING:
    from app.schemas.curriculum import (
        CurriculumAdminResponse,
        CurriculumSubjectResponse,
        GradeAdminResponse,
        SubjectAdminResponse,
        SubtopicAdminResponse,
        TopicAdminResponse,
    )

logger = structlog.get_logger()


class CurriculumServiceError(ValueError):
    """Base exception for curriculum service errors."""


class DuplicateError(CurriculumServiceError):
    """Raised when a duplicate unique value is detected."""


class ValidationError(CurriculumServiceError):
    """Raised when validation fails."""


class NotFoundError(CurriculumServiceError):
    """Raised when an entity is not found."""


class CurriculumService:
    """Service for managing curriculum data (CRUD operations).

    All methods follow Rule 1: business logic is here, routes are thin.
    Rule 12: KAIHLE_ADMIN bypass - no school_id filtering.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Curriculum Operations
    # ------------------------------------------------------------------

    async def create_curriculum(
        self,
        data: CurriculumCreate,
    ) -> "CurriculumAdminResponse":
        """Create a new curriculum board.

        Validates unique constraints before DB operation.
        Raises DuplicateError on name or code conflict.
        """
        # Check for duplicate name
        existing = await self.db.scalar(select(Curriculum).where(Curriculum.name == data.name))
        if existing:
            raise DuplicateError("Curriculum name already exists")

        # Check for duplicate code
        existing = await self.db.scalar(select(Curriculum).where(Curriculum.code == data.code))
        if existing:
            raise DuplicateError("Curriculum code already exists")

        curriculum = Curriculum(
            name=data.name,
            code=data.code,
            description=data.description,
            country=data.country,
            is_active=data.is_active,
        )
        self.db.add(curriculum)
        await self.db.flush()

        logger.info("curriculum_created", curriculum_id=str(curriculum.id), name=data.name)

        from app.schemas.curriculum import CurriculumAdminResponse

        return CurriculumAdminResponse(
            id=curriculum.id,
            name=curriculum.name,
            code=curriculum.code,
            description=curriculum.description,
            country=curriculum.country,
            is_active=curriculum.is_active,
            created_at=curriculum.created_at,
        )

    async def update_curriculum(
        self,
        curriculum_id: uuid.UUID,
        data: CurriculumUpdate,
    ) -> "CurriculumAdminResponse":
        """Update an existing curriculum.

        Validates unique constraints for name/code if changed.
        Raises NotFoundError if curriculum doesn't exist.
        Raises DuplicateError on name or code conflict.
        """
        curriculum = await self.db.get(Curriculum, curriculum_id)
        if not curriculum:
            raise NotFoundError("Curriculum not found")

        update_data = data.model_dump(exclude_unset=True)

        # Check for duplicate name if changing
        if "name" in update_data and update_data["name"] != curriculum.name:
            existing = await self.db.scalar(
                select(Curriculum).where(
                    Curriculum.name == update_data["name"],
                    Curriculum.id != curriculum_id,
                )
            )
            if existing:
                raise DuplicateError("Curriculum name already exists")

        # Check for duplicate code if changing
        if "code" in update_data and update_data["code"] != curriculum.code:
            existing = await self.db.scalar(
                select(Curriculum).where(
                    Curriculum.code == update_data["code"],
                    Curriculum.id != curriculum_id,
                )
            )
            if existing:
                raise DuplicateError("Curriculum code already exists")

        for field, value in update_data.items():
            setattr(curriculum, field, value)

        await self.db.flush()

        logger.info("curriculum_updated", curriculum_id=str(curriculum_id))

        from app.schemas.curriculum import CurriculumAdminResponse

        return CurriculumAdminResponse(
            id=curriculum.id,
            name=curriculum.name,
            code=curriculum.code,
            description=curriculum.description,
            country=curriculum.country,
            is_active=curriculum.is_active,
            created_at=curriculum.created_at,
        )

    # ------------------------------------------------------------------
    # Grade Operations
    # ------------------------------------------------------------------

    async def create_grade(self, data: GradeCreate) -> "GradeAdminResponse":
        """Create a new grade level.

        Validates level is 1-13 and unique.
        Raises ValidationError if level out of range.
        Raises DuplicateError if level already exists.
        """
        if data.level < 1 or data.level > 13:
            raise ValidationError("Grade level must be between 1 and 13")

        # Check for duplicate level
        existing = await self.db.scalar(select(Grade).where(Grade.level == data.level))
        if existing:
            raise DuplicateError(f"Level {data.level} already taken by {existing.name}")

        grade = Grade(
            name=data.name,
            level=data.level,
            description=data.description,
            is_active=data.is_active,
        )
        self.db.add(grade)
        await self.db.flush()

        logger.info("grade_created", grade_id=str(grade.id), level=data.level)

        from app.schemas.curriculum import GradeAdminResponse

        return GradeAdminResponse(
            id=grade.id,
            name=grade.name,
            level=grade.level,
            description=grade.description,
            is_active=grade.is_active,
        )

    async def update_grade(
        self,
        grade_id: uuid.UUID,
        data: GradeUpdate,
    ) -> "GradeAdminResponse":
        """Update an existing grade.

        Validates level constraints if changing.
        Raises NotFoundError if grade doesn't exist.
        """
        grade = await self.db.get(Grade, grade_id)
        if not grade:
            raise NotFoundError("Grade not found")

        update_data = data.model_dump(exclude_unset=True)

        # Validate level if changing
        if "level" in update_data:
            new_level = update_data["level"]
            if new_level is not None and (new_level < 1 or new_level > 13):
                raise ValidationError("Grade level must be between 1 and 13")

            if new_level is not None and new_level != grade.level:
                existing = await self.db.scalar(select(Grade).where(Grade.level == new_level, Grade.id != grade_id))
                if existing:
                    raise DuplicateError(f"Level {new_level} already taken by {existing.name}")

        for field, value in update_data.items():
            setattr(grade, field, value)

        await self.db.flush()

        logger.info("grade_updated", grade_id=str(grade_id))

        from app.schemas.curriculum import GradeAdminResponse

        return GradeAdminResponse(
            id=grade.id,
            name=grade.name,
            level=grade.level,
            description=grade.description,
            is_active=grade.is_active,
        )

    # ------------------------------------------------------------------
    # Subject Operations
    # ------------------------------------------------------------------

    async def create_subject(self, data: SubjectCreate) -> "SubjectAdminResponse":
        """Create a new subject.

        Validates unique constraints for name and code.
        Raises DuplicateError on conflict.
        """
        # Check for duplicate name
        existing = await self.db.scalar(select(Subject).where(Subject.name == data.name))
        if existing:
            raise DuplicateError("Subject name already exists")

        # Check for duplicate code
        existing = await self.db.scalar(select(Subject).where(Subject.code == data.code))
        if existing:
            raise DuplicateError("Subject code already exists")

        subject = Subject(
            name=data.name,
            code=data.code,
            description=data.description,
            icon=data.icon,
            color=data.color,
            is_active=data.is_active,
        )
        self.db.add(subject)
        await self.db.flush()

        logger.info("subject_created", subject_id=str(subject.id), name=data.name)

        from app.schemas.curriculum import SubjectAdminResponse

        return SubjectAdminResponse(
            id=subject.id,
            name=subject.name,
            code=subject.code,
            description=subject.description,
            icon=subject.icon,
            color=subject.color,
            is_active=subject.is_active,
        )

    async def update_subject(
        self,
        subject_id: uuid.UUID,
        data: SubjectUpdate,
    ) -> "SubjectAdminResponse":
        """Update an existing subject.

        Validates unique constraints if changing name/code.
        Raises NotFoundError if subject doesn't exist.
        """
        subject = await self.db.get(Subject, subject_id)
        if not subject:
            raise NotFoundError("Subject not found")

        update_data = data.model_dump(exclude_unset=True)

        # Check for duplicate name if changing
        if "name" in update_data and update_data["name"] != subject.name:
            existing = await self.db.scalar(
                select(Subject).where(Subject.name == update_data["name"], Subject.id != subject_id)
            )
            if existing:
                raise DuplicateError("Subject name already exists")

        # Check for duplicate code if changing
        if "code" in update_data and update_data["code"] != subject.code:
            existing = await self.db.scalar(
                select(Subject).where(Subject.code == update_data["code"], Subject.id != subject_id)
            )
            if existing:
                raise DuplicateError("Subject code already exists")

        for field, value in update_data.items():
            setattr(subject, field, value)

        await self.db.flush()

        logger.info("subject_updated", subject_id=str(subject_id))

        from app.schemas.curriculum import SubjectAdminResponse

        return SubjectAdminResponse(
            id=subject.id,
            name=subject.name,
            code=subject.code,
            description=subject.description,
            icon=subject.icon,
            color=subject.color,
            is_active=subject.is_active,
        )

    # ------------------------------------------------------------------
    # CurriculumSubject Operations (Link/Unlink)
    # ------------------------------------------------------------------

    async def link_subject_to_curriculum(
        self,
        curriculum_id: uuid.UUID,
        data: LinkSubjectRequest,
    ) -> "CurriculumSubjectResponse":
        """Link a subject to a curriculum.

        Raises NotFoundError if curriculum or subject doesn't exist.
        Raises DuplicateError if already linked.
        """
        # Verify curriculum exists
        curriculum = await self.db.get(Curriculum, curriculum_id)
        if not curriculum:
            raise NotFoundError("Curriculum not found")

        # Verify subject exists
        subject = await self.db.get(Subject, data.subject_id)
        if not subject:
            raise NotFoundError("Subject not found")

        # Check if already linked
        existing = await self.db.scalar(
            select(CurriculumSubject).where(
                CurriculumSubject.curriculum_id == curriculum_id,
                CurriculumSubject.subject_id == data.subject_id,
            )
        )
        if existing:
            raise DuplicateError("Subject already linked to this curriculum")

        link = CurriculumSubject(
            curriculum_id=curriculum_id,
            subject_id=data.subject_id,
            is_core=data.is_core,
            sort_order=data.sort_order,
        )
        self.db.add(link)
        await self.db.flush()

        logger.info(
            "subject_linked_to_curriculum",
            curriculum_id=str(curriculum_id),
            subject_id=str(data.subject_id),
        )

        from app.schemas.curriculum import CurriculumSubjectResponse

        return CurriculumSubjectResponse(
            curriculum_id=link.curriculum_id,
            subject_id=link.subject_id,
            subject_name=subject.name,
            subject_code=subject.code,
            is_core=link.is_core,
            sort_order=link.sort_order,
        )

    async def unlink_subject_from_curriculum(
        self,
        curriculum_id: uuid.UUID,
        subject_id: uuid.UUID,
    ) -> None:
        """Unlink a subject from a curriculum.

        Raises NotFoundError if link doesn't exist.
        """
        link = await self.db.scalar(
            select(CurriculumSubject).where(
                CurriculumSubject.curriculum_id == curriculum_id,
                CurriculumSubject.subject_id == subject_id,
            )
        )
        if not link:
            raise NotFoundError("Subject not linked to this curriculum")

        await self.db.delete(link)
        await self.db.flush()

        logger.info(
            "subject_unlinked_from_curriculum",
            curriculum_id=str(curriculum_id),
            subject_id=str(subject_id),
        )

    # ------------------------------------------------------------------
    # Topic Operations (Two-step: identity + placement)
    # ------------------------------------------------------------------

    async def add_topic_to_curriculum(
        self,
        curriculum_id: uuid.UUID,
        grade_id: uuid.UUID,
        subject_id: uuid.UUID,
        data: CurriculumTopicCreate,
    ) -> "TopicAdminResponse":
        """Add a topic to a curriculum/grade/subject combination.

        Accepts either topic_id (existing topic) or topic_data (create new).
        Validates exactly one is provided.
        Auto-calculates sequence_order if not provided.
        Raises DuplicateError if topic already placed at this location.
        """
        from app.schemas.curriculum import TopicAdminResponse

        # Verify curriculum, grade, subject exist
        curriculum = await self.db.get(Curriculum, curriculum_id)
        if not curriculum:
            raise NotFoundError("Curriculum not found")

        grade = await self.db.get(Grade, grade_id)
        if not grade:
            raise NotFoundError("Grade not found")

        subject = await self.db.get(Subject, subject_id)
        if not subject:
            raise NotFoundError("Subject not found")

        # Validate exactly one of topic_id or topic_data
        if bool(data.topic_id) == bool(data.topic_data):
            raise ValidationError("Provide exactly one of topic_id or topic_data")

        topic_id: uuid.UUID

        if data.topic_id:
            # Use existing topic
            topic = await self.db.get(Topic, data.topic_id)
            if not topic:
                raise NotFoundError("Topic not found")
            topic_id = topic.id
        else:
            # Create new topic from topic_data
            assert data.topic_data is not None  # guaranteed by validation above
            topic = await self._create_topic_identity(data.topic_data)
            topic_id = topic.id

        # Check for duplicate placement
        existing = await self.db.scalar(
            select(CurriculumTopic).where(
                CurriculumTopic.curriculum_id == curriculum_id,
                CurriculumTopic.grade_id == grade_id,
                CurriculumTopic.subject_id == subject_id,
                CurriculumTopic.topic_id == topic_id,
            )
        )
        if existing:
            raise DuplicateError("Topic already placed in this curriculum/grade/subject")

        # Auto-calculate sequence_order if not provided
        sequence_order = data.sequence_order
        if sequence_order is None:
            sequence_order = await self._get_next_sequence_order(curriculum_id, grade_id, subject_id)

        ct = CurriculumTopic(
            curriculum_id=curriculum_id,
            grade_id=grade_id,
            subject_id=subject_id,
            topic_id=topic_id,
            standard_code=data.standard_code,
            sequence_order=sequence_order,
            learning_objectives=data.learning_objectives or [],
            recommended_weeks=data.recommended_weeks,
            is_required=data.is_required,
            is_active=True,
        )
        self.db.add(ct)
        await self.db.flush()

        logger.info(
            "topic_added_to_curriculum",
            curriculum_topic_id=str(ct.id),
            curriculum_id=str(curriculum_id),
            grade_id=str(grade_id),
            subject_id=str(subject_id),
            topic_id=str(topic_id),
        )

        return TopicAdminResponse(
            curriculum_topic_id=ct.id,
            topic_id=topic.id,
            name=topic.name,
            canonical_code=topic.canonical_code,
            standard_code=ct.standard_code,
            sequence_order=ct.sequence_order,
            learning_objectives=ct.learning_objectives or [],
            recommended_weeks=ct.recommended_weeks,
            is_required=ct.is_required,
            is_active=ct.is_active,
            subtopic_count=0,  # newly created, no subtopics yet
        )

    async def _create_topic_identity(self, data: TopicIdentityCreate) -> Topic:
        """Create a new global topic identity.

        Internal helper - not exposed directly.
        """
        topic = Topic(
            name=data.name,
            canonical_code=data.canonical_code,
            description=data.description,
            keywords=data.keywords or [],
            is_active=True,
        )
        self.db.add(topic)
        await self.db.flush()

        logger.info("topic_identity_created", topic_id=str(topic.id), name=data.name)
        return topic

    async def _get_next_sequence_order(
        self,
        curriculum_id: uuid.UUID,
        grade_id: uuid.UUID,
        subject_id: uuid.UUID,
    ) -> int | None:
        """Get the next sequence order for a topic placement.

        Returns max + 1, or 1 if no topics yet.
        """
        result = await self.db.scalar(
            select(func.max(CurriculumTopic.sequence_order)).where(
                CurriculumTopic.curriculum_id == curriculum_id,
                CurriculumTopic.grade_id == grade_id,
                CurriculumTopic.subject_id == subject_id,
            )
        )
        return (result or 0) + 1

    async def update_curriculum_topic(
        self,
        ct_id: uuid.UUID,
        data: CurriculumTopicUpdate,
    ) -> "TopicAdminResponse":
        """Update a curriculum topic placement.

        Raises NotFoundError if curriculum_topic doesn't exist.
        Does NOT update topic identity - only placement fields.
        """
        ct = await self.db.get(CurriculumTopic, ct_id)
        if not ct:
            raise NotFoundError("Curriculum topic not found")

        update_data = data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(ct, field, value)

        await self.db.flush()

        # Fetch topic for response
        topic = await self.db.get(Topic, ct.topic_id)
        assert topic is not None  # FK constraint ensures this

        # Count subtopics
        subtopic_count = await self.db.scalar(
            select(func.count(Subtopic.id)).where(Subtopic.curriculum_topic_id == ct_id)
        )

        logger.info("curriculum_topic_updated", curriculum_topic_id=str(ct_id))

        from app.schemas.curriculum import TopicAdminResponse

        return TopicAdminResponse(
            curriculum_topic_id=ct.id,
            topic_id=topic.id,
            name=topic.name,
            canonical_code=topic.canonical_code,
            standard_code=ct.standard_code,
            sequence_order=ct.sequence_order,
            learning_objectives=ct.learning_objectives or [],
            recommended_weeks=ct.recommended_weeks,
            is_required=ct.is_required,
            is_active=ct.is_active,
            subtopic_count=subtopic_count or 0,
        )

    async def delete_curriculum_topic(self, ct_id: uuid.UUID) -> None:
        """Remove a topic from a curriculum (deletes the placement, not the topic).

        Raises NotFoundError if curriculum_topic doesn't exist.
        """
        ct = await self.db.get(CurriculumTopic, ct_id)
        if not ct:
            raise NotFoundError("Curriculum topic not found")

        await self.db.delete(ct)
        await self.db.flush()

        logger.info("curriculum_topic_deleted", curriculum_topic_id=str(ct_id))

    # ------------------------------------------------------------------
    # Subtopic Operations
    # ------------------------------------------------------------------

    async def create_subtopic(
        self,
        ct_id: uuid.UUID,
        data: SubtopicCreate,
    ) -> "SubtopicAdminResponse":
        """Create a subtopic under a curriculum topic.

        Validates learning_objective is present and min 10 chars.
        Validates difficulty_level is 1-5 if provided.
        Auto-calculates sequence_order if not provided.
        embedding field is set to None (populated by backend ingest).
        """
        from app.schemas.curriculum import SubtopicAdminResponse

        # Verify curriculum_topic exists
        ct = await self.db.get(CurriculumTopic, ct_id)
        if not ct:
            raise NotFoundError("Curriculum topic not found")

        # Validate learning_objective
        if not data.learning_objective or len(data.learning_objective.strip()) < 10:
            raise ValidationError("learning_objective is required (min 10 characters)")

        # Validate difficulty_level if provided
        if data.difficulty_level is not None and (data.difficulty_level < 1 or data.difficulty_level > 5):
            raise ValidationError("difficulty_level must be between 1 and 5")

        # Auto-calculate sequence_order if not provided
        sequence_order = data.sequence_order
        if sequence_order is None:
            sequence_order = await self._get_next_subtopic_sequence_order(ct_id)

        subtopic = Subtopic(
            curriculum_topic_id=ct_id,
            name=data.name,
            canonical_code=data.canonical_code,
            description=data.description,
            learning_objective=data.learning_objective,
            keywords=data.keywords or [],
            bloom_taxonomy_level=data.bloom_taxonomy_level,
            difficulty_level=data.difficulty_level,
            estimated_minutes=data.estimated_minutes,
            sequence_order=sequence_order,
            is_active=True,
            embedding=None,  # populated by backend ingest script
        )
        self.db.add(subtopic)
        await self.db.flush()

        logger.info("subtopic_created", subtopic_id=str(subtopic.id), name=data.name, ct_id=str(ct_id))

        return SubtopicAdminResponse(
            id=subtopic.id,
            curriculum_topic_id=subtopic.curriculum_topic_id,
            name=subtopic.name,
            canonical_code=subtopic.canonical_code,
            learning_objective=subtopic.learning_objective,
            description=subtopic.description,
            keywords=subtopic.keywords or [],
            bloom_taxonomy_level=subtopic.bloom_taxonomy_level,
            difficulty_level=subtopic.difficulty_level,
            estimated_minutes=subtopic.estimated_minutes,
            sequence_order=subtopic.sequence_order,
            is_active=subtopic.is_active,
        )

    async def _get_next_subtopic_sequence_order(self, ct_id: uuid.UUID) -> int | None:
        """Get the next sequence order for a subtopic.

        Returns max + 1, or 1 if no subtopics yet.
        """
        result = await self.db.scalar(
            select(func.max(Subtopic.sequence_order)).where(Subtopic.curriculum_topic_id == ct_id)
        )
        return (result or 0) + 1

    async def update_subtopic(
        self,
        subtopic_id: uuid.UUID,
        data: SubtopicUpdate,
    ) -> "SubtopicAdminResponse":
        """Update a subtopic.

        Validates difficulty_level is 1-5 if provided.
        Raises NotFoundError if subtopic doesn't exist.
        """
        subtopic = await self.db.get(Subtopic, subtopic_id)
        if not subtopic:
            raise NotFoundError("Subtopic not found")

        update_data = data.model_dump(exclude_unset=True)

        # Validate difficulty_level if changing
        if "difficulty_level" in update_data:
            new_level = update_data["difficulty_level"]
            if new_level is not None and (new_level < 1 or new_level > 5):
                raise ValidationError("difficulty_level must be between 1 and 5")

        for field, value in update_data.items():
            setattr(subtopic, field, value)

        await self.db.flush()

        logger.info("subtopic_updated", subtopic_id=str(subtopic_id))

        from app.schemas.curriculum import SubtopicAdminResponse

        return SubtopicAdminResponse(
            id=subtopic.id,
            curriculum_topic_id=subtopic.curriculum_topic_id,
            name=subtopic.name,
            canonical_code=subtopic.canonical_code,
            learning_objective=subtopic.learning_objective,
            description=subtopic.description,
            keywords=subtopic.keywords or [],
            bloom_taxonomy_level=subtopic.bloom_taxonomy_level,
            difficulty_level=subtopic.difficulty_level,
            estimated_minutes=subtopic.estimated_minutes,
            sequence_order=subtopic.sequence_order,
            is_active=subtopic.is_active,
        )

    async def delete_subtopic(self, subtopic_id: uuid.UUID) -> None:
        """Delete a subtopic.

        Raises NotFoundError if subtopic doesn't exist.
        """
        subtopic = await self.db.get(Subtopic, subtopic_id)
        if not subtopic:
            raise NotFoundError("Subtopic not found")

        await self.db.delete(subtopic)
        await self.db.flush()

        logger.info("subtopic_deleted", subtopic_id=str(subtopic_id))
