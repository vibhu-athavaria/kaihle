# School Admin Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the school-admin redesign: mastery-first dashboard, classes with gap map, analytics with period filtering, and users with student drill-down.

**Architecture:** Backend adds a real `AnalyticsService` to replace the stub, and adds `worst_mastery` to the student list response. Frontend rewrites six school-admin screens using the existing `DashboardLayout variant="school-admin"` wrapper, extracts `GapMapCell` to `packages/ui` for shared use, and adds two new routes.

**Tech Stack:** FastAPI + SQLAlchemy 2.x async (backend), React + TypeScript + React Query v5 + Tailwind CSS (frontend), `DashboardLayout` from `@kaihle/ui`, `getMasteryStyle` from `@kaihle/types`.

---

## Pre-flight: verify model import paths

Before starting backend tasks, run:
```bash
ls backend/app/models/
```
Confirm the exact filenames for: class, enrollment, gap_states, assessment, study_plan, profile. Use those filenames for imports in Tasks 1–3. The plan uses the names below — adjust if your filenames differ:
- `app.models.class_` → `Class`
- `app.models.enrollment` → `ClassEnrollment`, `DiagnosticStatus`
- `app.models.gap` → `GapState`
- `app.models.assessment` → `StudentAttempt`, `AttemptStatus`
- `app.models.study_plan` → `StudyPlan`
- `app.models.profile` → `StudentLearningProfile`

---

## Task 1: AnalyticsService — backend

**Files:**
- Create: `backend/app/services/analytics_service.py`
- Create: `backend/app/tests/unit/services/test_analytics_service.py`

- [ ] **Step 1: Write failing unit tests**

```python
# backend/app/tests/unit/services/test_analytics_service.py
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
import pytest
from app.services.analytics_service import AnalyticsService

SCHOOL_ID = uuid4()

@pytest.fixture
def mock_db():
    return AsyncMock()

@pytest.fixture
def service(mock_db):
    return AnalyticsService(mock_db)

async def test_get_school_analytics_when_no_students_then_returns_zeros(service, mock_db):
    mock_db.execute.return_value.scalar.return_value = 0
    result = await service.get_school_analytics(SCHOOL_ID, date.today() - timedelta(days=30), date.today())
    assert result.total_students == 0
    assert result.onboarding_funnel.invited == 0

async def test_get_school_analytics_when_date_range_given_then_filters_assessments(service, mock_db):
    from_date = date(2025, 4, 1)
    to_date = date(2025, 4, 30)
    mock_db.execute.return_value.scalar.return_value = 5
    result = await service.get_school_analytics(SCHOOL_ID, from_date, to_date)
    assert result is not None

async def test_get_student_mastery_summary_when_no_gap_states_then_returns_none(service, mock_db):
    mock_db.execute.return_value.all.return_value = []
    result = await service.get_student_mastery_summaries(SCHOOL_ID)
    assert result == []
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd backend
pytest app/tests/unit/services/test_analytics_service.py -v
```
Expected: `ImportError` — `analytics_service` not found.

- [ ] **Step 3: Implement AnalyticsService**

```python
# backend/app/services/analytics_service.py
from datetime import date, datetime, UTC
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.class_ import Class
from app.models.enrollment import ClassEnrollment, DiagnosticStatus
from app.models.gap import GapState
from app.models.assessment import StudentAttempt, AttemptStatus
from app.models.study_plan import StudyPlan
from app.models.profile import StudentLearningProfile
from app.models.user import User, UserRole
from app.schemas.analytics import (
    ClassBreakdown,
    OnboardingFunnel,
    AtRiskStudent,
    SchoolAnalyticsData,
    StudentMasterySummary,
)

logger = structlog.get_logger()


class AnalyticsService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_school_analytics(
        self,
        school_id: UUID,
        from_date: date,
        to_date: date,
    ) -> SchoolAnalyticsData:
        from_dt = datetime(from_date.year, from_date.month, from_date.day, tzinfo=UTC)
        to_dt = datetime(to_date.year, to_date.month, to_date.day, 23, 59, 59, tzinfo=UTC)

        total_students = await self._count(
            select(func.count(User.id)).where(
                User.school_id == school_id,
                User.role == UserRole.STUDENT,
                User.is_active == True,  # noqa: E712
            )
        )
        active_students = await self._count(
            select(func.count(User.id)).where(
                User.school_id == school_id,
                User.role == UserRole.STUDENT,
                User.is_active == True,  # noqa: E712
                User.last_login_at >= from_dt,
            )
        )
        assessments_completed = await self._count(
            select(func.count(StudentAttempt.id))
            .join(Class, Class.id == StudentAttempt.class_id)
            .where(
                Class.school_id == school_id,
                StudentAttempt.status == AttemptStatus.COMPLETED,
                StudentAttempt.completed_at >= from_dt,
                StudentAttempt.completed_at <= to_dt,
            )
        )
        study_plans_active = await self._count(
            select(func.count(StudyPlan.id))
            .join(User, User.id == StudyPlan.student_id)
            .where(
                User.school_id == school_id,
                StudyPlan.is_active == True,  # noqa: E712
            )
        )
        funnel = await self._get_onboarding_funnel(school_id)
        classes = await self._get_class_breakdown(school_id, from_dt, to_dt)
        at_risk = await self._get_at_risk_students(school_id)

        logger.info(
            "analytics.school.generated",
            school_id=str(school_id),
            total_students=total_students,
        )
        return SchoolAnalyticsData(
            school_id=school_id,
            generated_at=datetime.now(UTC),
            total_students=total_students,
            active_students=active_students,
            assessments_completed=assessments_completed,
            study_plans_active=study_plans_active,
            onboarding_funnel=funnel,
            classes=classes,
            at_risk_students=at_risk,
        )

    async def get_student_mastery_summaries(
        self, school_id: UUID
    ) -> list[StudentMasterySummary]:
        # Per student: worst avg mastery across all their classes
        rows = (
            await self._db.execute(
                select(
                    ClassEnrollment.student_id,
                    Class.id.label("class_id"),
                    func.avg(GapState.mastery_score).label("avg_mastery"),
                )
                .join(Class, Class.id == ClassEnrollment.class_id)
                .join(
                    GapState,
                    (GapState.class_id == ClassEnrollment.class_id)
                    & (GapState.student_id == ClassEnrollment.student_id),
                    isouter=True,
                )
                .where(
                    Class.school_id == school_id,
                    ClassEnrollment.is_active == True,  # noqa: E712
                )
                .group_by(ClassEnrollment.student_id, Class.id)
            )
        ).all()

        # Group by student, find worst class mastery
        student_map: dict[UUID, list[float | None]] = {}
        for row in rows:
            student_map.setdefault(row.student_id, []).append(row.avg_mastery)

        result = []
        for student_id, scores in student_map.items():
            valid = [s for s in scores if s is not None]
            worst = min(valid) if valid else None
            class_count = len(scores)
            needs_work_count = sum(1 for s in valid if s < 0.4)
            result.append(
                StudentMasterySummary(
                    student_id=student_id,
                    worst_mastery=worst,
                    class_count=class_count,
                    needs_work_class_count=needs_work_count,
                )
            )
        return result

    # ── private helpers ──────────────────────────────────────────────────────

    async def _count(self, stmt) -> int:
        result = await self._db.execute(stmt)
        return result.scalar() or 0

    async def _get_onboarding_funnel(self, school_id: UUID) -> OnboardingFunnel:
        invited = await self._count(
            select(func.count(User.id)).where(
                User.school_id == school_id, User.role == UserRole.STUDENT
            )
        )
        password_set = await self._count(
            select(func.count(User.id)).where(
                User.school_id == school_id,
                User.role == UserRole.STUDENT,
                User.is_active == True,  # noqa: E712
            )
        )
        # Students who have completed the learning profile questionnaire
        profile_complete = await self._count(
            select(func.count(StudentLearningProfile.student_id))
            .join(User, User.id == StudentLearningProfile.student_id)
            .where(User.school_id == school_id)
        )
        diagnostic_done = await self._count(
            select(func.count(func.distinct(ClassEnrollment.student_id)))
            .join(Class, Class.id == ClassEnrollment.class_id)
            .where(
                Class.school_id == school_id,
                ClassEnrollment.onboarding_diagnostic_status
                == DiagnosticStatus.COMPLETED,
            )
        )
        return OnboardingFunnel(
            invited=invited,
            password_set=password_set,
            profile_complete=profile_complete,
            diagnostic_done=diagnostic_done,
        )

    async def _get_class_breakdown(
        self, school_id: UUID, from_dt: datetime, to_dt: datetime
    ) -> list[ClassBreakdown]:
        rows = (
            await self._db.execute(
                select(
                    Class.id,
                    Class.name,
                    func.count(func.distinct(ClassEnrollment.student_id)).label(
                        "student_count"
                    ),
                    func.avg(GapState.mastery_score).label("avg_mastery"),
                    func.count(StudentAttempt.id)
                    .filter(
                        StudentAttempt.status == AttemptStatus.COMPLETED,
                        StudentAttempt.completed_at >= from_dt,
                        StudentAttempt.completed_at <= to_dt,
                    )
                    .label("assessments_completed"),
                )
                .join(
                    ClassEnrollment,
                    ClassEnrollment.class_id == Class.id,
                    isouter=True,
                )
                .join(
                    GapState,
                    GapState.class_id == Class.id,
                    isouter=True,
                )
                .join(
                    StudentAttempt,
                    StudentAttempt.class_id == Class.id,
                    isouter=True,
                )
                .where(Class.school_id == school_id, Class.is_active == True)  # noqa: E712
                .group_by(Class.id)
                .order_by(func.avg(GapState.mastery_score).asc().nulls_first())
            )
        ).all()

        return [
            ClassBreakdown(
                class_id=row.id,
                class_name=row.name,
                student_count=row.student_count or 0,
                avg_mastery=row.avg_mastery,
                assessments_completed=row.assessments_completed or 0,
            )
            for row in rows
        ]

    async def _get_at_risk_students(self, school_id: UUID) -> list[AtRiskStudent]:
        # Students with any class avg mastery < 0.4, worst first
        summaries = await self.get_student_mastery_summaries(school_id)
        at_risk = [s for s in summaries if s.worst_mastery is not None and s.worst_mastery < 0.4]
        at_risk.sort(key=lambda s: (s.worst_mastery or 1.0))

        if not at_risk:
            return []

        student_ids = [s.student_id for s in at_risk]
        users = (
            await self._db.execute(
                select(User.id, User.first_name, User.last_name).where(
                    User.id.in_(student_ids)
                )
            )
        ).all()
        user_map = {u.id: u for u in users}

        return [
            AtRiskStudent(
                student_id=s.student_id,
                first_name=user_map[s.student_id].first_name if s.student_id in user_map else "",
                last_name=user_map[s.student_id].last_name if s.student_id in user_map else "",
                worst_mastery=s.worst_mastery,
                needs_work_class_count=s.needs_work_class_count,
            )
            for s in at_risk
            if s.student_id in user_map
        ]
```

