"""Unit tests for generate_topic_mini_course Celery task and MiniCourseGenerationService.

Naming convention: test_<what>_when_<condition>_then_<expected>

Run with: pytest app/tests/unit/test_generate_course_task.py -v
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.mini_course_generation_service import (
    INTEREST_CATEGORIES,
    MiniCourseGenerationService,
)
from app.tasks.mini_course_tasks import GenerateMiniCourseTask, _run_generation

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db() -> AsyncMock:
    """Minimal mock AsyncSession."""
    db = AsyncMock()
    db.commit = AsyncMock()
    db.add = MagicMock()
    db.execute = AsyncMock()
    return db


def _make_subtopic(name: str = "Quadratic Equations") -> MagicMock:
    subtopic = MagicMock()
    subtopic.id = uuid.uuid4()
    subtopic.name = name
    subtopic.is_active = True
    subtopic.sequence_order = 1
    return subtopic


def _make_interest_category(name: str, cat_id: uuid.UUID | None = None) -> MagicMock:
    cat = MagicMock()
    cat.id = cat_id or uuid.uuid4()
    cat.name = name
    return cat


def _make_scalars_result(items: list) -> MagicMock:
    """Mock result where result.scalars().all() returns items."""
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = items
    result = MagicMock()
    result.scalars.return_value = scalars_mock
    return result


def _make_first_result(value: object) -> MagicMock:
    """Mock result where result.first() returns value."""
    result = MagicMock()
    result.first.return_value = value
    return result


def _make_scalar_one_or_none_result(value: object) -> MagicMock:
    """Mock result where result.scalar_one_or_none() returns value."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _make_all_result(rows: list) -> MagicMock:
    """Mock result where result.all() returns rows (used by _fetch_existing_content_pairs)."""
    result = MagicMock()
    result.all.return_value = rows
    return result


# ---------------------------------------------------------------------------
# MiniCourseGenerationService unit tests
# ---------------------------------------------------------------------------


