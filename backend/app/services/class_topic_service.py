"""ClassTopic service — teacher-configured topic list for a class."""

import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.class_topic import ClassTopic
from app.models.curriculum import CurriculumTopic, Grade, Subtopic, Topic
from app.models.school import Class
from app.schemas.class_topic import (
    ClassTopicAdd,
    ClassTopicReorder,
    ClassTopicResponse,
    ClassTopicUpdate,
)

logger = structlog.get_logger()


class ClassTopicNotFoundError(Exception):
    pass


class DuplicateClassTopicError(Exception):
    pass


class ClassTopicService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_topics(self, class_id: uuid.UUID) -> list[ClassTopicResponse]:
        """Return all topics for a class ordered by sequence_order.

        Covered topics (is_covered=True) are naturally sorted first because
        callers can expect sequence_order to be set with covered < uncovered,
        but ordering is the teacher's responsibility via reorder().
        """
        result = await self.db.execute(
            select(
                ClassTopic,
                Topic.id.label("topic_id"),
                Topic.name.label("topic_name"),
                func.count(Subtopic.id).label("subtopic_count"),
            )
            .join(CurriculumTopic, CurriculumTopic.id == ClassTopic.curriculum_topic_id)
            .join(Topic, Topic.id == CurriculumTopic.topic_id)
            .outerjoin(Subtopic, Subtopic.curriculum_topic_id == ClassTopic.curriculum_topic_id)
            .where(ClassTopic.class_id == class_id)
            .group_by(ClassTopic.id, Topic.id, Topic.name)
            .order_by(ClassTopic.sequence_order)
        )
        rows = result.all()
        return [
            ClassTopicResponse(
                id=row.ClassTopic.id,
                class_id=row.ClassTopic.class_id,
                curriculum_topic_id=row.ClassTopic.curriculum_topic_id,
                topic_id=row.topic_id,
                sequence_order=row.ClassTopic.sequence_order,
                is_covered=row.ClassTopic.is_covered,
                topic_name=row.topic_name,
                subtopic_count=row.subtopic_count,
            )
            for row in rows
        ]

    async def add_topic(
        self,
        class_id: uuid.UUID,
        school_id: uuid.UUID,
        data: ClassTopicAdd,
    ) -> ClassTopicResponse:
        """Add a curriculum topic to a class."""
        # Verify the curriculum_topic exists
        ct_result = await self.db.execute(select(CurriculumTopic).where(CurriculumTopic.id == data.curriculum_topic_id))
        curriculum_topic = ct_result.scalar_one_or_none()
        if not curriculum_topic:
            raise ClassTopicNotFoundError(f"CurriculumTopic {data.curriculum_topic_id} not found")

        # Check for duplicate
        existing = await self.db.execute(
            select(ClassTopic).where(
                ClassTopic.class_id == class_id,
                ClassTopic.curriculum_topic_id == data.curriculum_topic_id,
            )
        )
        if existing.scalar_one_or_none():
            raise DuplicateClassTopicError(f"Topic {data.curriculum_topic_id} already in class {class_id}")

        now = datetime.now(UTC)
        class_topic = ClassTopic(
            school_id=school_id,
            class_id=class_id,
            curriculum_topic_id=data.curriculum_topic_id,
            sequence_order=data.sequence_order,
            is_covered=data.is_covered,
            created_at=now,
        )
        self.db.add(class_topic)
        await self.db.flush()

        # Fetch topic id, name + subtopic count for response
        topic_result = await self.db.execute(
            select(
                Topic.id.label("topic_id"),
                Topic.name.label("topic_name"),
                func.count(Subtopic.id).label("subtopic_count"),
            )
            .join(CurriculumTopic, CurriculumTopic.topic_id == Topic.id)
            .outerjoin(Subtopic, Subtopic.curriculum_topic_id == CurriculumTopic.id)
            .where(CurriculumTopic.id == data.curriculum_topic_id)
            .group_by(Topic.id, Topic.name)
        )
        topic_row = topic_result.one()

        logger.info(
            "class_topic_added",
            class_id=str(class_id),
            curriculum_topic_id=str(data.curriculum_topic_id),
        )
        return ClassTopicResponse(
            id=class_topic.id,
            class_id=class_topic.class_id,
            curriculum_topic_id=class_topic.curriculum_topic_id,
            topic_id=topic_row.topic_id,
            sequence_order=class_topic.sequence_order,
            is_covered=class_topic.is_covered,
            topic_name=topic_row.topic_name,
            subtopic_count=topic_row.subtopic_count,
        )

    async def update_topic(
        self,
        class_id: uuid.UUID,
        class_topic_id: uuid.UUID,
        data: ClassTopicUpdate,
    ) -> ClassTopicResponse:
        """Update sequence_order or is_covered on a class topic."""
        result = await self.db.execute(
            select(ClassTopic).where(
                ClassTopic.id == class_topic_id,
                ClassTopic.class_id == class_id,
            )
        )
        class_topic = result.scalar_one_or_none()
        if not class_topic:
            raise ClassTopicNotFoundError(f"ClassTopic {class_topic_id} not found in class {class_id}")

        if data.sequence_order is not None:
            class_topic.sequence_order = data.sequence_order
        if data.is_covered is not None:
            class_topic.is_covered = data.is_covered
        class_topic.updated_at = datetime.now(UTC)
        await self.db.flush()

        # Fetch topic id, name + subtopic count for response
        topic_result = await self.db.execute(
            select(
                Topic.id.label("topic_id"),
                Topic.name.label("topic_name"),
                func.count(Subtopic.id).label("subtopic_count"),
            )
            .join(CurriculumTopic, CurriculumTopic.topic_id == Topic.id)
            .outerjoin(Subtopic, Subtopic.curriculum_topic_id == CurriculumTopic.id)
            .where(CurriculumTopic.id == class_topic.curriculum_topic_id)
            .group_by(Topic.id, Topic.name)
        )
        topic_row = topic_result.one()

        return ClassTopicResponse(
            id=class_topic.id,
            class_id=class_topic.class_id,
            curriculum_topic_id=class_topic.curriculum_topic_id,
            topic_id=topic_row.topic_id,
            sequence_order=class_topic.sequence_order,
            is_covered=class_topic.is_covered,
            topic_name=topic_row.topic_name,
            subtopic_count=topic_row.subtopic_count,
        )

    async def remove_topic(self, class_id: uuid.UUID, class_topic_id: uuid.UUID) -> None:
        """Remove a topic from a class."""
        result = await self.db.execute(
            select(ClassTopic).where(
                ClassTopic.id == class_topic_id,
                ClassTopic.class_id == class_id,
            )
        )
        class_topic = result.scalar_one_or_none()
        if not class_topic:
            raise ClassTopicNotFoundError(f"ClassTopic {class_topic_id} not found in class {class_id}")
        await self.db.delete(class_topic)
        await self.db.flush()
        logger.info(
            "class_topic_removed",
            class_topic_id=str(class_topic_id),
            class_id=str(class_id),
        )

    async def reorder_topics(
        self,
        class_id: uuid.UUID,
        data: ClassTopicReorder,
    ) -> list[ClassTopicResponse]:
        """Bulk-update sequence_order for all topics in a class after drag-and-drop."""
        ids = [item[0] for item in data.items]
        result = await self.db.execute(
            select(ClassTopic).where(
                ClassTopic.class_id == class_id,
                ClassTopic.id.in_(ids),
            )
        )
        topics_by_id = {ct.id: ct for ct in result.scalars().all()}

        now = datetime.now(UTC)
        for class_topic_id, new_order in data.items:
            if class_topic_id not in topics_by_id:
                raise ClassTopicNotFoundError(f"ClassTopic {class_topic_id} not found in class {class_id}")
            topics_by_id[class_topic_id].sequence_order = new_order
            topics_by_id[class_topic_id].updated_at = now

        await self.db.flush()
        return await self.list_topics(class_id)

    async def list_curriculum_topics_for_class(self, class_id: uuid.UUID) -> list[dict[str, object]]:
        """Return all CurriculumTopics for the class's curriculum/subject/grade
        that are NOT yet in class_topics — for the 'Add topic' picker."""
        class_result = await self.db.execute(select(Class).where(Class.id == class_id))
        class_ = class_result.scalar_one_or_none()
        if not class_:
            raise ClassTopicNotFoundError(f"Class {class_id} not found")

        # IDs already in the class
        existing_result = await self.db.execute(
            select(ClassTopic.curriculum_topic_id).where(ClassTopic.class_id == class_id)
        )
        existing_ids = set(existing_result.scalars().all())

        result = await self.db.execute(
            select(
                CurriculumTopic,
                Topic.name.label("topic_name"),
                func.count(Subtopic.id).label("subtopic_count"),
            )
            .join(Topic, Topic.id == CurriculumTopic.topic_id)
            .outerjoin(Subtopic, Subtopic.curriculum_topic_id == CurriculumTopic.id)
            .where(
                CurriculumTopic.curriculum_id == class_.curriculum_id,
                CurriculumTopic.subject_id == class_.subject_id,
                CurriculumTopic.grade_id == class_.grade_id,
                CurriculumTopic.is_active.is_(True),
                *([] if not existing_ids else [CurriculumTopic.id.not_in(existing_ids)]),
            )
            .group_by(CurriculumTopic.id, Topic.name)
            .order_by(CurriculumTopic.sequence_order)
        )
        return [
            {
                "curriculum_topic_id": row.CurriculumTopic.id,
                "topic_name": row.topic_name,
                "subtopic_count": row.subtopic_count,
                "sequence_order": row.CurriculumTopic.sequence_order,
            }
            for row in result.all()
        ]

    async def list_topics_for_diagnostic(
        self,
        class_id: uuid.UUID,
    ) -> dict[str, object]:
        """Return curriculum topics for the diagnostic topic picker.

        Returns two groups: current grade and previous grade (level - 1).
        Unlike list_curriculum_topics_for_class, this returns ALL topics
        for both grades regardless of whether they're in the teacher's class list.
        Used by the diagnostic wizard to let teachers select cross-grade topics.
        """
        class_result = await self.db.execute(select(Class).where(Class.id == class_id))
        class_ = class_result.scalar_one_or_none()
        if class_ is None:
            raise ClassTopicNotFoundError(f"Class {class_id} not found")

        # Resolve current grade level
        grade_result = await self.db.execute(select(Grade.level).where(Grade.id == class_.grade_id))
        current_level: int | None = grade_result.scalar_one_or_none()
        if current_level is None:
            raise ClassTopicNotFoundError(f"Grade not found for class {class_id}")

        prev_level = current_level - 1

        # Resolve previous grade id — only query if prev_level is valid (>= 1)
        prev_grade_id: uuid.UUID | None = None
        if prev_level >= 1:
            prev_grade_result = await self.db.execute(select(Grade.id).where(Grade.level == prev_level))
            prev_grade_id = prev_grade_result.scalar_one_or_none()

        # Query topics for both grades in one go
        grade_ids = [class_.grade_id]
        if prev_grade_id is not None:
            grade_ids.append(prev_grade_id)

        result = await self.db.execute(
            select(
                CurriculumTopic.id.label("curriculum_topic_id"),
                Topic.name.label("topic_name"),
                CurriculumTopic.grade_id,
                Grade.level.label("grade_level"),
                func.count(Subtopic.id).label("subtopic_count"),
            )
            .join(Topic, Topic.id == CurriculumTopic.topic_id)
            .join(Grade, Grade.id == CurriculumTopic.grade_id)
            .outerjoin(Subtopic, Subtopic.curriculum_topic_id == CurriculumTopic.id)
            .where(
                CurriculumTopic.curriculum_id == class_.curriculum_id,
                CurriculumTopic.subject_id == class_.subject_id,
                CurriculumTopic.grade_id.in_(grade_ids),
                CurriculumTopic.is_active.is_(True),
            )
            .group_by(CurriculumTopic.id, Topic.name, CurriculumTopic.grade_id, Grade.level)
            .order_by(Grade.level.desc(), CurriculumTopic.sequence_order)
        )
        rows = result.all()

        current_topics = [
            {
                "curriculum_topic_id": str(row.curriculum_topic_id),
                "topic_name": row.topic_name,
                "grade_level": row.grade_level,
                "subtopic_count": row.subtopic_count,
            }
            for row in rows
            if row.grade_level == current_level
        ]
        previous_topics = [
            {
                "curriculum_topic_id": str(row.curriculum_topic_id),
                "topic_name": row.topic_name,
                "grade_level": row.grade_level,
                "subtopic_count": row.subtopic_count,
            }
            for row in rows
            if row.grade_level == prev_level
        ]
        return {
            "current_grade_level": current_level,
            "previous_grade_level": prev_level,
            "current_grade_topics": current_topics,
            "previous_grade_topics": previous_topics,
        }
