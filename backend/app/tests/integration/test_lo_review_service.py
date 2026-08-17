"""Integration tests for the curriculum-mapping review queue.

The behaviours that matter: approving actually binds the questions, rejecting binds
nothing, an item cannot be resolved twice, and re-running the remap pipeline never
reopens a decision a human has already made.
"""

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.curriculum import (
    Grade,
    LearningObjective,
    LearningObjectiveReviewItem,
    QuestionBank,
    Topic,
)
from app.models.school import School
from app.models.user import User, UserRole
from app.services.lo_review_service import (
    ITEM_TYPE_GRADE_SPLIT,
    ITEM_TYPE_QUESTION_REMAP,
    STATUS_APPROVED,
    STATUS_PENDING,
    STATUS_REJECTED,
    STATUS_SPLIT,
    LoReviewService,
    upsert_review_item,
)


@pytest.mark.asyncio
class TestLoReviewQueue:
    async def _objective(self, db: AsyncSession, code_suffix: str = "") -> LearningObjective:
        topic = Topic(id=uuid.uuid4(), name="T", canonical_code=f"T{uuid.uuid4().hex[:8]}")
        db.add(topic)
        await db.flush()
        # grade_id is NOT NULL since ADR-003 T4. Reused rather than created per call:
        # grades.level is globally UNIQUE, so a second Grade 7 in one test collides.
        # Sharing it is safe here because each call makes its own topic, and identity is
        # (topic_id, grade_id, normalised_objective).
        grade = (await db.execute(select(Grade).where(Grade.level == 7))).scalar_one_or_none()
        if grade is None:
            grade = Grade(id=uuid.uuid4(), name="Grade 7", level=7)
            db.add(grade)
            await db.flush()
        objective = LearningObjective(
            id=uuid.uuid4(),
            canonical_code=f"LO-{code_suffix}{uuid.uuid4().hex[:8]}",
            name="Objective",
            learning_objective="Order negative integers.",
            normalised_objective="order negative integers",
            topic_id=topic.id,
            grade_id=grade.id,
            is_active=True,
        )
        db.add(objective)
        await db.flush()
        return objective

    async def _unbound_questions(self, db: AsyncSession, count: int) -> list[QuestionBank]:
        """Questions in the post-wipe state: no subtopic, no objective."""
        questions = []
        for _ in range(count):
            q = QuestionBank(
                id=uuid.uuid4(),
                subtopic_id=None,
                learning_objective_id=None,
                question_text="Q?",
                question_type="MCQ",
                options=[{"key": "A", "text": "1"}],
                correct_answer="A",
                canonical_form=f"q-{uuid.uuid4().hex[:10]}",
                problem_signature={},
                difficulty_level=2.0,
                source="bank",
                is_active=True,
            )
            db.add(q)
            questions.append(q)
        await db.flush()
        return questions

    async def _reviewer(self, db: AsyncSession) -> User:
        school = School(id=uuid.uuid4(), name="S", slug=f"s-{uuid.uuid4().hex[:8]}", status="active")
        db.add(school)
        await db.flush()
        user = User(
            id=uuid.uuid4(),
            school_id=None,
            email=f"admin-{uuid.uuid4().hex[:8]}@kaihle.com",
            first_name="Admin",
            last_name="User",
            role=UserRole.KAIHLE_ADMIN,
            is_active=True,
        )
        db.add(user)
        await db.flush()
        return user

    async def _item(
        self, db: AsyncSession, questions: list[QuestionBank], objective: LearningObjective
    ) -> LearningObjectiveReviewItem:
        item = LearningObjectiveReviewItem(
            id=uuid.uuid4(),
            item_type=ITEM_TYPE_QUESTION_REMAP,
            status=STATUS_PENDING,
            source_code=f"OLD-{uuid.uuid4().hex[:8]}",
            source_name="Old Subtopic",
            source_learning_objective="Old objective text.",
            subject_code="MATH",
            grade_level=7,
            question_count=len(questions),
            candidates=[
                {
                    "objective_id": str(objective.id),
                    "canonical_code": objective.canonical_code,
                    "learning_objective": objective.learning_objective,
                    "similarity": 0.72,
                }
            ],
            question_ids=[str(q.id) for q in questions],
        )
        db.add(item)
        await db.commit()
        return item

    async def test_approve_when_called_then_binds_every_question_in_the_group(self, db_session: AsyncSession) -> None:
        """One decision covers the whole group — that is the point of the design."""
        objective = await self._objective(db_session)
        questions = await self._unbound_questions(db_session, 5)
        item = await self._item(db_session, questions, objective)
        reviewer = await self._reviewer(db_session)

        result = await LoReviewService(db_session).approve_item(item.id, objective.id, reviewer.id)

        assert result["questions_bound"] == 5
        rows = await db_session.execute(select(QuestionBank).where(QuestionBank.id.in_([q.id for q in questions])))
        assert all(q.learning_objective_id == objective.id for q in rows.scalars())

    async def test_approve_when_called_then_records_who_decided_and_when(self, db_session: AsyncSession) -> None:
        objective = await self._objective(db_session)
        item = await self._item(db_session, await self._unbound_questions(db_session, 1), objective)
        reviewer = await self._reviewer(db_session)

        await LoReviewService(db_session).approve_item(item.id, objective.id, reviewer.id, admin_note="looks right")

        await db_session.refresh(item)
        assert item.status == STATUS_APPROVED
        assert item.chosen_objective_id == objective.id
        assert item.resolved_by == reviewer.id
        assert item.resolved_at is not None
        assert item.admin_note == "looks right"

    async def test_approve_when_objective_is_not_a_candidate_then_still_allowed(self, db_session: AsyncSession) -> None:
        """Candidates are the machine's shortlist. A curriculum specialist may know a
        better target, and must not be boxed into the top three."""
        listed = await self._objective(db_session, "listed-")
        other = await self._objective(db_session, "other-")
        item = await self._item(db_session, await self._unbound_questions(db_session, 2), listed)
        reviewer = await self._reviewer(db_session)

        result = await LoReviewService(db_session).approve_item(item.id, other.id, reviewer.id)

        assert result["questions_bound"] == 2
        await db_session.refresh(item)
        assert item.chosen_objective_id == other.id

    async def test_approve_when_objective_does_not_exist_then_404(self, db_session: AsyncSession) -> None:
        objective = await self._objective(db_session)
        item = await self._item(db_session, await self._unbound_questions(db_session, 1), objective)
        reviewer = await self._reviewer(db_session)

        with pytest.raises(HTTPException) as exc:
            await LoReviewService(db_session).approve_item(item.id, uuid.uuid4(), reviewer.id)
        assert exc.value.status_code == 404

    async def test_approve_when_item_already_resolved_then_409(self, db_session: AsyncSession) -> None:
        """Two reviewers working the same queue must not both resolve one item."""
        objective = await self._objective(db_session)
        item = await self._item(db_session, await self._unbound_questions(db_session, 1), objective)
        reviewer = await self._reviewer(db_session)

        await LoReviewService(db_session).approve_item(item.id, objective.id, reviewer.id)

        with pytest.raises(HTTPException) as exc:
            await LoReviewService(db_session).approve_item(item.id, objective.id, reviewer.id)
        assert exc.value.status_code == 409

    async def test_reject_when_called_then_binds_nothing_and_closes_item(self, db_session: AsyncSession) -> None:
        """Rejecting leaves the questions as a reported gap, which is the honest
        outcome when no candidate assesses the same skill."""
        objective = await self._objective(db_session)
        questions = await self._unbound_questions(db_session, 3)
        item = await self._item(db_session, questions, objective)
        reviewer = await self._reviewer(db_session)

        result = await LoReviewService(db_session).reject_item(item.id, reviewer.id, admin_note="no match")

        assert result["questions_bound"] == 0
        await db_session.refresh(item)
        assert item.status == STATUS_REJECTED
        assert item.chosen_objective_id is None
        rows = await db_session.execute(select(QuestionBank).where(QuestionBank.id.in_([q.id for q in questions])))
        assert all(q.learning_objective_id is None for q in rows.scalars())

    async def test_approve_when_question_already_bound_then_existing_binding_wins(
        self, db_session: AsyncSession
    ) -> None:
        """Only NULLs are filled — a binding made by another route is not overwritten."""
        objective = await self._objective(db_session, "a-")
        other = await self._objective(db_session, "b-")
        questions = await self._unbound_questions(db_session, 2)
        questions[0].learning_objective_id = other.id
        await db_session.flush()
        item = await self._item(db_session, questions, objective)
        reviewer = await self._reviewer(db_session)

        result = await LoReviewService(db_session).approve_item(item.id, objective.id, reviewer.id)

        assert result["questions_bound"] == 1
        await db_session.refresh(questions[0])
        assert questions[0].learning_objective_id == other.id

    async def test_list_when_multiple_items_then_ordered_by_blast_radius(self, db_session: AsyncSession) -> None:
        """A reviewer with limited time should see the biggest decisions first."""
        objective = await self._objective(db_session)
        await self._item(db_session, await self._unbound_questions(db_session, 2), objective)
        await self._item(db_session, await self._unbound_questions(db_session, 9), objective)

        result = await LoReviewService(db_session).list_items()

        counts = [i["question_count"] for i in result["items"]]
        assert counts == sorted(counts, reverse=True)

    async def test_upsert_when_item_already_resolved_then_does_not_reopen_it(self, db_session: AsyncSession) -> None:
        """Re-running the remap pipeline must never undo a human decision."""
        objective = await self._objective(db_session)
        item = await self._item(db_session, await self._unbound_questions(db_session, 1), objective)
        reviewer = await self._reviewer(db_session)
        await LoReviewService(db_session).approve_item(item.id, objective.id, reviewer.id)

        written = await upsert_review_item(
            db_session,
            item_type=ITEM_TYPE_QUESTION_REMAP,
            source_code=item.source_code,
            source_name="changed",
            source_learning_objective="changed",
            subject_code="MATH",
            grade_level=7,
            question_ids=[str(uuid.uuid4())],
            candidates=[],
        )
        await db_session.commit()

        assert written is False
        await db_session.refresh(item)
        assert item.status == STATUS_APPROVED
        assert item.source_name == "Old Subtopic"

    async def test_upsert_when_item_still_pending_then_refreshes_it(self, db_session: AsyncSession) -> None:
        objective = await self._objective(db_session)
        item = await self._item(db_session, await self._unbound_questions(db_session, 1), objective)

        written = await upsert_review_item(
            db_session,
            item_type=ITEM_TYPE_QUESTION_REMAP,
            source_code=item.source_code,
            source_name="refreshed",
            source_learning_objective="refreshed objective",
            subject_code="SCI",
            grade_level=8,
            question_ids=[str(uuid.uuid4()), str(uuid.uuid4())],
            candidates=[],
        )
        await db_session.commit()

        assert written is True
        await db_session.refresh(item)
        assert item.source_name == "refreshed"
        assert item.question_count == 2

    async def test_search_objectives_when_query_matches_then_returns_them(self, db_session: AsyncSession) -> None:
        objective = await self._objective(db_session)

        results = await LoReviewService(db_session).search_objectives("negative integers")

        assert any(r["objective_id"] == str(objective.id) for r in results)

    async def test_counts_when_queue_has_items_then_reports_every_status(self, db_session: AsyncSession) -> None:
        objective = await self._objective(db_session)
        await self._item(db_session, await self._unbound_questions(db_session, 1), objective)

        counts = await LoReviewService(db_session).counts_by_status()

        assert set(counts) == {STATUS_PENDING, STATUS_APPROVED, STATUS_REJECTED, STATUS_SPLIT}
        assert counts[STATUS_PENDING] >= 1


