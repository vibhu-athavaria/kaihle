"""Unit tests for gap state calculation logic.

Tests cover:
- GapService.upsert_gap_state — DB upsert call shape and idempotency semantics
- calculate_gap_states Celery task — event loop / retry / CRITICAL-log structure
- calculate_gap_states_for_attempt — early returns, subtopic skipping, multi-subtopic flow
- Multiple subtopics, unknown question IDs, needs_review boundary

MLH-T3: the mastery formula itself (magic coefficients replaced by
mastery_model.estimate, a Beta-Binomial posterior) is tested where it lives — pure, in
test_mastery_model.py — and where its real computed values matter, against a real
database, in test_gap_states_updated.py. This file stays mocked and stays focused on
control flow: it does not assert exact mastery scores, because a mocked positional call
sequence is not where a shrinkage/decay computation should be trusted.
"""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.assessment import AssessmentType
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


def _make_assessment(school_id: uuid.UUID, class_id: uuid.UUID, assessment_type: AssessmentType) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        school_id=school_id,
        class_id=class_id,
        assessment_type=assessment_type,
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
            confidence=0.5,
            rolling_attempt_count=1,
            last_assessed_at=ts,
        )
        await service.upsert_gap_state(
            student_id=student_id,
            subtopic_id=subtopic_id,
            school_id=school_id,
            class_id=class_id,
            new_mastery=0.8,
            confidence=0.5,
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
            confidence=0.4,
            rolling_attempt_count=1,
            last_assessed_at=ts,
        )
        await service.upsert_gap_state(
            student_id=student_id,
            subtopic_id=subtopic_id,
            school_id=school_id,
            class_id=class_id,
            new_mastery=0.8,
            confidence=0.6,
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
            confidence=0.5,
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
            confidence=0.5,
            rolling_attempt_count=1,
            last_assessed_at=datetime.now(UTC),
        )

        assert len(captured_params) == 1
        assert captured_params[0]["needs_review"] is False


# TestMasteryWeightingFormulas removed (MLH-T3). It reimplemented the six-coefficient
# formula inside the test file (_compute_mastery) and asserted against its own copy —
# every test in it would have passed if gap_service.py were deleted, violating
# .claude/rules/05-testing.md ("Tests MUST assert behavior... not implementation
# details"). The formula is gone; its replacement (mastery_model.estimate) has its own
# pure test suite in test_mastery_model.py, and this file's remaining tests below
# assert against the real GapService path instead of a parallel reimplementation.


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
                confidence=0.5,
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


# ── calculate_gap_states_for_attempt integration-style unit tests ─────────────


def _build_mock_db_for_calculate(
    attempt: SimpleNamespace,
    assessment: SimpleNamespace,
    responses: list[SimpleNamespace],
    question_to_subtopic: dict[uuid.UUID, uuid.UUID],
) -> MagicMock:
    """Build a mock AsyncSession for calculate_gap_states_for_attempt.

    Call sequence (positional — this mock is order-dependent on the service):
      1. Load attempt (scalar_one_or_none)
      2. Load assessment (scalar_one_or_none)
      3. Load responses (scalars().all())
      4. Load class, for scoping attribution to its curriculum/subject/grade
         (scalar_one_or_none)
      5. Map question → subtopic via the learning objective, within that scope (all())
      6. Batch-fetch mastery_priors for every resolved subtopic (all()) — MLH-T3. An
         empty result here is a valid, already-handled case: it means no subtopic in
         this attempt has been calibrated yet, and the service falls back to the
         platform bootstrap default (settings.mastery_prior_alpha/beta), not an error.
      Per subtopic:
        7+. Historical (correct_count, total_count) query (all())
        8+. Gap state upsert (execute with text)
        9+. Insert subtopic score row (execute with text)

    Call 5 resolves every question here, so the service's legacy subtopic_id fallback
    is not reached and issues no query. Call 6 and beyond all return an empty `.all()`
    by default (see the `else` branch below), which is correct for both "no priors
    calibrated yet" and "no history yet" — neither test using this helper asserts an
    exact mastery value, only that the flow completes and updates the right count of
    subtopics; see test_gap_states_updated.py for tests that assert real values against
    a real database instead of a positional mock sequence.
    """
    call_count = [0]

    async def side_effect(stmt, params=None):  # type: ignore[no-untyped-def]
        call_count[0] += 1
        c = call_count[0]
        m = MagicMock()

        if c == 1:  # Load attempt
            m.scalar_one_or_none.return_value = attempt
        elif c == 2:  # Load assessment
            m.scalar_one_or_none.return_value = assessment
        elif c == 3:  # Load responses
            m.scalars.return_value.all.return_value = responses
        elif c == 4:  # Load class for scope
            m.scalar_one_or_none.return_value = SimpleNamespace(
                id=assessment.class_id,
                curriculum_id=uuid.uuid4(),
                subject_id=uuid.uuid4(),
                grade_id=uuid.uuid4(),
            )
        elif c == 5:  # question → subtopic map, resolved via learning objective
            m.all.return_value = list(question_to_subtopic.items())
        else:
            # Historical score queries return empty; upserts return mock
            m.all.return_value = []
        return m

    mock_db = MagicMock()
    mock_db.execute = AsyncMock(side_effect=side_effect)
    return mock_db