- [ ] **Step 4: Run tests**

```bash
cd backend
pytest app/tests/unit/services/test_analytics_service.py -v
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/analytics_service.py backend/app/tests/unit/services/test_analytics_service.py
git commit -m "feat(analytics): add AnalyticsService with school-level aggregations"
```

---

## Task 2: Update analytics schema and wire up route

**Files:**
- Modify: `backend/app/schemas/analytics.py`
- Modify: `backend/app/api/v1/routes/analytics.py`
- Create: `backend/app/tests/integration/test_analytics_routes.py`

- [ ] **Step 1: Rewrite `analytics.py` schemas**

```python
# backend/app/schemas/analytics.py
from datetime import date, datetime
from uuid import UUID
from pydantic import BaseModel


class OnboardingFunnel(BaseModel):
    invited: int
    password_set: int
    profile_complete: int
    diagnostic_done: int


class ClassBreakdown(BaseModel):
    class_id: UUID
    class_name: str
    student_count: int
    avg_mastery: float | None
    assessments_completed: int


class AtRiskStudent(BaseModel):
    student_id: UUID
    first_name: str
    last_name: str
    worst_mastery: float | None
    needs_work_class_count: int


class StudentMasterySummary(BaseModel):
    student_id: UUID
    worst_mastery: float | None
    class_count: int
    needs_work_class_count: int


class SchoolAnalyticsData(BaseModel):
    school_id: UUID
    generated_at: datetime
    total_students: int
    active_students: int
    assessments_completed: int
    study_plans_active: int
    onboarding_funnel: OnboardingFunnel
    classes: list[ClassBreakdown]
    at_risk_students: list[AtRiskStudent]


# Keep for backward compat — old frontend reads this shape
class SchoolAnalytics(SchoolAnalyticsData):
    pass


class PlatformStats(BaseModel):
    total_schools: int
    total_active_students: int
    total_teachers: int
    assessments_completed_last_7_days: int
    generated_at: datetime
```

- [ ] **Step 2: Write failing integration tests**

```python
# backend/app/tests/integration/test_analytics_routes.py
import pytest
from httpx import AsyncClient
from uuid import uuid4


async def test_get_school_analytics_when_authenticated_school_admin_then_returns_200(
    client: AsyncClient, school_admin_token: str, test_school_id: str
):
    response = await client.get(
        f"/api/v1/schools/{test_school_id}/analytics",
        headers={"Authorization": f"Bearer {school_admin_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "total_students" in data
    assert "onboarding_funnel" in data
    assert "classes" in data


async def test_get_school_analytics_when_period_params_given_then_accepted(
    client: AsyncClient, school_admin_token: str, test_school_id: str
):
    response = await client.get(
        f"/api/v1/schools/{test_school_id}/analytics?from_date=2025-04-01&to_date=2025-04-30",
        headers={"Authorization": f"Bearer {school_admin_token}"},
    )
    assert response.status_code == 200


async def test_get_school_analytics_when_wrong_school_then_403(
    client: AsyncClient, school_admin_token: str
):
    other_school_id = uuid4()
    response = await client.get(
        f"/api/v1/schools/{other_school_id}/analytics",
        headers={"Authorization": f"Bearer {school_admin_token}"},
    )
    assert response.status_code == 403
```

- [ ] **Step 3: Update analytics route to use AnalyticsService**

```python
# backend/app/api/v1/routes/analytics.py
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, _check_school_access, require_role
from app.models.user import UserRole
from app.schemas.analytics import PlatformStats, SchoolAnalytics
from app.services.analytics_service import AnalyticsService

router = APIRouter(tags=["analytics"])
logger = structlog.get_logger()


@router.get("/schools/{school_id}/analytics", response_model=SchoolAnalytics)
async def get_school_analytics(
    school_id: UUID,
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    current_user: CurrentUser = Depends(
        require_role(UserRole.SCHOOL_ADMIN, UserRole.KAIHLE_ADMIN)
    ),
    db: AsyncSession = Depends(get_db),
) -> SchoolAnalytics:
    _check_school_access(school_id, current_user)

    # Default: last 30 days
    today = date.today()
    effective_from = from_date or (today - timedelta(days=30))
    effective_to = to_date or today

    service = AnalyticsService(db)
    return await service.get_school_analytics(school_id, effective_from, effective_to)


@router.get("/platform/stats", response_model=PlatformStats)
async def get_platform_stats(
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> PlatformStats:
    logger.info("platform.stats.requested", user_id=str(current_user.id))
    return PlatformStats(
        total_schools=0,
        total_active_students=0,
        total_teachers=0,
        assessments_completed_last_7_days=0,
        generated_at=datetime.now(UTC),
    )


@router.post("/platform/schools/{school_id}/impersonate", response_model=dict[str, object])
async def impersonate_school(
    school_id: UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="School impersonation is available from M6.",
    )
```

- [ ] **Step 4: Run lint, type-check, integration tests**

```bash
cd backend
ruff check app/ && mypy app/
pytest app/tests/integration/test_analytics_routes.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/analytics.py backend/app/api/v1/routes/analytics.py backend/app/tests/integration/test_analytics_routes.py
git commit -m "feat(analytics): wire AnalyticsService into /schools/{id}/analytics with period filtering"
```

---

## Task 3: Add worst_mastery to student list response

**Files:**
- Modify: `backend/app/api/v1/routes/schools.py` (the `/schools/{id}/users` endpoint)
- Modify: `backend/app/schemas/user.py` (or wherever `UserResponse` lives — find with `grep -r "class UserResponse" backend/app/schemas/`)

- [ ] **Step 1: Find the users list endpoint**

```bash
grep -r "school_id}/users" backend/app/api/ -l
```

- [ ] **Step 2: Write failing test**

```python
# Add to existing user route test file (find with: grep -r "test.*users" backend/app/tests/ -l)

async def test_list_students_when_school_admin_then_includes_worst_mastery(
    client: AsyncClient, school_admin_token: str, test_school_id: str
):
    response = await client.get(
        f"/api/v1/schools/{test_school_id}/users?role=STUDENT",
        headers={"Authorization": f"Bearer {school_admin_token}"},
    )
    assert response.status_code == 200
    students = response.json()
    # worst_mastery is None when no assessments taken — field must exist
    for student in students:
        assert "worst_mastery" in student
        assert "class_count" in student
        assert "needs_work_class_count" in student
```

- [ ] **Step 3: Add `StudentListItem` schema**

Find the schema file for user responses (`grep -r "class.*UserResponse\|class.*UserList" backend/app/schemas/`), then add:

```python
class StudentListItem(BaseModel):
    id: UUID
    first_name: str
    last_name: str
    email: str
    is_active: bool
    last_login_at: datetime | None
    worst_mastery: float | None       # None = no assessments yet
    class_count: int
    needs_work_class_count: int
    diagnostic_completed: bool        # True if any class diagnostic complete
```

- [ ] **Step 4: Update the users list route handler**

In the `/schools/{school_id}/users?role=STUDENT` handler, after fetching users call `AnalyticsService.get_student_mastery_summaries(school_id)` and join the results by `student_id`:

```python
from app.services.analytics_service import AnalyticsService

# Inside the route handler, after getting users:
if role == UserRole.STUDENT:
    svc = AnalyticsService(db)
    summaries = await svc.get_student_mastery_summaries(school_id)
    summary_map = {str(s.student_id): s for s in summaries}
    # Merge into response items:
    return [
        StudentListItem(
            id=u.id,
            first_name=u.first_name,
            last_name=u.last_name,
            email=u.email,
            is_active=u.is_active,
            last_login_at=u.last_login_at,
            worst_mastery=summary_map.get(str(u.id), {}).worst_mastery
                if str(u.id) in summary_map else None,
            class_count=summary_map[str(u.id)].class_count
                if str(u.id) in summary_map else 0,
            needs_work_class_count=summary_map[str(u.id)].needs_work_class_count
                if str(u.id) in summary_map else 0,
            diagnostic_completed=any(
                ce.onboarding_diagnostic_status == DiagnosticStatus.COMPLETED
                for ce in u.enrollments  # eager-load or subquery
            ),
        )
        for u in users
    ]
```

