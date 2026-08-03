"""KaihleAdmin endpoints for the curriculum-mapping review queue.

Thin handlers — all logic lives in LoReviewService.

KAIHLE_ADMIN only. These decisions are curriculum-level and apply to every school, so
there is no school scoping here and no per-tenant filtering to apply.
"""

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, require_role
from app.models.user import UserRole
from app.services.lo_review_service import LoReviewService

router = APIRouter(prefix="/lo-review", tags=["lo-review"])
logger = structlog.get_logger()


class CandidateItem(BaseModel):
    objective_id: str
    canonical_code: str
    learning_objective: str
    similarity: float | None = None


class ReviewItemResponse(BaseModel):
    id: str
    item_type: str
    status: str
    source_code: str
    source_name: str | None
    source_learning_objective: str
    subject_code: str | None
    grade_level: int | None
    question_count: int
    candidates: list[CandidateItem]
    llm_suggested_code: str | None
    llm_reason: str | None
    chosen_objective_id: str | None
    admin_note: str | None
    resolved_at: str | None


class ReviewListResponse(BaseModel):
    total: int
    items: list[ReviewItemResponse]


class ReviewCountsResponse(BaseModel):
    PENDING: int
    APPROVED: int
    REJECTED: int
    SPLIT: int


class ApproveRequest(BaseModel):
    # Any objective is permitted, not only a listed candidate — the candidates are the
    # machine's shortlist, and a curriculum specialist may know better.
    objective_id: uuid.UUID
    admin_note: str | None = Field(default=None, max_length=2000)


class RejectRequest(BaseModel):
    admin_note: str | None = Field(default=None, max_length=2000)


class ResolveResponse(BaseModel):
    item_id: str
    questions_bound: int
    status: str


class SplitResponse(BaseModel):
    item_id: str
    questions_bound: int
    objectives_used: int
    undecided: int
    status: str


class ObjectiveSearchItem(BaseModel):
    objective_id: str
    canonical_code: str
    name: str
    learning_objective: str


@router.get("/items", response_model=ReviewListResponse)
async def list_review_items(
    status_filter: str = Query("PENDING", pattern="^(PENDING|APPROVED|REJECTED|SPLIT)$", alias="status"),
    item_type: str | None = Query(None, pattern="^(QUESTION_REMAP|OBJECTIVE_DEDUP)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
) -> ReviewListResponse:
    """List review items, largest question_count first."""
    result = await LoReviewService(db).list_items(
        status_filter=status_filter, item_type=item_type, limit=limit, offset=offset
    )
    return ReviewListResponse(**result)


@router.get("/counts", response_model=ReviewCountsResponse)
async def get_review_counts(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
) -> ReviewCountsResponse:
    """Queue totals by status, for the nav badge."""
    return ReviewCountsResponse(**await LoReviewService(db).counts_by_status())


@router.get("/objectives/search", response_model=list[ObjectiveSearchItem])
async def search_objectives(
    q: str = Query(..., min_length=2, max_length=200),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
) -> list[ObjectiveSearchItem]:
    """Search objectives so a reviewer can bind outside the suggested candidates."""
    results = await LoReviewService(db).search_objectives(q, limit)
    return [ObjectiveSearchItem(**r) for r in results]


class ItemQuestion(BaseModel):
    question_id: str
    question_text: str
    question_type: str
    difficulty_level: float | None
    objective_id: str | None
    objective_code: str | None
    objective_text: str | None


class ItemQuestionsResponse(BaseModel):
    item_id: str
    source_name: str | None
    source_learning_objective: str
    total: int
    unbound: int
    questions: list[ItemQuestion]


class RebindRequest(BaseModel):
    # null unbinds the question, returning it to the coverage gap report.
    objective_id: uuid.UUID | None = None


@router.get("/items/{item_id}/questions", response_model=ItemQuestionsResponse)
async def list_item_questions(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
) -> ItemQuestionsResponse:
    """Every question in the group with the objective it is currently bound to."""
    return ItemQuestionsResponse(**await LoReviewService(db).list_item_questions(item_id))


@router.patch("/questions/{question_id}/objective")
async def rebind_question(
    question_id: uuid.UUID,
    body: RebindRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
) -> dict[str, str | None]:
    """Correct a single question's objective, or unbind it."""
    if current_user.id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing user context")
    return await LoReviewService(db).rebind_question(question_id, body.objective_id, current_user.id)


@router.post("/items/{item_id}/approve", response_model=ResolveResponse)
async def approve_review_item(
    item_id: uuid.UUID,
    body: ApproveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
) -> ResolveResponse:
    """Bind every question this item governs to the chosen objective."""
    if current_user.id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing user context")
    result = await LoReviewService(db).approve_item(
        item_id=item_id,
        objective_id=body.objective_id,
        reviewer_id=current_user.id,
        admin_note=body.admin_note,
    )
    return ResolveResponse(**result)


@router.post("/items/{item_id}/split", response_model=SplitResponse)
async def split_review_item(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
) -> SplitResponse:
    """Assign each question in the group individually.

    For groups whose old subtopic was broader than any one objective in the newer
    curriculum. Runs one model call per question, bounded-concurrent, so a large group
    takes tens of seconds rather than minutes.
    """
    if current_user.id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing user context")
    result = await LoReviewService(db).split_item(item_id=item_id, reviewer_id=current_user.id)
    return SplitResponse(**result)


@router.post("/items/{item_id}/reject", response_model=ResolveResponse)
async def reject_review_item(
    item_id: uuid.UUID,
    body: RejectRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
) -> ResolveResponse:
    """Close the item without binding. Its questions remain a reported coverage gap."""
    if current_user.id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing user context")
    result = await LoReviewService(db).reject_item(
        item_id=item_id,
        reviewer_id=current_user.id,
        admin_note=body.admin_note,
    )
    return ResolveResponse(**result)
