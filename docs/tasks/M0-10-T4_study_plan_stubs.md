# M0-10-T4 — Study Plan Stub Routes
**Milestone:** M0 · **Epic:** M0-10 · **Task:** T4
**Depends on:** M0-10-T1 (schemas must exist)
**Parallel with:** M0-10-T2, T3, T5, T6
**Real implementation:** M3-2-T2 (study_plan_routes.md)
**Estimated effort:** 2 hours

---

## User Story

As a frontend developer building the student study plan view and teacher assignment
flow, I want study plan endpoints that return correct schema shapes with empty data
so I can build the UI without waiting for M3.

---

## Files to Create / Modify

```
backend/app/api/v1/routes/study_plans.py   ← CREATE
backend/app/main.py                        ← MODIFY: register router
```

---

## `routes/study_plans.py`

```python
"""Study plan API routes.

Three sections:
1. Class-scoped assignment — POST /classes/{id}/study-plans (teacher assigns)
2. Student-scoped list — GET /students/me/study-plans and GET /students/{id}/study-plans
3. Plan-scoped operations — /study-plans/{plan_id}/...

Stub implementations. Real implementation: M3-2-T2.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, require_role, require_full_access
from app.models.user import UserRole
from app.schemas.common import Page
from app.schemas.study_plans import (
    QuizSubmitRequest,
    QuizSubmitResponse,
    StudyPlanAssignRequest,
    StudyPlanAssignResponse,
    StudyPlanResponse,
)

router = APIRouter(tags=["study-plans"])


# ── Teacher: assign plans to students ────────────────────────────────────────

@router.post(
    "/classes/{class_id}/study-plans",
    response_model=StudyPlanAssignResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def assign_study_plans(
    class_id: UUID,
    body: StudyPlanAssignRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER)),
    db: AsyncSession = Depends(get_db),
) -> StudyPlanAssignResponse:
    # STUB — M0-10-T4 | Real implementation: M3-2-T2
    # 202 Accepted is correct — generation is async (Celery).
    # M3 adds: create StudyPlan rows, queue generation Celery tasks per student.
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Study plan assignment is available from M3.",
    )


# ── Student: view own plans ───────────────────────────────────────────────────

@router.get("/students/me/study-plans", response_model=Page[StudyPlanResponse])
async def list_my_study_plans(
    status_filter: str | None = Query(None, alias="status"),
    subject_id: UUID | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: CurrentUser = Depends(require_role(UserRole.STUDENT)),
    db: AsyncSession = Depends(get_db),
) -> Page[StudyPlanResponse]:
    # STUB — M0-10-T4 | Real implementation: M3-2-T2
    # /me shortcut — resolves to authenticated student's own plans.
    return Page(data=[], total=0, page=page, page_size=page_size)


@router.get("/students/{student_id}/study-plans", response_model=Page[StudyPlanResponse])
async def list_student_study_plans(
    student_id: UUID,
    status_filter: str | None = Query(None, alias="status"),
    subject_id: UUID | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: CurrentUser = Depends(require_full_access),
    db: AsyncSession = Depends(get_db),
) -> Page[StudyPlanResponse]:
    # STUB — M0-10-T4 | Real implementation: M3-2-T2
    # M3 adds: student sees own only, teacher sees class students only,
    # parent sees linked child only.
    return Page(data=[], total=0, page=page, page_size=page_size)


# ── Plan-scoped operations ────────────────────────────────────────────────────

@router.get("/study-plans/{plan_id}", response_model=StudyPlanResponse)
async def get_study_plan(
    plan_id: UUID,
    current_user: CurrentUser = Depends(require_full_access),
    db: AsyncSession = Depends(get_db),
) -> StudyPlanResponse:
    # STUB — M0-10-T4 | Real implementation: M3-2-T2
    # M3 adds: ownership check, resource list, quiz questions (no correct_answer).
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="No study plans assigned yet.",
    )


@router.patch(
    "/study-plans/{plan_id}/resources/{resource_id}/watched",
    response_model=dict,
)
async def mark_resource_watched(
    plan_id: UUID,
    resource_id: UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.STUDENT)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    # STUB — M0-10-T4 | Real implementation: M3-2-T2
    # Plausible stub response — the shape is simple enough to stub meaningfully.
    # M3 adds: verify student owns plan, upsert watched record in DB.
    return {"resource_id": str(resource_id), "is_watched": True}


@router.post("/study-plans/{plan_id}/quiz/submit", response_model=QuizSubmitResponse)
async def submit_study_plan_quiz(
    plan_id: UUID,
    body: QuizSubmitRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.STUDENT)),
    db: AsyncSession = Depends(get_db),
) -> QuizSubmitResponse:
    # STUB — M0-10-T4 | Real implementation: M3-2-T2
    # M3 adds: score MCQ responses, update gap_states, update plan status.
    return QuizSubmitResponse(
        score=0.0,
        correct_count=0,
        total_questions=0,
        plan_status="IN_PROGRESS",
    )
```

---

## `main.py` Registration

```python
from app.api.v1.routes import study_plans   # add to imports
app.include_router(study_plans.router, prefix="/api/v1")
```

---

## Acceptance Criteria

- `GET /api/v1/students/me/study-plans` with student JWT returns `200` with `{ data: [], total: 0, page: 1, page_size: 20 }`
- `GET /api/v1/students/{id}/study-plans` with teacher JWT returns `200` with empty page
- `GET /api/v1/study-plans/{id}` with any JWT returns `404` (not 500)
- `POST /api/v1/classes/{id}/study-plans` with teacher JWT returns `501`
- `PATCH /api/v1/study-plans/{id}/resources/{rid}/watched` with student JWT returns `200` with `{ resource_id, is_watched: true }`
- `POST /api/v1/study-plans/{id}/quiz/submit` with student JWT returns `200` with `{ score: 0.0, ... }`
- All routes appear in `/docs` under the `study-plans` tag
- `mypy app/api/v1/routes/study_plans.py` passes

---

## Do NOT Touch

- Any existing route file
- `schemas/study_plans.py` — read only
