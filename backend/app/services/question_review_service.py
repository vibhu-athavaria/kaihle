"""KaihleAdmin question review service.

Manages the unified review queue for:
- TEACHER_QUESTION: teacher-submitted questions pending promotion to global bank.
- EDIT_SUGGESTION: teacher-proposed edits to existing questions.

Design:
- list_pending_items: single JOIN query across question_review_items → question_bank
  → subtopic → curriculum_topic → topic, schools, users.
- approve_item: branched on item_type.
  TEACHER_QUESTION: apply admin edits (if any) to question_bank, clear school_id → global.
  EDIT_SUGGESTION: apply suggested (or admin-edited) fields to question_bank row.
- reject_item: TEACHER_QUESTION → deactivate question; EDIT_SUGGESTION → no bank change.
"""

import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import QuestionReviewItem
from app.models.curriculum import CurriculumTopic, QuestionBank, Subtopic, Topic
from app.models.school import School
from app.models.user import User
from app.schemas.question_review import (
    ApproveReviewItemRequest,
    QuestionReviewItemResponse,
    QuestionReviewListResponse,
    RejectReviewItemRequest,
)

logger = structlog.get_logger()


class ReviewItemNotFoundError(Exception):
    """Raised when a question_review_items row does not exist."""


class ReviewItemAlreadyResolvedError(Exception):
    """Raised when trying to approve/reject an already-resolved item."""


