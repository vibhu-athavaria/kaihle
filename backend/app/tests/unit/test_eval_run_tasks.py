"""Unit tests for the production-evaluation Celery tasks (MLH-T18 slice 5b-ii)."""

import asyncio
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from celery.schedules import crontab

from app.services.eval_run_admin_service import ScheduleOutcome
from app.tasks import eval_run_tasks
from app.tasks.celery_app import celery_app


def _spy_loop_and_forbid_asyncio_run(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    real_new_event_loop = asyncio.new_event_loop
    new_loop = MagicMock(side_effect=real_new_event_loop)
    monkeypatch.setattr(eval_run_tasks.asyncio, "new_event_loop", new_loop)
    monkeypatch.setattr(
        eval_run_tasks.asyncio, "run", MagicMock(side_effect=AssertionError("asyncio.run must not be used"))
    )
    return new_loop


def test_run_task_when_final_retry_fails_then_critical_logged_with_exc_info_and_task_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = MagicMock()
    monkeypatch.setattr(eval_run_tasks, "logger", logger)
    run_id = str(uuid.uuid4())
    exc = RuntimeError("infrastructure down: secret prompt text must not be logged")

    eval_run_tasks.EvalRunTask().on_failure(exc, "task-1", (run_id,), {}, None)

    logger.critical.assert_called_once()
    event = logger.critical.call_args.args[0]
    fields = logger.critical.call_args.kwargs
    assert event == "eval_run_task_permanently_failed"
    assert fields["task_name"] == eval_run_tasks.RUN_TASK_NAME
    assert fields["run_id"] == run_id and fields["task_id"] == "task-1"
    assert fields["exc_info"]
    assert "secret" not in repr(fields.get("error", "")) and fields["error_type"] == "RuntimeError"


def test_run_task_when_run_id_passed_by_keyword_then_failure_log_still_carries_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = MagicMock()
    monkeypatch.setattr(eval_run_tasks, "logger", logger)

    eval_run_tasks.EvalRunTask().on_failure(RuntimeError("x"), "t", (), {"run_id": "abc"}, None)

    assert logger.critical.call_args.kwargs["run_id"] == "abc"


def test_run_task_when_executed_then_uses_new_event_loop_not_asyncio_run(monkeypatch: pytest.MonkeyPatch) -> None:
    new_loop = _spy_loop_and_forbid_asyncio_run(monkeypatch)
    execute = AsyncMock()
    monkeypatch.setattr(eval_run_tasks, "_execute_run", execute)
    run_id = uuid.uuid4()

    eval_run_tasks.run_eval_run.run(str(run_id))

    new_loop.assert_called_once()
    execute.assert_awaited_once_with(run_id)


def test_run_task_when_infrastructure_error_then_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(eval_run_tasks, "_execute_run", AsyncMock(side_effect=ConnectionError("db down")))
    retry = MagicMock(side_effect=ConnectionError("retry"))
    monkeypatch.setattr(eval_run_tasks.run_eval_run, "retry", retry)

    with pytest.raises(ConnectionError):
        eval_run_tasks.run_eval_run.run(str(uuid.uuid4()))

    retry.assert_called_once()


def test_run_task_when_run_id_malformed_then_logged_and_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    retry = MagicMock()
    monkeypatch.setattr(eval_run_tasks.run_eval_run, "retry", retry)

    eval_run_tasks.run_eval_run.run("not-a-uuid")

    retry.assert_not_called()


async def test_execute_run_when_run_missing_then_returns_without_raising(monkeypatch: pytest.MonkeyPatch) -> None:
    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    monkeypatch.setattr(eval_run_tasks, "CeleryAsyncSessionLocal", MagicMock(return_value=session))
    service = MagicMock()
    service.execute_run = AsyncMock(side_effect=LookupError("gone"))
    monkeypatch.setattr(eval_run_tasks, "EvalRunService", MagicMock(return_value=service))

    await eval_run_tasks._execute_run(uuid.uuid4())

    service.execute_run.assert_awaited_once()
    assert service.execute_run.await_args.args[1] is eval_run_tasks.SYSTEM_EVAL_ACTOR


async def test_execute_run_when_run_exists_then_executed_with_system_actor(monkeypatch: pytest.MonkeyPatch) -> None:
    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    monkeypatch.setattr(eval_run_tasks, "CeleryAsyncSessionLocal", MagicMock(return_value=session))
    service = MagicMock()
    service.execute_run = AsyncMock()
    monkeypatch.setattr(eval_run_tasks, "EvalRunService", MagicMock(return_value=service))
    run_id = uuid.uuid4()

    await eval_run_tasks._execute_run(run_id)

    service.execute_run.assert_awaited_once_with(run_id, eval_run_tasks.SYSTEM_EVAL_ACTOR)


def test_enqueue_eval_run_when_called_then_sends_run_id_as_string(monkeypatch: pytest.MonkeyPatch) -> None:
    delay = MagicMock()
    monkeypatch.setattr(eval_run_tasks.run_eval_run, "delay", delay)
    run_id = uuid.uuid4()

    eval_run_tasks.enqueue_eval_run(run_id)

    delay.assert_called_once_with(str(run_id))


def test_schedule_task_when_executed_then_uses_new_event_loop_and_logs_outcome(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    new_loop = _spy_loop_and_forbid_asyncio_run(monkeypatch)
    schedule = AsyncMock(return_value=ScheduleOutcome(started=2, skipped_not_allowed=1))
    monkeypatch.setattr(eval_run_tasks, "_schedule_weekly_runs", schedule)
    logger = MagicMock()
    monkeypatch.setattr(eval_run_tasks, "logger", logger)

    eval_run_tasks.schedule_weekly_eval_runs.run()

    new_loop.assert_called_once()
    schedule.assert_awaited_once()
    assert logger.info.call_args.kwargs["started"] == 2 and logger.info.call_args.kwargs["skipped_not_allowed"] == 1


def test_schedule_task_when_infrastructure_error_then_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(eval_run_tasks, "_schedule_weekly_runs", AsyncMock(side_effect=ConnectionError("db")))
    retry = MagicMock(side_effect=ConnectionError("retry"))
    monkeypatch.setattr(eval_run_tasks.schedule_weekly_eval_runs, "retry", retry)

    with pytest.raises(ConnectionError):
        eval_run_tasks.schedule_weekly_eval_runs.run()

    retry.assert_called_once()


async def test_schedule_weekly_runs_when_called_then_service_built_with_enqueue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    monkeypatch.setattr(eval_run_tasks, "CeleryAsyncSessionLocal", MagicMock(return_value=session))
    outcome = ScheduleOutcome(started=1)
    service = MagicMock()
    service.schedule_weekly_runs = AsyncMock(return_value=outcome)
    factory = MagicMock(return_value=service)
    monkeypatch.setattr(eval_run_tasks, "EvalRunAdminService", factory)

    assert await eval_run_tasks._schedule_weekly_runs() is outcome
    assert factory.call_args.kwargs["enqueue"] is eval_run_tasks.enqueue_eval_run


def test_celery_app_when_configured_then_includes_eval_tasks_and_weekly_beat_entry() -> None:
    assert "app.tasks.eval_run_tasks" in celery_app.conf.include
    entry: Any = celery_app.conf.beat_schedule["schedule-weekly-eval-runs"]
    assert entry["task"] == eval_run_tasks.SCHEDULE_TASK_NAME
    assert entry["schedule"] == crontab(hour=4, minute=0, day_of_week=1)
    assert eval_run_tasks.run_eval_run.name == eval_run_tasks.RUN_TASK_NAME
