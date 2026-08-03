"""KaihleAdmin review queue for curriculum-mapping decisions.

The remap pipeline resolves what it can automatically and stops where it cannot: an
embedding similarity in the ambiguous band, or an adjudicating model that declined to
choose. Those cases are curriculum judgements — "does this old objective assess the
same skill as this new one?" — and belong with an educator, not an engineer reading
JSON out of a backups directory.

Approving an item binds every question it governs in one action. That is the whole
economy of the design: the 2278 questions orphaned by the cambridge_v2 remap came from
71 old subtopics, so a reviewer makes 71 decisions rather than 2278.

Items are curriculum-scoped and carry no school_id — one ruling applies everywhere.
"""

import json
import uuid
from datetime import UTC, datetime
from typing import Any, cast

import structlog
from fastapi import HTTPException, status
from sqlalchemy import func, select, text, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.curriculum import LearningObjective, LearningObjectiveReviewItem, QuestionBank

logger = structlog.get_logger()

ITEM_TYPE_QUESTION_REMAP = "QUESTION_REMAP"
STATUS_PENDING = "PENDING"
STATUS_APPROVED = "APPROVED"
STATUS_REJECTED = "REJECTED"


class LoReviewService:
    """Business logic for the learning-objective review queue."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_items(
        self,
        status_filter: str = STATUS_PENDING,
        item_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Return a page of review items, largest blast radius first.

        Ordered by question_count descending so a reviewer with limited time spends it
        where a decision affects the most questions.
        """
        conditions = [LearningObjectiveReviewItem.status == status_filter]
        if item_type:
            conditions.append(LearningObjectiveReviewItem.item_type == item_type)

        total = await self.db.execute(select(func.count()).select_from(LearningObjectiveReviewItem).where(*conditions))
        rows = await self.db.execute(
            select(LearningObjectiveReviewItem)
            .where(*conditions)
            .order_by(
                LearningObjectiveReviewItem.question_count.desc(),
                LearningObjectiveReviewItem.source_code,
            )
            .limit(limit)
            .offset(offset)
        )
        items = list(rows.scalars().all())

        return {
            "total": int(total.scalar_one()),
            "items": [self._serialise(item) for item in items],
        }

    async def counts_by_status(self) -> dict[str, int]:
        """Queue summary for the admin dashboard badge."""
        rows = await self.db.execute(
            select(LearningObjectiveReviewItem.status, func.count()).group_by(LearningObjectiveReviewItem.status)
        )
        counts = {row[0]: int(row[1]) for row in rows.all()}
        for state in (STATUS_PENDING, STATUS_APPROVED, STATUS_REJECTED):
            counts.setdefault(state, 0)
        return counts

    async def approve_item(
        self,
        item_id: uuid.UUID,
        objective_id: uuid.UUID,
        reviewer_id: uuid.UUID,
        admin_note: str | None = None,
    ) -> dict[str, Any]:
        """Bind the item's questions to the chosen objective and close it.

        The reviewer may pick any objective, not only a listed candidate — the
        candidates are the machine's shortlist, and an educator who knows the
        curriculum may well know better.
        """
        item = await self._get_pending(item_id)

        objective = await self.db.execute(select(LearningObjective).where(LearningObjective.id == objective_id))
        if objective.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Learning objective {objective_id} not found",
            )

        bound = 0
        if item.question_ids:
            # Only fill NULLs. If a question was bound by some other route in the
            # meantime, that binding stands rather than being silently overwritten.
            result = await self.db.execute(
                update(QuestionBank)
                .where(
                    QuestionBank.id.in_([uuid.UUID(q) for q in item.question_ids]),
                    QuestionBank.learning_objective_id.is_(None),
                )
                .values(learning_objective_id=objective_id)
            )
            bound = cast("CursorResult[Any]", result).rowcount or 0

        item.status = STATUS_APPROVED
        item.chosen_objective_id = objective_id
        item.resolved_by = reviewer_id
        item.resolved_at = datetime.now(UTC)
        item.admin_note = admin_note
        await self.db.commit()

        logger.info(
            "lo_review_item_approved",
            item_id=str(item_id),
            source_code=item.source_code,
            objective_id=str(objective_id),
            questions_bound=bound,
            followed_llm_suggestion=item.llm_suggested_code is not None
            and any(
                c.get("canonical_code") == item.llm_suggested_code and c.get("objective_id") == str(objective_id)
                for c in item.candidates
            ),
            reviewer_id=str(reviewer_id),
        )
        return {"item_id": str(item_id), "questions_bound": bound, "status": STATUS_APPROVED}

    async def reject_item(
        self,
        item_id: uuid.UUID,
        reviewer_id: uuid.UUID,
        admin_note: str | None = None,
    ) -> dict[str, Any]:
        """Close an item without binding anything.

        Used when no candidate assesses the same skill. The questions stay unbound and
        surface in the coverage report as a genuine gap — which is the honest outcome,
        and better than forcing them onto an approximate objective.
        """
        item = await self._get_pending(item_id)

        item.status = STATUS_REJECTED
        item.resolved_by = reviewer_id
        item.resolved_at = datetime.now(UTC)
        item.admin_note = admin_note
        await self.db.commit()

        logger.info(
            "lo_review_item_rejected",
            item_id=str(item_id),
            source_code=item.source_code,
            question_count=item.question_count,
            reviewer_id=str(reviewer_id),
        )
        return {"item_id": str(item_id), "questions_bound": 0, "status": STATUS_REJECTED}

    async def search_objectives(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Free-text objective search, so a reviewer can pick outside the shortlist."""
        pattern = f"%{query.strip()}%"
        rows = await self.db.execute(
            select(LearningObjective)
            .where(
                LearningObjective.is_active.is_(True),
                # Bound parameters — never string-formatted into the SQL.
                (LearningObjective.learning_objective.ilike(pattern))
                | (LearningObjective.canonical_code.ilike(pattern))
                | (LearningObjective.name.ilike(pattern)),
            )
            .order_by(LearningObjective.canonical_code)
            .limit(limit)
        )
        return [
            {
                "objective_id": str(o.id),
                "canonical_code": o.canonical_code,
                "name": o.name,
                "learning_objective": o.learning_objective,
            }
            for o in rows.scalars().all()
        ]

    async def _get_pending(self, item_id: uuid.UUID) -> LearningObjectiveReviewItem:
        result = await self.db.execute(
            select(LearningObjectiveReviewItem).where(LearningObjectiveReviewItem.id == item_id)
        )
        item = result.scalar_one_or_none()
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Review item {item_id} not found",
            )
        if item.status != STATUS_PENDING:
            # Two reviewers on the same queue must not both resolve one item.
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Review item is already {item.status}",
            )
        return item

    @staticmethod
    def _serialise(item: LearningObjectiveReviewItem) -> dict[str, Any]:
        return {
            "id": str(item.id),
            "item_type": item.item_type,
            "status": item.status,
            "source_code": item.source_code,
            "source_name": item.source_name,
            "source_learning_objective": item.source_learning_objective,
            "subject_code": item.subject_code,
            "grade_level": item.grade_level,
            "question_count": item.question_count,
            "candidates": item.candidates,
            "llm_suggested_code": item.llm_suggested_code,
            "llm_reason": item.llm_reason,
            "chosen_objective_id": str(item.chosen_objective_id) if item.chosen_objective_id else None,
            "admin_note": item.admin_note,
            "resolved_at": item.resolved_at.isoformat() if item.resolved_at else None,
        }


async def upsert_review_item(
    db: AsyncSession,
    *,
    item_type: str,
    source_code: str,
    source_name: str | None,
    source_learning_objective: str,
    subject_code: str | None,
    grade_level: int | None,
    question_ids: list[str],
    candidates: list[dict[str, Any]],
    llm_suggested_code: str | None = None,
    llm_reason: str | None = None,
) -> bool:
    """Create or refresh a pending review item. Returns True if a row was written.

    Called by the remap scripts. Already-resolved items are left alone: re-running the
    pipeline must never reopen a decision an educator has already made.
    """
    result = await db.execute(
        text(
            """
            INSERT INTO lo_review_items (
                id, item_type, status, source_code, source_name, source_learning_objective,
                subject_code, grade_level, question_count, candidates, question_ids,
                llm_suggested_code, llm_reason, created_at
            )
            VALUES (
                gen_random_uuid(), :item_type, 'PENDING', :source_code, :source_name, :source_lo,
                :subject_code, :grade_level, :question_count,
                CAST(:candidates AS jsonb), CAST(:question_ids AS jsonb),
                :llm_code, :llm_reason, now()
            )
            ON CONFLICT (item_type, source_code) DO UPDATE SET
                source_name               = EXCLUDED.source_name,
                source_learning_objective = EXCLUDED.source_learning_objective,
                question_count            = EXCLUDED.question_count,
                candidates                = EXCLUDED.candidates,
                question_ids              = EXCLUDED.question_ids,
                llm_suggested_code        = EXCLUDED.llm_suggested_code,
                llm_reason                = EXCLUDED.llm_reason,
                updated_at                = now()
            WHERE lo_review_items.status = 'PENDING'
            """
        ),
        {
            "item_type": item_type,
            "source_code": source_code,
            "source_name": source_name,
            "source_lo": source_learning_objective,
            "subject_code": subject_code,
            "grade_level": grade_level,
            "question_count": len(question_ids),
            "candidates": json.dumps(candidates),
            "question_ids": json.dumps(question_ids),
            "llm_code": llm_suggested_code,
            "llm_reason": llm_reason,
        },
    )
    return bool(cast("CursorResult[Any]", result).rowcount)
