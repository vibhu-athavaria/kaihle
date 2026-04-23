"""Parent portal API routes.

Parents can view their linked children's progress — weekly narrative reports
and a simplified gap map. CRITICAL design constraint: numeric mastery scores
are NEVER returned from any endpoint in this file. Parents see plain-language
status labels only ("Strong", "Developing", "Needs Work"). This constraint
is encoded in the ParentGapMap schema, which has no mastery_score field.

Stub implementations. Real implementation: M5-1-T2.
"""

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, require_role
from app.models.gap import GapState
from app.models.school import ClassEnrollment
from app.models.user import ParentStudent, User, UserRole
from app.schemas.common import Page
from app.schemas.parent import ChildSummary, ParentGapMap, WeeklyReport

logger = structlog.get_logger()

router = APIRouter(prefix="/parent", tags=["parent"])
parents_router = APIRouter(prefix="/parents", tags=["parents"])


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


# =============================================================================
# GET /parents/{parent_id} — parent detail for school admin
# =============================================================================


class LinkedStudentSummary(BaseModel):
    """Summary of a student linked to a parent."""

    student_id: UUID
    first_name: str
    last_name: str
    worst_mastery: float | None
    class_count: int


class ParentDetailResponse(BaseModel):
    """Full parent profile for school-admin detail view."""

    id: UUID
    first_name: str
    last_name: str
    email: str
    is_active: bool
    linked_students: list[LinkedStudentSummary]


@parents_router.get("/{parent_id}", response_model=ParentDetailResponse)
async def get_parent_detail(
    parent_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_role(UserRole.SCHOOL_ADMIN, UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> ParentDetailResponse:
    """Get full parent detail including linked students.

    Auth: SCHOOL_ADMIN (same school) or KAIHLE_ADMIN only.

    Raises:
        404: If parent not found.
    """
    parent_query = select(User).where(User.id == parent_id, User.role == UserRole.PARENT)
    if current_user.role == UserRole.SCHOOL_ADMIN:
        parent_query = parent_query.where(User.school_id == current_user.school_id)

    parent_result = await db.execute(parent_query)
    parent = parent_result.scalar_one_or_none()

    if parent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parent not found",
        )

    # Fetch linked students
    links_query = (
        select(ParentStudent, User)
        .join(User, User.id == ParentStudent.student_id)
        .where(ParentStudent.parent_id == parent_id)
        .order_by(User.first_name, User.last_name)
    )
    links_result = await db.execute(links_query)
    link_rows = links_result.all()

    linked_students: list[LinkedStudentSummary] = []
    for _link, student in link_rows:
        # Count active class enrollments
        count_result = await db.execute(
            select(func.count(ClassEnrollment.class_id)).where(
                ClassEnrollment.student_id == student.id,
                ClassEnrollment.is_active.is_(True),
            )
        )
        class_count = count_result.scalar() or 0

        # Worst (minimum) mastery score across all gap states for this student
        worst_result = await db.execute(
            select(func.min(GapState.mastery_score)).where(GapState.student_id == student.id)
        )
        worst_mastery: float | None = worst_result.scalar()

        linked_students.append(
            LinkedStudentSummary(
                student_id=student.id,
                first_name=student.first_name or "",
                last_name=student.last_name or "",
                worst_mastery=worst_mastery,
                class_count=class_count,
            )
        )

    logger.info(
        "parent_detail_requested",
        requester_id=str(current_user.id),
        requester_role=str(current_user.role),
        target_parent_id=str(parent_id),
        linked_student_count=len(linked_students),
    )

    return ParentDetailResponse(
        id=parent.id,
        first_name=parent.first_name or "",
        last_name=parent.last_name or "",
        email=parent.email,
        is_active=parent.is_active,
        linked_students=linked_students,
    )
