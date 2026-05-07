"""Pydantic schemas for class topic management."""

import uuid

from pydantic import BaseModel, ConfigDict, Field


class ClassTopicAdd(BaseModel):
    """Add a curriculum topic to a class."""

    curriculum_topic_id: uuid.UUID
    sequence_order: int = Field(..., ge=0)
    is_covered: bool = False


class ClassTopicUpdate(BaseModel):
    """Update sequence_order or is_covered on an existing class topic."""

    sequence_order: int | None = Field(None, ge=0)
    is_covered: bool | None = None


class ClassTopicReorder(BaseModel):
    """Bulk reorder: list of (class_topic_id, new_sequence_order) pairs."""

    items: list[tuple[uuid.UUID, int]] = Field(..., min_length=1)


class ClassTopicResponse(BaseModel):
    """Response for a single class topic."""

    id: uuid.UUID
    class_id: uuid.UUID
    curriculum_topic_id: uuid.UUID
    topic_id: uuid.UUID
    sequence_order: int
    is_covered: bool
    # Denormalized from curriculum_topics for display
    topic_name: str
    subtopic_count: int

    model_config = ConfigDict(from_attributes=True)