class TestGenerateForTopic:
    """Tests for MiniCourseGenerationService.generate_for_topic."""

    @pytest.mark.asyncio
    async def test_generate_topic_mini_course_when_no_subtopics_then_logs_warning_and_returns(
        self,
    ) -> None:
        """Rule 17: log WARNING and return early when topic has no subtopics."""
        db = _make_db()
        topic_id = str(uuid.uuid4())
        school_id = str(uuid.uuid4())

        # _fetch_topic_context: returns a row
        topic_context_row = MagicMock()
        topic_context_row.topic_name = "Algebra"
        topic_context_row.subject_name = "Mathematics"
        topic_context_row.grade_level = 8

        # _fetch_subtopics: returns empty list
        db.execute.side_effect = [
            _make_first_result(topic_context_row),  # _fetch_topic_context
            _make_scalars_result([]),  # _fetch_subtopics
        ]

        service = MiniCourseGenerationService(db)

        with patch("app.services.mini_course_generation_service.logger") as mock_logger:
            result = await service.generate_for_topic(topic_id=topic_id, school_id=school_id)

        assert result["subtopics_found"] == 0
        assert result["explanations_written"] == 0
        mock_logger.warning.assert_called_once()
        warning_call_event = mock_logger.warning.call_args[0][0]
        assert "no_subtopics" in warning_call_event
        # Code-review finding: this early return used to omit these keys entirely,
        # so callers' result.get("complete") read None/falsy and mismarked a topic
        # with nothing to generate as "partial" instead of "ready".
        assert result["complete"] is True
        assert result["explanation_gaps"] == []
        assert result["quiz_gaps"] == []

    @pytest.mark.asyncio
    async def test_generate_topic_mini_course_when_subtopics_exist_then_calls_llm_for_each_interest_category(
        self,
    ) -> None:
        """One LLM call per (subtopic, interest_category) pair — 4 calls for 1 subtopic."""
        db = _make_db()
        topic_id = str(uuid.uuid4())
        school_id = str(uuid.uuid4())
        subtopic = _make_subtopic()

        topic_context_row = MagicMock()
        topic_context_row.topic_name = "Algebra"
        topic_context_row.subject_name = "Mathematics"
        topic_context_row.grade_level = 8

        categories = [_make_interest_category(db_name) for db_name, _, _ in INTEREST_CATEGORIES]

        # Simulate this subtopic already having 5 llm questions → skip quiz generation
        # so the LLM call count stays at exactly len(INTEREST_CATEGORIES).
        question_count_row = MagicMock()
        question_count_row.subtopic_id = subtopic.id
        question_count_row.cnt = 5

        # execute call sequence:
        # Setup (3): _fetch_topic_context, _fetch_subtopics, _resolve_interest_category_ids
        # Batch (2): _fetch_existing_content_pairs, _fetch_existing_question_counts
        # Loop ×4:   _upsert_content rejected-row check → scalar_one_or_none()
        execute_returns = [
            _make_first_result(topic_context_row),  # _fetch_topic_context
            _make_scalars_result([subtopic]),  # _fetch_subtopics
            _make_scalars_result(categories),  # _resolve_interest_category_ids
            _make_all_result([]),  # _fetch_existing_content_pairs
            _make_all_result([question_count_row]),  # _fetch_existing_question_counts (5 → skip quiz)
            # upsert check ×4 — no rejected row exists → fresh insert each time
            _make_scalar_one_or_none_result(None),
            _make_scalar_one_or_none_result(None),
            _make_scalar_one_or_none_result(None),
            _make_scalar_one_or_none_result(None),
        ]
        db.execute.side_effect = execute_returns

        llm_response = "Great explanation about quadratic equations."

        service = MiniCourseGenerationService(db)

        with patch(
            "app.services.mini_course_generation_service.llm_router.complete",
            new=AsyncMock(return_value=llm_response),
        ) as mock_llm:
            result = await service.generate_for_topic(topic_id=topic_id, school_id=school_id)

        assert mock_llm.call_count == len(INTEREST_CATEGORIES)
        assert result["subtopics_found"] == 1
        assert result["subtopics_processed"] == 1
        assert result["explanations_written"] == len(INTEREST_CATEGORIES)
        # Every LLM call must use the mini_course_explanation task key
        for call in mock_llm.call_args_list:
            assert call.kwargs.get("task") == "mini_course_explanation" or call.args[0] == "mini_course_explanation"
        # Content rows are added to the session
        assert db.add.call_count == len(INTEREST_CATEGORIES)
        db.commit.assert_awaited_once()
        assert result["complete"] is True
        assert result["explanation_gaps"] == []
        assert result["quiz_gaps"] == []

    @pytest.mark.asyncio
    async def test_generate_topic_mini_course_when_one_pair_fails_then_others_still_written_and_gap_recorded(
        self,
    ) -> None:
        """MCR-T3: one bad call among several must not block or discard the rest."""
        db = _make_db()
        topic_id = str(uuid.uuid4())
        school_id = str(uuid.uuid4())
        subtopic = _make_subtopic()

        topic_context_row = MagicMock()
        topic_context_row.topic_name = "Algebra"
        topic_context_row.subject_name = "Mathematics"
        topic_context_row.grade_level = 8

        categories = [_make_interest_category(db_name) for db_name, _, _ in INTEREST_CATEGORIES]
        question_count_row = MagicMock(subtopic_id=subtopic.id, cnt=5)  # skip quiz generation

        db.execute.side_effect = [
            _make_first_result(topic_context_row),
            _make_scalars_result([subtopic]),
            _make_scalars_result(categories),
            _make_all_result([]),  # _fetch_existing_content_pairs
            _make_all_result([question_count_row]),  # quiz already at target
            _make_scalar_one_or_none_result(None),  # upsert check, pair 1 (succeeds)
            _make_scalar_one_or_none_result(None),  # upsert check, pair 3 (succeeds)
            _make_scalar_one_or_none_result(None),  # upsert check, pair 4 (succeeds)
        ]

        # 4 interest categories: sports fails, the other 3 succeed.
        async def _complete_side_effect(*args: object, **kwargs: Any) -> str:
            messages: list[dict[str, str]] = kwargs["messages"]
            prompt = messages[0]["content"]
            if "Sports & Fitness" in prompt:
                raise RuntimeError("provider timeout")
            return "A fine explanation."

        service = MiniCourseGenerationService(db)

        with patch(
            "app.services.mini_course_generation_service.llm_router.complete",
            new=AsyncMock(side_effect=_complete_side_effect),
        ):
            result = await service.generate_for_topic(topic_id=topic_id, school_id=school_id)

        assert result["explanations_written"] == len(INTEREST_CATEGORIES) - 1
        assert result["complete"] is False
        assert result["explanation_gaps"] == [{"subtopic_name": subtopic.name, "interest_category": "Sports & Fitness"}]
        assert result["quiz_gaps"] == []
        # The 3 successful pairs are still committed — nothing lost because one pair failed.
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_generate_topic_mini_course_when_quiz_self_gate_returns_none_then_not_recorded_as_gap(
        self,
    ) -> None:
        """Code-review finding: _generate_quiz_questions returning None (self-gate found
        the row already sufficient on a fresh re-check — e.g. an overlapping run for
        this topic finished it between the batch snapshot and this call) must not be
        recorded as a quiz_gap. Only an actual 0 (LLM/parse failure) is a gap."""
        db = _make_db()
        topic_id = str(uuid.uuid4())
        school_id = str(uuid.uuid4())
        subtopic = _make_subtopic()

        topic_context_row = MagicMock()
        topic_context_row.topic_name = "Algebra"
        topic_context_row.subject_name = "Mathematics"
        topic_context_row.grade_level = 8

        categories = [_make_interest_category(db_name) for db_name, _, _ in INTEREST_CATEGORIES]
        # existing_count=0 < target, so generate_for_topic will call
        # _generate_quiz_questions — mocked below to return None.
        existing_pair_rows = [MagicMock(subtopic_id=subtopic.id, interest_category_id=cat.id) for cat in categories]

        db.execute.side_effect = [
            _make_first_result(topic_context_row),
            _make_scalars_result([subtopic]),
            _make_scalars_result(categories),
            _make_all_result(existing_pair_rows),  # _fetch_existing_content_pairs: all 4 pairs already exist
            _make_all_result([]),  # _fetch_existing_question_counts: none yet
        ]

        service = MiniCourseGenerationService(db)

        with patch.object(MiniCourseGenerationService, "_generate_quiz_questions", new=AsyncMock(return_value=None)):
            result = await service.generate_for_topic(topic_id=topic_id, school_id=school_id)

        assert result["quiz_gaps"] == []
        assert result["questions_written"] == 0
        assert result["complete"] is True

    @pytest.mark.asyncio
    async def test_generate_topic_mini_course_when_content_already_approved_then_skips_subtopic(
        self,
    ) -> None:
        """Non-rejected content row exists → skip LLM call for that pair."""
        db = _make_db()
        topic_id = str(uuid.uuid4())
        school_id = str(uuid.uuid4())
        subtopic = _make_subtopic()

        topic_context_row = MagicMock()
        topic_context_row.topic_name = "Algebra"
        topic_context_row.subject_name = "Mathematics"
        topic_context_row.grade_level = 8

        categories = [_make_interest_category(db_name) for db_name, _, _ in INTEREST_CATEGORIES]

        # All 4 interest categories already have non-rejected content —
        # batch query returns one row per (subtopic_id, category_id) pair.
        existing_pairs = []
        for cat in categories:
            pair = MagicMock()
            pair.subtopic_id = subtopic.id
            pair.interest_category_id = cat.id
            existing_pairs.append(pair)

        # Simulate this subtopic already having 5 llm questions → skip quiz generation
        question_count_row = MagicMock()
        question_count_row.subtopic_id = subtopic.id
        question_count_row.cnt = 5

        execute_returns = [
            _make_first_result(topic_context_row),
            _make_scalars_result([subtopic]),
            _make_scalars_result(categories),
            _make_all_result(existing_pairs),  # _fetch_existing_content_pairs → all 4 pairs present
            _make_all_result([question_count_row]),  # _fetch_existing_question_counts (5 → skip quiz)
        ]
        db.execute.side_effect = execute_returns

        service = MiniCourseGenerationService(db)

        with patch(
            "app.services.mini_course_generation_service.llm_router.complete",
            new=AsyncMock(),
        ) as mock_llm:
            result = await service.generate_for_topic(topic_id=topic_id, school_id=school_id)

        # LLM must not be called at all — both explanations and quiz gen are skipped
        mock_llm.assert_not_called()
        assert result["subtopics_found"] == 1
        assert result["explanations_written"] == 0
        db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_generate_topic_mini_course_when_llm_fails_then_isolated_per_item_not_raised(
        self,
    ) -> None:
        """MCR-T3: a total LLM outage no longer propagates as an exception — each

        (subtopic, interest_category) pair and the quiz call are caught and skipped
        individually, so the run completes (and commits) with everything landed in
        explanation_gaps/quiz_gaps instead of discarding partial progress and forcing a
        full Celery retry. This replaces the old
        test_generate_topic_mini_course_when_llm_fails_then_retries, which asserted the
        pre-MCR-T3 fail-fast behavior this task deliberately removed.
        """
        db = _make_db()
        topic_id = str(uuid.uuid4())
        school_id = str(uuid.uuid4())
        subtopic = _make_subtopic()

        topic_context_row = MagicMock()
        topic_context_row.topic_name = "Algebra"
        topic_context_row.subject_name = "Mathematics"
        topic_context_row.grade_level = 8

        categories = [_make_interest_category(db_name) for db_name, _, _ in INTEREST_CATEGORIES]

        no_existing_quiz_row = MagicMock()
        no_existing_quiz_row.scalars.return_value = MagicMock(first=MagicMock(return_value=None))

        execute_returns = [
            _make_first_result(topic_context_row),
            _make_scalars_result([subtopic]),
            _make_scalars_result(categories),
            _make_all_result([]),  # _fetch_existing_content_pairs
            _make_all_result([]),  # _fetch_existing_question_counts
            no_existing_quiz_row,  # _generate_quiz_questions: existing quiz row check
        ]
        db.execute.side_effect = execute_returns

        service = MiniCourseGenerationService(db)

        with patch(
            "app.services.mini_course_generation_service.llm_router.complete",
            new=AsyncMock(side_effect=RuntimeError("LLM provider unavailable")),
        ):
            result = await service.generate_for_topic(topic_id=topic_id, school_id=school_id)

        assert result["complete"] is False
        assert result["explanations_written"] == 0
        assert len(result["explanation_gaps"]) == len(INTEREST_CATEGORIES)
        assert len(result["quiz_gaps"]) == 1

        # The run completed without raising, so the (empty) work done still commits —
        # this is what lets a later retry pick up only the gaps, not redo everything.
        db.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# _run_generation status-mapping unit tests (MCR-T3)
