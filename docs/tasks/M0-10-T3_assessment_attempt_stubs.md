# M0-10-T3 — Assessment + Attempt Stub Routes
**Milestone:** M0 · **Epic:** M0-10 · **Task:** T3
**Depends on:** M0-10-T1 (schemas must exist)
**Parallel with:** M0-10-T2, T4, T5, T6
**Real implementation:** M1-3-T2 (assessments), M1-4-T1 (attempts)
**Estimated effort:** 2–3 hours

---

## Context

This task creates two route files covering the full assessment lifecycle. There is an
important distinction in path structure that must be understood before writing a line
of code. The class-scoped list endpoint (`GET /classes/{id}/assessments`) gives a
teacher a list of all assessments for their class — it is part of the class domain.
The individual assessment endpoints (`GET /assessments/{id}`, `POST /assessments/{id}/publish`)
operate on a specific assessment by its own ID — they are part of the assessment domain.
Both patterns are correct REST; they serve different use cases and belong in different
route files.

The attempt routes cover the student-facing assessment-taking flow: retrieving an
attempt (which includes the questions), submitting individual answers, submitting the
whole attempt, and retrieving results.

---

## Files to Create / Modify

```
backend/app/api/v1/routes/assessments.py   ← CREATE
backend/app/api/v1/routes/attempts.py      ← CREATE
backend/app/main.py                        ← MODIFY: register both routers
```

---

## `routes/assessments.py`

```python
"""Assessment API routes.

Two logical sections:
1. Class-scoped list — GET /classes/{class_id}/assessments
   (teacher sees assessments for their class dashboard)
2. Assessment-scoped operations — /assessments/{assessment_id}/...
   (operate on a specific assessment by ID)

Stub implementations. Real implementation: M1-3-T2.
"""

from datetime import datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, require_role
from app.models.user import UserRole
from app.schemas.assessments import (
    AssessmentCreateRequest,
    AssessmentResponse,
)
from app.schemas.common import Page

router = APIRouter(tags=["assessments"])


# ── Class-scoped list ─────────────────────────────────────────────────────────

@router.get("/classes/{class_id}/assessments", response_model=Page[AssessmentResponse])
async def list_class_assessments(
    class_id: UUID,
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: CurrentUser = Depends(
        require_role(UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.KAIHLE_ADMIN)
    ),
    db: AsyncSession = Depends(get_db),
) -> Page[AssessmentResponse]:
    # STUB — M0-10-T3 | Real implementation: M1-3-T2
    # M1 adds: teacher-owns-class check, real DB query filtered by class_id + status.
    return Page(data=[], total=0, page=page, page_size=page_size)


@router.post(
    "/classes/{class_id}/assessments",
    response_model=AssessmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_assessment(
    class_id: UUID,
    body: AssessmentCreateRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER)),
    db: AsyncSession = Depends(get_db),
) -> AssessmentResponse:
    # STUB — M0-10-T3 | Real implementation: M1-3-T2
    # Returns 501 for write operations — no data model to create against yet.
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Assessment creation is available from M1.",
    )


# ── Assessment-scoped operations ──────────────────────────────────────────────

@router.get("/assessments/{assessment_id}", response_model=AssessmentResponse)
async def get_assessment(
    assessment_id: UUID,
    current_user: CurrentUser = Depends(
        require_role(
            UserRole.TEACHER,
            UserRole.SCHOOL_ADMIN,
            UserRole.KAIHLE_ADMIN,
            UserRole.STUDENT,
        )
    ),
    db: AsyncSession = Depends(get_db),
) -> AssessmentResponse:
    # STUB — M0-10-T3 | Real implementation: M1-3-T2
    # M1 note: teacher/admin response includes correct_answer via
    # AssessmentQuestionWithAnswer; student response uses AssessmentQuestion (no answer).
    # Role-based field filtering is implemented in the service layer, not here.
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="No assessments exist yet.",
    )


@router.post("/assessments/{assessment_id}/publish", response_model=AssessmentResponse)
async def publish_assessment(
    assessment_id: UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER)),
    db: AsyncSession = Depends(get_db),
) -> AssessmentResponse:
    # STUB — M0-10-T3 | Real implementation: M1-3-T2
    # M1 adds: DRAFT → ACTIVE transition, deadline validation, empty-question guard.
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="No assessments exist yet.",
    )


@router.post("/assessments/{assessment_id}/close", response_model=AssessmentResponse)
async def close_assessment(
    assessment_id: UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER)),
    db: AsyncSession = Depends(get_db),
) -> AssessmentResponse:
    # STUB — M0-10-T3 | Real implementation: M1-3-T2
    # M1 adds: ACTIVE → CLOSED transition, prevents new attempts after close.
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="No assessments exist yet.",
    )
```

---

## `routes/attempts.py`

```python
"""Student attempt API routes — the assessment-taking flow.

An attempt is the record of one student taking one assessment.
Lifecycle: NOT_STARTED → IN_PROGRESS (on first answer) → SUBMITTED.

The diagnostic endpoint GET /classes/{id}/diagnostic is here because it is
student-facing and returns an AttemptResponse — it logically belongs with
the attempt lifecycle, not with class management.

Stub implementations. Real implementation: M1-4-T1.
"""

from datetime import datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, require_role, require_full_access
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
        submitted_at=datetime.utcnow(),
        score=None,   # None until gap states are calculated
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
        submitted_at=datetime.utcnow(),
    )
```

---

## `main.py` Registration

```python
from app.api.v1.routes import assessments, attempts   # add to imports

app.include_router(assessments.router, prefix="/api/v1")
app.include_router(attempts.router, prefix="/api/v1")
```

---

## Acceptance Criteria

- `GET /api/v1/classes/{id}/assessments` with teacher JWT returns `200` with `{ data: [], total: 0, page: 1, page_size: 20 }`
- `GET /api/v1/classes/{id}/assessments` with student JWT returns `403`
- `POST /api/v1/classes/{id}/assessments` with teacher JWT returns `501`
- `GET /api/v1/assessments/{id}` with any authenticated JWT returns `404` (no data yet — not 500)
- `GET /api/v1/classes/{id}/diagnostic` with student JWT returns `200` with `status: "NOT_STARTED"`
- `GET /api/v1/classes/{id}/diagnostic` with teacher JWT returns `403`
- `POST /api/v1/attempts/{id}/responses` with student JWT returns `204`
- `POST /api/v1/attempts/{id}/submit` with student JWT returns `200` with `status: "SUBMITTED"`
- `GET /api/v1/attempts/{id}/results` with student JWT returns `200`
- All routes appear in `/docs` under the correct tags
- `mypy app/api/v1/routes/assessments.py app/api/v1/routes/attempts.py` passes

---

## Do NOT Touch

- Any existing route file
- `schemas/assessments.py` and `schemas/attempts.py` — read only
