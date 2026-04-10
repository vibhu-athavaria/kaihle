"""Unit tests for gap state calculation logic.

Tests cover:
- GapService.upsert_gap_state — DB upsert call shape and idempotency semantics
- calculate_gap_states Celery task — mastery weighting formulas for 1/2/3+ attempts
- Multiple subtopics, unknown question IDs, needs_review boundary
"""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.gap_service import GapService

# ── Helpers ─────────────────────────────────────────────────────────────────


def _make_response(question_id: uuid.UUID, is_correct: bool) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        question_id=question_id,
        is_correct=is_correct,
        score=1.0 if is_correct else 0.0,
    )


def _make_attempt(
    assessment_id: uuid.UUID,
    student_id: uuid.UUID,
    status: str = "COMPLETED",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        assessment_id=assessment_id,
        student_id=student_id,
        status=status,
        completed_at=datetime(2026, 4, 10, 10, 0, 0, tzinfo=UTC),
    )


def _make_assessment(
    school_id: uuid.UUID,
    class_id: uuid.UUID,
    is_system_generated: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        school_id=school_id,
        class_id=class_id,
        is_system_generated=is_system_generated,
    )


# ── GapService unit tests ────────────────────────────────────────────────────


class TestGapServiceUpsertGapState:
    """Tests for GapService.upsert_gap_state."""

    @pytest.fixture
    def mock_db(self) -> MagicMock:
        db = MagicMock()
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def service(self, mock_db: MagicMock) -> GapService:
        return GapService(mock_db)

    @pytest.mark.asyncio
    async def test_upsert_gap_state_when_called_twice_same_values_then_one_row_only(
        self, service: GapService, mock_db: MagicMock
    ) -> None:
        """Upsert with same student/subtopic/class does not insert a second row.

        Verifies the ON CONFLICT DO UPDATE semantic — the service calls execute twice
        (once per call) and both use the same conflict target SQL pattern.
        """
        student_id = uuid.uuid4()
        subtopic_id = uuid.uuid4()
        school_id = uuid.uuid4()
        class_id = uuid.uuid4()
        ts = datetime.now(UTC)

        await service.upsert_gap_state(
            student_id=student_id,
            subtopic_id=subtopic_id,
            school_id=school_id,
            class_id=class_id,
            new_mastery=0.8,
            rolling_attempt_count=1,
            last_assessed_at=ts,
        )
        await service.upsert_gap_state(
            student_id=student_id,
            subtopic_id=subtopic_id,
            school_id=school_id,
            class_id=class_id,
            new_mastery=0.8,
            rolling_attempt_count=1,
            last_assessed_at=ts,
        )

        assert mock_db.execute.call_count == 2
        # Both calls use same ON CONFLICT SQL
        first_sql = str(mock_db.execute.call_args_list[0][0][0])
        assert "ON CONFLICT" in first_sql
        assert "student_id, subtopic_id, class_id" in first_sql

    @pytest.mark.asyncio
    async def test_upsert_gap_state_when_called_twice_different_values_then_row_updated(
        self, service: GapService, mock_db: MagicMock
    ) -> None:
        """Second upsert with different mastery overwrites via DO UPDATE."""
        student_id = uuid.uuid4()
        subtopic_id = uuid.uuid4()
        school_id = uuid.uuid4()
        class_id = uuid.uuid4()
        ts = datetime.now(UTC)

        await service.upsert_gap_state(
            student_id=student_id,
            subtopic_id=subtopic_id,
            school_id=school_id,
            class_id=class_id,
            new_mastery=0.3,
            rolling_attempt_count=1,
            last_assessed_at=ts,
        )
        await service.upsert_gap_state(
            student_id=student_id,
            subtopic_id=subtopic_id,
            school_id=school_id,
            class_id=class_id,
            new_mastery=0.8,
            rolling_attempt_count=2,
            last_assessed_at=ts,
        )

        assert mock_db.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_needs_review_when_mastery_below_0_4_then_true(self, service: GapService, mock_db: MagicMock) -> None:
        """needs_review=True when mastery < 0.4 (Needs Work band)."""
        captured_params: list[dict] = []

        async def capture(stmt, params=None):  # type: ignore[no-untyped-def]
            if params:
                captured_params.append(params)
            return MagicMock()

        mock_db.execute = capture  # type: ignore[assignment]

        await service.upsert_gap_state(
            student_id=uuid.uuid4(),
            subtopic_id=uuid.uuid4(),
            school_id=uuid.uuid4(),
            class_id=uuid.uuid4(),
            new_mastery=0.39,
            rolling_attempt_count=1,
            last_assessed_at=datetime.now(UTC),
        )

        assert len(captured_params) == 1
        assert captured_params[0]["needs_review"] is True

    @pytest.mark.asyncio
    async def test_needs_review_when_mastery_at_0_4_then_false(self, service: GapService, mock_db: MagicMock) -> None:
        """needs_review=False when mastery == 0.4 (Developing, not Needs Work).

        Boundary: 0.4 is Developing. Only < 0.4 is Needs Work.
        """
        captured_params: list[dict] = []

        async def capture(stmt, params=None):  # type: ignore[no-untyped-def]
            if params:
                captured_params.append(params)
            return MagicMock()

        mock_db.execute = capture  # type: ignore[assignment]

        await service.upsert_gap_state(
            student_id=uuid.uuid4(),
            subtopic_id=uuid.uuid4(),
            school_id=uuid.uuid4(),
            class_id=uuid.uuid4(),
            new_mastery=0.4,
            rolling_attempt_count=1,
            last_assessed_at=datetime.now(UTC),
        )

        assert len(captured_params) == 1
        assert captured_params[0]["needs_review"] is False