# ---------------------------------------------------------------------------


class _FakeSessionCM:
    """Minimal async context manager standing in for CeleryAsyncSessionLocal()."""

    def __init__(self, db: AsyncMock) -> None:
        self._db = db

    async def __aenter__(self) -> AsyncMock:
        return self._db

    async def __aexit__(self, *exc_info: object) -> bool:
        return False


def _make_topic(status: str = "none") -> MagicMock:
    topic = MagicMock()
    topic.name = "Algebra"
    topic.mini_course_status = status
    return topic


class TestRunGeneration:
    """Tests for _run_generation's mapping of service results onto Topic.mini_course_status."""

    @pytest.mark.asyncio
    async def test_run_generation_when_result_complete_then_status_set_to_ready(self) -> None:
        db = _make_db()
        topic = _make_topic()
        teacher = MagicMock(email="teacher@test.com")
        db.execute.side_effect = [
            _make_scalar_one_or_none_result(topic),  # topic lookup
            _make_all_result([]),  # subtopic_ids (empty -> fast-path block skipped)
            _make_scalar_one_or_none_result(teacher),  # teacher lookup for email
        ]

        mock_service = MagicMock()
        mock_service.generate_for_topic = AsyncMock(
            return_value={"complete": True, "explanation_gaps": [], "quiz_gaps": []}
        )

        with (
            patch("app.core.database.CeleryAsyncSessionLocal", return_value=_FakeSessionCM(db)),
            patch(
                "app.services.mini_course_generation_service.MiniCourseGenerationService",
                return_value=mock_service,
            ),
            patch("app.tasks.mini_course_tasks.send_mini_course_ready_email") as mock_email,
        ):
            result = await _run_generation(
                task=MagicMock(), topic_id=str(uuid.uuid4()), school_id=str(uuid.uuid4()), teacher_id=str(uuid.uuid4())
            )

        assert topic.mini_course_status == "ready"
        assert result["complete"] is True
        mock_email.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_generation_when_result_incomplete_with_partial_progress_then_status_set_to_partial(
        self,
    ) -> None:
        db = _make_db()
        topic = _make_topic()
        teacher = MagicMock(email="teacher@test.com")
        db.execute.side_effect = [
            _make_scalar_one_or_none_result(topic),
            _make_all_result([]),
            _make_scalar_one_or_none_result(teacher),
        ]

        mock_service = MagicMock()
        mock_service.generate_for_topic = AsyncMock(
            return_value={
                "complete": False,
                "explanations_written": 3,
                "questions_written": 1,
                "explanation_gaps": [{"subtopic_name": "Fractions", "interest_category": "Sports & Fitness"}],
                "quiz_gaps": [],
            }
        )

        with (
            patch("app.core.database.CeleryAsyncSessionLocal", return_value=_FakeSessionCM(db)),
            patch(
                "app.services.mini_course_generation_service.MiniCourseGenerationService",
                return_value=mock_service,
            ),
            patch("app.tasks.mini_course_tasks.send_mini_course_ready_email"),
        ):
            result = await _run_generation(
                task=MagicMock(), topic_id=str(uuid.uuid4()), school_id=str(uuid.uuid4()), teacher_id=str(uuid.uuid4())
            )

        assert topic.mini_course_status == "partial"
        assert result["complete"] is False

    @pytest.mark.asyncio
    async def test_run_generation_when_result_incomplete_then_warning_logged_with_gap_detail(self) -> None:
        db = _make_db()
        topic = _make_topic()
        db.execute.side_effect = [
            _make_scalar_one_or_none_result(topic),
            _make_all_result([]),
            _make_scalar_one_or_none_result(None),  # no teacher_id path exercised below
        ]

        gaps = [{"subtopic_name": "Fractions", "interest_category": "Sports & Fitness"}]
        mock_service = MagicMock()
        mock_service.generate_for_topic = AsyncMock(
            return_value={
                "complete": False,
                "explanations_written": 3,
                "questions_written": 1,
                "explanation_gaps": gaps,
                "quiz_gaps": [],
            }
        )

        with (
            patch("app.core.database.CeleryAsyncSessionLocal", return_value=_FakeSessionCM(db)),
            patch(
                "app.services.mini_course_generation_service.MiniCourseGenerationService",
                return_value=mock_service,
            ),
            patch("app.tasks.mini_course_tasks.logger") as mock_logger,
        ):
            await _run_generation(
                task=MagicMock(), topic_id=str(uuid.uuid4()), school_id=str(uuid.uuid4()), teacher_id=""
            )

        warning_calls = [c for c in mock_logger.warning.call_args_list if c[0][0] == "mini_course_generation_partial"]
        assert len(warning_calls) == 1
        assert warning_calls[0].kwargs["explanation_gaps"] == gaps
        assert warning_calls[0].kwargs["gap_count"] == 1

    @pytest.mark.asyncio
    async def test_run_generation_when_zero_items_succeed_then_raises_and_marks_failed(self) -> None:
        """Code-review finding: catching per-item LLM failures internally (MCR-T3) must
        not silently remove Celery's retry for a TOTAL outage — the case it was built
        for. A run that attempted work (gaps present) and produced zero successes must
        still raise, hit the except block, mark 'failed', and let Celery retry / the
        on_failure CRITICAL alert fire after retries are exhausted — exactly the
        pre-MCR-T3 behavior for this specific case. A partial success (something
        landed) must NOT raise — see test_run_generation_when_result_incomplete_with_partial_progress_then_status_set_to_partial.
        """
        db = _make_db()
        topic = _make_topic()
        db.execute.side_effect = [
            _make_scalar_one_or_none_result(topic),
            _make_all_result([]),
        ]

        mock_service = MagicMock()
        mock_service.generate_for_topic = AsyncMock(
            return_value={
                "complete": False,
                "explanations_written": 0,
                "questions_written": 0,
                "explanation_gaps": [{"subtopic_name": "Fractions", "interest_category": "Sports & Fitness"}],
                "quiz_gaps": [],
            }
        )

        with (
            patch("app.core.database.CeleryAsyncSessionLocal", return_value=_FakeSessionCM(db)),
            patch(
                "app.services.mini_course_generation_service.MiniCourseGenerationService",
                return_value=mock_service,
            ),
            pytest.raises(RuntimeError, match="zero successful items"),
        ):
            await _run_generation(
                task=MagicMock(), topic_id=str(uuid.uuid4()), school_id=str(uuid.uuid4()), teacher_id=""
            )

        assert topic.mini_course_status == "failed"

    @pytest.mark.asyncio
    async def test_run_generation_when_no_subtopics_then_marked_ready_not_partial(self) -> None:
        """Code-review finding: generate_for_topic's Rule-17 'no subtopics' early return
        used to omit complete/explanation_gaps/quiz_gaps, so result.get('complete') read
        None/falsy and this case was mismarked 'partial' instead of 'ready' — a topic
        with nothing to generate isn't a failure of any kind."""
        db = _make_db()
        topic = _make_topic()
        db.execute.side_effect = [
            _make_scalar_one_or_none_result(topic),
            _make_all_result([]),
        ]

        mock_service = MagicMock()
        mock_service.generate_for_topic = AsyncMock(
            return_value={
                "subtopics_found": 0,
                "subtopics_processed": 0,
                "explanations_written": 0,
                "questions_written": 0,
                "explanation_gaps": [],
                "quiz_gaps": [],
                "complete": True,
            }
        )

        with (
            patch("app.core.database.CeleryAsyncSessionLocal", return_value=_FakeSessionCM(db)),
            patch(
                "app.services.mini_course_generation_service.MiniCourseGenerationService",
                return_value=mock_service,
            ),
        ):
            await _run_generation(
                task=MagicMock(), topic_id=str(uuid.uuid4()), school_id=str(uuid.uuid4()), teacher_id=""
            )

        assert topic.mini_course_status == "ready"

    @pytest.mark.asyncio
    async def test_run_generation_when_fast_path_checked_then_query_scopes_to_caller_school(self) -> None:
        """Code-review finding: the fast-path 'already complete' check counted ALL
        schools' content for a topic with no scope filter — School A finishing
        generation for a shared curriculum topic could make this fast path fire for
        School B too, marking School B's topic 'ready' while School B's own students
        still see nothing. A mocked db.execute doesn't evaluate WHERE clauses, so this
        asserts the compiled SQL of the actual_count query references the caller's
        school_id, rather than trusting the returned (mocked) count alone."""
        db = _make_db()
        topic = _make_topic()
        school_id = uuid.uuid4()
        subtopic_id = uuid.uuid4()

        subtopic_ids_result = MagicMock()
        subtopic_ids_result.all = MagicMock(return_value=[(subtopic_id,)])
        cat_count_result = MagicMock()
        cat_count_result.scalar_one = MagicMock(return_value=4)
        actual_count_result = MagicMock()
        actual_count_result.scalar_one = MagicMock(return_value=0)  # not complete -> slow path

        mock_service = MagicMock()
        mock_service.generate_for_topic = AsyncMock(
            return_value={
                "complete": True,
                "explanations_written": 4,
                "questions_written": 5,
                "explanation_gaps": [],
                "quiz_gaps": [],
            }
        )

        db.execute.side_effect = [
            _make_scalar_one_or_none_result(topic),
            subtopic_ids_result,
            cat_count_result,
            actual_count_result,
            _make_scalar_one_or_none_result(None),  # teacher_id == "" -> not queried, placeholder unused
        ]

        with (
            patch("app.core.database.CeleryAsyncSessionLocal", return_value=_FakeSessionCM(db)),
            patch(
                "app.services.mini_course_generation_service.MiniCourseGenerationService",
                return_value=mock_service,
            ),
        ):
            await _run_generation(task=MagicMock(), topic_id=str(uuid.uuid4()), school_id=str(school_id), teacher_id="")

        actual_count_query = db.execute.call_args_list[3].args[0]
        compiled_sql = str(actual_count_query.compile(compile_kwargs={"literal_binds": True}))
        assert "subtopic_content.scope" in compiled_sql
        assert str(school_id).replace("-", "") in compiled_sql

    @pytest.mark.asyncio
    async def test_run_generation_when_service_raises_unexpectedly_then_status_set_to_failed(self) -> None:
        db = _make_db()
        topic = _make_topic()
        db.execute.side_effect = [
            _make_scalar_one_or_none_result(topic),
            _make_all_result([]),
        ]

        mock_service = MagicMock()
        mock_service.generate_for_topic = AsyncMock(side_effect=RuntimeError("database connection lost"))

        with (
            patch("app.core.database.CeleryAsyncSessionLocal", return_value=_FakeSessionCM(db)),
            patch(
                "app.services.mini_course_generation_service.MiniCourseGenerationService",
                return_value=mock_service,
            ),
            pytest.raises(RuntimeError, match="database connection lost"),
        ):
            await _run_generation(
                task=MagicMock(), topic_id=str(uuid.uuid4()), school_id=str(uuid.uuid4()), teacher_id=""
            )

        assert topic.mini_course_status == "failed"

    @pytest.mark.asyncio
    async def test_run_generation_when_partial_then_email_still_sent_to_teacher(self) -> None:
        db = _make_db()
        topic = _make_topic()
        teacher = MagicMock(email="teacher@test.com")
        db.execute.side_effect = [
            _make_scalar_one_or_none_result(topic),
            _make_all_result([]),
            _make_scalar_one_or_none_result(teacher),
        ]

        mock_service = MagicMock()
        mock_service.generate_for_topic = AsyncMock(
            return_value={
                "complete": False,
                "explanations_written": 3,
                "questions_written": 1,
                "explanation_gaps": [{"subtopic_name": "Fractions", "interest_category": "Sports & Fitness"}],
                "quiz_gaps": [],
            }
        )

        with (
            patch("app.core.database.CeleryAsyncSessionLocal", return_value=_FakeSessionCM(db)),
            patch(
                "app.services.mini_course_generation_service.MiniCourseGenerationService",
                return_value=mock_service,
            ),
            patch("app.tasks.mini_course_tasks.send_mini_course_ready_email") as mock_email,
        ):
            await _run_generation(
                task=MagicMock(), topic_id=str(uuid.uuid4()), school_id=str(uuid.uuid4()), teacher_id=str(uuid.uuid4())
            )

        # A teacher landing at "partial" must still hear generation finished — silence
        # here would look identical to the task having never run at all.
        mock_email.assert_called_once()


# ---------------------------------------------------------------------------
# Celery task wrapper unit tests
# ---------------------------------------------------------------------------


class TestGenerateMiniCourseTask:
    """Tests for the generate_topic_mini_course Celery task wrapper."""

    def test_generate_topic_mini_course_task_on_failure_logs_critical(self) -> None:
        """GenerateMiniCourseTask.on_failure must emit a CRITICAL log (Rule 18)."""
        task = GenerateMiniCourseTask()
        topic_id = str(uuid.uuid4())
        exc = RuntimeError("Some unrecoverable error")

        with patch("app.tasks.mini_course_tasks.logger") as mock_logger:
            task.on_failure(
                exc=exc,
                task_id="celery-task-123",
                args=(topic_id, "school-id"),
                kwargs={},
                einfo=None,
            )

        mock_logger.critical.assert_called_once()
        call_kwargs = mock_logger.critical.call_args
        event_name = call_kwargs[0][0]
        assert "permanently_failed" in event_name
        assert call_kwargs[1].get("topic_id") == topic_id
        assert call_kwargs[1].get("exc_info") is True
