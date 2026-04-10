"""Unit tests for AttemptService.

Uses mock DB sessions — no real database required.
Naming convention: test_<what>_when_<condition>_then_<expected>
"""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import AssessmentStatus, AttemptStatus
from app.services.attempt_service import (
    AttemptAlreadyCompletedError,
    AttemptNotFoundError,
    AttemptService,
    DuplicateResponseError,
    QuestionNotInAssessmentError,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db() -> MagicMock:
    session = MagicMock(spec=AsyncSession)
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    return session


@pytest.fixture
def service(mock_db: MagicMock) -> AttemptService:
    return AttemptService(mock_db)


def _make_assessment(
    *,
    school_id: uuid.UUID | None = None,
    class_id: uuid.UUID | None = None,
    status: str = AssessmentStatus.ACTIVE,
    is_system_generated: bool = True,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        school_id=school_id or uuid.uuid4(),
        class_id=class_id or uuid.uuid4(),
        status=status,
        is_system_generated=is_system_generated,
    )


def _make_attempt(
    *,
    student_id: uuid.UUID | None = None,
    assessment_id: uuid.UUID | None = None,
    status: str = AttemptStatus.NOT_STARTED,
    overall_score: float | None = None,
    completed_at: datetime | None = None,
    started_at: datetime | None = None,
    time_taken_seconds: int | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        student_id=student_id or uuid.uuid4(),
        assessment_id=assessment_id or uuid.uuid4(),
        status=status,
        overall_score=overall_score,
        completed_at=completed_at,
        started_at=started_at,
        time_taken_seconds=time_taken_seconds,
    )


def _make_question(correct_answer: str = "A") -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        question_text="What is 1+1?",
        question_type="MCQ",
        options=[{"key": "A", "text": "2"}, {"key": "B", "text": "3"}],
        correct_answer=correct_answer,
        explanation=None,
    )


def _make_response(
    *,
    attempt_id: uuid.UUID | None = None,
    question_id: uuid.UUID | None = None,
    is_correct: bool = True,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        attempt_id=attempt_id or uuid.uuid4(),
        question_id=question_id or uuid.uuid4(),
        is_correct=is_correct,
        answer_given="A",
        score=1.0 if is_correct else 0.0,
    )


def _scalar_result(value: object) -> MagicMock:
    """Build a mock execute() result that returns ``value`` from scalar_one_or_none."""
    m = MagicMock()
    m.scalar_one_or_none.return_value = value
    m.scalar_one.return_value = value
    return m


def _scalars_result(values: list) -> MagicMock:
    """Build a mock execute() result that returns ``values`` from scalars().all()."""
    m = MagicMock()
    scalars_m = MagicMock()
    scalars_m.all.return_value = values
    m.scalars.return_value = scalars_m
    # Also support .all() for non-scalars calls
    m.all.return_value = [(v,) for v in values]
    return m


# ---------------------------------------------------------------------------
# get_class_diagnostic
# ---------------------------------------------------------------------------


class TestGetClassDiagnostic:
    @pytest.mark.asyncio
    async def test_get_class_diagnostic_when_attempt_exists_then_returns_with_questions(
        self, service: AttemptService, mock_db: MagicMock
    ) -> None:
        """Happy path: active assessment + existing attempt → returns both."""
        school_id = uuid.uuid4()
        student_id = uuid.uuid4()
        class_id = uuid.uuid4()
        assessment = _make_assessment(school_id=school_id, class_id=class_id)
        attempt = _make_attempt(student_id=student_id, assessment_id=assessment.id)
        question = _make_question()

        # Execute calls: assessment, attempt, questions
        questions_result = MagicMock()
        questions_result.all.return_value = [(question,)]

        mock_db.execute = AsyncMock(
            side_effect=[
                _scalar_result(assessment),
                _scalar_result(attempt),
                questions_result,
            ]
        )

        result_attempt, result_questions = await service.get_class_diagnostic(
            class_id=class_id,
            student_id=student_id,
            school_id=school_id,
        )

        assert result_attempt.id == attempt.id
        assert len(result_questions) == 1
        # correct_answer must be stripped
        assert result_questions[0].correct_answer is None

    @pytest.mark.asyncio
    async def test_get_class_diagnostic_when_no_attempt_then_raises_attempt_not_found_error(
        self, service: AttemptService, mock_db: MagicMock
    ) -> None:
        """Assessment exists but attempt not yet created → AttemptNotFoundError."""
        school_id = uuid.uuid4()
        student_id = uuid.uuid4()
        class_id = uuid.uuid4()
        assessment = _make_assessment(school_id=school_id, class_id=class_id)

        mock_db.execute = AsyncMock(
            side_effect=[
                _scalar_result(assessment),
                _scalar_result(None),  # no attempt
            ]
        )

        with pytest.raises(AttemptNotFoundError):
            await service.get_class_diagnostic(class_id=class_id, student_id=student_id, school_id=school_id)

    @pytest.mark.asyncio
    async def test_get_class_diagnostic_when_no_active_tier1_assessment_then_raises_value_error(
        self, service: AttemptService, mock_db: MagicMock
    ) -> None:
        """No ACTIVE system-generated assessment → ValueError."""
        mock_db.execute = AsyncMock(return_value=_scalar_result(None))

        with pytest.raises(ValueError, match="No active Tier 1 diagnostic"):
            await service.get_class_diagnostic(class_id=uuid.uuid4(), student_id=uuid.uuid4(), school_id=uuid.uuid4())