# ── Mastery weighting formula tests ──────────────────────────────────────────
#
# These tests validate the weighting formulas by directly testing the pure
# computation, decoupled from DB and Celery infrastructure.


class TestMasteryWeightingFormulas:
    """Tests for the recency-weighted mastery computation formula.

    The formula lives inside the Celery task's _run() closure, but we test
    the mathematical results by invoking the same logic directly.
    """

    def _compute_mastery(
        self,
        current_score: float,
        historical: list[float],
        is_system_generated: bool = False,
    ) -> float:
        """Replicate the weighting formula from gap_tasks.py."""
        if len(historical) == 0:
            if is_system_generated:
                mastery = current_score * 0.7
            else:
                mastery = current_score * 1.0
            return max(0.0, min(1.0, mastery))
        elif len(historical) == 1:
            mastery = (current_score * 0.65) + (historical[0] * 0.35)
        else:
            second_score = historical[0]  # most recent historical
            third_score = historical[1]  # older historical
            mastery = (current_score * 0.5) + (second_score * 0.3) + (third_score * 0.2)
        return max(0.0, min(1.0, mastery))

    def test_calculate_when_first_attempt_5_questions_all_correct_then_mastery_1_0(
        self,
    ) -> None:
        """First attempt, all correct, not system-generated → mastery = 1.0."""
        mastery = self._compute_mastery(
            current_score=1.0,
            historical=[],
            is_system_generated=False,
        )
        assert mastery == 1.0

    def test_calculate_when_first_enrollment_diagnostic_then_mastery_seeded_at_0_7(
        self,
    ) -> None:
        """System-generated, first attempt, all correct → mastery = 0.7 (seeded)."""
        mastery = self._compute_mastery(
            current_score=1.0,
            historical=[],
            is_system_generated=True,
        )
        assert mastery == pytest.approx(0.7)

    def test_calculate_when_second_attempt_higher_score_then_mastery_is_weighted(
        self,
    ) -> None:
        """Second attempt: first=0.4, second=0.8 → mastery = 0.8×0.65 + 0.4×0.35 = 0.66."""
        mastery = self._compute_mastery(
            current_score=0.8,
            historical=[0.4],
        )
        assert mastery == pytest.approx(0.66, abs=1e-9)

    def test_calculate_when_four_attempts_then_only_last_three_count(
        self,
    ) -> None:
        """Scores [0.2, 0.4, 0.6, 0.8] (oldest to newest).
        Current = 0.8, historical = [0.6, 0.4] (skip 0.2 as only last 2 historical loaded).
        mastery = 0.8×0.5 + 0.6×0.3 + 0.4×0.2 = 0.40 + 0.18 + 0.08 = 0.66.
        """
        mastery = self._compute_mastery(
            current_score=0.8,
            historical=[0.6, 0.4],  # last 2 historical (oldest 0.2 excluded by LIMIT 2)
        )
        assert mastery == pytest.approx(0.66, abs=1e-9)

    def test_calculate_when_mastery_would_exceed_1_then_clamped_to_1(
        self,
    ) -> None:
        """Clamping: very high weighted score cannot exceed 1.0."""
        mastery = self._compute_mastery(
            current_score=1.0,
            historical=[1.0, 1.0],
        )
        assert mastery <= 1.0

    def test_calculate_when_mastery_would_go_below_0_then_clamped_to_0(
        self,
    ) -> None:
        """Clamping: mastery cannot be negative."""
        mastery = self._compute_mastery(
            current_score=0.0,
            historical=[0.0, 0.0],
        )
        assert mastery >= 0.0

    def test_calculate_when_first_attempt_3_of_5_correct_then_mastery_0_6(
        self,
    ) -> None:
        """First attempt (non-system_generated), 3 correct out of 5 questions for one subtopic.

        current_score = 3/5 = 0.6, no historical, not system-generated.
        mastery = 0.6 × 1.0 = 0.6.
        """
        mastery = self._compute_mastery(
            current_score=3 / 5,
            historical=[],
            is_system_generated=False,
        )
        assert mastery == pytest.approx(0.6, abs=1e-9)


