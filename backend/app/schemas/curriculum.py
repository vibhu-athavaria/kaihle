"""Curriculum schemas — global read-only data, no school_id.

This module contains both existing read schemas and new admin-specific
schemas for Kaihle Admin curriculum management.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# =============================================================================
# Existing Read Schemas (kept for backward compatibility)
# =============================================================================


class GradeResponse(BaseModel):
    id: UUID
    name: str  # e.g. "Grade 9"
    level: int  # e.g. 9
    curriculum_id: UUID | None = None  # None when no curriculum filter applied


class SubjectResponse(BaseModel):
    id: UUID
    name: str  # e.g. "Mathematics"
    code: str  # e.g. "MATH"


class TopicResponse(BaseModel):
    id: UUID
    name: str
    subject_id: UUID
    grade_id: UUID
    order: int


class SubtopicResponse(BaseModel):
    id: UUID
    name: str
    topic_id: UUID
    order: int


class CurriculumResponse(BaseModel):
    id: UUID
    name: str  # e.g. "Cambridge IGCSE"
    code: str  # e.g. "igcse"
    is_active: bool


# Simplified schemas for dropdown use (id, name only)
class TopicSimpleResponse(BaseModel):
    id: UUID
    name: str


class SubtopicSimpleResponse(BaseModel):
    id: UUID
    name: str


class CurriculumTopicSimpleResponse(BaseModel):
    id: UUID
    name: str


# =============================================================================
# Admin Response Schemas (richer for Kaihle Admin UI)
# =============================================================================


class CurriculumAdminResponse(BaseModel):
    """Full curriculum data for admin management."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    code: str
    description: str | None = None
    country: str | None = None
    is_active: bool
    created_at: datetime


class GradeAdminResponse(BaseModel):
    """Full grade data for admin management."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    level: int
    description: str | None = None
    is_active: bool
    curriculum_ids: list[UUID] = []


class SubjectAdminResponse(BaseModel):
    """Full subject data for admin management."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    code: str
    description: str | None = None
    icon: str | None = None
    color: str | None = None
    is_active: bool


class CurriculumSubjectResponse(BaseModel):
    """Curriculum-Subject link data."""

    model_config = ConfigDict(from_attributes=True)

    curriculum_id: UUID
    subject_id: UUID
    subject_name: str
    subject_code: str
    is_core: bool
    sort_order: int | None = None


class TopicAdminResponse(BaseModel):
    """Curriculum Topic (placement) data with topic identity."""

    model_config = ConfigDict(from_attributes=True)

    curriculum_topic_id: UUID
    topic_id: UUID
    name: str
    canonical_code: str | None = None
    standard_code: str | None = None
    sequence_order: int | None = None
    learning_objectives: list[str] = []
    recommended_weeks: int | None = None
    is_required: bool
    is_active: bool
    subtopic_count: int = 0
    grade_id: UUID | None = None
    grade_name: str | None = None


