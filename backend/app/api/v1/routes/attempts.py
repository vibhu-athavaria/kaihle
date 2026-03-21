"""Student attempt API routes — the assessment-taking flow.

An attempt is the record of one student taking one assessment.
Lifecycle: NOT_STARTED → IN_PROGRESS (on first answer) → SUBMITTED.

The diagnostic endpoint GET /classes/{id}/diagnostic is here because it is
student-facing and returns an AttemptResponse — it logically belongs with
the attempt lifecycle, not with class management.

Stub implementations. Real implementation: M1-4-T1.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, require_full_access, require_role
from app.models.user import UserRole
from app.schemas.attempts import (
    AnswerSubmitRequest,
    AttemptResponse,
    AttemptResultResponse,
    AttemptSubmitRequest,
)

router = APIRouter(tags=["attempts"])


@router.get("/classes/{class_id}/diagnostic", response_model=AttemptResponse)
async def get_class_diagnostic(
    class_id: UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.STUDENT)),
    db: AsyncSession = Depends(get_db),
) -> AttemptResponse:
    # STUB — M0-10-T3 | Real implementation: M1-4-T1
    # Returns the student's existing Tier 1 attempt for this class, or a
    # NOT_STARTED stub if the attempt exists in DB but has no questions loaded yet.
    # M1 note: this endpoint must NOT be gated by require_diagnostic_complete —
    # students must be able to access it in order to complete the diagnostic.
    return AttemptResponse(
        id=uuid4(),
        assessment_id=uuid4(),
        student_id=current_user.id,
        status="NOT_STARTED",
        started_at=None,
        submitted_at=None,
        score=None,
        questions=[],
    )


@router.get("/attempts/{attempt_id}", response_model=AttemptResponse)
async def get_attempt(
    attempt_id: UUID,
    current_user: CurrentUser = Depends(require_full_access),
    db: AsyncSession = Depends(get_db),
) -> AttemptResponse:
    # STUB — M0-10-T3 | Real implementation: M1-4-T1
    # M1 adds: fetch real attempt from DB, load questions, enforce ownership.
    return AttemptResponse(
        id=attempt_id,
        assessment_id=uuid4(),
        student_id=current_user.id,
        status="NOT_STARTED",
        started_at=None,
        submitted_at=None,
        score=None,
        questions=[],
    )


@router.post("/attempts/{attempt_id}/responses", status_code=status.HTTP_204_NO_CONTENT)
async def submit_response(
    attempt_id: UUID,
    body: AnswerSubmitRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.STUDENT)),
    db: AsyncSession = Depends(get_db),
) -> None:
    # STUB — M0-10-T3 | Real implementation: M1-4-T1
    # 204 No Content is the correct final shape for this endpoint.
    # M1 adds: upsert StudentResponse row, transition attempt to IN_PROGRESS.
    return None


@router.post("/attempts/{attempt_id}/submit", response_model=AttemptResponse)
async def submit_attempt(
    attempt_id: UUID,
    body: AttemptSubmitRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.STUDENT)),
    db: AsyncSession = Depends(get_db),
) -> AttemptResponse:
    # STUB — M0-10-T3 | Real implementation: M1-4-T1
    # M1 adds: bulk answer upsert, MCQ scoring (deterministic — no LLM),
    # trigger calculate_gap_states Celery task,
    # call check_and_update_onboarding_complete() if is_system_generated.
    return AttemptResponse(
        id=attempt_id,
        assessment_id=uuid4(),
        student_id=current_user.id,
        status="SUBMITTED",
        started_at=None,
        submitted_at=datetime.now(UTC),
        score=None,  # None until gap states are calculated
        questions=[],
    )


@router.get("/attempts/{attempt_id}/results", response_model=AttemptResultResponse)
async def get_attempt_results(
    attempt_id: UUID,
    current_user: CurrentUser = Depends(require_full_access),
    db: AsyncSession = Depends(get_db),
) -> AttemptResultResponse:
    # STUB — M0-10-T3 | Real implementation: M1-4-T1
    # M1 adds: real score, per-question breakdown, gap state links.
    return AttemptResultResponse(
        attempt_id=attempt_id,
        score=0.0,
        total_questions=0,
        correct_count=0,
        time_taken_seconds=None,
        submitted_at=datetime.now(UTC),
    )
