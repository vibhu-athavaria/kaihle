# M0-10-T6 — Parent Portal + Analytics Stub Routes
**Milestone:** M0 · **Epic:** M0-10 · **Task:** T6
**Depends on:** M0-10-T1 (schemas must exist)
**Parallel with:** M0-10-T2, T3, T4, T5
**Real implementation:** M5-1-T2 (parent), M6-1-T1 (analytics)
**Estimated effort:** 2 hours

---

## User Story

As a frontend developer building the parent portal and school admin analytics
dashboard, I want endpoints that return correct schema shapes with empty data so
I can build the UI without waiting for M5 and M6.

---

## Files to Create / Modify

```
backend/app/api/v1/routes/parent.py     ← CREATE
backend/app/api/v1/routes/analytics.py  ← CREATE
backend/app/main.py                     ← MODIFY: register both routers
```

---

## `routes/parent.py`

```python
"""Parent portal API routes.

Parents can view their linked children's progress — weekly narrative reports
and a simplified gap map. CRITICAL design constraint: numeric mastery scores
are NEVER returned from any endpoint in this file. Parents see plain-language
status labels only ("Strong", "Developing", "Needs Work"). This constraint
is encoded in the ParentGapMap schema, which has no mastery_score field.

Stub implementations. Real implementation: M5-1-T2.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, require_role
from app.models.user import UserRole
from app.schemas.common import Page
from app.schemas.parent import ChildSummary, ParentGapMap, WeeklyReport

router = APIRouter(prefix="/parent", tags=["parent"])


@router.get("/children", response_model=list[ChildSummary])
async def list_children(
    current_user: CurrentUser = Depends(require_role(UserRole.PARENT)),
    db: AsyncSession = Depends(get_db),
) -> list[ChildSummary]:
    # STUB — M0-10-T6 | Real implementation: M5-1-T2
    # M5 adds: JOIN parent_student → users → student_profiles → classes → subjects.
    return []


@router.get(
    "/children/{student_id}/reports",
    response_model=Page[WeeklyReport],
)
async def list_child_reports(
    student_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=52),
    current_user: CurrentUser = Depends(require_role(UserRole.PARENT)),
    db: AsyncSession = Depends(get_db),
) -> Page[WeeklyReport]:
    # STUB — M0-10-T6 | Real implementation: M5-1-T2
    # M5 adds: verify parent_student link before returning any data (403 if not linked).
    return Page(data=[], total=0, page=page, page_size=page_size)


@router.get(
    "/children/{student_id}/reports/{report_id}",
    response_model=WeeklyReport,
)
async def get_child_report(
    student_id: UUID,
    report_id: UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.PARENT)),
    db: AsyncSession = Depends(get_db),
) -> WeeklyReport:
    # STUB — M0-10-T6 | Real implementation: M5-1-T2
    # M5 adds: parent_student link check, report-belongs-to-student check.
    raise HTTPException(status_code=404, detail="No reports generated yet.")


@router.get(
    "/children/{student_id}/gap-map",
    response_model=ParentGapMap,
)
async def get_child_gap_map(
    student_id: UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.PARENT)),
    db: AsyncSession = Depends(get_db),
) -> ParentGapMap:
    # STUB — M0-10-T6 | Real implementation: M5-1-T2
    # REMINDER: ParentGapMap schema has no mastery_score field — by design.
    # M5 converts raw gap_states to plain-language labels in the service layer.
    return ParentGapMap(student_name="", grade_name="", subjects=[])
```

---

## `routes/analytics.py`

```python
"""Analytics and platform management routes.

Three sections:
1. School analytics — GET /schools/{id}/analytics (SchoolAdmin sees own school)
2. Platform stats  — GET /platform/stats (KaihleAdmin only)
3. Platform actions — POST /platform/schools/{id}/impersonate (KaihleAdmin only)

Note on the /platform prefix: platform-level endpoints are not nested under
/schools because they operate across all schools, not within one. This mirrors
the separation between tenant-scoped and platform-scoped concerns.

Stub implementations. Real implementations: M6-1-T1 (analytics), M6 (impersonate).
"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, require_role
from app.models.user import UserRole
from app.schemas.analytics import PlatformStats, SchoolAnalytics

router = APIRouter(tags=["analytics"])


@router.get("/schools/{school_id}/analytics", response_model=SchoolAnalytics)
async def get_school_analytics(
    school_id: UUID,
    current_user: CurrentUser = Depends(
        require_role(UserRole.SCHOOL_ADMIN, UserRole.KAIHLE_ADMIN)
    ),
    db: AsyncSession = Depends(get_db),
) -> SchoolAnalytics:
    # STUB — M0-10-T6 | Real implementation: M6-1-T1
    # M6 adds: school_id-scoped aggregation queries across all feature tables.
    return SchoolAnalytics(
        school_id=school_id,
        school_name="",
        generated_at=datetime.utcnow(),
        total_students=0,
        active_students_last_7_days=0,
        onboarding_completion_rate=0.0,
        students_pending_onboarding=0,
        assessments_completed=0,
        study_plans_assigned=0,
        study_plans_completed=0,
        lesson_plans_generated=0,
        lesson_plans_used=0,
        classes=[],
    )


@router.get("/platform/stats", response_model=PlatformStats)
async def get_platform_stats(
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> PlatformStats:
    # STUB — M0-10-T6 | Real implementation: M6-1-T1
    # KaihleAdmin only — cross-school aggregation.
    return PlatformStats(
        total_schools=0,
        total_active_students=0,
        total_teachers=0,
        assessments_completed_last_7_days=0,
        generated_at=datetime.utcnow(),
    )


@router.post("/platform/schools/{school_id}/impersonate", response_model=dict)
async def impersonate_school(
    school_id: UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    # STUB — M0-10-T6 | Real implementation: M6 (no task file yet — added in M6 update)
    # Will issue a scoped JWT carrying the target school's school_id so KaihleAdmin
    # can browse a school's data as if they were that school's admin.
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="School impersonation is available from M6.",
    )
```

---

## `main.py` Registration

```python
from app.api.v1.routes import parent, analytics   # add to imports

app.include_router(parent.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
```

---

## Acceptance Criteria

For the parent routes, verify that: `GET /api/v1/parent/children` with parent JWT returns `200` with `[]`. `GET /api/v1/parent/children/{id}/reports` with parent JWT returns `200` with `{ data: [], total: 0, page: 1, page_size: 10 }`. `GET /api/v1/parent/children/{id}/gap-map` with parent JWT returns `200` and the response body contains no `mastery_score` field anywhere. `GET /api/v1/parent/children/{id}/reports` with teacher JWT returns `403`. All parent routes return `403` for any role that is not `PARENT`.

For the analytics routes, verify that: `GET /api/v1/schools/{id}/analytics` with school admin JWT returns `200` with all zero/empty values — not an error. `GET /api/v1/platform/stats` with KaihleAdmin JWT returns `200` with all zero values. `GET /api/v1/platform/stats` with teacher JWT returns `403`. `POST /api/v1/platform/schools/{id}/impersonate` with KaihleAdmin JWT returns `501`.

All routes appear in `/docs` under correct tags. `mypy app/api/v1/routes/parent.py app/api/v1/routes/analytics.py` passes.

---

## Do NOT Touch

- Any existing route file
- `schemas/parent.py` and `schemas/analytics.py` — read only