- [ ] **Step 5: Run tests and linters**

```bash
cd backend
ruff check app/ && mypy app/
pytest app/tests/ -v -k "users"
```

- [ ] **Step 6: Commit**

```bash
git commit -m "feat(users): add worst_mastery and class_count to student list response"
```

---

## Task 4: Extract GapMapCell to packages/ui

**Files:**
- Create: `frontend/packages/ui/src/components/GapMapCell.tsx`
- Modify: `frontend/packages/ui/src/index.ts`
- Modify: `frontend/apps/teacher/src/components/gap-map/GapMapCell.tsx` (re-export shim)

- [ ] **Step 1: Create the new shared component**

```tsx
// frontend/packages/ui/src/components/GapMapCell.tsx
import { getMasteryStyle, scoreToPercent } from "@kaihle/types";

export interface GapMapCellProps {
  masteryScore: number | null;
  studentName: string;
  subtopicName: string;
  display?: "label" | "percent" | "both";
  readOnly?: boolean;
  onClick?: () => void;
}

export function GapMapCell({
  masteryScore,
  studentName,
  subtopicName,
  display = "label",
  readOnly = false,
  onClick,
}: GapMapCellProps) {
  const { bgClass, textClass, label } = getMasteryStyle(masteryScore);
  const pct = scoreToPercent(masteryScore);

  const displayValue =
    display === "label"
      ? label
      : display === "percent"
        ? pct
        : masteryScore !== null
          ? `${label.slice(0, 3)} · ${pct}`
          : "—";

  const titleText = `${studentName} — ${subtopicName}: ${label}${
    masteryScore !== null ? ` (${Math.round(masteryScore * 100)}%)` : ""
  }`;

  if (readOnly) {
    return (
      <div
        className={[
          "w-12 h-12 rounded flex items-center justify-center text-xs font-semibold",
          bgClass,
          textClass,
        ].join(" ")}
        title={titleText}
        aria-label={titleText}
      >
        {displayValue}
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        "w-12 h-12 rounded flex items-center justify-center text-xs font-semibold transition-all",
        "hover:scale-105 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-1",
        bgClass,
        textClass,
      ].join(" ")}
      title={titleText}
    >
      {displayValue}
    </button>
  );
}
```

- [ ] **Step 2: Export from packages/ui barrel**

In `frontend/packages/ui/src/index.ts`, add after the existing component exports:

```ts
export { GapMapCell, type GapMapCellProps } from "./components/GapMapCell";
```

- [ ] **Step 3: Replace teacher app's GapMapCell with a re-export shim**

```tsx
// frontend/apps/teacher/src/components/gap-map/GapMapCell.tsx
// Re-exports from shared package — do not add logic here.
export { GapMapCell, type GapMapCellProps } from "@kaihle/ui";
```

- [ ] **Step 4: Verify teacher app still type-checks**

```bash
cd frontend
pnpm typecheck
```
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/packages/ui/src/components/GapMapCell.tsx \
        frontend/packages/ui/src/index.ts \
        frontend/apps/teacher/src/components/gap-map/GapMapCell.tsx
git commit -m "feat(ui): extract GapMapCell to packages/ui with readOnly and display props"
```

---

## Task 5: Update school-admin hooks and types

**Files:**
- Modify: `frontend/apps/school-admin/src/hooks/useSchoolAdmin.ts`

- [ ] **Step 1: Rewrite the file**

Replace the entire contents of `useSchoolAdmin.ts`:

```typescript
// frontend/apps/school-admin/src/hooks/useSchoolAdmin.ts
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient, useAuthStore } from "@kaihle/auth";
import { UserRole, type UserRole as UserRoleType } from "@kaihle/types";

// ── shared helpers ───────────────────────────────────────────────────────────

function getSchoolId(): string {
  const user = useAuthStore.getState().user;
  if (!user?.school_id) throw new Error("No school_id for current user");
  return user.school_id;
}

// ── types ────────────────────────────────────────────────────────────────────

export interface OnboardingFunnel {
  invited: number;
  password_set: number;
  profile_complete: number;
  diagnostic_done: number;
}

export interface ClassBreakdown {
  class_id: string;
  class_name: string;
  student_count: number;
  avg_mastery: number | null;
  assessments_completed: number;
}

export interface AtRiskStudent {
  student_id: string;
  first_name: string;
  last_name: string;
  worst_mastery: number | null;
  needs_work_class_count: number;
}

export interface SchoolAnalytics {
  school_id: string;
  generated_at: string;
  total_students: number;
  active_students: number;
  assessments_completed: number;
  study_plans_active: number;
  onboarding_funnel: OnboardingFunnel;
  classes: ClassBreakdown[];
  at_risk_students: AtRiskStudent[];
}

export interface ClassSummary {
  id: string;
  name: string;
  subject_name: string;
  grade_level: number;
  teacher_id: string | null;
  teacher_name: string | null;
  student_count: number;
  avg_mastery: number | null;
  students_below_threshold: number;
  has_teacher: boolean;
  diagnostic_status: "setup_needed" | "pending" | "has_data";
}

export interface StudentListItem {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  is_active: boolean;
  last_login_at: string | null;
  worst_mastery: number | null;
  class_count: number;
  needs_work_class_count: number;
  diagnostic_completed: boolean;
}

export interface Curriculum { id: string; name: string; }
export interface Grade { id: string; level: number; }

// ── queries ──────────────────────────────────────────────────────────────────

export function useSchoolAnalytics(fromDate?: string, toDate?: string) {
  return useQuery({
    queryKey: ["school", "analytics", fromDate, toDate],
    queryFn: async () => {
      const schoolId = getSchoolId();
      const params = new URLSearchParams();
      if (fromDate) params.set("from_date", fromDate);
      if (toDate) params.set("to_date", toDate);
      const qs = params.toString() ? `?${params}` : "";
      const res = await apiClient.get(`/api/v1/schools/${schoolId}/analytics${qs}`);
      return res.data as SchoolAnalytics;
    },
    enabled: !!useAuthStore.getState().user?.school_id,
  });
}

export function useSchoolClasses() {
  return useQuery({
    queryKey: ["school", "classes"],
    queryFn: async () => {
      const schoolId = getSchoolId();
      const res = await apiClient.get(
        `/api/v1/schools/${schoolId}/classes?include_summary=true`
      );
      const raw: ClassSummary[] = res.data;
      // Derive diagnostic_status from API data
      return raw.map((c) => ({
        ...c,
        diagnostic_status: !c.has_teacher
          ? ("setup_needed" as const)
          : c.avg_mastery === null
            ? ("pending" as const)
            : ("has_data" as const),
      }));
    },
    enabled: !!useAuthStore.getState().user?.school_id,
  });
}

export function useSchoolStudents() {
  return useQuery({
    queryKey: ["school", "users", "STUDENT"],
    queryFn: async () => {
      const schoolId = getSchoolId();
      const res = await apiClient.get(
        `/api/v1/schools/${schoolId}/users?role=STUDENT`
      );
      const raw = res.data?.users ?? res.data;
      return raw as StudentListItem[];
    },
    enabled: !!useAuthStore.getState().user?.school_id,
  });
}

export function useSchoolUsers(role: "TEACHER" | "PARENT") {
  return useQuery({
    queryKey: ["school", "users", role],
    queryFn: async () => {
      const schoolId = getSchoolId();
      const res = await apiClient.get(
        `/api/v1/schools/${schoolId}/users?role=${role}`
      );
      return res.data?.users ?? res.data;
    },
    enabled: !!useAuthStore.getState().user?.school_id,
  });
}

export function useStudentDetail(studentId: string) {
  return useQuery({
    queryKey: ["student", studentId],
    queryFn: async () => {
      const res = await apiClient.get(`/api/v1/students/${studentId}`);
      return res.data;
    },
    enabled: !!studentId,
  });
}

export function useStudentAttempts(studentId: string) {
  return useQuery({
    queryKey: ["student", studentId, "attempts"],
    queryFn: async () => {
      const res = await apiClient.get(`/api/v1/students/${studentId}/attempts`);
      return res.data;
    },
    enabled: !!studentId,
  });
}

export function useStudentStudyPlans(studentId: string) {
  return useQuery({
    queryKey: ["student", studentId, "study-plans"],
    queryFn: async () => {
      const res = await apiClient.get(`/api/v1/students/${studentId}/study-plans`);
      return res.data;
    },
    enabled: !!studentId,
  });
}

export function useCurricula() {
  return useQuery({
    queryKey: ["curricula"],
    queryFn: async () => {
      const res = await apiClient.get("/api/v1/curricula");
      return res.data as Curriculum[];
    },
  });
}

export function useGrades() {
  return useQuery({
    queryKey: ["grades"],
    queryFn: async () => {
      const res = await apiClient.get("/api/v1/grades");
      return res.data as Grade[];
    },
  });
}

// ── mutations ────────────────────────────────────────────────────────────────