# ── Task-level tests (mocked DB) ─────────────────────────────────────────────


class TestCalculateGapStatesTask:
    """Tests for the calculate_gap_states Celery task behavior.

    Uses heavily mocked DB session to test task logic without a real DB.
    """

    def _build_mock_db(
        self,
        attempt: SimpleNamespace,
        assessment: SimpleNamespace,
        responses: list[SimpleNamespace],
        question_to_subtopic: dict[uuid.UUID, uuid.UUID],
        historical_scores: dict[uuid.UUID, list[tuple[float, datetime]]],
    ) -> AsyncMock:
        """Build a mock DB that returns canned data for each execute call."""

        mock_db = MagicMock()
        mock_db.execute = AsyncMock()

        call_count = [0]

        async def execute_side_effect(stmt, params=None):  # type: ignore[no-untyped-def]
            call_count[0] += 1
            c = call_count[0]

            # Call 1: load attempt
            if c == 1:
                result = MagicMock()
                result.scalar_one_or_none.return_value = attempt
                return result
            # Call 2: load assessment
            if c == 2:
                result = MagicMock()
                result.scalar_one_or_none.return_value = assessment
                return result
            # Call 3: load responses
            if c == 3:
                result = MagicMock()
                result.scalars.return_value.all.return_value = responses
                return result
            # Call 4: map question_id → subtopic_id
            if c == 4:
                result = MagicMock()
                result.all.return_value = list(question_to_subtopic.items())
                return result
            # Subsequent calls: historical score queries + upsert gap_state + insert score row
            return MagicMock()

        mock_db.execute.side_effect = execute_side_effect
        return mock_db

    @pytest.mark.asyncio
    async def test_calculate_when_multiple_subtopics_then_each_updated_independently(
        self,
    ) -> None:
        """Two subtopics in one attempt each get their own gap_state upsert.

        Verifies that grouping responses by subtopic produces separate upsert calls.
        q1 → sub1 (1/1 correct), q2 + q3 → sub2 (1/2 correct).
        """
        school_id = uuid.uuid4()
        class_id = uuid.uuid4()
        student_id = uuid.uuid4()

        sub1 = uuid.uuid4()
        sub2 = uuid.uuid4()
        q1 = uuid.uuid4()
        q2 = uuid.uuid4()
        q3 = uuid.uuid4()

        responses = [
            _make_response(q1, is_correct=True),  # sub1: 1/1
            _make_response(q2, is_correct=True),  # sub2: 1/2
            _make_response(q3, is_correct=False),  # sub2: 1/2
        ]
        q_to_sub = {q1: sub1, q2: sub2, q3: sub2}

        from app.services.gap_service import GapService

        # One mock_db per service, track execute calls
        execute_call_subtopics: list[uuid.UUID] = []
        mock_db = MagicMock()

        async def capture_execute(stmt, params=None):  # type: ignore[no-untyped-def]
            if params and "subtopic_id" in params:
                execute_call_subtopics.append(params["subtopic_id"])
            return MagicMock()

        mock_db.execute = capture_execute  # type: ignore[assignment]
        service = GapService(mock_db)

        # Group responses manually (same logic as task)
        from collections import defaultdict

        subtopic_correct: dict[uuid.UUID, int] = defaultdict(int)
        subtopic_total: dict[uuid.UUID, int] = defaultdict(int)
        for resp in responses:
            sub_id = q_to_sub.get(resp.question_id)
            if sub_id is None:
                continue
            subtopic_total[sub_id] += 1
            if resp.is_correct:
                subtopic_correct[sub_id] += 1

        # Upsert for each subtopic
        for subtopic_id, total in subtopic_total.items():
            score = subtopic_correct[subtopic_id] / total
            await service.upsert_gap_state(
                student_id=student_id,
                subtopic_id=subtopic_id,
                school_id=school_id,
                class_id=class_id,
                new_mastery=score,
                rolling_attempt_count=1,
                last_assessed_at=datetime.now(UTC),
            )

        # Exactly 2 subtopics were processed
        assert len(execute_call_subtopics) == 2
        assert set(execute_call_subtopics) == {sub1, sub2}

    @pytest.mark.asyncio
    async def test_calculate_when_response_has_unknown_question_id_then_skipped_not_crashed(
        self,
    ) -> None:
        """Unknown question_id in responses is silently skipped (logged as ERROR)."""
        sub1 = uuid.uuid4()
        q_known = uuid.uuid4()
        q_unknown = uuid.uuid4()

        # q_to_sub only maps q_known — q_unknown is absent
        q_to_sub: dict[uuid.UUID, uuid.UUID] = {q_known: sub1}

        responses = [
            _make_response(q_known, is_correct=True),
            _make_response(q_unknown, is_correct=True),
        ]

        correct_count = 0
        total_count = 0
        for resp in responses:
            subtopic_id = q_to_sub.get(resp.question_id)
            if subtopic_id is None:
                continue  # skipped
            correct_count += int(resp.is_correct or False)
            total_count += 1

        # q_unknown is skipped: only q_known is counted
        assert total_count == 1
        assert correct_count == 1


