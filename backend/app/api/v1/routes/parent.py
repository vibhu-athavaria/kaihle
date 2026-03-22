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