# ---------------------------------------------------------------------------
# submit_response
# ---------------------------------------------------------------------------


class TestSubmitResponse:
    def _setup_mock_db(
        self,
        mock_db: MagicMock,
        attempt: SimpleNamespace,
        assessment: SimpleNamespace,
        bridge: SimpleNamespace | None,
        existing_response: SimpleNamespace | None,
        question: SimpleNamespace,
    ) -> None:
        """Wire up mock_db.execute side_effect for submit_response."""
        mock_db.execute = AsyncMock(
            side_effect=[
                _scalar_result(attempt),  # _load_and_verify_attempt: attempt lookup
                _scalar_result(assessment),  # _load_and_verify_attempt: assessment lookup
                _scalar_result(bridge),  # bridge table lookup
                _scalar_result(existing_response),  # duplicate guard
                _scalar_result(question),  # question for scoring
            ]
        )

    @pytest.mark.asyncio
    async def test_submit_response_when_correct_mcq_then_is_correct_true(
        self, service: AttemptService, mock_db: MagicMock
    ) -> None:
        student_id = uuid.uuid4()
        school_id = uuid.uuid4()
        assessment = _make_assessment(school_id=school_id)
        attempt = _make_attempt(student_id=student_id, assessment_id=assessment.id)
        question = _make_question(correct_answer="A")
        bridge = SimpleNamespace(assessment_id=assessment.id, question_id=question.id, order_index=0)

        self._setup_mock_db(mock_db, attempt, assessment, bridge, None, question)

        await service.submit_response(
            attempt_id=attempt.id,
            student_id=student_id,
            school_id=school_id,
            question_id=question.id,
            selected_key="A",
        )

        added = mock_db.add.call_args[0][0]
        assert added.is_correct is True

    @pytest.mark.asyncio
    async def test_submit_response_when_wrong_mcq_then_is_correct_false(
        self, service: AttemptService, mock_db: MagicMock
    ) -> None:
        student_id = uuid.uuid4()
        school_id = uuid.uuid4()
        assessment = _make_assessment(school_id=school_id)
        attempt = _make_attempt(student_id=student_id, assessment_id=assessment.id)
        question = _make_question(correct_answer="A")
        bridge = SimpleNamespace(assessment_id=assessment.id, question_id=question.id, order_index=0)

        self._setup_mock_db(mock_db, attempt, assessment, bridge, None, question)

        await service.submit_response(
            attempt_id=attempt.id,
            student_id=student_id,
            school_id=school_id,
            question_id=question.id,
            selected_key="B",
        )

        added = mock_db.add.call_args[0][0]
        assert added.is_correct is False

    @pytest.mark.asyncio
    async def test_submit_response_when_case_different_then_still_correct(
        self, service: AttemptService, mock_db: MagicMock
    ) -> None:
        """Case-insensitive comparison: student answers "a", correct is "A"."""
        student_id = uuid.uuid4()
        school_id = uuid.uuid4()
        assessment = _make_assessment(school_id=school_id)
        attempt = _make_attempt(student_id=student_id, assessment_id=assessment.id)
        question = _make_question(correct_answer="A")
        bridge = SimpleNamespace(assessment_id=assessment.id, question_id=question.id, order_index=0)

        self._setup_mock_db(mock_db, attempt, assessment, bridge, None, question)

        await service.submit_response(
            attempt_id=attempt.id,
            student_id=student_id,
            school_id=school_id,
            question_id=question.id,
            selected_key="a",
        )

        added = mock_db.add.call_args[0][0]
        assert added.is_correct is True

    @pytest.mark.asyncio
    async def test_submit_response_when_duplicate_question_then_raises_duplicate_response_error(
        self, service: AttemptService, mock_db: MagicMock
    ) -> None:
        student_id = uuid.uuid4()
        school_id = uuid.uuid4()
        assessment = _make_assessment(school_id=school_id)
        attempt = _make_attempt(student_id=student_id, assessment_id=assessment.id)
        question = _make_question()
        bridge = SimpleNamespace(assessment_id=assessment.id, question_id=question.id, order_index=0)
        existing_resp = _make_response()

        self._setup_mock_db(mock_db, attempt, assessment, bridge, existing_resp, question)

        with pytest.raises(DuplicateResponseError):
            await service.submit_response(
                attempt_id=attempt.id,
                student_id=student_id,
                school_id=school_id,
                question_id=question.id,
                selected_key="A",
            )

    @pytest.mark.asyncio
    async def test_submit_response_when_attempt_completed_then_raises_attempt_already_completed_error(
        self, service: AttemptService, mock_db: MagicMock
    ) -> None:
        student_id = uuid.uuid4()
        school_id = uuid.uuid4()
        assessment = _make_assessment(school_id=school_id)
        attempt = _make_attempt(
            student_id=student_id,
            assessment_id=assessment.id,
            status=AttemptStatus.COMPLETED,
        )

        mock_db.execute = AsyncMock(
            side_effect=[
                _scalar_result(attempt),
                _scalar_result(assessment),
            ]
        )

        with pytest.raises(AttemptAlreadyCompletedError):
            await service.submit_response(
                attempt_id=attempt.id,
                student_id=student_id,
                school_id=school_id,
                question_id=uuid.uuid4(),
                selected_key="A",
            )

    @pytest.mark.asyncio
    async def test_submit_response_when_question_not_in_assessment_then_raises_error(
        self, service: AttemptService, mock_db: MagicMock
    ) -> None:
        student_id = uuid.uuid4()
        school_id = uuid.uuid4()
        assessment = _make_assessment(school_id=school_id)
        attempt = _make_attempt(student_id=student_id, assessment_id=assessment.id)

        mock_db.execute = AsyncMock(
            side_effect=[
                _scalar_result(attempt),
                _scalar_result(assessment),
                _scalar_result(None),  # bridge not found
            ]
        )

        with pytest.raises(QuestionNotInAssessmentError):
            await service.submit_response(
                attempt_id=attempt.id,
                student_id=student_id,
                school_id=school_id,
                question_id=uuid.uuid4(),
                selected_key="A",
            )

    @pytest.mark.asyncio
    async def test_submit_response_transitions_attempt_from_not_started_to_in_progress(
        self, service: AttemptService, mock_db: MagicMock
    ) -> None:
        student_id = uuid.uuid4()
        school_id = uuid.uuid4()
        assessment = _make_assessment(school_id=school_id)
        attempt = _make_attempt(
            student_id=student_id,
            assessment_id=assessment.id,
            status=AttemptStatus.NOT_STARTED,
        )
        question = _make_question(correct_answer="A")
        bridge = SimpleNamespace(assessment_id=assessment.id, question_id=question.id, order_index=0)

        self._setup_mock_db(mock_db, attempt, assessment, bridge, None, question)

        await service.submit_response(
            attempt_id=attempt.id,
            student_id=student_id,
            school_id=school_id,
            question_id=question.id,
            selected_key="A",
        )

        assert attempt.status == AttemptStatus.IN_PROGRESS