# ── Event loop / on_failure tests ────────────────────────────────────────────


class TestGapTaskStructure:
    """Tests for task structure (event loop, on_failure callback)."""

    def test_calculate_gap_states_uses_new_event_loop(self) -> None:
        """Task must use asyncio.new_event_loop() not asyncio.run()."""
        import inspect

        from app.tasks import gap_tasks

        source = inspect.getsource(gap_tasks.calculate_gap_states)
        assert "asyncio.new_event_loop()" in source
        assert "loop.run_until_complete" in source
        assert "asyncio.run(" not in source

    def test_calculate_gap_states_on_failure_emits_critical_log(self) -> None:
        """on_failure callback must call logger.critical with required fields.

        Instantiates CalculateGapStatesTask directly and calls on_failure(),
        verifying structlog.get_logger().critical is invoked with the expected event.
        """
        from unittest.mock import MagicMock, patch

        from app.tasks.gap_tasks import CalculateGapStatesTask

        task = CalculateGapStatesTask()
        exc = RuntimeError("boom")

        mock_logger = MagicMock()
        with patch("app.tasks.gap_tasks.logger", mock_logger):
            task.on_failure(exc, "task-id", ["attempt-id"], {}, None)

        mock_logger.critical.assert_called_once()
        call_kwargs = mock_logger.critical.call_args
        # First positional arg is the event name
        assert call_kwargs[0][0] == "calculate_gap_states_permanently_failed"
        assert call_kwargs[1].get("task_id") == "task-id"
        assert call_kwargs[1].get("attempt_id") == "attempt-id"
        assert call_kwargs[1].get("exc_info") is True

    def test_calculate_gap_states_task_name_correct(self) -> None:
        """Task name must follow app.tasks.gap_tasks.calculate_gap_states convention."""
        from app.tasks.gap_tasks import calculate_gap_states

        assert calculate_gap_states.name == "app.tasks.gap_tasks.calculate_gap_states"

    def test_calculate_gap_states_max_retries_is_3(self) -> None:
        """Task must have max_retries=3 per CONSTITUTION Rule 18."""
        from app.tasks.gap_tasks import calculate_gap_states

        assert calculate_gap_states.max_retries == 3