class QuestionReviewService:
    """Service for KaihleAdmin question review operations."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_pending_items(
        self,
        item_type: str | None,
        page: int,
        page_size: int,
    ) -> QuestionReviewListResponse:
        """Return paginated PENDING review items with full context.

        Args:
            item_type: Optional filter — 'TEACHER_QUESTION' or 'EDIT_SUGGESTION'.
            page: 1-based page number.
            page_size: Items per page (max 100).

        Returns:
            QuestionReviewListResponse with items and total count.
        """
        base_q = (
            select(
                QuestionReviewItem.id,
                QuestionReviewItem.item_type,
                QuestionReviewItem.question_id,
                QuestionReviewItem.assessment_id,
                QuestionReviewItem.suggested_question_text,
                QuestionReviewItem.suggested_options,
                QuestionReviewItem.suggested_correct_answer,
                QuestionReviewItem.suggested_explanation,
                QuestionReviewItem.suggested_difficulty_level,
                QuestionReviewItem.reason,
                QuestionReviewItem.status,
                QuestionReviewItem.admin_note,
                QuestionReviewItem.created_at,
                QuestionBank.question_text,
                QuestionBank.question_type,
                QuestionBank.options,
                QuestionBank.correct_answer,
                QuestionBank.explanation,
                QuestionBank.difficulty_level,
                Subtopic.name.label("subtopic_name"),
                Topic.name.label("topic_name"),
                School.name.label("school_name"),
                User.first_name.label("submitted_by_first"),
                User.last_name.label("submitted_by_last"),
            )
            .join(QuestionBank, QuestionBank.id == QuestionReviewItem.question_id)
            .join(Subtopic, Subtopic.id == QuestionBank.subtopic_id)
            .join(CurriculumTopic, CurriculumTopic.id == Subtopic.curriculum_topic_id)
            .join(Topic, Topic.id == CurriculumTopic.topic_id)
            .join(School, School.id == QuestionReviewItem.school_id)
            .join(User, User.id == QuestionReviewItem.submitted_by)
            .where(QuestionReviewItem.status == "PENDING")
            .order_by(QuestionReviewItem.created_at.asc())
        )

        if item_type is not None:
            base_q = base_q.where(QuestionReviewItem.item_type == item_type)

        # Count total
        from sqlalchemy import func  # noqa: PLC0415

        count_q = select(func.count()).select_from(base_q.subquery())
        total = (await self.db.execute(count_q)).scalar() or 0

        # Paginate
        offset = (page - 1) * page_size
        rows = (await self.db.execute(base_q.offset(offset).limit(page_size))).all()

        items = [
            QuestionReviewItemResponse(
                id=row.id,
                item_type=row.item_type,
                question_id=row.question_id,
                question_text=row.question_text,
                question_type=row.question_type,
                options=row.options,
                correct_answer=row.correct_answer,
                explanation=row.explanation,
                difficulty_level=row.difficulty_level,
                subtopic_name=row.subtopic_name,
                topic_name=row.topic_name,
                school_name=row.school_name,
                submitted_by_name=(
                    f"{row.submitted_by_first or ''} {row.submitted_by_last or ''}".strip() or "Unknown"
                ),
                assessment_id=row.assessment_id,
                suggested_question_text=row.suggested_question_text,
                suggested_options=row.suggested_options,
                suggested_correct_answer=row.suggested_correct_answer,
                suggested_explanation=row.suggested_explanation,
                suggested_difficulty_level=row.suggested_difficulty_level,
                reason=row.reason,
                status=row.status,
                admin_note=row.admin_note,
                created_at=row.created_at,
            )
            for row in rows
        ]

        return QuestionReviewListResponse(items=items, total=total, page=page, page_size=page_size)

    async def approve_item(
        self,
        item_id: uuid.UUID,
        admin_id: uuid.UUID,
        body: ApproveReviewItemRequest,
    ) -> None:
        """Approve a pending review item.

        TEACHER_QUESTION: apply admin edits (if any) to question_bank,
            then clear school_id → question promoted to global bank.
        EDIT_SUGGESTION: apply admin edits if provided, else teacher's suggested
            fields, to question_bank.

        Args:
            item_id: The QuestionReviewItem UUID.
            admin_id: The KaihleAdmin user ID.
            body: Optional admin edits to apply before approving.

        Raises:
            ReviewItemNotFoundError: Item does not exist.
            ReviewItemAlreadyResolvedError: Item is not PENDING.
        """
        item = await self.db.get(QuestionReviewItem, item_id)
        if item is None:
            raise ReviewItemNotFoundError(f"Review item not found: {item_id}")
        if item.status != "PENDING":
            raise ReviewItemAlreadyResolvedError(f"Review item {item_id} is already {item.status}.")

        question = await self.db.get(QuestionBank, item.question_id)
        if question is None:
            raise ReviewItemNotFoundError(f"Question {item.question_id} not found in bank.")

        admin_edits = body.model_dump(exclude_unset=True)

        if item.item_type == "TEACHER_QUESTION":
            # Apply admin edits to the question_bank row (overrides teacher submission)
            for field, value in admin_edits.items():
                setattr(question, field, value)
            # Promote: clear school_id so it becomes globally available
            question.school_id = None
            question.review_status = "APPROVED"

            logger.info(
                "teacher_question_approved",
                item_id=str(item_id),
                question_id=str(item.question_id),
                admin_id=str(admin_id),
            )

        elif item.item_type == "EDIT_SUGGESTION":
            # Admin edits take precedence; fall back to teacher's suggestion
            field_map = {
                "question_text": "suggested_question_text",
                "options": "suggested_options",
                "correct_answer": "suggested_correct_answer",
                "explanation": "suggested_explanation",
                "difficulty_level": "suggested_difficulty_level",
            }
            for qb_field, suggestion_field in field_map.items():
                if qb_field in admin_edits:
                    setattr(question, qb_field, admin_edits[qb_field])
                elif getattr(item, suggestion_field) is not None:
                    setattr(question, qb_field, getattr(item, suggestion_field))

            logger.info(
                "edit_suggestion_approved",
                item_id=str(item_id),
                question_id=str(item.question_id),
                admin_id=str(admin_id),
            )

        # Mark review item resolved
        item.status = "APPROVED"
        item.resolved_by = admin_id
        item.resolved_at = datetime.now(UTC)

    async def reject_item(
        self,
        item_id: uuid.UUID,
        admin_id: uuid.UUID,
        body: RejectReviewItemRequest,
    ) -> None:
        """Reject a pending review item.

        TEACHER_QUESTION: set question_bank.is_active=False, review_status='REJECTED'.
        EDIT_SUGGESTION: no change to question_bank.
        Both: set item.status='REJECTED'.

        Args:
            item_id: The QuestionReviewItem UUID.
            admin_id: The KaihleAdmin user ID.
            body: Optional admin_note explaining the rejection.

        Raises:
            ReviewItemNotFoundError: Item does not exist.
            ReviewItemAlreadyResolvedError: Item is not PENDING.
        """
        item = await self.db.get(QuestionReviewItem, item_id)
        if item is None:
            raise ReviewItemNotFoundError(f"Review item not found: {item_id}")
        if item.status != "PENDING":
            raise ReviewItemAlreadyResolvedError(f"Review item {item_id} is already {item.status}.")

        if item.item_type == "TEACHER_QUESTION":
            question = await self.db.get(QuestionBank, item.question_id)
            if question is not None:
                question.is_active = False
                question.review_status = "REJECTED"

            logger.info(
                "teacher_question_rejected",
                item_id=str(item_id),
                question_id=str(item.question_id),
                admin_id=str(admin_id),
            )
        else:
            logger.info(
                "edit_suggestion_rejected",
                item_id=str(item_id),
                question_id=str(item.question_id),
                admin_id=str(admin_id),
            )

        item.status = "REJECTED"
        item.admin_note = body.admin_note
        item.resolved_by = admin_id
        item.resolved_at = datetime.now(UTC)
