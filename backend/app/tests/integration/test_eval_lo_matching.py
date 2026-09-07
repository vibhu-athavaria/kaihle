"""Integration tests for the LO-matching evaluation harness.

Two things need a real database to verify. First, that `load_outcomes` reads the review
queue's actual shape — the JSONB candidates column, the LEFT JOIN to the chosen objective,
and the NULLs that appear when the model declined. Second, and more importantly, that the
harness writes nothing: an evaluation tool that mutates the data it measures is worse than
no tool.
"""

import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.curriculum import Grade, LearningObjective, LearningObjectiveReviewItem, Topic
from scripts.eval_lo_matching import compute_report, load_outcomes


@pytest.mark.asyncio
class TestEvalHarnessAgainstRealSchema:
    async def _grade(self, db: AsyncSession) -> Grade:
        """Find-or-create grade 6.

        `grades.level` is unique and the table is global, so a test needing two
        objectives at the same grade must share one row rather than insert twice.
        """
        existing = await db.execute(select(Grade).where(Grade.level == 6))
        found = existing.scalar_one_or_none()
        if found is not None:
            return found
        grade = Grade(id=uuid.uuid4(), name="Grade 6", level=6)
        db.add(grade)
        await db.flush()
        return grade

    async def _objective(self, db: AsyncSession, code: str) -> LearningObjective:
        topic = Topic(id=uuid.uuid4(), name="Number", canonical_code=f"T{uuid.uuid4().hex[:8]}")
        db.add(topic)
        grade = await self._grade(db)
        await db.flush()

        objective = LearningObjective(
            id=uuid.uuid4(),
            topic_id=topic.id,
            grade_id=grade.id,
            canonical_code=code,
            name="Ordering decimals",
            learning_objective="Order decimals of differing lengths.",
            normalised_objective=f"order decimals {uuid.uuid4().hex[:8]}",
            is_active=True,
        )
        db.add(objective)
        await db.flush()
        return objective

    async def _item(
        self,
        db: AsyncSession,
        source_code: str,
        status: str,
        llm_suggested_code: str | None,
        chosen: LearningObjective | None,
        question_count: int = 10,
        top_similarity: float = 0.72,
    ) -> LearningObjectiveReviewItem:
        item = LearningObjectiveReviewItem(
            id=uuid.uuid4(),
            item_type="QUESTION_REMAP",
            status=status,
            source_code=source_code,
            source_name="Old subtopic",
            source_learning_objective="Old objective text.",
            subject_code="MATH",
            grade_level=6,
            question_count=question_count,
            candidates=[
                {
                    "objective_id": str(chosen.id) if chosen else str(uuid.uuid4()),
                    "canonical_code": chosen.canonical_code if chosen else "OTHER",
                    "learning_objective": "Candidate text.",
                    "similarity": top_similarity,
                }
            ],
            question_ids=[],
            llm_suggested_code=llm_suggested_code,
            llm_reason=None,
            chosen_objective_id=chosen.id if chosen else None,
            resolved_by=None,
            resolved_at=None,
            admin_note=None,
        )
        db.add(item)
        await db.flush()
        return item

    async def test_report_mode_when_no_resolved_items_then_reports_zero_without_error(
        self, db_session: AsyncSession
    ) -> None:
        outcomes = await load_outcomes(db_session)
        report = compute_report(outcomes)
        # An empty queue is a legitimate state, not a crash: the harness runs against
        # environments where the remap has never been executed.
        assert report["adjudicator_agreement"].denominator == 0
        assert report["adjudicator_agreement"].high == 1.0

    async def test_report_mode_when_mixed_rulings_then_rates_match_hand_computed_values(
        self, db_session: AsyncSession
    ) -> None:
        agreed = await self._objective(db_session, f"AGREE-{uuid.uuid4().hex[:6]}")
        other = await self._objective(db_session, f"OTHER-{uuid.uuid4().hex[:6]}")

        # Reviewer took the model's suggestion.
        await self._item(db_session, "S1", "APPROVED", agreed.canonical_code, agreed)
        # Reviewer overrode it.
        await self._item(db_session, "S2", "APPROVED", other.canonical_code, agreed)
        # Model declined; reviewer found a match anyway.
        await self._item(db_session, "S3", "APPROVED", None, agreed)
        # Still queued — must not enter any denominator.
        await self._item(db_session, "S4", "PENDING", None, None)

        report = compute_report(await load_outcomes(db_session))

        assert report["adjudicator_agreement"].numerator == 1
        assert report["adjudicator_agreement"].denominator == 2
        assert report["decline_recoverability"].numerator == 1
        assert report["resolved_total"] == 3

    async def test_report_mode_when_candidates_read_then_top_similarity_parsed_from_jsonb(
        self, db_session: AsyncSession
    ) -> None:
        chosen = await self._objective(db_session, f"C-{uuid.uuid4().hex[:6]}")
        await self._item(db_session, "S5", "APPROVED", "SOMETHING-ELSE", chosen, top_similarity=0.63)

        outcomes = await load_outcomes(db_session)
        overridden = next(o for o in outcomes if o.source_code == "S5")
        # Reading this as a string, or not at all, would silently empty the
        # disagreement-by-similarity table that tells us where the band edges belong.
        assert overridden.top_similarity == pytest.approx(0.63)

    async def test_report_mode_when_run_twice_then_writes_nothing_to_database(self, db_session: AsyncSession) -> None:
        chosen = await self._objective(db_session, f"NOWRITE-{uuid.uuid4().hex[:6]}")
        await self._item(db_session, "S6", "APPROVED", chosen.canonical_code, chosen)
        await db_session.commit()

        async def snapshot() -> tuple[int, list[tuple[str, str, str | None]]]:
            count = await db_session.execute(select(func.count()).select_from(LearningObjectiveReviewItem))
            rows = await db_session.execute(
                select(
                    LearningObjectiveReviewItem.source_code,
                    LearningObjectiveReviewItem.status,
                    LearningObjectiveReviewItem.llm_suggested_code,
                ).order_by(LearningObjectiveReviewItem.source_code)
            )
            return int(count.scalar_one()), [tuple(r) for r in rows.all()]

        before = await snapshot()
        await load_outcomes(db_session)
        await load_outcomes(db_session)
        after = await snapshot()

        assert before == after
