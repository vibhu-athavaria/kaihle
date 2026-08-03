"""Integration tests for learning-objective creation.

The behaviours worth proving against a real database are the ones that make the LO
layer worth having: de-duplication across placements, deterministic backfill of
untouched scopes, question binding, and idempotent re-runs.

Embeddings are stubbed. These tests assert the de-duplication *decisions* given
similarity, not the quality of any particular embedding model.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.curriculum import (
    Curriculum,
    CurriculumTopic,
    Grade,
    LearningObjective,
    QuestionBank,
    Subject,
    Subtopic,
    SubtopicObjective,
    Topic,
)
from scripts.create_learning_objectives import (
    Stats,
    bind_questions_via_subtopic,
    run_legacy_backfill,
    run_new_tree,
)

# learning_objectives.embedding is vector(768), so stubs must be full width or the
# column rejects them.
EMBEDDING_DIM = 768


def vec(*head: float) -> list[float]:
    """A 768-dim vector with the given leading components, zero-padded."""
    return list(head) + [0.0] * (EMBEDDING_DIM - len(head))


# Mutually orthogonal -> cosine 0, i.e. "definitely different concepts".
_ORTHOGONAL = [vec(1.0), vec(0.0, 1.0), vec(0.0, 0.0, 1.0), vec(0.0, 0.0, 0.0, 1.0)]


@pytest.mark.asyncio
class TestLearningObjectiveCreation:
    async def _scope(
        self,
        db: AsyncSession,
        objectives: list[tuple[str, str]],
        *,
        grade_levels: list[int] | None = None,
        with_questions: bool = False,
    ) -> tuple[Curriculum, Subject, list[Subtopic]]:
        """Build one topic carrying the given (name, objective_text) subtopics."""
        curriculum = Curriculum(id=uuid.uuid4(), name=f"C {uuid.uuid4().hex[:8]}", code=f"cur{uuid.uuid4().hex[:6]}")
        subject = Subject(id=uuid.uuid4(), name=f"S {uuid.uuid4().hex[:8]}", code=f"X{uuid.uuid4().hex[:5]}")
        topic = Topic(id=uuid.uuid4(), name="Number", canonical_code=f"T{uuid.uuid4().hex[:6]}")
        db.add_all([curriculum, subject, topic])
        await db.flush()

        levels = grade_levels or [6] * len(objectives)
        subtopics: list[Subtopic] = []
        cts: dict[int, CurriculumTopic] = {}

        for (name, objective_text), level in zip(objectives, levels, strict=True):
            if level not in cts:
                grade = Grade(id=uuid.uuid4(), name=f"Grade {level}", level=level)
                db.add(grade)
                await db.flush()
                ct = CurriculumTopic(
                    id=uuid.uuid4(),
                    curriculum_id=curriculum.id,
                    subject_id=subject.id,
                    grade_id=grade.id,
                    topic_id=topic.id,
                    sequence_order=1,
                )
                db.add(ct)
                await db.flush()
                cts[level] = ct

            subtopic = Subtopic(
                id=uuid.uuid4(),
                curriculum_topic_id=cts[level].id,
                name=name,
                canonical_code=f"ST-{uuid.uuid4().hex[:8]}",
                learning_objective=objective_text,
                is_active=True,
            )
            db.add(subtopic)
            await db.flush()
            subtopics.append(subtopic)

            if with_questions:
                db.add(
                    QuestionBank(
                        id=uuid.uuid4(),
                        subtopic_id=subtopic.id,
                        question_text=f"Q for {name}",
                        question_type="MCQ",
                        options=[{"key": "A", "text": "1"}],
                        correct_answer="A",
                        canonical_form=f"q-{uuid.uuid4().hex[:8]}",
                        problem_signature={},
                        difficulty_level=1.0,
                        source="bank",
                        is_active=True,
                    )
                )
        await db.commit()
        return curriculum, subject, subtopics

    @staticmethod
    def _stub_embeddings(vectors: list[list[float]]) -> AsyncMock:
        return AsyncMock(return_value=vectors)

    async def _run_new_tree(
        self,
        db: AsyncSession,
        curriculum: Curriculum,
        subject: Subject,
        grades: list[int],
        vectors: list[list[float]],
    ) -> Stats:
        stats = Stats()
        with patch(
            "scripts.create_learning_objectives.embed_all",
            self._stub_embeddings(vectors),
        ):
            await run_new_tree(db, stats, curriculum.code, [subject.code], grades, dry_run=False)
        await db.commit()
        return stats

    async def test_new_tree_when_objectives_distinct_then_one_lo_each(self, db_session: AsyncSession) -> None:
        curriculum, subject, subtopics = await self._scope(
            db_session,
            [("Negative numbers", "Order negative integers."), ("Prime factors", "Express a number as prime factors.")],
        )

        stats = await self._run_new_tree(db_session, curriculum, subject, [6], _ORTHOGONAL[:2])

        assert stats.created == 2
        assert stats.linked_by_similarity == 0
        for subtopic in subtopics:
            links = await db_session.execute(
                select(SubtopicObjective).where(SubtopicObjective.subtopic_id == subtopic.id)
            )
            assert len(links.scalars().all()) == 1

    async def test_new_tree_when_objective_text_identical_then_shares_one_lo(self, db_session: AsyncSession) -> None:
        """The same concept taught in two grades must resolve to a single objective —
        this is the property that makes the bank curriculum-agnostic."""
        curriculum, subject, subtopics = await self._scope(
            db_session,
            [("Ordering decimals G6", "Order decimals by size."), ("Ordering decimals G7", "Order decimals by size.")],
            grade_levels=[6, 7],
        )

        stats = await self._run_new_tree(db_session, curriculum, subject, [6, 7], _ORTHOGONAL[:2])

        assert stats.created == 1
        assert stats.linked_by_text == 1

        rows = await db_session.execute(
            select(SubtopicObjective.learning_objective_id).where(
                SubtopicObjective.subtopic_id.in_([s.id for s in subtopics])
            )
        )
        assert len({r[0] for r in rows}) == 1

    async def test_new_tree_when_similarity_above_auto_link_then_shares_one_lo(self, db_session: AsyncSession) -> None:
        curriculum, subject, _ = await self._scope(
            db_session,
            [("A", "Order decimals by size."), ("B", "Put decimals in order of size.")],
            grade_levels=[6, 7],
        )

        # Identical vectors -> similarity 1.0, above the 0.90 auto-link threshold.
        stats = await self._run_new_tree(db_session, curriculum, subject, [6, 7], [vec(1.0), vec(1.0)])

        assert stats.created == 1
        assert stats.linked_by_similarity == 1

    async def test_new_tree_when_similarity_in_review_band_then_creates_lo_and_flags(
        self, db_session: AsyncSession
    ) -> None:
        """A near-miss is a judgement call, so it creates a distinct LO and records the
        pair rather than guessing in either direction."""
        curriculum, subject, _ = await self._scope(
            db_session,
            [("A", "Order decimals by size."), ("B", "Compare decimal quantities.")],
            grade_levels=[6, 7],
        )

        # cos ~= 0.857 — inside 0.80-0.89.
        stats = await self._run_new_tree(db_session, curriculum, subject, [6, 7], [vec(1.0), vec(0.857, 0.515)])

        assert stats.created == 2
        assert stats.linked_by_similarity == 0
        assert len(stats.review_items) == 1
        assert 0.80 <= stats.review_items[0]["similarity"] < 0.90

    async def test_new_tree_when_similarity_below_review_band_then_no_review_item(
        self, db_session: AsyncSession
    ) -> None:
        curriculum, subject, _ = await self._scope(
            db_session,
            [("A", "Order decimals by size."), ("B", "Name the parts of a plant cell.")],
            grade_levels=[6, 7],
        )

        stats = await self._run_new_tree(db_session, curriculum, subject, [6, 7], _ORTHOGONAL[:2])

        assert stats.created == 2
        assert stats.review_items == []

    async def test_new_tree_when_run_twice_then_second_run_is_a_noop(self, db_session: AsyncSession) -> None:
        curriculum, subject, _ = await self._scope(
            db_session, [("A", "Order negative integers."), ("B", "Express prime factors.")]
        )

        first = await self._run_new_tree(db_session, curriculum, subject, [6], _ORTHOGONAL[:2])
        second = await self._run_new_tree(db_session, curriculum, subject, [6], _ORTHOGONAL[:2])

        assert first.created == 2
        assert second.created == 0
        assert second.subtopics_seen == 0

    async def test_legacy_backfill_when_run_then_mirrors_every_subtopic_one_to_one(
        self, db_session: AsyncSession
    ) -> None:
        _, _, subtopics = await self._scope(
            db_session,
            [("A", "Analyse a persuasive text."), ("B", "Write a formal letter.")],
        )
        stats = Stats()

        await run_legacy_backfill(db_session, stats, dry_run=False)
        await db_session.commit()

        assert stats.created >= 2
        for subtopic in subtopics:
            rows = await db_session.execute(
                select(LearningObjective)
                .join(SubtopicObjective, SubtopicObjective.learning_objective_id == LearningObjective.id)
                .where(SubtopicObjective.subtopic_id == subtopic.id)
            )
            objective = rows.scalar_one()
            # Deterministic: the objective text is copied verbatim, never inferred.
            assert objective.learning_objective == subtopic.learning_objective
            # No embeddings are required for this mode to be correct.
            assert objective.embedding is None

    async def test_legacy_backfill_when_questions_present_then_bound_via_subtopic(
        self, db_session: AsyncSession
    ) -> None:
        _, _, subtopics = await self._scope(
            db_session,
            [("A", "Analyse a persuasive text."), ("B", "Write a formal letter.")],
            with_questions=True,
        )
        stats = Stats()

        await run_legacy_backfill(db_session, stats, dry_run=False)
        bound = await bind_questions_via_subtopic(db_session, dry_run=False)
        await db_session.commit()

        assert bound >= 2
        for subtopic in subtopics:
            rows = await db_session.execute(select(QuestionBank).where(QuestionBank.subtopic_id == subtopic.id))
            question = rows.scalar_one()
            assert question.learning_objective_id is not None

            link = await db_session.execute(
                select(SubtopicObjective.learning_objective_id).where(SubtopicObjective.subtopic_id == subtopic.id)
            )
            assert question.learning_objective_id == link.scalar_one()

    async def test_dry_run_when_used_then_writes_nothing(self, db_session: AsyncSession) -> None:
        _, _, subtopics = await self._scope(db_session, [("A", "Analyse a persuasive text.")])
        before = await db_session.execute(text("SELECT count(*) FROM learning_objectives"))
        baseline = before.scalar_one()

        stats = Stats()
        await run_legacy_backfill(db_session, stats, dry_run=True)
        await db_session.rollback()

        after = await db_session.execute(text("SELECT count(*) FROM learning_objectives"))
        assert after.scalar_one() == baseline
        # The count is still reported, so a dry run is a usable preview.
        assert stats.created >= 1

    async def test_canonical_codes_when_many_objectives_then_all_unique(self, db_session: AsyncSession) -> None:
        """canonical_code is UNIQUE; a generator collision would abort the whole run."""
        await self._scope(
            db_session,
            [(f"S{i}", "Order and use negative numbers in context.") for i in range(12)],
        )
        stats = Stats()

        await run_legacy_backfill(db_session, stats, dry_run=False)
        await db_session.commit()

        rows = await db_session.execute(select(LearningObjective.canonical_code))
        codes = [r[0] for r in rows]
        assert len(codes) == len(set(codes))
