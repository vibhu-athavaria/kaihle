"""Unit tests for `llm_log_service` — the per-call list/detail read side backing the
Kaihle Admin "LLM Logs" page. `db.execute` is mocked, matching this codebase's
`tests/unit/` convention (see `test_analytics_service.py`)."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.llm_log_service import get_llm_log, list_llm_logs

LOG_ID = uuid.uuid4()
SCHOOL_ID = uuid.uuid4()
CREATED_AT = datetime(2026, 9, 1, tzinfo=UTC)


def _summary_row(**overrides: object) -> dict[str, object]:
    defaults: dict[str, object] = {
        "id": LOG_ID,
        "created_at": CREATED_AT,
        "task": "question_generation",
        "model": "test/model-a",
        "component": "script:generate_gap_questions",
        "run_id": "run-1",
        "prompt_tokens": 100,
        "completion_tokens": 200,
        "total_tokens": 300,
        "latency_ms": 500,
        "estimated_cost_usd": Decimal("0.001500"),
        "succeeded": True,
        "error_type": None,
    }
    defaults.update(overrides)
    return defaults


def _detail_row(**overrides: object) -> dict[str, object]:
    defaults = _summary_row()
    defaults.update(
        {
            "prompt_text": "[user] What is 2+2?",
            "response_text": "4",
            "error_detail": None,
            "correlation_id": "corr-1",
            "school_id": SCHOOL_ID,
            "streamed": False,
        }
    )
    defaults.update(overrides)
    return defaults


def _mock_db(rows: list[dict[str, object]], total: int) -> MagicMock:
    db = MagicMock(spec=AsyncSession)

    rows_result = MagicMock()
    rows_result.mappings.return_value = rows

    count_result = MagicMock()
    count_result.scalar_one.return_value = total

    db.execute = AsyncMock(side_effect=[rows_result, count_result])
    return db


class TestListLlmLogs:
    async def test_list_llm_logs_when_no_events_then_returns_empty_list_and_zero_total(self) -> None:
        db = _mock_db(rows=[], total=0)

        logs, total = await list_llm_logs(db)

        assert logs == []
        assert total == 0

    async def test_list_llm_logs_when_events_present_then_mapped_to_summary_rows(self) -> None:
        db = _mock_db(rows=[_summary_row()], total=1)

        logs, total = await list_llm_logs(db)

        assert total == 1
        assert len(logs) == 1
        log = logs[0]
        assert log.id == LOG_ID
        assert log.task == "question_generation"
        assert log.model == "test/model-a"
        assert log.estimated_cost_usd == Decimal("0.001500")

    async def test_list_llm_logs_when_page_requested_then_correct_limit_and_offset_applied(self) -> None:
        db = _mock_db(rows=[], total=0)

        await list_llm_logs(db, page=3, page_size=10)

        params = db.execute.call_args_list[0].args[1]
        assert params["limit"] == 10
        assert params["offset"] == 20

    async def test_list_llm_logs_when_default_page_then_offset_zero(self) -> None:
        db = _mock_db(rows=[], total=0)

        await list_llm_logs(db)

        params = db.execute.call_args_list[0].args[1]
        assert params["offset"] == 0


class TestGetLlmLog:
    async def test_get_llm_log_when_found_then_returns_detail_with_prompt_and_response_text(self) -> None:
        db = MagicMock(spec=AsyncSession)
        result = MagicMock()
        result.mappings.return_value.one_or_none.return_value = _detail_row()
        db.execute = AsyncMock(return_value=result)

        log = await get_llm_log(db, LOG_ID)

        assert log is not None
        assert log.id == LOG_ID
        assert log.prompt_text == "[user] What is 2+2?"
        assert log.response_text == "4"
        assert log.school_id == SCHOOL_ID

    async def test_get_llm_log_when_not_found_then_returns_none(self) -> None:
        db = MagicMock(spec=AsyncSession)
        result = MagicMock()
        result.mappings.return_value.one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result)

        log = await get_llm_log(db, uuid.uuid4())

        assert log is None
