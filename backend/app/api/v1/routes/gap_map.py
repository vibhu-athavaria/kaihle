"""Gap map API routes.

Stub implementations — returns correct schema shape with empty data.
Real implementation: M2-1-T2 (gap_map_routes.md).
"""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, require_full_access, require_role
from app.models.user import UserRole
from app.schemas.gap_map import ClassGapMap, ClassSummary, StudentGapMap

router = APIRouter(tags=["gap-map"])


@router.get("/classes/{class_id}/gap-map", response_model=ClassGapMap)
async def get_class_gap_map(
    class_id: UUID,
    subject_id: UUID = Query(..., description="Filter gap map by subject"),
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> ClassGapMap:
    """Get class gap map for a specific subject.

    STUB — M0-10-T2 | Real implementation: M2-1-T2
    Replace this entire function body. Do not change the signature or response_model.
    M2 adds: school_id scoping, teacher-owns-class check, real gap_state aggregation.
    """
    return ClassGapMap(
        class_id=class_id,
        subject_id=subject_id,
        generated_at=datetime.now(UTC),
        nodes=[],
    )


@router.get("/classes/{class_id}/summary", response_model=ClassSummary)
async def get_class_summary(
    class_id: UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.KAIHLE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> ClassSummary:
    """Get lightweight class summary for teacher dashboard class cards.

    STUB — M0-10-T2 | Real implementation: M2-1-T1
    Lightweight summary for teacher dashboard class cards.
    Replace with real aggregation from gap_states once M2 data exists.
    """
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
    """Get authenticated student's own gap map.

    STUB — M0-10-T2 | Real implementation: M2-1-T2
    /me shortcut — resolves to authenticated student's own gap map.
    M2 adds: real gap_state query filtered to current_user.id.
    """
    return StudentGapMap(
        student_id=current_user.id,
        subject_id=subject_id,
        generated_at=datetime.now(UTC),
        scores=[],
    )


@router.get("/students/{student_id}/gap-map", response_model=StudentGapMap)
async def get_student_gap_map(
    student_id: UUID,
    subject_id: UUID = Query(...),
    current_user: CurrentUser = Depends(require_full_access),
    db: AsyncSession = Depends(get_db),
) -> StudentGapMap:
    """Get specific student's gap map.

    STUB — M0-10-T2 | Real implementation: M2-1-T2
    M2 adds: student can only see own, teacher must own the class,
    parent must be linked via parent_student table, school-scoping.
    """
    return StudentGapMap(
        student_id=student_id,
        subject_id=subject_id,
        generated_at=datetime.now(UTC),
        scores=[],
    )
