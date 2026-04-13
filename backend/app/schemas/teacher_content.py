"""Teacher content review schemas — M3-0-T2b."""

from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.subtopic_content import ReviewStatus


class TeacherExplanationReviewItem(BaseModel):
    """One subtopic's explanation for teacher review."""

    subtopic_content_id: UUID
    subtopic_id: UUID
    subtopic_name: str
    explanation_text: str | None = None
    teacher_explanation: str | None = None
    review_status: str
    has_teacher_override: bool = False


class TeacherExplanationReviewWithClass(BaseModel):
    """Explanation review item with class info for teacher-wide list."""

    subtopic_content_id: UUID
    subtopic_id: UUID
    subtopic_name: str
    explanation_text: str | None = None
    teacher_explanation: str | None = None
    review_status: str
    has_teacher_override: bool = False
    class_id: UUID
    class_name: str
    created_at: str


class TeacherExplanationReviewListResponse(BaseModel):
    """Paginated list of explanation content for a class."""

    items: list[TeacherExplanationReviewItem]
    total: int
    pending_count: int


class TeacherExplanationReviewDetailResponse(BaseModel):
    """Full explanation detail for one subtopic."""

    subtopic_content_id: UUID
    subtopic_id: UUID
    subtopic_name: str
    learning_objective: str
    explanation_text: str | None = None
    teacher_explanation: str | None = None
    review_status: str
    has_teacher_override: bool = False
    applicable_tiers: list[int]


class TeacherExplanationUpdateRequest(BaseModel):
    """Request to update explanation status and/or add teacher override."""

    review_status: ReviewStatus | None = None
    teacher_explanation: str | None = Field(
        default=None,
        max_length=5000,
        description="Teacher's own explanation to override the AI explanation",
    )


class TeacherExplanationUpdateResponse(BaseModel):
    """Response after updating explanation."""

    subtopic_content_id: UUID
    review_status: str
    teacher_explanation: str | None = None
    has_teacher_override: bool
