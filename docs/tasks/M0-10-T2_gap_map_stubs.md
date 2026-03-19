# M0-10-T2 — Gap Map + Class Summary Stub Routes
**Milestone:** M0 · **Epic:** M0-10 · **Task:** T2
**Depends on:** M0-10-T1 (schemas must exist before this task starts)
**Parallel with:** M0-10-T3, T4, T5, T6
**Real implementation:** M2-1-T2 (gap_map_routes.md)
**Estimated effort:** 2 hours

---

## User Story

As a frontend developer building the teacher heatmap and student progress views,
I want gap map endpoints that return the correct schema shape with empty data so
I can build and test the UI without waiting for M2.

---

## Files to Create / Modify

```
backend/app/api/v1/routes/gap_map.py    ← CREATE
backend/app/main.py                     ← MODIFY: register new router
```

---

## Routes to Create

All four routes live in a single file. The stub comment pattern is mandatory on
every route — it tells the M2 developer exactly what to replace.

```python
"""Gap map API routes.

Stub implementations — returns correct schema shape with empty data.
Real implementation: M2-1-T2 (gap_map_routes.md).
"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, require_role, require_full_access
from app.models.user import UserRole
from app.schemas.gap_map import ClassGapMap, StudentGapMap, ClassSummary

router = APIRouter(tags=["gap-map"])


@router.get("/classes/{class_id}/gap-map", response_model=ClassGapMap)
async def get_class_gap_map(
    class_id: UUID,
    subject_id: UUID = Query(..., description="Filter gap map by subject"),
    current_user: CurrentUser = Depends(
        require_role(UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.KAIHLE_ADMIN)
    ),
    db: AsyncSession = Depends(get_db),
) -> ClassGapMap:
    # STUB — M0-10-T2 | Real implementation: M2-1-T2
    # Replace this entire function body. Do not change the signature or response_model.
    # M2 adds: school_id scoping, teacher-owns-class check, real gap_state aggregation.
    return ClassGapMap(
        class_id=class_id,
        subject_id=subject_id,
        generated_at=datetime.utcnow(),
        nodes=[],
    )


@router.get("/classes/{class_id}/summary", response_model=ClassSummary)
async def get_class_summary(
    class_id: UUID,
    current_user: CurrentUser = Depends(
        require_role(UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.KAIHLE_ADMIN)
    ),
    db: AsyncSession = Depends(get_db),
) -> ClassSummary:
    # STUB — M0-10-T2 | Real implementation: M2-1-T1
    # Lightweight summary for teacher dashboard class cards.
    # Replace with real aggregation from gap_states once M2 data exists.
    return ClassSummary(
        class_id=class_id,
        avg_mastery=None,
        student_count=0,
        assessed_student_count=0,
        last_updated_at=None,
    )


@router.get("/students/me/gap-map", response_model=StudentGapMap)
async def get_my_gap_map(
    subject_id: UUID = Query(...),
    current_user: CurrentUser = Depends(require_role(UserRole.STUDENT)),
    db: AsyncSession = Depends(get_db),
) -> StudentGapMap:
    # STUB — M0-10-T2 | Real implementation: M2-1-T2
    # /me shortcut — resolves to authenticated student's own gap map.
    # M2 adds: real gap_state query filtered to current_user.id.
    return StudentGapMap(
        student_id=current_user.id,
        subject_id=subject_id,
        generated_at=datetime.utcnow(),
        scores=[],
    )


@router.get("/students/{student_id}/gap-map", response_model=StudentGapMap)
async def get_student_gap_map(
    student_id: UUID,
    subject_id: UUID = Query(...),
    current_user: CurrentUser = Depends(require_full_access),
    db: AsyncSession = Depends(get_db),
) -> StudentGapMap:
    # STUB — M0-10-T2 | Real implementation: M2-1-T2
    # M2 adds: student can only see own, teacher must own the class,
    # parent must be linked via parent_student table, school-scoping.
    return StudentGapMap(
        student_id=student_id,
        subject_id=subject_id,
        generated_at=datetime.utcnow(),
        scores=[],
    )
```

---

## `main.py` Registration

Add the following import and include_router call to `main.py`, after the existing
router registrations:

```python
from app.api.v1.routes import gap_map   # add to imports
app.include_router(gap_map.router, prefix="/api/v1")
```

---

## Acceptance Criteria

- `GET /api/v1/classes/{id}/gap-map?subject_id={uuid}` with teacher JWT returns `200` with `{ class_id, subject_id, generated_at, nodes: [] }`
- `GET /api/v1/classes/{id}/gap-map` without `subject_id` returns `422` (required query param)
- `GET /api/v1/classes/{id}/gap-map` with student JWT returns `403`
- `GET /api/v1/classes/{id}/summary` with teacher JWT returns `200` with `{ avg_mastery: null, student_count: 0, ... }`
- `GET /api/v1/students/me/gap-map?subject_id={uuid}` with student JWT returns `200` with `student_id` matching the token's `sub`
- `GET /api/v1/students/{id}/gap-map?subject_id={uuid}` with teacher JWT returns `200`
- `GET /api/v1/students/{id}/gap-map?subject_id={uuid}` with parent JWT returns `403` (parent role not in require_full_access allowed roles — M5 adds parent gap map via `/parent/children/{id}/gap-map` instead)
- All four routes appear in `GET /docs` under the `gap-map` tag
- `mypy app/api/v1/routes/gap_map.py` passes with zero errors

---

## Do NOT Touch

- Any existing route file
- Any existing test file
- `schemas/gap_map.py` — read only, do not modify
