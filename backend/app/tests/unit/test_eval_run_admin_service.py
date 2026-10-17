"""Unit tests for `EvalRunAdminService` (MLH-T18 slice 5b-ii): manual request, listing, weekly beat.

The run service and settings source are faked; the real Postgres behaviour is covered by
`integration/test_eval_run_routes.py`.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.eval_results import EvalRun
from app.services.eval_results_service import EvalResultsValidationError
from app.services.eval_run_admin_service import (
    EnqueueFailedError,
    EvalRunAdminService,
    EvalRunRequestError,
    ScheduleOutcome,
)
from app.services.eval_run_service import RunNotAllowedError
from app.services.platform_settings_service import EvalSettings

NOW = datetime(2026, 10, 19, 4, 0, tzinfo=UTC)
JUDGE = "judgevendor/judge-1"
CONFIG = settings.model_copy(update={"llm_eval_judge_model": JUDGE})


def _eval_settings(**overrides: Any) -> EvalSettings:
    values: dict[str, Any] = {
        "monthly_budget_usd": Decimal("50"),
        "enabled_tasks": ["question_generation"],
        "sample_size_per_task": 50,
        "window_days": 7,
        "include_indicative": False,
        "student_text_ack": {},
        "updated_by": None,
        "updated_at": None,
    }
    values.update(overrides)
    return EvalSettings(**values)


def _run(status: str = "pending", task: str = "question_generation") -> EvalRun:
    return EvalRun(
        id=uuid.uuid4(),
        task=task,
        window_start=NOW - timedelta(days=7),
        window_end=NOW,
        seed="s",
        trigger="manual",
        status=status,
    )


class _Platform:
    def __init__(self, eval_settings: EvalSettings) -> None:
        self._settings = eval_settings

    async def get_eval_settings(self) -> EvalSettings:
        return self._settings


def _service(
    eval_settings: EvalSettings | None = None,
    *,
    request_run: AsyncMock | None = None,
    enqueue: MagicMock | None = None,
    config: Any = CONFIG,
    results: Any = None,
) -> tuple[EvalRunAdminService, AsyncMock, MagicMock]:
    runner = MagicMock()
    runner.request_run = request_run or AsyncMock(return_value=(_run(), True))
    enqueue = enqueue or MagicMock()
    service = EvalRunAdminService(
        MagicMock(spec=AsyncSession),
        enqueue=enqueue,
        runner=runner,
        platform_settings=_Platform(eval_settings or _eval_settings()),
        results=results,
        config=config,
        clock=lambda: NOW,
    )
    return service, runner.request_run, enqueue


async def test_request_manual_run_when_created_then_enqueued_once_and_requester_recorded() -> None:
    run = _run()
    service, request_run, enqueue = _service(request_run=AsyncMock(return_value=(run, True)))
    admin_id = uuid.uuid4()

    result, created = await service.request_manual_run(
        task="question_generation", window_start=None, window_end=None, seed=None, requested_by=admin_id
    )

    assert (result, created) == (run, True)
    enqueue.assert_called_once_with(run.id)
    kwargs = request_run.await_args_list[-1].kwargs
    assert kwargs["requested_by"] == admin_id and kwargs["trigger"] == "manual"


async def test_request_manual_run_when_run_already_exists_then_not_enqueued_again() -> None:
    service, _, enqueue = _service(request_run=AsyncMock(return_value=(_run(), False)))

    _, created = await service.request_manual_run(
        task="question_generation", window_start=None, window_end=None, seed="same", requested_by=uuid.uuid4()
    )

    assert created is False
    enqueue.assert_not_called()


async def test_request_manual_run_when_bounds_omitted_then_window_is_saved_length_ending_now_with_fresh_seed() -> None:
    service, request_run, _ = _service(_eval_settings(window_days=14))

    await service.request_manual_run(
        task="question_generation", window_start=None, window_end=None, seed=None, requested_by=uuid.uuid4()
    )

    kwargs = request_run.await_args_list[-1].kwargs
    assert kwargs["window_end"] == NOW and kwargs["window_start"] == NOW - timedelta(days=14)
    assert kwargs["seed"].startswith("manual-") and len(kwargs["seed"]) <= 64


async def test_request_manual_run_when_only_start_given_then_end_defaults_to_now() -> None:
    service, request_run, _ = _service()
    start = NOW - timedelta(days=3)

    await service.request_manual_run(
        task="question_generation", window_start=start, window_end=None, seed="x", requested_by=uuid.uuid4()
    )

    kwargs = request_run.await_args_list[-1].kwargs
    assert (kwargs["window_start"], kwargs["window_end"], kwargs["seed"]) == (start, NOW, "x")


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (datetime(2026, 10, 1), NOW),  # naive start
        (NOW, NOW - timedelta(days=1)),  # end before start
        (NOW - timedelta(days=400), NOW),  # over the cap
    ],
    ids=["naive", "unordered", "too_long"],
)
async def test_request_manual_run_when_window_invalid_then_request_error_and_nothing_enqueued(
    start: datetime, end: datetime
) -> None:
    service, request_run, enqueue = _service()

    with pytest.raises(EvalRunRequestError):
        await service.request_manual_run(
            task="question_generation", window_start=start, window_end=end, seed="x", requested_by=uuid.uuid4()
        )

    request_run.assert_not_awaited()
    enqueue.assert_not_called()


async def test_request_manual_run_when_task_not_allowed_then_generic_message_without_echoing_input() -> None:
    service, _, enqueue = _service(request_run=AsyncMock(side_effect=RunNotAllowedError("task 'secret-x' no")))

    with pytest.raises(EvalRunRequestError) as excinfo:
        await service.request_manual_run(
            task="secret-x", window_start=None, window_end=None, seed=None, requested_by=uuid.uuid4()
        )

    assert "secret-x" not in str(excinfo.value)
    enqueue.assert_not_called()


async def test_request_manual_run_when_store_rejects_input_then_request_error() -> None:
    service, _, _ = _service(request_run=AsyncMock(side_effect=EvalResultsValidationError("seed must not be blank")))

    with pytest.raises(EvalRunRequestError, match="seed must not be blank"):
        await service.request_manual_run(
            task="question_generation", window_start=None, window_end=None, seed="  ", requested_by=uuid.uuid4()
        )


async def test_request_manual_run_when_enqueue_fails_then_enqueue_failed_error_raised() -> None:
    service, _, _ = _service(enqueue=MagicMock(side_effect=ConnectionError("broker down")))

    with pytest.raises(EnqueueFailedError):
        await service.request_manual_run(
            task="question_generation", window_start=None, window_end=None, seed=None, requested_by=uuid.uuid4()
        )


async def test_list_and_get_run_when_called_then_delegate_to_results_store() -> None:
    run = _run()
    results = MagicMock()
    results.list_runs = AsyncMock(return_value=([run], 1))
    results.get_run = AsyncMock(return_value=run)
    service, _, _ = _service(results=results)

    assert await service.list_runs(page=2, page_size=10) == ([run], 1)
    results.list_runs.assert_awaited_once_with(page=2, page_size=10)
    assert await service.get_run(run.id) is run


async def test_list_runs_when_page_out_of_bounds_then_request_error() -> None:
    service, _, _ = _service(results=MagicMock())

    with pytest.raises(EvalRunRequestError):
        await service.list_runs(page=0, page_size=10)
    with pytest.raises(EvalRunRequestError):
        await service.list_runs(page=1, page_size=1000)


async def test_beat_entry_when_budget_zero_then_run_not_started() -> None:
    service, request_run, enqueue = _service(_eval_settings(monthly_budget_usd=Decimal("0")))

    outcome = await service.schedule_weekly_runs()

    assert outcome == ScheduleOutcome(refused_reason="budget_zero")
    request_run.assert_not_awaited()
    enqueue.assert_not_called()


async def test_beat_entry_when_no_tasks_enabled_then_run_not_started() -> None:
    service, request_run, enqueue = _service(_eval_settings(enabled_tasks=[]))

    outcome = await service.schedule_weekly_runs()

    assert outcome.refused_reason == "no_tasks_enabled"
    request_run.assert_not_awaited()
    enqueue.assert_not_called()


async def test_beat_entry_when_judge_unset_then_run_not_started() -> None:
    service, request_run, enqueue = _service(config=settings.model_copy(update={"llm_eval_judge_model": ""}))

    outcome = await service.schedule_weekly_runs()

    assert outcome.refused_reason == "judge_unset"
    request_run.assert_not_awaited()
    enqueue.assert_not_called()


async def test_beat_entry_when_tasks_enabled_then_scheduled_run_created_and_enqueued_per_task() -> None:
    runs = {"a_task": _run(task="a_task"), "b_task": _run(task="b_task")}

    async def request_run(**kwargs: Any) -> tuple[EvalRun, bool]:
        return runs[kwargs["task"]], True

    service, request_run_mock, enqueue = _service(
        _eval_settings(enabled_tasks=["b_task", "a_task"], window_days=7),
        request_run=AsyncMock(side_effect=request_run),
    )

    outcome = await service.schedule_weekly_runs()

    assert outcome == ScheduleOutcome(started=2)
    assert [c.kwargs["task"] for c in request_run_mock.await_args_list] == ["a_task", "b_task"]
    first = request_run_mock.await_args_list[0].kwargs
    assert first["trigger"] == "scheduled" and first.get("requested_by") is None
    assert first["seed"] == "scheduled-2026-10-19" and first["window_end"] == datetime(2026, 10, 19, tzinfo=UTC)
    assert [c.args[0] for c in enqueue.call_args_list] == [runs["a_task"].id, runs["b_task"].id]


async def test_beat_entry_when_acknowledgement_missing_then_task_skipped_counted_and_others_still_run() -> None:
    ok = _run(task="ok_task")

    async def request_run(**kwargs: Any) -> tuple[EvalRun, bool]:
        if kwargs["task"] == "needs_ack":
            raise RunNotAllowedError("no ack")
        return ok, True

    service, _, enqueue = _service(
        _eval_settings(enabled_tasks=["needs_ack", "ok_task"]), request_run=AsyncMock(side_effect=request_run)
    )

    outcome = await service.schedule_weekly_runs()

    assert outcome == ScheduleOutcome(started=1, skipped_not_allowed=1)
    enqueue.assert_called_once_with(ok.id)


async def test_beat_entry_when_repeated_same_day_then_pending_run_requeued_but_finished_run_left_alone() -> None:
    pending, finished = _run(status="pending", task="a_task"), _run(status="completed", task="b_task")
    returned = {"a_task": pending, "b_task": finished}

    async def request_run(**kwargs: Any) -> tuple[EvalRun, bool]:
        return returned[kwargs["task"]], False

    service, _, enqueue = _service(
        _eval_settings(enabled_tasks=["a_task", "b_task"]), request_run=AsyncMock(side_effect=request_run)
    )

    outcome = await service.schedule_weekly_runs()

    assert outcome == ScheduleOutcome(started=1, existing=1)
    enqueue.assert_called_once_with(pending.id)