# ---------------------------------------------------------------------------
# submit_attempt
# ---------------------------------------------------------------------------


class TestSubmitAttempt:
    def _make_10_question_answers(self, *, correct_count: int = 10) -> tuple[list[SimpleNamespace], list[dict]]:
        """Create 10 questions and matching answers with the specified correct count."""
        questions = [_make_question(correct_answer="A") for _ in range(10)]
        answers = []
        for i, q in enumerate(questions):
            answers.append({"question_id": q.id, "selected_key": "A" if i < correct_count else "B"})
        return questions, answers

    def _build_mock_db_for_submit(
        self,
        mock_db: MagicMock,
        attempt: SimpleNamespace,
        assessment: SimpleNamespace,
        questions: list[SimpleNamespace],
        already_answered_ids: list[uuid.UUID] | None = None,
    ) -> None:
        """Wire mock_db for submit_attempt."""
        # Existing response ids (for idempotency)
        already_answered_ids = already_answered_ids or []
        existing_q_ids_result = MagicMock()
        existing_q_ids_result.all.return_value = [(qid,) for qid in already_answered_ids]

        # Each question needs: bridge lookup + question lookup
        side_effects: list = [
            _scalar_result(attempt),  # _load_and_verify_attempt: attempt
            _scalar_result(assessment),  # _load_and_verify_attempt: assessment
            _scalar_result(assessment),  # reload assessment for is_system_generated
            existing_q_ids_result,  # existing response ids
        ]

        for q in questions:
            # Skip already answered
            if q.id in already_answered_ids:
                continue
            bridge = SimpleNamespace(assessment_id=assessment.id, question_id=q.id, order_index=0)
            side_effects.append(_scalar_result(bridge))
            side_effects.append(_scalar_result(q))

        # All responses for scoring
        responses = [
            _make_response(is_correct=(a["selected_key"] == "A"))
            for a in [{"selected_key": "A"} for q in questions]  # simplified
        ]
        all_resp_result = MagicMock()
        scalars_m = MagicMock()
        scalars_m.all.return_value = responses
        all_resp_result.scalars.return_value = scalars_m
        side_effects.append(all_resp_result)

        mock_db.execute = AsyncMock(side_effect=side_effects)

    @pytest.mark.asyncio
    async def test_submit_attempt_when_10_correct_then_score_1_0(
        self, service: AttemptService, mock_db: MagicMock
    ) -> None:
        student_id = uuid.uuid4()
        school_id = uuid.uuid4()
        assessment = _make_assessment(school_id=school_id, is_system_generated=False)
        attempt = _make_attempt(student_id=student_id, assessment_id=assessment.id)
        questions, answers = self._make_10_question_answers(correct_count=10)

        self._build_mock_db_for_submit(mock_db, attempt, assessment, questions)
        mock_onboarding = AsyncMock()

        with patch("app.tasks.gap_tasks.calculate_gap_states") as mock_task:
            mock_task.delay = MagicMock()
            result = await service.submit_attempt(
                attempt_id=attempt.id,
                student_id=student_id,
                school_id=school_id,
                answers=answers,
                onboarding_service=mock_onboarding,
            )

        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_submit_attempt_when_7_correct_of_10_then_score_0_7(
        self, service: AttemptService, mock_db: MagicMock
    ) -> None:
        student_id = uuid.uuid4()
        school_id = uuid.uuid4()
        assessment = _make_assessment(school_id=school_id, is_system_generated=False)
        attempt = _make_attempt(student_id=student_id, assessment_id=assessment.id)
        questions, answers = self._make_10_question_answers(correct_count=7)

        # Build mock but override final responses to have 7 correct / 3 wrong
        existing_q_ids_result = MagicMock()
        existing_q_ids_result.all.return_value = []

        side_effects: list = [
            _scalar_result(attempt),
            _scalar_result(assessment),
            _scalar_result(assessment),
            existing_q_ids_result,
        ]
        for q in questions:
            bridge = SimpleNamespace(assessment_id=assessment.id, question_id=q.id, order_index=0)
            side_effects.append(_scalar_result(bridge))
            side_effects.append(_scalar_result(q))

        responses = [_make_response(is_correct=True)] * 7 + [_make_response(is_correct=False)] * 3
        all_resp_result = MagicMock()
        scalars_m = MagicMock()
        scalars_m.all.return_value = responses
        all_resp_result.scalars.return_value = scalars_m
        side_effects.append(all_resp_result)
        mock_db.execute = AsyncMock(side_effect=side_effects)

        mock_onboarding = AsyncMock()
        with patch("app.tasks.gap_tasks.calculate_gap_states") as mock_task:
            mock_task.delay = MagicMock()
            result = await service.submit_attempt(
                attempt_id=attempt.id,
                student_id=student_id,
                school_id=school_id,
                answers=answers,
                onboarding_service=mock_onboarding,
            )

        assert abs(result.score - 0.7) < 1e-9
        assert result.correct_count == 7
        assert result.total_questions == 10

    @pytest.mark.asyncio
    async def test_submit_attempt_when_tier1_then_onboarding_check_called(
        self, service: AttemptService, mock_db: MagicMock
    ) -> None:
        """For is_system_generated=True, check_and_update_onboarding_complete is called."""
        student_id = uuid.uuid4()
        school_id = uuid.uuid4()
        class_id = uuid.uuid4()
        assessment = _make_assessment(school_id=school_id, class_id=class_id, is_system_generated=True)
        attempt = _make_attempt(student_id=student_id, assessment_id=assessment.id)

        existing_q_ids_result = MagicMock()
        existing_q_ids_result.all.return_value = []

        all_resp_result = MagicMock()
        scalars_m = MagicMock()
        scalars_m.all.return_value = []
        all_resp_result.scalars.return_value = scalars_m

        mock_db.execute = AsyncMock(
            side_effect=[
                _scalar_result(attempt),
                _scalar_result(assessment),
                _scalar_result(assessment),
                existing_q_ids_result,
                all_resp_result,
            ]
        )

        mock_onboarding = MagicMock()
        mock_onboarding.check_and_update_onboarding_complete = AsyncMock(return_value=True)

        with patch("app.tasks.gap_tasks.calculate_gap_states") as mock_task:
            mock_task.delay = MagicMock()
            await service.submit_attempt(
                attempt_id=attempt.id,
                student_id=student_id,
                school_id=school_id,
                answers=[],
                onboarding_service=mock_onboarding,
            )

        mock_onboarding.check_and_update_onboarding_complete.assert_awaited_once_with(
            student_id=student_id,
            class_id=class_id,
        )

    @pytest.mark.asyncio
    async def test_submit_attempt_when_tier2_then_onboarding_check_not_called(
        self, service: AttemptService, mock_db: MagicMock
    ) -> None:
        """For is_system_generated=False, onboarding check is NOT called."""
        student_id = uuid.uuid4()
        school_id = uuid.uuid4()
        assessment = _make_assessment(school_id=school_id, is_system_generated=False)
        attempt = _make_attempt(student_id=student_id, assessment_id=assessment.id)

        existing_q_ids_result = MagicMock()
        existing_q_ids_result.all.return_value = []
        all_resp_result = MagicMock()
        scalars_m = MagicMock()
        scalars_m.all.return_value = []
        all_resp_result.scalars.return_value = scalars_m

        mock_db.execute = AsyncMock(
            side_effect=[
                _scalar_result(attempt),
                _scalar_result(assessment),
                _scalar_result(assessment),
                existing_q_ids_result,
                all_resp_result,
            ]
        )

        mock_onboarding = MagicMock()
        mock_onboarding.check_and_update_onboarding_complete = AsyncMock()

        with patch("app.tasks.gap_tasks.calculate_gap_states") as mock_task:
            mock_task.delay = MagicMock()
            await service.submit_attempt(
                attempt_id=attempt.id,
                student_id=student_id,
                school_id=school_id,
                answers=[],
                onboarding_service=mock_onboarding,
            )

        mock_onboarding.check_and_update_onboarding_complete.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_submit_attempt_fires_calculate_gap_states_celery_task(
        self, service: AttemptService, mock_db: MagicMock
    ) -> None:
        student_id = uuid.uuid4()
        school_id = uuid.uuid4()
        assessment = _make_assessment(school_id=school_id, is_system_generated=False)
        attempt = _make_attempt(student_id=student_id, assessment_id=assessment.id)

        existing_q_ids_result = MagicMock()
        existing_q_ids_result.all.return_value = []
        all_resp_result = MagicMock()
        scalars_m = MagicMock()
        scalars_m.all.return_value = []
        all_resp_result.scalars.return_value = scalars_m

        mock_db.execute = AsyncMock(
            side_effect=[
                _scalar_result(attempt),
                _scalar_result(assessment),
                _scalar_result(assessment),
                existing_q_ids_result,
                all_resp_result,
            ]
        )

        mock_onboarding = MagicMock()
        mock_onboarding.check_and_update_onboarding_complete = AsyncMock()

        with patch("app.tasks.gap_tasks.calculate_gap_states") as mock_task:
            mock_task.delay = MagicMock()
            await service.submit_attempt(
                attempt_id=attempt.id,
                student_id=student_id,
                school_id=school_id,
                answers=[],
                onboarding_service=mock_onboarding,
            )
            mock_task.delay.assert_called_once_with(str(attempt.id))

    @pytest.mark.asyncio
    async def test_submit_attempt_idempotent_when_some_responses_already_saved(
        self, service: AttemptService, mock_db: MagicMock
    ) -> None:
        """Questions already answered are skipped — no duplicate StudentResponse created."""
        student_id = uuid.uuid4()
        school_id = uuid.uuid4()
        assessment = _make_assessment(school_id=school_id, is_system_generated=False)
        attempt = _make_attempt(student_id=student_id, assessment_id=assessment.id)

        q1 = _make_question(correct_answer="A")
        q2 = _make_question(correct_answer="A")
        answers = [
            {"question_id": q1.id, "selected_key": "A"},
            {"question_id": q2.id, "selected_key": "A"},
        ]

        # q1 is already answered
        existing_q_ids_result = MagicMock()
        existing_q_ids_result.all.return_value = [(q1.id,)]

        # Only q2 will be processed
        bridge2 = SimpleNamespace(assessment_id=assessment.id, question_id=q2.id, order_index=1)
        all_resp_result = MagicMock()
        scalars_m = MagicMock()
        scalars_m.all.return_value = [_make_response(is_correct=True), _make_response(is_correct=True)]
        all_resp_result.scalars.return_value = scalars_m

        mock_db.execute = AsyncMock(
            side_effect=[
                _scalar_result(attempt),
                _scalar_result(assessment),
                _scalar_result(assessment),
                existing_q_ids_result,
                _scalar_result(bridge2),  # bridge for q2 only
                _scalar_result(q2),  # question for q2 only
                all_resp_result,
            ]
        )

        mock_onboarding = MagicMock()
        mock_onboarding.check_and_update_onboarding_complete = AsyncMock()

        with patch("app.tasks.gap_tasks.calculate_gap_states") as mock_task:
            mock_task.delay = MagicMock()
            result = await service.submit_attempt(
                attempt_id=attempt.id,
                student_id=student_id,
                school_id=school_id,
                answers=answers,
                onboarding_service=mock_onboarding,
            )

        # Only q2 was added (q1 skipped)
        assert mock_db.add.call_count == 1
        assert result.total_questions == 2  # two responses in DB


