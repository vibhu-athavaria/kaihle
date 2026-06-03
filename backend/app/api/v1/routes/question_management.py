"""KaihleAdmin question review API.

Unified endpoint set for reviewing teacher-submitted questions (TEACHER_QUESTION)
and teacher edit suggestions (EDIT_SUGGESTION) via the question_review_items table.
"""

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, require_role
from app.models.user import UserRole
from app.schemas.question_review import (
    ApproveReviewItemRequest,
    QuestionReviewListResponse,
    RejectReviewItemRequest,
)
from app.services.question_review_service import (
    QuestionReviewService,
    ReviewItemAlreadyResolvedError,
    ReviewItemNotFoundError,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/question-review-items", tags=["question-review"])


@router.get("", response_model=QuestionReviewListResponse)
async def list_question_review_items(
    item_type: str | None = Query(
        None,
        description="Filter by item type: 'TEACHER_QUESTION' or 'EDIT_SUGGESTION'",
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> QuestionReviewListResponse:
    """List all PENDING review items.

    KaihleAdmin only. Returns questions awaiting promotion and edit suggestions
    awaiting review. Use item_type filter to see only one type at a time.
    """
    service = QuestionReviewService(db)
    return await service.list_pending_items(item_type=item_type, page=page, page_size=page_size)


@router.post("/{item_id}/approve", status_code=status.HTTP_204_NO_CONTENT)
async def approve_review_item(
    item_id: UUID,
    body: ApproveReviewItemRequest | None = None,
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Approve a pending review item.

    For TEACHER_QUESTION: optional admin edits are applied to the question,
    then school_id is cleared so it becomes globally available.

    For EDIT_SUGGESTION: admin edits (if provided) take precedence over teacher's
    suggestion; the final values are applied to the question_bank row.
    """
    service = QuestionReviewService(db)
    resolved_body = body or ApproveReviewItemRequest()
    try:
        await service.approve_item(
            item_id=item_id,
            admin_id=current_user.id,
            body=resolved_body,
        )
        await db.commit()
    except ReviewItemNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ReviewItemAlreadyResolvedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.post("/{item_id}/reject", status_code=status.HTTP_204_NO_CONTENT)
async def reject_review_item(
    item_id: UUID,
    body: RejectReviewItemRequest | None = None,
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Reject a pending review item.

    For TEACHER_QUESTION: the submitted question is deactivated in question_bank.
    For EDIT_SUGGESTION: question_bank is unchanged.
    Optional admin_note stored on the review item.
    """
    service = QuestionReviewService(db)
    resolved_body = body or RejectReviewItemRequest()
    try:
        await service.reject_item(
            item_id=item_id,
            admin_id=current_user.id,
            body=resolved_body,
        )
        await db.commit()
    except ReviewItemNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ReviewItemAlreadyResolvedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