@pytest.mark.asyncio
class TestGradeSplitItems:
    """OBJECTIVE_GRADE_SPLIT breaks the queue's oldest assumption, deliberately.

    Every other item type governs questions with learning_objective_id IS NULL, and every
    path is built on that: approve fills NULLs, the card counts NULLs, split adjudicates
    which concept an unbound question assesses. A grade-split item's questions arrive
    ALREADY bound — to the lowest-grade copy of one objective, which the T3 script
    assigned as a placeholder because it had to bind them to something. The open question
    is which grade, not which objective.

    Left unhandled, that is not a crash but something worse: approve binds zero rows and
    still closes the item APPROVED, so a reviewer is told their decision was applied when
    nothing moved.
    """

    async def _graded_objective(
        self, db: AsyncSession, level: int, topic_id: uuid.UUID | None = None
    ) -> LearningObjective:
        if topic_id is None:
            topic = Topic(id=uuid.uuid4(), name="T", canonical_code=f"T{uuid.uuid4().hex[:8]}")
            db.add(topic)
            await db.flush()
            topic_id = topic.id
        grade = Grade(id=uuid.uuid4(), name=f"Grade {level}", level=level)
        db.add(grade)
        await db.flush()
        objective = LearningObjective(
            id=uuid.uuid4(),
            canonical_code=f"LO-G{level}-{uuid.uuid4().hex[:8]}",
            name="Objective",
            learning_objective="Order a set of decimal numbers",
            normalised_objective="order a set of decimal numbers",
            topic_id=topic_id,
            grade_id=grade.id,
            is_active=True,
        )
        db.add(objective)
        await db.flush()
        return objective

    async def _bound_question(self, db: AsyncSession, objective_id: uuid.UUID) -> QuestionBank:
        question = QuestionBank(
            id=uuid.uuid4(),
            subtopic_id=None,
            learning_objective_id=objective_id,
            question_text="Q?",
            question_type="MCQ",
            options=[{"key": "A", "text": "1"}],
            correct_answer="A",
            canonical_form=f"q-{uuid.uuid4().hex[:10]}",
            problem_signature={},
            difficulty_level=2.0,
            source="bank",
            is_active=True,
        )
        db.add(question)
        await db.flush()
        return question

    async def _grade_split_item(
        self,
        db: AsyncSession,
        questions: list[QuestionBank],
        copies: list[LearningObjective],
    ) -> LearningObjectiveReviewItem:
        item = LearningObjectiveReviewItem(
            id=uuid.uuid4(),
            item_type=ITEM_TYPE_GRADE_SPLIT,
            status=STATUS_PENDING,
            source_code=f"SPLIT-{uuid.uuid4().hex[:8]}",
            source_name="Ordering decimals — taught at grades 6, 7",
            source_learning_objective="Order a set of decimal numbers",
            subject_code="MATH",
            grade_level=None,
            question_count=len(questions),
            candidates=[
                {
                    "objective_id": str(objective.id),
                    "canonical_code": objective.canonical_code,
                    "learning_objective": objective.learning_objective,
                }
                for objective in copies
            ],
            question_ids=[str(q.id) for q in questions],
        )
        db.add(item)
        await db.commit()
        return item

    async def _reviewer(self, db: AsyncSession) -> User:
        user = User(
            id=uuid.uuid4(),
            school_id=None,
            email=f"admin-{uuid.uuid4().hex[:8]}@kaihle.com",
            first_name="Admin",
            last_name="User",
            role=UserRole.KAIHLE_ADMIN,
            is_active=True,
        )
        db.add(user)
        await db.flush()
        return user

    async def test_approve_when_grade_split_then_rebinds_already_bound_questions(
        self, db_session: AsyncSession
    ) -> None:
        """The regression that matters: fill-NULL would bind 0 and still report success."""
        lowest = await self._graded_objective(db_session, 6)
        higher = await self._graded_objective(db_session, 7, lowest.topic_id)
        questions = [await self._bound_question(db_session, lowest.id) for _ in range(3)]
        item = await self._grade_split_item(db_session, questions, [lowest, higher])
        reviewer = await self._reviewer(db_session)

        result = await LoReviewService(db_session).approve_item(item.id, higher.id, reviewer.id)

        assert result["questions_bound"] == 3
        rows = await db_session.execute(select(QuestionBank).where(QuestionBank.id.in_([q.id for q in questions])))
        assert all(q.learning_objective_id == higher.id for q in rows.scalars())

    async def test_approve_when_question_moved_outside_candidates_then_left_alone(
        self, db_session: AsyncSession
    ) -> None:
        """Re-binding is scoped to the item's own grade copies.

        Widening approve to "overwrite whatever is there" would let a stale card undo a
        binding some other route made deliberately. The scope is the decision's own
        candidates, which is exactly the set the split put these questions in.
        """
        lowest = await self._graded_objective(db_session, 6)
        higher = await self._graded_objective(db_session, 7, lowest.topic_id)
        elsewhere = await self._graded_objective(db_session, 8)
        stays = await self._bound_question(db_session, elsewhere.id)
        moves = await self._bound_question(db_session, lowest.id)
        item = await self._grade_split_item(db_session, [stays, moves], [lowest, higher])
        reviewer = await self._reviewer(db_session)

        result = await LoReviewService(db_session).approve_item(item.id, higher.id, reviewer.id)

        assert result["questions_bound"] == 1
        await db_session.refresh(stays)
        await db_session.refresh(moves)
        assert stays.learning_objective_id == elsewhere.id
        assert moves.learning_objective_id == higher.id

    async def test_approve_when_not_grade_split_then_still_only_fills_nulls(self, db_session: AsyncSession) -> None:
        """The new branch must not loosen binding for the types it does not apply to."""
        already_bound_to = await self._graded_objective(db_session, 6)
        target = await self._graded_objective(db_session, 7)
        question = await self._bound_question(db_session, already_bound_to.id)
        item = LearningObjectiveReviewItem(
            id=uuid.uuid4(),
            item_type=ITEM_TYPE_QUESTION_REMAP,
            status=STATUS_PENDING,
            source_code=f"OLD-{uuid.uuid4().hex[:8]}",
            source_name="Old Subtopic",
            source_learning_objective="Old objective text.",
            subject_code="MATH",
            grade_level=7,
            question_count=1,
            candidates=[{"objective_id": str(already_bound_to.id), "canonical_code": already_bound_to.canonical_code}],
            question_ids=[str(question.id)],
        )
        db_session.add(item)
        await db_session.commit()
        reviewer = await self._reviewer(db_session)

        result = await LoReviewService(db_session).approve_item(item.id, target.id, reviewer.id)

        assert result["questions_bound"] == 0
        await db_session.refresh(question)
        assert question.learning_objective_id == already_bound_to.id

    async def test_list_items_when_grade_split_pending_then_reports_whole_group_outstanding(
        self, db_session: AsyncSession
    ) -> None:
        """Counting NULL bindings would print "All assigned" on an undecided card."""
        lowest = await self._graded_objective(db_session, 6)
        higher = await self._graded_objective(db_session, 7, lowest.topic_id)
        questions = [await self._bound_question(db_session, lowest.id) for _ in range(4)]
        item = await self._grade_split_item(db_session, questions, [lowest, higher])

        result = await LoReviewService(db_session).list_items(item_type=ITEM_TYPE_GRADE_SPLIT)

        card = next(row for row in result["items"] if row["id"] == str(item.id))
        assert card["unbound_count"] == 4

    async def test_list_items_when_grade_split_resolved_then_nothing_outstanding(
        self, db_session: AsyncSession
    ) -> None:
        lowest = await self._graded_objective(db_session, 6)
        higher = await self._graded_objective(db_session, 7, lowest.topic_id)
        questions = [await self._bound_question(db_session, lowest.id) for _ in range(2)]
        item = await self._grade_split_item(db_session, questions, [lowest, higher])
        reviewer = await self._reviewer(db_session)
        await LoReviewService(db_session).approve_item(item.id, higher.id, reviewer.id)

        result = await LoReviewService(db_session).list_items(status_filter=STATUS_APPROVED)

        card = next(row for row in result["items"] if row["id"] == str(item.id))
        assert card["unbound_count"] == 0

    async def test_split_when_item_is_grade_split_then_409_rather_than_coin_toss(
        self, db_session: AsyncSession
    ) -> None:
        """Auto-split adjudicates concept by embedding similarity.

        Every candidate here is the same objective text at a different grade, so the
        embeddings are identical and the model would be picking between indistinguishable
        strings. Judging grade means judging demand — a different question, and one this
        path was never built to ask.
        """
        lowest = await self._graded_objective(db_session, 6)
        higher = await self._graded_objective(db_session, 7, lowest.topic_id)
        questions = [await self._bound_question(db_session, lowest.id)]
        item = await self._grade_split_item(db_session, questions, [lowest, higher])
        reviewer = await self._reviewer(db_session)

        with pytest.raises(HTTPException) as exc:
            await LoReviewService(db_session).split_item(item.id, reviewer.id)

        assert exc.value.status_code == 409
        assert "grade" in str(exc.value.detail).lower()
        await db_session.refresh(item)
        assert item.status == STATUS_PENDING