# ---------------------------------------------------------------------------
# get_attempt_results
# ---------------------------------------------------------------------------


class TestGetAttemptResults:
    @pytest.mark.asyncio
    async def test_get_results_when_own_student_then_200_with_score(
        self, service: AttemptService, mock_db: MagicMock
    ) -> None:
        student_id = uuid.uuid4()
        school_id = uuid.uuid4()
        assessment = _make_assessment(school_id=school_id)
        completed_at = datetime.now(UTC)
        attempt = _make_attempt(
            student_id=student_id,
            assessment_id=assessment.id,
            status=AttemptStatus.COMPLETED,
            overall_score=0.8,
            completed_at=completed_at,
        )

        responses = [_make_response(is_correct=True)] * 8 + [_make_response(is_correct=False)] * 2
        all_resp_result = MagicMock()
        scalars_m = MagicMock()
        scalars_m.all.return_value = responses
        all_resp_result.scalars.return_value = scalars_m

        mock_db.execute = AsyncMock(
            side_effect=[
                _scalar_result(attempt),
                all_resp_result,
            ]
        )

        result = await service.get_attempt_results(
            attempt_id=attempt.id,
            requesting_user_id=student_id,
            requesting_user_role="STUDENT",
            school_id=school_id,
        )

        assert result.score == 0.8
        assert result.correct_count == 8
        assert result.total_questions == 10

    @pytest.mark.asyncio
    async def test_get_results_when_different_student_then_raises_access_denied(
        self, service: AttemptService, mock_db: MagicMock
    ) -> None:
        real_student_id = uuid.uuid4()
        other_student_id = uuid.uuid4()
        school_id = uuid.uuid4()
        attempt = _make_attempt(
            student_id=real_student_id,
            status=AttemptStatus.COMPLETED,
            overall_score=0.8,
            completed_at=datetime.now(UTC),
        )

        mock_db.execute = AsyncMock(return_value=_scalar_result(attempt))

        with pytest.raises(ValueError, match="Access denied"):
            await service.get_attempt_results(
                attempt_id=attempt.id,
                requesting_user_id=other_student_id,
                requesting_user_role="STUDENT",
                school_id=school_id,
            )