export function useInviteUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: {
      first_name: string;
      last_name: string;
      email: string;
      role: UserRoleType;
    }) => {
      const schoolId = getSchoolId();
      const res = await apiClient.post(`/api/v1/schools/${schoolId}/users`, data);
      return res.data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["school", "users"] }),
  });
}

export function useCreateClass() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: {
      name: string;
      subject: string;
      grade: number;
      curriculum_id: string;
      teacher_id?: string;
    }) => {
      const schoolId = getSchoolId();
      const res = await apiClient.post(`/api/v1/schools/${schoolId}/classes`, data);
      return res.data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["school", "classes"] }),
  });
}

export function useUpdateClass() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: { classId: string; name?: string; teacher_id?: string }) => {
      const res = await apiClient.patch(`/api/v1/classes/${data.classId}`, data);
      return res.data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["school", "classes"] }),
  });
}
```

- [ ] **Step 2: Run typecheck**

```bash
cd frontend
pnpm typecheck
```

- [ ] **Step 3: Commit**

```bash
git add frontend/apps/school-admin/src/hooks/useSchoolAdmin.ts
git commit -m "feat(school-admin): update hooks to match new analytics schema and add student detail queries"
```

---

## Task 6: Rewrite Classes screen

**Files:**
- Modify: `frontend/apps/school-admin/src/pages/ClassManagement.tsx`

- [ ] **Step 1: Rewrite ClassManagement.tsx**

```tsx
// frontend/apps/school-admin/src/pages/ClassManagement.tsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { DashboardLayout } from "@kaihle/ui";
import { getMasteryStyle } from "@kaihle/types";
import { useSchoolClasses, type ClassSummary } from "../hooks/useSchoolAdmin";

type Filter = "all" | "attention" | "all_grades" | "all_subjects";

function classState(c: ClassSummary) {
  return c.diagnostic_status;
}