class SubtopicAdminResponse(BaseModel):
    """Full subtopic data for admin management."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    curriculum_topic_id: UUID
    name: str
    canonical_code: str | None = None
    learning_objective: str
    description: str | None = None
    keywords: list[str] | None = None
    bloom_taxonomy_level: str | None = None
    difficulty_level: int | None = None
    estimated_minutes: int | None = None
    sequence_order: int | None = None
    is_active: bool


# =============================================================================
# Write Request Schemas
# =============================================================================


class CurriculumCreate(BaseModel):
    """Create a new curriculum board."""

    name: str = Field(..., max_length=200, description="Unique curriculum name")
    code: str = Field(..., max_length=50, description="Unique slug code")
    description: str | None = Field(None, description="Optional description")
    country: str | None = Field(None, description="Country code, blank for international")
    is_active: bool = Field(True, description="Whether the curriculum is active")


class CurriculumUpdate(BaseModel):
    """Update an existing curriculum."""

    name: str | None = Field(None, max_length=200)
    code: str | None = Field(None, max_length=50)
    description: str | None = None
    country: str | None = None
    is_active: bool | None = None


class GradeCreate(BaseModel):
    """Create a new grade level."""

    name: str = Field(..., max_length=50, description="Display name e.g. 'Grade 7'")
    level: int = Field(..., ge=1, le=13, description="Numeric level 1-13")
    description: str | None = Field(None, description="Optional description")
    is_active: bool = Field(True, description="Whether the grade is active")
    curriculum_ids: list[UUID] = Field(default_factory=list, description="Curricula this grade belongs to")


class GradeUpdate(BaseModel):
    """Update an existing grade."""

    name: str | None = Field(None, max_length=50)
    level: int | None = Field(None, ge=1, le=13)
    description: str | None = None
    is_active: bool | None = None
    curriculum_ids: list[UUID] | None = Field(
        None, description="Full-replace curriculum associations; omit to leave unchanged"
    )


class SubjectCreate(BaseModel):
    """Create a new subject."""

    name: str = Field(..., max_length=100, description="Unique subject name")
    code: str = Field(..., max_length=20, description="Unique uppercase code")
    description: str | None = Field(None, description="Optional description")
    icon: str | None = Field(None, max_length=50, description="Lucide icon name")
    color: str | None = Field(None, max_length=7, description="Hex color e.g. #1a5c38")
    is_active: bool = Field(True, description="Whether the subject is active")


class SubjectUpdate(BaseModel):
    """Update an existing subject."""

    name: str | None = Field(None, max_length=100)
    code: str | None = Field(None, max_length=20)
    description: str | None = None
    icon: str | None = Field(None, max_length=50)
    color: str | None = Field(None, max_length=7)
    is_active: bool | None = None


class LinkSubjectRequest(BaseModel):
    """Link a subject to a curriculum."""

    subject_id: UUID = Field(..., description="Subject to link")
    is_core: bool = Field(True, description="Whether this is a core subject")
    sort_order: int | None = Field(None, description="Display order within curriculum")


class TopicIdentityCreate(BaseModel):
    """Create a new global topic identity (used when not reusing existing topic)."""

    name: str = Field(..., max_length=255, description="Topic name")
    canonical_code: str | None = Field(None, max_length=50, description="Stable code e.g. MATH-ALG")
    description: str | None = Field(None, description="Optional description")
    keywords: list[str] = Field(default_factory=list, description="Keywords for search")


class CurriculumTopicCreate(BaseModel):
    """Create a curriculum topic placement.

    Exactly one of topic_id or topic_data must be provided.
    """

    topic_id: UUID | None = Field(None, description="Existing topic ID to reuse")
    topic_data: TopicIdentityCreate | None = Field(None, description="Create new topic identity")
    standard_code: str | None = Field(None, max_length=100, description="Standard code e.g. 8Ma1")
    sequence_order: int | None = Field(None, description="Teaching order, auto-assigned if blank")
    learning_objectives: list[str] = Field(default_factory=list, description="Learning objectives")
    recommended_weeks: int | None = Field(None, description="Recommended weeks to teach")
    is_required: bool = Field(True, description="Whether topic is required (core)")


class CurriculumTopicUpdate(BaseModel):
    """Update a curriculum topic placement."""

    standard_code: str | None = Field(None, max_length=100)
    sequence_order: int | None = Field(None)
    learning_objectives: list[str] | None = None
    recommended_weeks: int | None = None
    is_required: bool | None = None
    is_active: bool | None = None


class SubtopicCreate(BaseModel):
    """Create a subtopic under a curriculum topic."""

    name: str = Field(..., description="Subtopic name")
    learning_objective: str = Field(
        ...,
        min_length=10,
        description="Required learning objective (min 10 chars, fed to LLM)",
    )
    canonical_code: str | None = Field(None, max_length=50, description="Code e.g. 8Ma1.2")
    description: str | None = Field(None, description="Optional detailed description")
    keywords: list[str] = Field(default_factory=list, description="Keywords")
    bloom_taxonomy_level: str | None = Field(
        None,
        pattern="^(Remember|Understand|Apply|Analyse|Evaluate|Create)$",
        description="Bloom's taxonomy level",
    )
    difficulty_level: int | None = Field(None, ge=1, le=5, description="Difficulty 1-5")
    estimated_minutes: int | None = Field(None, description="Estimated learning time")
    sequence_order: int | None = Field(None, description="Order within topic, auto if blank")


class SubtopicUpdate(BaseModel):
    """Update a subtopic."""

    name: str | None = None
    learning_objective: str | None = Field(None, min_length=10)
    canonical_code: str | None = Field(None, max_length=50)
    description: str | None = None
    keywords: list[str] | None = None
    bloom_taxonomy_level: str | None = Field(
        None,
        pattern="^(Remember|Understand|Apply|Analyse|Evaluate|Create)$",
    )
    difficulty_level: int | None = Field(None, ge=1, le=5)
    estimated_minutes: int | None = None
    sequence_order: int | None = None
    is_active: bool | None = None
