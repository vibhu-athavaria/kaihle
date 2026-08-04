"""Unit tests for per-question adjudication during a split.

A wrong binding here is silent: the question is served to students as evidence of a
skill it does not test, and nothing downstream detects it. Every failure mode must
therefore decline rather than guess, which is what these tests pin down.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.curriculum import LearningObjectiveReviewItem
from app.services.lo_review_service import LoReviewService, adjudicate_question


def _review_item(
    question_ids: list[str] | None = None,
    question_count: int | None = None,
    candidates: list[dict] | None = None,
) -> LearningObjectiveReviewItem:
    """A real model instance rather than a stand-in.

    Every attribute the code under test reads is set explicitly: SQLAlchemy applies
    column defaults at flush, so an unsaved instance leaves them None and a fake would
    quietly diverge from the real row shape.
    """
    ids = question_ids if question_ids is not None else []
    return LearningObjectiveReviewItem(
        id=uuid.uuid4(),
        item_type="QUESTION_REMAP",
        status="PENDING",
        source_code="MATH-NUM-G6-04",
        source_name="Ratio and Proportion",
        source_learning_objective="Write and simplify ratios.",
        subject_code="MATH",
        grade_level=6,
        question_count=question_count if question_count is not None else len(ids),
        question_ids=ids,
        candidates=candidates if candidates is not None else [],
        llm_suggested_code=None,
        llm_reason=None,
        chosen_objective_id=None,
        resolved_by=None,
        resolved_at=None,
        admin_note=None,
    )


def _question(text: str = "What is 3:4 simplified?") -> dict:
    return {
        "id": "11111111-1111-1111-1111-111111111111",
        "question_text": text,
        "options": [{"key": "A", "text": "3:4"}],
    }


def _context(candidate_count: int = 3) -> dict:
    return {
        "subject_code": "MATH",
        "grade_level": 6,
        "old_learning_objective": "Write and simplify ratios; divide a quantity.",
        "candidates": [
            {
                "objective_id": f"0000000{i}-0000-0000-0000-000000000000",
                "canonical_code": f"MATH-CODE-{i}",
                "learning_objective": f"Candidate {i}.",
                "similarity": 0.7,
            }
            for i in range(1, candidate_count + 1)
        ],
    }


@pytest.mark.asyncio
class TestAdjudicateQuestion:
    @staticmethod
    def _reply(text: str) -> AsyncMock:
        return AsyncMock(return_value=text)

    async def test_when_model_picks_candidate_then_returns_its_code(self) -> None:
        with patch("app.services.lo_review_service.complete", self._reply('{"choice": 2}')):
            assert await adjudicate_question(_question(), _context()) == "MATH-CODE-2"

    async def test_when_reply_is_fenced_then_still_parsed(self) -> None:
        """Models wrap JSON in a code fence regardless of instructions."""
        with patch(
            "app.services.lo_review_service.complete",
            self._reply('```json\n{"choice": 1, "confidence": "high"}\n```'),
        ):
            assert await adjudicate_question(_question(), _context()) == "MATH-CODE-1"

    async def test_when_model_declines_then_returns_none(self) -> None:
        with patch("app.services.lo_review_service.complete", self._reply('{"choice": null}')):
            assert await adjudicate_question(_question(), _context()) is None

    async def test_when_choice_out_of_range_then_returns_none(self) -> None:
        # Binding to a candidate never offered would be arbitrary.
        with patch("app.services.lo_review_service.complete", self._reply('{"choice": 9}')):
            assert await adjudicate_question(_question(), _context(3)) is None

    async def test_when_choice_is_zero_then_returns_none(self) -> None:
        """Candidates are 1-indexed; 0 would silently select the last one."""
        with patch("app.services.lo_review_service.complete", self._reply('{"choice": 0}')):
            assert await adjudicate_question(_question(), _context()) is None

    async def test_when_choice_not_an_integer_then_returns_none(self) -> None:
        with patch("app.services.lo_review_service.complete", self._reply('{"choice": "MATH-CODE-1"}')):
            assert await adjudicate_question(_question(), _context()) is None

    async def test_when_reply_unparseable_then_returns_none(self) -> None:
        with patch(
            "app.services.lo_review_service.complete",
            self._reply("I think candidate 2 fits best."),
        ):
            assert await adjudicate_question(_question(), _context()) is None

    async def test_when_provider_raises_then_returns_none(self) -> None:
        """A provider outage must leave questions unbound, never abort the split."""
        with patch(
            "app.services.lo_review_service.complete",
            AsyncMock(side_effect=RuntimeError("boom")),
        ):
            assert await adjudicate_question(_question(), _context()) is None

    async def test_when_called_then_uses_deterministic_sampling(self) -> None:
        mock = self._reply('{"choice": 1}')
        with patch("app.services.lo_review_service.complete", mock):
            await adjudicate_question(_question(), _context())

        assert mock.call_args.kwargs["temperature"] == 0.0
        assert mock.call_args.args[0] == "lo_matching"

    async def test_when_called_then_prompt_carries_question_and_candidates(self) -> None:
        mock = self._reply('{"choice": 1}')
        with patch("app.services.lo_review_service.complete", mock):
            await adjudicate_question(_question("What is 6:8 simplified?"), _context())

        prompt = mock.call_args.args[1][0]["content"]
        assert "What is 6:8 simplified?" in prompt
        assert "MATH-CODE-1" in prompt
        # The old objective is included so the model knows why the group is splitting.
        assert "Write and simplify ratios" in prompt

    async def test_when_candidate_lacks_a_code_then_returns_none(self) -> None:
        context = _context(1)
        context["candidates"][0].pop("canonical_code")
        with patch("app.services.lo_review_service.complete", self._reply('{"choice": 1}')):
            assert await adjudicate_question(_question(), context) is None


class TestSerialise:
    """The list payload the review screen renders."""

    @staticmethod
    def _item() -> LearningObjectiveReviewItem:
        return _review_item(question_count=103, candidates=[{"canonical_code": "MATH-X"}])

    def test_serialise_when_unresolved_then_ids_are_null_not_missing(self) -> None:
        payload = LoReviewService._serialise(self._item())

        # The client distinguishes "no decision yet" from "field absent"; emitting the
        # key with null keeps that unambiguous.
        assert payload["chosen_objective_id"] is None
        assert payload["resolved_at"] is None

    def test_serialise_when_called_then_carries_the_blast_radius(self) -> None:
        payload = LoReviewService._serialise(self._item())

        # question_count drives ordering and the confirm-button label.
        assert payload["question_count"] == 103
        assert payload["source_name"] == "Ratio and Proportion"


@pytest.mark.asyncio
class TestUnboundCounts:
    """Drives the "N still unassigned" badge — the only way a reviewer can tell a
    finished split from an unfinished one without opening every card."""

    @staticmethod
    def _service(unbound_ids: list[uuid.UUID]) -> LoReviewService:
        rows = MagicMock()
        rows.all.return_value = [(qid,) for qid in unbound_ids]
        db = MagicMock()
        db.execute = AsyncMock(return_value=rows)
        return LoReviewService(db)

    async def test_counts_only_the_questions_still_unbound(self) -> None:
        q1, q2, q3 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        item = _review_item(question_ids=[str(q1), str(q2), str(q3)])
        service = self._service([q1, q3])

        counts = await service._unbound_counts([item])

        assert counts[str(item.id)] == 2

    async def test_when_all_bound_then_zero(self) -> None:
        item = _review_item(question_ids=[str(uuid.uuid4())])
        service = self._service([])

        assert (await service._unbound_counts([item]))[str(item.id)] == 0

    async def test_when_no_items_have_questions_then_no_query_is_issued(self) -> None:
        db = MagicMock()
        db.execute = AsyncMock()
        service = LoReviewService(db)

        assert await service._unbound_counts([_review_item(question_ids=[])]) == {}
        db.execute.assert_not_awaited()

    async def test_attributes_shared_questions_to_every_item_holding_them(self) -> None:
        """A remainder item's questions also belong to its parent split group, so one
        unbound question must be counted against both."""
        shared = uuid.uuid4()
        parent = _review_item(question_ids=[str(shared), str(uuid.uuid4())])
        child = _review_item(question_ids=[str(shared)])
        service = self._service([shared])

        counts = await service._unbound_counts([parent, child])

        assert counts[str(parent.id)] == 1
        assert counts[str(child.id)] == 1


@pytest.mark.asyncio
class TestCountsByStatus:
    async def test_absent_statuses_report_zero_not_missing(self) -> None:
        """The tab badges read every key unconditionally; a missing one renders NaN."""
        rows = MagicMock()
        rows.all.return_value = [("PENDING", 7)]
        db = MagicMock()
        db.execute = AsyncMock(return_value=rows)

        counts = await LoReviewService(db).counts_by_status()

        assert counts == {"PENDING": 7, "APPROVED": 0, "REJECTED": 0, "SPLIT": 0}


@pytest.mark.asyncio
class TestListItems:
    @staticmethod
    def _service(items: list[LearningObjectiveReviewItem], total: int, unbound_ids: list[uuid.UUID]) -> LoReviewService:
        total_row = MagicMock()
        total_row.scalar_one.return_value = total
        item_rows = MagicMock()
        item_rows.scalars.return_value.all.return_value = items
        unbound_rows = MagicMock()
        unbound_rows.all.return_value = [(qid,) for qid in unbound_ids]

        db = MagicMock()
        db.execute = AsyncMock(side_effect=[total_row, item_rows, unbound_rows])
        return LoReviewService(db)

    async def test_each_row_carries_its_unbound_count(self) -> None:
        q1, q2 = uuid.uuid4(), uuid.uuid4()
        item = _review_item(question_ids=[str(q1), str(q2)])
        service = self._service([item], total=1, unbound_ids=[q2])

        result = await service.list_items()

        assert result["total"] == 1
        assert result["items"][0]["unbound_count"] == 1

    async def test_item_without_questions_reports_zero_unbound(self) -> None:
        # _unbound_counts returns {} for these, so the lookup must default rather
        # than KeyError — an empty item is a data defect, not a crash.
        item = _review_item(question_ids=[])
        service = self._service([item], total=1, unbound_ids=[])

        result = await service.list_items(status_filter="SPLIT", item_type="QUESTION_REMAP")

        assert result["items"][0]["unbound_count"] == 0


@pytest.mark.asyncio
class TestResolveCompletedItems:
    """An item worked question-by-question must leave the queue on its own.

    Before this existed, a reviewer could bind all 54 questions of a remainder item and
    the card stayed PENDING forever — finished work was indistinguishable from
    outstanding work without opening every card.
    """

    @staticmethod
    def _service(item: LearningObjectiveReviewItem | None, bindings: list[tuple[object, ...]]) -> LoReviewService:
        """Wire a db whose first execute() yields the item, second the bindings."""
        candidates = MagicMock()
        candidates.scalars.return_value.all.return_value = [item] if item else []
        binding_rows = MagicMock()
        binding_rows.all.return_value = bindings

        db = MagicMock()
        db.execute = AsyncMock(side_effect=[candidates, binding_rows])
        return LoReviewService(db)

    @staticmethod
    def _item(question_count: int = 3) -> LearningObjectiveReviewItem:
        return _review_item(question_ids=[str(uuid.uuid4()) for _ in range(question_count)])

    async def test_when_all_bound_to_one_objective_then_marks_approved(self) -> None:
        item = self._item(3)
        one = uuid.uuid4()
        service = self._service(item, [(one,), (one,), (one,)])

        resolved = await service._resolve_completed_items([uuid.uuid4()], uuid.uuid4())

        # A single objective across the whole group is an approval by another name.
        assert item.status == "APPROVED"
        assert resolved[0]["status"] == "APPROVED"

    async def test_when_bound_across_several_objectives_then_marks_split(self) -> None:
        item = self._item(3)
        service = self._service(item, [(uuid.uuid4(),), (uuid.uuid4(),), (uuid.uuid4(),)])

        await service._resolve_completed_items([uuid.uuid4()], uuid.uuid4())

        # Recording SPLIT rather than APPROVED keeps the audit trail honest about how
        # the group was actually resolved.
        assert item.status == "SPLIT"

    async def test_when_any_question_unbound_then_stays_pending(self) -> None:
        item = self._item(3)
        service = self._service(item, [(uuid.uuid4(),), (None,), (uuid.uuid4(),)])

        assert await service._resolve_completed_items([uuid.uuid4()], uuid.uuid4()) == []
        assert item.status == "PENDING"
        assert item.resolved_at is None

    async def test_when_item_has_no_questions_then_stays_pending(self) -> None:
        """An empty item is a data defect, not a completed one."""
        item = self._item(0)
        service = self._service(item, [])

        assert await service._resolve_completed_items([uuid.uuid4()], uuid.uuid4()) == []
        assert item.status == "PENDING"

    async def test_when_resolved_then_records_reviewer_and_time(self) -> None:
        item = self._item(2)
        one = uuid.uuid4()
        reviewer = uuid.uuid4()
        service = self._service(item, [(one,), (one,)])

        await service._resolve_completed_items([uuid.uuid4()], reviewer)

        assert item.resolved_by == reviewer
        assert item.resolved_at is not None
        assert "2 questions" in (item.admin_note or "")


@pytest.mark.asyncio
class TestWithPlacements:
    """Placement attachment is what lets a reviewer tell a Grade 6 objective from a
    Grade 12 one; every search return path must apply it."""

    async def test_attaches_placements_by_objective_id(self) -> None:
        service = LoReviewService(MagicMock())
        with patch.object(
            service,
            "_placements_for",
            AsyncMock(return_value={"1": [{"subject_code": "MATH", "grade_level": 6, "topic_name": "Fractions"}]}),
        ):
            result = await service._with_placements([{"objective_id": "1"}, {"objective_id": "2"}])

        assert result[0]["placements"][0]["grade_level"] == 6
        # An objective with no placement gets an empty list, never a missing key —
        # the UI renders that as an explicit data defect.
        assert result[1]["placements"] == []

    async def test_when_no_results_then_returns_empty_without_querying(self) -> None:
        service = LoReviewService(MagicMock())
        with patch.object(service, "_placements_for", AsyncMock(return_value={})) as mock:
            assert await service._with_placements([]) == []
        mock.assert_awaited_once_with([])