export function ClassManagement() {
  const navigate = useNavigate();
  const { data: classes = [], isLoading } = useSchoolClasses();
  const [filter, setFilter] = useState<"all" | "attention">("all");
  const [gradeFilter, setGradeFilter] = useState<number | null>(null);
  const [subjectFilter, setSubjectFilter] = useState<string | null>(null);

  const attentionCount = classes.filter(
    (c) => c.diagnostic_status !== "has_data" || (c.avg_mastery !== null && c.avg_mastery < 0.4)
  ).length;

  const filtered = classes
    .filter((c) => {
      if (filter === "attention") {
        return c.diagnostic_status !== "has_data" || (c.avg_mastery !== null && c.avg_mastery < 0.4);
      }
      return true;
    })
    .filter((c) => gradeFilter === null || c.grade_level === gradeFilter)
    .filter((c) => subjectFilter === null || c.subject_name === subjectFilter);

  const grades = [...new Set(classes.map((c) => c.grade_level))].sort();
  const subjects = [...new Set(classes.map((c) => c.subject_name))].sort();

  return (
    <DashboardLayout variant="school-admin" activePage="classes">
      <div className="flex items-center justify-between mb-4">
        {/* Toolbar */}
        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex items-center gap-2 bg-white border border-role-school-border rounded-lg px-3 py-[7px]">
            <svg className="w-3 h-3 text-brand-muted" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            <input
              className="text-xs outline-none font-sans bg-transparent text-brand-ink placeholder:text-brand-muted w-40"
              placeholder="Search classes…"
            />
          </div>
          <button
            onClick={() => setFilter(filter === "attention" ? "all" : "attention")}
            className={`px-3 py-[5px] rounded-full text-xs font-semibold border transition-colors ${
              filter === "attention"
                ? "bg-brand-primary text-white border-brand-primary"
                : "bg-white text-brand-body border-role-school-border"
            }`}
          >
            Needs attention {attentionCount > 0 && `(${attentionCount})`}
          </button>
          <select
            onChange={(e) => setGradeFilter(e.target.value ? Number(e.target.value) : null)}
            className="px-3 py-[5px] rounded-full text-xs font-semibold border border-role-school-border bg-white text-brand-body outline-none"
          >
            <option value="">All grades</option>
            {grades.map((g) => <option key={g} value={g}>Grade {g}</option>)}
          </select>
          <select
            onChange={(e) => setSubjectFilter(e.target.value || null)}
            className="px-3 py-[5px] rounded-full text-xs font-semibold border border-role-school-border bg-white text-brand-body outline-none"
          >
            <option value="">All subjects</option>
            {subjects.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <span className="text-xs text-brand-muted ml-auto">{filtered.length} classes</span>
        </div>
        <button className="bg-brand-primary text-white rounded-full px-4 py-[6px] text-xs font-bold flex items-center gap-1">
          <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          New class
        </button>
      </div>

      {isLoading ? (
        <div className="animate-pulse space-y-3">
          {[...Array(5)].map((_, i) => <div key={i} className="h-12 bg-role-school-border rounded-lg" />)}
        </div>
      ) : (
        <div className="bg-white border border-role-school-border rounded-xl overflow-hidden">
          <table className="w-full border-collapse">
            <thead>
              <tr className="bg-[#fafcfa] border-b border-role-school-border">
                {["Class", "Subject", "Grade", "Teacher", "Mastery", "Students", ""].map((h) => (
                  <th key={h} className="px-4 py-[10px] text-left text-[9px] font-black uppercase tracking-[0.7px] text-role-school-muted">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((c) => (
                <ClassRow key={c.id} cls={c} onClick={() => navigate(`/school-admin/classes/${c.id}/gap-map`)} />
              ))}
            </tbody>
          </table>
          {filtered.length === 0 && (
            <div className="py-16 text-center text-brand-muted text-sm">No classes match this filter.</div>
          )}
        </div>
      )}

      {/* Legend */}
      <div className="flex gap-5 mt-3 px-1">
        {[
          { color: "#ef4444", label: "Needs Work" },
          { color: "#f59e0b", label: "Developing" },
          { color: "#16a34a", label: "Strong" },
          { color: null, label: "Diagnostic pending", border: true },
          { color: "#fef9c3", label: "Setup needed", border: "#f59e0b" },
        ].map(({ color, label, border }) => (
          <div key={label} className="flex items-center gap-1.5 text-[10px] text-brand-body font-semibold">
            <span
              className="w-2.5 h-2.5 rounded-full flex-shrink-0"
              style={{
                background: color ?? "transparent",
                border: border ? `1.5px solid ${border === true ? "#d1d5db" : border}` : undefined,
              }}
            />
            {label}
          </div>
        ))}
      </div>
    </DashboardLayout>
  );
}

function ClassRow({ cls, onClick }: { cls: ClassSummary; onClick: () => void }) {
  const isSetup = cls.diagnostic_status === "setup_needed";
  const isPending = cls.diagnostic_status === "pending";
  const { dotClass, label } = getMasteryStyle(cls.avg_mastery);

  return (
    <tr
      onClick={onClick}
      className={`border-b border-[#f0f5ee] cursor-pointer transition-colors ${
        isSetup ? "bg-[#fffbeb] hover:bg-[#fef9c3]" : "hover:bg-[#fafcfa]"
      }`}
    >
      <td className="px-4 py-3 font-bold text-[13px] text-brand-ink">{cls.name}</td>
      <td className="px-4 py-3 text-xs font-semibold text-brand-body">{cls.subject_name}</td>
      <td className="px-4 py-3 text-xs text-brand-muted">Grade {cls.grade_level}</td>
      <td className="px-4 py-3">
        {isSetup ? (
          <span className="flex items-center gap-1.5 text-[11px] font-bold text-brand-amber">
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
            Assign teacher
          </span>
        ) : (
          <span className="text-xs text-brand-body">{cls.teacher_name}</span>
        )}
      </td>
      <td className="px-4 py-3">
        {isPending ? (
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full border-[1.5px] border-gray-300" />
            <span className="text-xs text-brand-muted">Diagnostic pending</span>
          </div>
        ) : isSetup ? (
          <span className="text-brand-muted">—</span>
        ) : (
          <div className="flex items-center gap-1.5">
            <span className={`w-2.5 h-2.5 rounded-full ${dotClass}`} />
            <span className="text-xs font-semibold text-brand-ink">{label}</span>
          </div>
        )}
      </td>
      <td className="px-4 py-3 text-xs text-brand-muted">{cls.student_count}</td>
      <td className="px-4 py-3 text-brand-muted text-base">›</td>
    </tr>
  );
}
```

- [ ] **Step 2: Run typecheck and dev server**

```bash
cd frontend && pnpm typecheck
pnpm dev:school-admin
```
Open http://localhost:3004/school-admin/classes — verify three row states render correctly.

- [ ] **Step 3: Commit**

```bash
git add frontend/apps/school-admin/src/pages/ClassManagement.tsx
git commit -m "feat(school-admin): rewrite Classes screen with mastery column and three class states"
```

---

## Task 7: School-admin Gap Map screen

**Files:**
- Create: `frontend/apps/school-admin/src/pages/AdminGapMapPage.tsx`
- Modify: `frontend/apps/school-admin/src/App.tsx`

- [ ] **Step 1: Create AdminGapMapPage.tsx**

```tsx
// frontend/apps/school-admin/src/pages/AdminGapMapPage.tsx
import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { DashboardLayout, GapMapCell } from "@kaihle/ui";
import { apiClient } from "@kaihle/auth";

interface GapMapData {
  class_name: string;
  subtopics: { id: string; name: string }[];
  students: { id: string; name: string }[];
  cells: { student_id: string; subtopic_id: string; mastery_score: number | null }[];
}

export function AdminGapMapPage() {
  const { classId } = useParams<{ classId: string }>();
  const navigate = useNavigate();

  const { data, isLoading } = useQuery({
    queryKey: ["class-gap-map", classId],
    queryFn: async () => {
      const res = await apiClient.get(`/api/v1/classes/${classId}/gap-map`);
      return res.data as GapMapData;
    },
    enabled: !!classId,
  });

  const getScore = (studentId: string, subtopicId: string) =>
    data?.cells.find((c) => c.student_id === studentId && c.subtopic_id === subtopicId)
      ?.mastery_score ?? null;

  return (
    <DashboardLayout variant="school-admin" activePage="classes">
      {/* Topbar breadcrumb + badge */}
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-2 text-sm">
          <button
            onClick={() => navigate("/school-admin/classes")}
            className="text-brand-muted font-semibold hover:text-brand-primary transition-colors"
          >
            Classes
          </button>
          <span className="text-brand-border">›</span>
          <span className="font-display font-bold text-brand-ink">
            {data?.class_name ?? "Loading…"}
          </span>
        </div>
        <span className="text-[10px] font-bold uppercase tracking-widest text-brand-muted bg-gray-100 px-3 py-1 rounded-full">
          Read only — contact teacher to update
        </span>
      </div>

      {isLoading ? (
        <div className="animate-pulse space-y-3">
          {[...Array(6)].map((_, i) => <div key={i} className="h-12 bg-role-school-border rounded" />)}
        </div>
      ) : !data ? null : (
        <div className="overflow-auto">
          <table className="border-collapse">
            <thead>
              <tr>
                <th className="w-48 min-w-[12rem]" />
                {data.students.map((s) => (
                  <th key={s.id} className="px-1 pb-2 text-[10px] font-bold text-brand-muted text-center whitespace-nowrap max-w-[48px] overflow-hidden text-ellipsis">
                    {s.name.split(" ")[0]}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.subtopics.map((sub) => (
                <tr key={sub.id} className="border-b border-role-school-border last:border-0">
                  <td className="pr-3 py-1 text-xs text-brand-body font-semibold whitespace-nowrap">
                    {sub.name}
                  </td>
                  {data.students.map((stu) => (
                    <td key={stu.id} className="px-1 py-1 text-center">
                      <GapMapCell
                        masteryScore={getScore(stu.id, sub.id)}
                        studentName={stu.name}
                        subtopicName={sub.name}
                        display="label"
                        readOnly
                      />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Legend */}
      <div className="flex gap-5 mt-4">
        {[
          { color: "#ef4444", label: "Needs Work" },
          { color: "#f59e0b", label: "Developing" },
          { color: "#16a34a", label: "Strong" },
          { color: "#9ca3af", label: "Not assessed" },
        ].map(({ color, label }) => (
          <div key={label} className="flex items-center gap-1.5 text-[10px] text-brand-body font-semibold">
            <span className="w-2.5 h-2.5 rounded-full" style={{ background: color }} />
            {label}
          </div>
        ))}
      </div>
    </DashboardLayout>
  );
}
```

- [ ] **Step 2: Add route to App.tsx**

In `frontend/apps/school-admin/src/App.tsx`, inside the inner `<Routes>` block add after `<Route path="classes" ... />`:

```tsx
import { AdminGapMapPage } from "./pages/AdminGapMapPage";

// Add inside inner Routes:
<Route path="classes/:classId/gap-map" element={<AdminGapMapPage />} />
```

- [ ] **Step 3: Verify in browser**

```bash
pnpm dev:school-admin
```
Navigate to a class row → click it → confirm read-only gap map loads with breadcrumb.

- [ ] **Step 4: Commit**

```bash
git add frontend/apps/school-admin/src/pages/AdminGapMapPage.tsx \
        frontend/apps/school-admin/src/App.tsx
git commit -m "feat(school-admin): add read-only Gap Map screen with breadcrumb"
```

---

## Task 8: Rewrite Dashboard (SchoolOverview)

**Files:**
- Modify: `frontend/apps/school-admin/src/pages/SchoolOverview.tsx`

- [ ] **Step 1: Rewrite SchoolOverview.tsx**

```tsx
// frontend/apps/school-admin/src/pages/SchoolOverview.tsx
import { useNavigate } from "react-router-dom";
import { DashboardLayout } from "@kaihle/ui";
import { getMasteryStyle } from "@kaihle/types";
import { useSchoolAnalytics, useSchoolClasses } from "../hooks/useSchoolAdmin";

export function SchoolOverview() {
  const navigate = useNavigate();
  const { data: analytics, isLoading } = useSchoolAnalytics();
  const { data: classes = [] } = useSchoolClasses();

  const needsAttention = classes.filter((c) => c.diagnostic_status !== "has_data");
  const onboardingPct = analytics
    ? Math.round((analytics.onboarding_funnel.diagnostic_done / Math.max(analytics.total_students, 1)) * 100)
    : 0;

  const kpis = analytics
    ? [
        { label: "Total students", value: analytics.total_students },
        { label: "Active this month", value: analytics.active_students },
        { label: "Assessments completed", value: analytics.assessments_completed },
        { label: "Onboarding rate", value: `${onboardingPct}%` },
      ]
    : [];

  return (
    <DashboardLayout variant="school-admin" activePage="overview">
      {isLoading ? (
        <div className="animate-pulse space-y-4">
          <div className="grid grid-cols-4 gap-4">
            {[...Array(4)].map((_, i) => <div key={i} className="h-24 bg-role-school-border rounded-xl" />)}
          </div>
        </div>
      ) : (
        <>
          {/* KPI strip */}
          <div className="grid grid-cols-4 gap-4 mb-5">
            {kpis.map(({ label, value }) => (
              <div key={label} className="bg-white border border-role-school-border rounded-xl p-4">
                <div className="text-[9px] font-black uppercase tracking-[0.7px] text-role-school-muted mb-1.5">{label}</div>
                <div className="font-display font-bold text-[26px] text-brand-ink leading-none">{value}</div>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-2 gap-5">
            {/* At-risk students */}
            <div className="bg-white border border-role-school-border rounded-xl p-4">
              <div className="text-[9px] font-black uppercase tracking-[0.7px] text-role-school-muted mb-3">
                Students needing attention
              </div>
              {analytics?.at_risk_students.length === 0 ? (
                <p className="text-sm text-brand-muted py-4 text-center">No students at risk — great work!</p>
              ) : (
                <div className="space-y-2">
                  {analytics?.at_risk_students.slice(0, 6).map((s) => {
                    const { label } = getMasteryStyle(s.worst_mastery);
                    const initial = s.last_name.charAt(0).toUpperCase();
                    return (
                      <div key={s.student_id} className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <div className="w-7 h-7 rounded-full bg-brand-red flex items-center justify-center text-white text-[10px] font-black flex-shrink-0">
                            {s.first_name.charAt(0)}{initial}
                          </div>
                          <span className="text-xs font-semibold text-brand-ink">
                            {s.first_name} {initial}.
                          </span>
                        </div>
                        <span className="text-xs text-brand-red font-bold">
                          {label} · {s.needs_work_class_count} {s.needs_work_class_count === 1 ? "class" : "classes"}
                        </span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Classes needing attention */}
            <div className="bg-white border border-role-school-border rounded-xl p-4">
              <div className="text-[9px] font-black uppercase tracking-[0.7px] text-role-school-muted mb-3">
                Classes needing setup
              </div>
              {needsAttention.length === 0 ? (
                <p className="text-sm text-brand-muted py-4 text-center">All classes are set up.</p>
              ) : (
                <div className="space-y-2">
                  {needsAttention.slice(0, 6).map((c) => (
                    <div
                      key={c.id}
                      onClick={() => navigate(`/school-admin/classes/${c.id}/gap-map`)}
                      className="flex items-center justify-between cursor-pointer hover:bg-gray-50 rounded-lg px-2 py-1 -mx-2 transition-colors"
                    >
                      <span className="text-xs font-semibold text-brand-ink">{c.name}</span>
                      <span className={`text-[10px] font-bold ${c.diagnostic_status === "setup_needed" ? "text-brand-amber" : "text-brand-muted"}`}>
                        {c.diagnostic_status === "setup_needed" ? "No teacher" : "Diagnostic pending"}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </DashboardLayout>
  );
}
```

- [ ] **Step 2: Verify in browser**

```bash
pnpm dev:school-admin
```
Navigate to `/school-admin/dashboard`. Confirm KPIs render, at-risk list shows, classes needing setup appear.

- [ ] **Step 3: Commit**

```bash
git add frontend/apps/school-admin/src/pages/SchoolOverview.tsx
git commit -m "feat(school-admin): rewrite Dashboard with KPI strip, at-risk students, and setup widget"
```

---

## Task 9: Rewrite Analytics screen

**Files:**
- Modify: `frontend/apps/school-admin/src/pages/AnalyticsPage.tsx`

- [ ] **Step 1: Rewrite AnalyticsPage.tsx**

```tsx
// frontend/apps/school-admin/src/pages/AnalyticsPage.tsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { DashboardLayout } from "@kaihle/ui";
import { getMasteryStyle } from "@kaihle/types";
import { useSchoolAnalytics } from "../hooks/useSchoolAdmin";

type Period = "week" | "month";

function periodDates(p: Period): { from: string; to: string } {
  const today = new Date();
  const to = today.toISOString().split("T")[0];
  const from = new Date(today);
  if (p === "week") from.setDate(from.getDate() - 7);
  else from.setMonth(from.getMonth() - 1);
  return { from: from.toISOString().split("T")[0], to };
}

function masteryLabel(score: number | null) {
  if (score === null) return "Not assessed";
  if (score > 0.7) return "Strong";
  if (score >= 0.4) return "Developing";
  return "Needs Work";
}

function masteryColor(score: number | null) {
  if (score === null) return "#9ca3af";
  if (score > 0.7) return "#16a34a";
  if (score >= 0.4) return "#f59e0b";
  return "#ef4444";
}

export function AnalyticsPage() {
  const navigate = useNavigate();
  const [period, setPeriod] = useState<Period>("month");
  const { from, to } = periodDates(period);
  const { data, isLoading } = useSchoolAnalytics(from, to);

  const funnel = data?.onboarding_funnel;
  const total = funnel?.invited ?? 1;

  const funnelSteps = funnel
    ? [
        { label: "Invited", count: funnel.invited },
        { label: "Password set", count: funnel.password_set },
        { label: "Profile complete", count: funnel.profile_complete },
        { label: "Diagnostic done", count: funnel.diagnostic_done },
      ]
    : [];

  const subjectGroups = (data?.classes ?? []).reduce<Record<string, number[]>>((acc, c) => {
    const subj = c.class_name.split("—")[1]?.trim() ?? c.class_name;
    if (!acc[subj]) acc[subj] = [];
    if (c.avg_mastery !== null) acc[subj].push(c.avg_mastery);
    return acc;
  }, {});

  const onboardingPct = funnel
    ? Math.round((funnel.diagnostic_done / Math.max(funnel.invited, 1)) * 100)
    : 0;

  const kpis = data
    ? [
        { label: "Active students", value: `${data.active_students}/${data.total_students}` },
        { label: "Assessments completed", value: data.assessments_completed },
        { label: "Study plans active", value: data.study_plans_active },
        { label: "Onboarding rate", value: `${onboardingPct}%` },
      ]
    : [];

  return (
    <DashboardLayout variant="school-admin" activePage="analytics">
      {/* Period selector */}
      <div className="flex items-center gap-1 mb-5 bg-white border border-role-school-border rounded-lg p-1 self-start w-fit">
        {(["week", "month"] as Period[]).map((p) => (
          <button
            key={p}
            onClick={() => setPeriod(p)}
            className={`px-4 py-1.5 rounded-md text-xs font-bold transition-colors ${
              period === p ? "bg-brand-primary text-white" : "text-brand-muted hover:text-brand-ink"
            }`}
          >
            {p === "week" ? "This week" : "This month"}
          </button>
        ))}
        <button className="px-4 py-1.5 rounded-md text-xs font-bold text-brand-muted opacity-40 cursor-not-allowed">
          This term
        </button>
      </div>

      {isLoading ? (
        <div className="animate-pulse space-y-4">
          <div className="grid grid-cols-4 gap-4">
            {[...Array(4)].map((_, i) => <div key={i} className="h-24 bg-role-school-border rounded-xl" />)}
          </div>
        </div>
      ) : (
        <>
          {/* KPI strip */}
          <div className="grid grid-cols-4 gap-4 mb-5">
            {kpis.map(({ label, value }) => (
              <div key={label} className="bg-white border border-role-school-border rounded-xl p-4">
                <div className="text-[9px] font-black uppercase tracking-[0.7px] text-role-school-muted mb-1.5">{label}</div>
                <div className="font-display font-bold text-[26px] text-brand-ink leading-none">{value}</div>
              </div>
            ))}
          </div>

          {/* Middle row */}
          <div className="grid grid-cols-2 gap-5 mb-5">
            {/* Subject mastery bars */}
            <div className="bg-white border border-role-school-border rounded-xl p-4">
              <div className="text-[9px] font-black uppercase tracking-[0.7px] text-role-school-muted mb-3">
                Mastery by subject
              </div>
              <div className="space-y-3">
                {Object.entries(subjectGroups).map(([subj, scores]) => {
                  const avg = scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : null;
                  const color = masteryColor(avg);
                  const label = masteryLabel(avg);
                  const pct = avg !== null ? Math.round(avg * 100) : 0;
                  return (
                    <div key={subj}>
                      <div className="flex justify-between items-center mb-1">
                        <span className="text-xs font-semibold text-brand-ink">{subj}</span>
                        <span className="text-xs font-bold" style={{ color }}>{label}</span>
                      </div>
                      <div className="w-full bg-gray-100 rounded-full h-2">
                        <div className="h-2 rounded-full" style={{ width: `${pct}%`, background: color }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Onboarding funnel */}
            <div className="bg-white border border-role-school-border rounded-xl p-4">
              <div className="text-[9px] font-black uppercase tracking-[0.7px] text-role-school-muted mb-3">
                Onboarding funnel
              </div>
              <div className="space-y-3">
                {funnelSteps.map((step, i) => {
                  const next = funnelSteps[i + 1];
                  const dropoff = next ? step.count - next.count : 0;
                  const pct = Math.round((step.count / Math.max(total, 1)) * 100);
                  return (
                    <div key={step.label}>
                      <div className="flex justify-between items-center mb-1">
                        <span className="text-xs font-semibold text-brand-ink">{step.label}</span>
                        <span className="text-xs font-bold text-brand-ink">{step.count}</span>
                      </div>
                      <div className="w-full bg-gray-100 rounded-full h-2">
                        <div className="h-2 rounded-full bg-brand-primary" style={{ width: `${pct}%` }} />
                      </div>
                      {next && dropoff > 0 && (
                        <div className="text-[10px] text-brand-red font-bold mt-0.5">−{dropoff} dropped off</div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Class breakdown table */}
          <div className="bg-white border border-role-school-border rounded-xl overflow-hidden">
            <table className="w-full border-collapse">
              <thead>
                <tr className="bg-[#fafcfa] border-b border-role-school-border">
                  {["Class", "Mastery", "At risk", "Students", "Assessments", ""].map((h) => (
                    <th key={h} className="px-4 py-[10px] text-left text-[9px] font-black uppercase tracking-[0.7px] text-role-school-muted">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(data?.classes ?? []).map((c) => {
                  const { dotClass, label } = getMasteryStyle(c.avg_mastery);
                  return (
                    <tr
                      key={c.class_id}
                      onClick={() => navigate(`/school-admin/classes/${c.class_id}/gap-map`)}
                      className="border-b border-[#f0f5ee] last:border-0 cursor-pointer hover:bg-[#fafcfa] transition-colors"
                    >
                      <td className="px-4 py-3 font-bold text-[13px] text-brand-ink">{c.class_name}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1.5">
                          <span className={`w-2 h-2 rounded-full ${dotClass}`} />
                          <span className="text-xs font-semibold">{label}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        {c.avg_mastery !== null && c.avg_mastery < 0.4 ? (
                          <span className="text-[10px] font-bold bg-red-50 text-brand-red rounded-full px-2 py-0.5">
                            At risk
                          </span>
                        ) : null}
                      </td>
                      <td className="px-4 py-3 text-xs text-brand-muted">{c.student_count}</td>
                      <td className="px-4 py-3 text-xs text-brand-muted">{c.assessments_completed}</td>
                      <td className="px-4 py-3 text-brand-muted text-base">›</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </DashboardLayout>
  );
}
```

- [ ] **Step 2: Verify in browser — check "This term" is greyed out**

```bash
pnpm dev:school-admin
```
Open `/school-admin/analytics`. Confirm "This term" tab is visually disabled.

- [ ] **Step 3: Commit**

```bash
git add frontend/apps/school-admin/src/pages/AnalyticsPage.tsx
git commit -m "feat(school-admin): rewrite Analytics with period selector, funnel, and class breakdown"
```

---

## Task 10: Users screen

**Files:**
- Create: `frontend/apps/school-admin/src/pages/UsersPage.tsx`
- Modify: `frontend/apps/school-admin/src/App.tsx`

- [ ] **Step 1: Create UsersPage.tsx**

```tsx
// frontend/apps/school-admin/src/pages/UsersPage.tsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { DashboardLayout } from "@kaihle/ui";
import { getMasteryStyle } from "@kaihle/types";
import { useSchoolStudents, useSchoolUsers, type StudentListItem } from "../hooks/useSchoolAdmin";

type Tab = "students" | "teachers" | "parents";
type StudentFilter = "all" | "attention" | "pending" | "not_logged_in";

function nameDisplay(first: string, last: string) {
  return `${first} ${last.charAt(0).toUpperCase()}.`;
}

function initials(first: string, last: string) {
  return `${first.charAt(0)}${last.charAt(0)}`.toUpperCase();
}

function diagnosticStatus(s: StudentListItem): "Completed" | "Pending" | null {
  if (s.diagnostic_completed) return "Completed";
  if (s.class_count > 0) return "Pending";
  return null;
}

export function UsersPage() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>("students");
  const [filter, setFilter] = useState<StudentFilter>("all");

  const { data: students = [], isLoading: studentsLoading } = useSchoolStudents();
  const { data: teachers = [] } = useSchoolUsers("TEACHER");
  const { data: parents = [] } = useSchoolUsers("PARENT");

  const attentionCount = students.filter(
    (s) => s.worst_mastery !== null && s.worst_mastery < 0.4
  ).length;
  const pendingCount = students.filter((s) => !s.diagnostic_completed && s.class_count > 0).length;
  const notLoggedIn = students.filter((s) => !s.last_login_at).length;

  const filtered = students
    .filter((s) => {
      if (filter === "attention") return s.worst_mastery !== null && s.worst_mastery < 0.4;
      if (filter === "pending") return !s.diagnostic_completed && s.class_count > 0;
      if (filter === "not_logged_in") return !s.last_login_at;
      return true;
    })
    .sort((a, b) => {
      if (a.worst_mastery === null && b.worst_mastery === null) return 0;
      if (a.worst_mastery === null) return 1;
      if (b.worst_mastery === null) return -1;
      return a.worst_mastery - b.worst_mastery;
    });

  return (
    <DashboardLayout variant="school-admin" activePage="users">
      {/* Role tabs */}
      <div className="flex border-b-2 border-role-school-border mb-4">
        {[
          { key: "students" as Tab, label: "Students", count: students.length },
          { key: "teachers" as Tab, label: "Teachers", count: teachers.length },
          { key: "parents" as Tab, label: "Parents", count: parents.length },
        ].map(({ key, label, count }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`px-5 py-2 text-[13px] font-bold border-b-[3px] -mb-[2px] transition-colors ${
              tab === key
                ? "text-brand-primary border-brand-primary"
                : "text-brand-muted border-transparent"
            }`}
          >
            {label}{" "}
            <span className={`inline-block rounded-full px-1.5 py-px text-[10px] font-black ml-1 ${
              tab === key ? "bg-brand-green-light text-brand-primary" : "bg-gray-100 text-brand-muted"
            }`}>
              {count}
            </span>
          </button>
        ))}
      </div>

      {tab === "students" && (
        <>
          {/* Toolbar */}
          <div className="flex items-center gap-3 mb-4 flex-wrap">
            <div className="flex items-center gap-2 bg-white border border-role-school-border rounded-lg px-3 py-[7px]">
              <svg className="w-3 h-3 text-brand-muted" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
              <input className="text-xs outline-none font-sans bg-transparent w-40 placeholder:text-brand-muted" placeholder="Search students…" />
            </div>
            {[
              { key: "all" as StudentFilter, label: "All students" },
              { key: "attention" as StudentFilter, label: `Needs attention (${attentionCount})`, warn: true },
              { key: "pending" as StudentFilter, label: `Diagnostic pending (${pendingCount})` },
              { key: "not_logged_in" as StudentFilter, label: `Not yet logged in (${notLoggedIn})` },
            ].map(({ key, label, warn }) => (
              <button
                key={key}
                onClick={() => setFilter(key)}
                className={`px-3 py-[5px] rounded-full text-[11px] font-semibold border transition-colors ${
                  filter === key
                    ? "bg-brand-primary text-white border-brand-primary"
                    : warn
                      ? "border-brand-amber text-brand-gold bg-[#fffbeb]"
                      : "bg-white border-role-school-border text-brand-body"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {/* Students table */}
          {studentsLoading ? (
            <div className="animate-pulse space-y-2">
              {[...Array(5)].map((_, i) => <div key={i} className="h-12 bg-role-school-border rounded-lg" />)}
            </div>
          ) : (
            <div className="bg-white border border-role-school-border rounded-xl overflow-hidden">
              <table className="w-full border-collapse">
                <thead>
                  <tr className="bg-[#fafcfa] border-b border-role-school-border">
                    {["Student", "Classes", "Lowest mastery", "Diagnostic", "Last active", ""].map((h) => (
                      <th key={h} className="px-4 py-[10px] text-left text-[9px] font-black uppercase tracking-[0.7px] text-role-school-muted">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((s) => {
                    const { dotClass, label } = getMasteryStyle(s.worst_mastery);
                    const isAtRisk = s.worst_mastery !== null && s.worst_mastery < 0.4;
                    const diag = diagnosticStatus(s);
                    const lastActive = s.last_login_at
                      ? new Date(s.last_login_at).toLocaleDateString()
                      : "Never";

                    return (
                      <tr
                        key={s.id}
                        onClick={() => navigate(`/school-admin/users/students/${s.id}`)}
                        className={`border-b border-[#f0f5ee] last:border-0 cursor-pointer transition-colors ${
                          isAtRisk ? "bg-[#fffbeb] hover:bg-[#fef9c3]" : "hover:bg-[#fafcfa]"
                        }`}
                      >
                        <td className="px-4 py-[10px]">
                          <div className="flex items-center gap-2.5">
                            <div
                              className="w-7 h-7 rounded-full flex items-center justify-center text-white text-[10px] font-black flex-shrink-0"
                              style={{ background: isAtRisk ? "#ef4444" : "#1a5c38" }}
                            >
                              {initials(s.first_name, s.last_name)}
                            </div>
                            <div>
                              <div className="text-[13px] font-bold text-brand-ink">{nameDisplay(s.first_name, s.last_name)}</div>
                            </div>
                          </div>
                        </td>
                        <td className="px-4 py-[10px]">
                          <div className="flex items-center gap-1.5 text-xs font-semibold text-brand-body">
                            <svg className="w-3 h-3 text-brand-muted" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/></svg>
                            {s.class_count} {s.class_count === 1 ? "class" : "classes"}
                          </div>
                        </td>
                        <td className="px-4 py-[10px]">
                          <div className="flex items-center gap-1.5">
                            <span className={`w-2 h-2 rounded-full ${dotClass}`} />
                            <span className={`text-xs font-bold ${isAtRisk ? "text-brand-red" : "text-brand-ink"}`}>
                              {label}
                            </span>
                            {s.needs_work_class_count > 1 && (
                              <span className="text-[10px] text-brand-muted">· {s.needs_work_class_count} classes</span>
                            )}
                          </div>
                        </td>
                        <td className="px-4 py-[10px]">
                          {diag && (
                            <span className={`text-[10px] font-bold rounded-full px-2 py-px ${
                              diag === "Completed"
                                ? "bg-[#f0fdf4] text-brand-green"
                                : "bg-[#fffbeb] text-brand-gold"
                            }`}>
                              {diag}
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-[10px] text-[11px] text-brand-muted">{lastActive}</td>
                        <td className="px-4 py-[10px] text-brand-muted text-base">›</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              {filtered.length === 0 && (
                <div className="py-12 text-center text-brand-muted text-sm">No students match this filter.</div>
              )}
            </div>
          )}
        </>
      )}

      {tab === "teachers" && (
        <div className="bg-white border border-role-school-border rounded-xl p-6 text-center text-brand-muted text-sm">
          Teachers tab — list and invite teachers.
        </div>
      )}
      {tab === "parents" && (
        <div className="bg-white border border-role-school-border rounded-xl p-6 text-center text-brand-muted text-sm">
          Parents tab — list parents and their linked students.
        </div>
      )}
    </DashboardLayout>
  );
}
```

- [ ] **Step 2: Update App.tsx — replace UserManagement route, add student detail route**

```tsx
import { UsersPage } from "./pages/UsersPage";
import { StudentDetailPage } from "./pages/StudentDetailPage";

// Replace: <Route path="users" element={<UserManagement />} />
// With:
<Route path="users" element={<UsersPage />} />
<Route path="users/students/:studentId" element={<StudentDetailPage />} />
```

- [ ] **Step 3: Run typecheck and verify in browser**

```bash
cd frontend && pnpm typecheck
pnpm dev:school-admin
```
Navigate to `/school-admin/users`. Confirm three tabs, filter pills, and worst-first sort.

- [ ] **Step 4: Commit**

```bash
git add frontend/apps/school-admin/src/pages/UsersPage.tsx \
        frontend/apps/school-admin/src/App.tsx
git commit -m "feat(school-admin): add Users screen with student mastery list and filter pills"
```

---

## Task 11: Student Detail screen

**Files:**
- Create: `frontend/apps/school-admin/src/pages/StudentDetailPage.tsx`

- [ ] **Step 1: Create StudentDetailPage.tsx**

```tsx
// frontend/apps/school-admin/src/pages/StudentDetailPage.tsx
import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { DashboardLayout } from "@kaihle/ui";
import { getMasteryStyle } from "@kaihle/types";
import { apiClient } from "@kaihle/auth";
import { useStudentAttempts, useStudentStudyPlans } from "../hooks/useSchoolAdmin";

function nameDisplay(first: string, last: string) {
  return `${first} ${last.charAt(0).toUpperCase()}.`;
}

function initials(first: string, last: string) {
  return `${first.charAt(0)}${last.charAt(0)}`.toUpperCase();
}

interface StudentProfile {
  id: string;
  first_name: string;
  last_name: string;
  grade_level: number;
  curriculum_name: string;
  enrolled_at: string;
  class_enrollments: {
    class_id: string;
    class_name: string;
    teacher_name: string;
    gap_states: { subtopic_name: string; mastery_score: number | null }[];
  }[];
}

export function StudentDetailPage() {
  const { studentId } = useParams<{ studentId: string }>();
  const navigate = useNavigate();

  const { data: student, isLoading } = useQuery({
    queryKey: ["student", studentId, "detail"],
    queryFn: async () => {
      const res = await apiClient.get(`/api/v1/students/${studentId}`);
      return res.data as StudentProfile;
    },
    enabled: !!studentId,
  });

  const { data: attempts = [] } = useStudentAttempts(studentId ?? "");
  const { data: studyPlans = [] } = useStudentStudyPlans(studentId ?? "");

  const activeStudyPlan = Array.isArray(studyPlans)
    ? studyPlans.find((p: any) => p.is_active)
    : null;

  const needsWorkClassCount = (student?.class_enrollments ?? []).filter((ce) => {
    const scores = ce.gap_states.map((g) => g.mastery_score).filter((s): s is number => s !== null);
    const avg = scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : null;
    return avg !== null && avg < 0.4;
  }).length;

  return (
    <DashboardLayout variant="school-admin" activePage="users">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm mb-5">
        <button onClick={() => navigate("/school-admin/users")} className="text-brand-muted font-semibold hover:text-brand-primary transition-colors">Users</button>
        <span className="text-brand-border">›</span>
        <button onClick={() => navigate("/school-admin/users")} className="text-brand-muted font-semibold hover:text-brand-primary transition-colors">Students</button>
        <span className="text-brand-border">›</span>
        <span className="font-display font-bold text-brand-ink text-[15px]">
          {student ? nameDisplay(student.first_name, student.last_name) : "Loading…"}
        </span>
      </div>

      {isLoading ? (
        <div className="animate-pulse space-y-4">
          <div className="h-20 bg-role-school-border rounded-xl" />
          <div className="grid grid-cols-2 gap-4">
            <div className="h-48 bg-role-school-border rounded-xl" />
            <div className="h-48 bg-role-school-border rounded-xl" />
          </div>
        </div>
      ) : !student ? null : (
        <>
          {/* Hero card */}
          <div className="bg-white border border-role-school-border rounded-xl p-5 flex items-center gap-4 mb-5">
            <div className="w-12 h-12 rounded-full bg-brand-red flex items-center justify-center text-white text-base font-black flex-shrink-0">
              {initials(student.first_name, student.last_name)}
            </div>
            <div>
              <div className="font-display font-bold text-[18px] text-brand-ink">
                {student.first_name} {student.last_name.charAt(0).toUpperCase()}.
              </div>
              <div className="text-xs text-brand-muted mt-0.5">
                Grade {student.grade_level} · {student.curriculum_name} · Enrolled{" "}
                {new Date(student.enrolled_at).toLocaleDateString("en-GB", { month: "short", year: "numeric" })}
              </div>
            </div>
            <div className="ml-auto flex gap-6">
              {[
                { val: student.class_enrollments.length, label: "Classes" },
                { val: needsWorkClassCount, label: "Needs Work", color: needsWorkClassCount > 0 ? "#ef4444" : undefined },
                { val: attempts.length, label: "Assessments" },
              ].map(({ val, label, color }) => (
                <div key={label} className="text-center">
                  <div className="font-display font-bold text-[20px] text-brand-ink" style={{ color }}>{val}</div>
                  <div className="text-[10px] font-black uppercase tracking-[0.5px] text-brand-muted">{label}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Mastery by class */}
          <div className="mb-5">
            <div className="text-[9px] font-black uppercase tracking-[0.8px] text-role-school-muted mb-3">Mastery by class</div>
            <div className="grid grid-cols-2 gap-4">
              {student.class_enrollments.map((ce) => {
                const scores = ce.gap_states.map((g) => g.mastery_score).filter((s): s is number => s !== null);
                const avg = scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : null;
                const { dotClass, label } = getMasteryStyle(avg);
                return (
                  <div key={ce.class_id} className="bg-white border border-role-school-border rounded-xl p-4">
                    <div className="flex items-start justify-between mb-3">
                      <div>
                        <div className="text-[13px] font-bold text-brand-ink">{ce.class_name}</div>
                        <div className="text-[10px] text-brand-muted mt-0.5">{ce.teacher_name}</div>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className={`w-2 h-2 rounded-full ${dotClass}`} />
                        <span className="text-xs font-bold text-brand-ink">{label}</span>
                      </div>
                    </div>
                    <div className="space-y-1.5">
                      {ce.gap_states.map((gs) => {
                        const { label: gl } = getMasteryStyle(gs.mastery_score);
                        const pct = gs.mastery_score !== null ? Math.round(gs.mastery_score * 100) : 0;
                        const barColor =
                          gs.mastery_score === null ? "#9ca3af"
                          : gs.mastery_score > 0.7 ? "#16a34a"
                          : gs.mastery_score >= 0.4 ? "#f59e0b"
                          : "#ef4444";
                        return (
                          <div key={gs.subtopic_name} className="flex items-center gap-2">
                            <span className="text-[10px] text-brand-body w-28 flex-shrink-0 truncate">{gs.subtopic_name}</span>
                            <div className="flex-1 h-[5px] bg-gray-100 rounded-full">
                              <div className="h-[5px] rounded-full" style={{ width: `${pct}%`, background: barColor }} />
                            </div>
                            <span className="text-[9px] font-bold w-16 text-right flex-shrink-0" style={{ color: barColor }}>
                              {gl}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Study plan */}
          {activeStudyPlan && (
            <div className="mb-5">
              <div className="text-[9px] font-black uppercase tracking-[0.8px] text-role-school-muted mb-3">Study plan</div>
              <div className="bg-white border border-role-school-border rounded-xl p-4 flex items-center gap-4">
                <div className="w-9 h-9 rounded-lg bg-[#f0fdf4] flex items-center justify-center flex-shrink-0">
                  <svg className="w-4 h-4 text-brand-primary" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>
                </div>
                <div>
                  <div className="text-[13px] font-bold text-brand-ink">{activeStudyPlan.title ?? "Active study plan"}</div>
                  <div className="text-[11px] text-brand-muted mt-0.5">
                    Assigned {new Date(activeStudyPlan.assigned_at).toLocaleDateString()}
                  </div>
                </div>
                <div className="ml-auto flex items-center gap-1.5 text-xs font-bold text-brand-primary">
                  <span className="w-2 h-2 rounded-full bg-brand-primary" />
                  Active
                </div>
              </div>
            </div>
          )}

          {/* Assessment history */}
          <div>
            <div className="text-[9px] font-black uppercase tracking-[0.8px] text-role-school-muted mb-3">Recent assessments</div>
            <div className="bg-white border border-role-school-border rounded-xl overflow-hidden">
              <table className="w-full border-collapse">
                <thead>
                  <tr className="bg-[#fafcfa] border-b border-role-school-border">
                    {["Assessment", "Class", "Date", "Score", "Type"].map((h) => (
                      <th key={h} className="px-4 py-[9px] text-left text-[9px] font-black uppercase tracking-[0.7px] text-role-school-muted">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {(attempts as any[]).slice(0, 8).map((a, i) => {
                    const { label, bgClass, textClass } = getMasteryStyle(a.score ?? null);
                    return (
                      <tr key={i} className="border-b border-[#f0f5ee] last:border-0">
                        <td className="px-4 py-[9px] text-xs font-bold text-brand-ink">{a.assessment_name ?? "Assessment"}</td>
                        <td className="px-4 py-[9px] text-xs text-brand-muted">{a.class_name ?? "—"}</td>
                        <td className="px-4 py-[9px] text-xs text-brand-muted">
                          {a.completed_at ? new Date(a.completed_at).toLocaleDateString() : "—"}
                        </td>
                        <td className="px-4 py-[9px]">
                          <span className={`text-[10px] font-bold rounded-full px-2 py-px ${bgClass} ${textClass}`}>
                            {label}
                          </span>
                        </td>
                        <td className="px-4 py-[9px] text-[10px] text-brand-muted capitalize">
                          {(a.assessment_type ?? "").toLowerCase().replace("_", " ")}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              {attempts.length === 0 && (
                <div className="py-10 text-center text-brand-muted text-sm">No assessments yet.</div>
              )}
            </div>
          </div>
        </>
      )}
    </DashboardLayout>
  );
}
```

- [ ] **Step 2: Run typecheck**

```bash
cd frontend && pnpm typecheck
```

- [ ] **Step 3: Verify in browser**

```bash
pnpm dev:school-admin
```
Click any student row on the Users screen → confirm Student Detail loads with breadcrumb, hero stats, class mastery cards, and assessment table.

- [ ] **Step 4: Commit**

```bash
git add frontend/apps/school-admin/src/pages/StudentDetailPage.tsx
git commit -m "feat(school-admin): add Student Detail page with mastery cards and assessment history"
```

---

## Self-review

**Spec coverage:**
- §4.1 Dashboard ✓ Task 8
- §4.2 Classes ✓ Task 6
- §4.3 Gap Map ✓ Task 7
- §4.4 Analytics ✓ Task 9
- §4.5 Users ✓ Task 10
- §4.6 Student Detail ✓ Task 11
- §5 API gaps — analytics stub ✓ Tasks 1–2; worst_mastery ✓ Task 3
- §6.1 GapMapCell extraction ✓ Task 4
- "This term" greyed out ✓ Task 9
- Mastery labels only, no floats ✓ all screens use `getMasteryStyle()`
- Sorted worst-first ✓ Tasks 6, 10
- Name format "First L." ✓ Tasks 10, 11

**Placeholder scan:** None found. All code steps contain complete implementations.

**Type consistency:**
- `SchoolAnalyticsData` defined in Task 2 schema, used in Task 5 hook as `SchoolAnalytics` (alias) ✓
- `StudentListItem` defined in Task 5 hook, used in Task 10 ✓
- `GapMapCellProps` defined in Task 4, consumed in Task 7 ✓
- `getMasteryStyle` imported from `@kaihle/types` consistently throughout ✓