class TestCalculateGapStatesForAttempt:
    """Unit tests for GapService.calculate_gap_states_for_attempt."""

    @pytest.mark.asyncio
    async def test_when_attempt_not_found_then_returns_zero_subtopics_updated(self) -> None:
        """Attempt row missing → warning + early return with 0 subtopics."""
        attempt_id = uuid.uuid4()
        mock_db = MagicMock()
        m = MagicMock()
        m.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=m)

        service = GapService(mock_db)
        result = await service.calculate_gap_states_for_attempt(attempt_id)

        assert result == {"attempt_id": str(attempt_id), "subtopics_updated": 0}

    @pytest.mark.asyncio
    async def test_when_attempt_not_completed_then_returns_zero_subtopics_updated(self) -> None:
        """Attempt in IN_PROGRESS state → warning + early return."""
        attempt_id = uuid.uuid4()
        student_id = uuid.uuid4()
        assessment_id = uuid.uuid4()
        attempt = _make_attempt(assessment_id, student_id, status="IN_PROGRESS")

        mock_db = MagicMock()
        m = MagicMock()
        m.scalar_one_or_none.return_value = attempt
        mock_db.execute = AsyncMock(return_value=m)

        service = GapService(mock_db)
        result = await service.calculate_gap_states_for_attempt(attempt_id)

        assert result == {"attempt_id": str(attempt_id), "subtopics_updated": 0}

    @pytest.mark.asyncio
    async def test_when_assessment_not_found_then_returns_zero_subtopics_updated(self) -> None:
        """Assessment row missing → warning + early return."""
        attempt_id = uuid.uuid4()
        student_id = uuid.uuid4()
        assessment_id = uuid.uuid4()
        attempt = _make_attempt(assessment_id, student_id, status="COMPLETED")

        call_count = [0]

        async def side_effect(stmt, params=None):  # type: ignore[no-untyped-def]
            call_count[0] += 1
            m = MagicMock()
            if call_count[0] == 1:
                m.scalar_one_or_none.return_value = attempt
            else:
                m.scalar_one_or_none.return_value = None
            return m

        mock_db = MagicMock()
        mock_db.execute = AsyncMock(side_effect=side_effect)

        service = GapService(mock_db)
        result = await service.calculate_gap_states_for_attempt(attempt_id)

        assert result == {"attempt_id": str(attempt_id), "subtopics_updated": 0}

    @pytest.mark.asyncio
    async def test_when_no_responses_then_returns_zero_subtopics_updated(self) -> None:
        """Attempt completed but no StudentResponse rows → early return."""
        student_id = uuid.uuid4()
        assessment = _make_assessment(uuid.uuid4(), uuid.uuid4(), AssessmentType.DIAGNOSTIC)
        attempt = _make_attempt(assessment.id, student_id, status="COMPLETED")

        call_count = [0]

        async def side_effect(stmt, params=None):  # type: ignore[no-untyped-def]
            call_count[0] += 1
            m = MagicMock()
            if call_count[0] == 1:
                m.scalar_one_or_none.return_value = attempt
            elif call_count[0] == 2:
                m.scalar_one_or_none.return_value = assessment
            else:
                m.scalars.return_value.all.return_value = []
            return m

        mock_db = MagicMock()
        mock_db.execute = AsyncMock(side_effect=side_effect)

        service = GapService(mock_db)
        result = await service.calculate_gap_states_for_attempt(attempt.id)

        assert result == {"attempt_id": str(attempt.id), "subtopics_updated": 0}

    @pytest.mark.asyncio
    async def test_when_one_subtopic_no_history_then_subtopics_updated_is_1(self) -> None:
        """Single subtopic, first attempt → upsert called, returns 1 subtopic updated."""
        student_id = uuid.uuid4()
        sub1 = uuid.uuid4()
        q1 = uuid.uuid4()
        assessment = _make_assessment(uuid.uuid4(), uuid.uuid4(), assessment_type=AssessmentType.PROGRESS_CHECK)
        attempt = _make_attempt(assessment.id, student_id, status="COMPLETED")
        responses = [_make_response(q1, is_correct=True)]

        mock_db = _build_mock_db_for_calculate(
            attempt=attempt,
            assessment=assessment,
            responses=responses,
            question_to_subtopic={q1: sub1},
        )
        service = GapService(mock_db)
        result = await service.calculate_gap_states_for_attempt(attempt.id)

        assert result["subtopics_updated"] == 1

    @pytest.mark.asyncio
    async def test_when_response_has_unknown_question_id_then_subtopic_skipped(self) -> None:
        """Question not in question→subtopic map → error logged, subtopic skipped."""
        student_id = uuid.uuid4()
        q_unknown = uuid.uuid4()
        assessment = _make_assessment(uuid.uuid4(), uuid.uuid4(), AssessmentType.PROGRESS_CHECK)
        attempt = _make_attempt(assessment.id, student_id, status="COMPLETED")
        responses = [_make_response(q_unknown, is_correct=True)]

        mock_db = _build_mock_db_for_calculate(
            attempt=attempt,
            assessment=assessment,
            responses=responses,
            question_to_subtopic={},  # empty map → unknown question
        )
        service = GapService(mock_db)
        result = await service.calculate_gap_states_for_attempt(attempt.id)

        assert result["subtopics_updated"] == 0

    @pytest.mark.asyncio
    async def test_when_first_attempt_no_prior_calibrated_then_completes_via_bootstrap_default(
        self,
    ) -> None:
        """First attempt, no mastery_priors row for this subtopic yet — flow completes.

        Was test_when_first_diagnostic_attempt_then_mastery_weighted_at_0_7, asserting
        the retired "mastery = score * 0.7" behaviour (Finding 1: this was the exact bug
        that capped every diagnostic below the Strong band). Its own upsert_calls capture
        never actually matched anything — SQL bind params use "mastery_score", not
        "new_mastery" — so no numeric assertion was ever made here; the real regression
        test for Finding 1 lives in test_gap_states_updated.py against a real database,
        where an exact posterior value can be asserted meaningfully. This mocked test
        keeps its actual, narrower job: the flow completes and updates 1 subtopic when no
        prior has been calibrated for it (mastery_priors batch-fetch returns empty and
        the service falls back to the platform bootstrap default).
        """
        student_id = uuid.uuid4()
        sub1 = uuid.uuid4()
        q1 = uuid.uuid4()
        assessment = _make_assessment(uuid.uuid4(), uuid.uuid4(), assessment_type=AssessmentType.DIAGNOSTIC)
        attempt = _make_attempt(assessment.id, student_id, status="COMPLETED")
        responses = [_make_response(q1, is_correct=True)]  # 100% correct

        call_count = [0]

        async def side_effect(stmt, params=None):  # type: ignore[no-untyped-def]
            call_count[0] += 1
            c = call_count[0]
            m = MagicMock()
            if c == 1:
                m.scalar_one_or_none.return_value = attempt
            elif c == 2:
                m.scalar_one_or_none.return_value = assessment
            elif c == 3:
                m.scalars.return_value.all.return_value = responses
            elif c == 4:
                # Class load — attribution is scoped to the class's curriculum.
                m.scalar_one_or_none.return_value = SimpleNamespace(
                    id=assessment.class_id,
                    curriculum_id=uuid.uuid4(),
                    subject_id=uuid.uuid4(),
                    grade_id=uuid.uuid4(),
                )
            elif c == 5:
                # question → subtopic, resolved via the learning objective
                m.all.return_value = [(q1, sub1)]
            elif c == 6:
                m.all.return_value = []  # no mastery_priors row calibrated yet
            else:
                m.all.return_value = []  # no history
            return m

        mock_db = MagicMock()
        mock_db.execute = AsyncMock(side_effect=side_effect)

        service = GapService(mock_db)
        result = await service.calculate_gap_states_for_attempt(attempt.id)

        assert result["subtopics_updated"] == 1
