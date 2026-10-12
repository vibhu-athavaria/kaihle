"""Unit tests for `PlatformSettingsService` — the Kaihle Admin production-evaluation controls.

`db.execute` is mocked, matching this codebase's `tests/unit/` convention. The DB-level
guarantees (singleton, CHECK ranges) are covered by the integration tests.
"""

import uuid
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.providers.router import TASK_MODEL_MAP
from app.core.config import Settings
from app.models.platform_settings import PlatformSettings
from app.services.platform_settings_service import (
    DEFAULT_SAMPLE_SIZE,
    DEFAULT_WINDOW_DAYS,
    TASKS_WITH_STUDENT_TEXT,
    EvalSettingsValidationError,
    PlatformSettingsService,
)

ACTOR_ID = uuid.uuid4()
OTHER_ACTOR_ID = uuid.uuid4()
NO_STUDENT_TEXT_TASK = "question_generation"
STUDENT_TEXT_TASK = "grade_open_answer"


def _row(**overrides: Any) -> PlatformSettings:
    values: dict[str, Any] = {
        "id": 1,
        "eval_monthly_budget_usd": Decimal("0"),
        "eval_enabled_tasks": [],
        "eval_sample_size_per_task": DEFAULT_SAMPLE_SIZE,
        "eval_window_days": DEFAULT_WINDOW_DAYS,
        "eval_include_indicative": False,
        "eval_student_text_ack": {},
        "updated_by": None,
        "updated_at": None,
    }
    values.update(overrides)
    return PlatformSettings(**values)


def _db(row: PlatformSettings | None) -> AsyncMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = row
    result.scalar_one.return_value = row
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = result
    return db


def _update_kwargs(**overrides: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "actor_id": ACTOR_ID,
        "monthly_budget_usd": Decimal("25.00"),
        "enabled_tasks": [NO_STUDENT_TEXT_TASK],
        "sample_size_per_task": 40,
        "window_days": 14,
        "include_indicative": True,
        "acknowledge_student_text_tasks": [],
    }
    kwargs.update(overrides)
    return kwargs


async def test_get_eval_settings_when_no_row_then_returns_defaults_with_budget_zero_and_empty_allowlist() -> None:
    db = _db(None)

    settings = await PlatformSettingsService(db).get_eval_settings()

    assert settings.monthly_budget_usd == Decimal("0")
    assert settings.enabled_tasks == []
    assert settings.sample_size_per_task == DEFAULT_SAMPLE_SIZE
    assert settings.window_days == DEFAULT_WINDOW_DAYS
    assert settings.include_indicative is False
    assert settings.student_text_ack == {}
    assert settings.updated_at is None
    db.add.assert_not_called()  # reading never inserts a row
    db.commit.assert_not_called()


async def test_update_eval_settings_when_valid_then_persists_and_returns_new_values() -> None:
    row = _row()
    db = _db(row)

    settings = await PlatformSettingsService(db).update_eval_settings(**_update_kwargs())

    assert row.eval_monthly_budget_usd == Decimal("25.00")
    assert row.eval_enabled_tasks == [NO_STUDENT_TEXT_TASK]
    assert row.eval_sample_size_per_task == 40
    assert row.eval_window_days == 14
    assert row.eval_include_indicative is True
    assert row.updated_by == ACTOR_ID
    assert settings.monthly_budget_usd == Decimal("25.00")
    assert settings.enabled_tasks == [NO_STUDENT_TEXT_TASK]
    db.commit.assert_awaited_once()


@pytest.mark.parametrize("budget", [Decimal("-0.01"), Decimal("NaN"), Decimal("Infinity"), Decimal("1e12")])
async def test_update_eval_settings_when_budget_negative_then_raises_validation_error(budget: Decimal) -> None:
    row = _row()
    db = _db(row)

    with pytest.raises(EvalSettingsValidationError, match="budget"):
        await PlatformSettingsService(db).update_eval_settings(**_update_kwargs(monthly_budget_usd=budget))

    assert row.eval_monthly_budget_usd == Decimal("0")
    db.commit.assert_not_called()


@pytest.mark.parametrize("sample_size", [0, 201, -5])
async def test_update_eval_settings_when_sample_size_over_max_then_raises_validation_error(sample_size: int) -> None:
    db = _db(_row())

    with pytest.raises(EvalSettingsValidationError, match="sample"):
        await PlatformSettingsService(db).update_eval_settings(**_update_kwargs(sample_size_per_task=sample_size))

    db.commit.assert_not_called()


@pytest.mark.parametrize("window_days", [0, 91])
async def test_update_eval_settings_when_window_out_of_range_then_raises_validation_error(window_days: int) -> None:
    db = _db(_row())

    with pytest.raises(EvalSettingsValidationError, match="window"):
        await PlatformSettingsService(db).update_eval_settings(**_update_kwargs(window_days=window_days))

    db.commit.assert_not_called()


@pytest.mark.parametrize("bad_task", ["not_a_real_task", "eval_judge", "embeddings"])
async def test_update_eval_settings_when_unknown_task_in_allowlist_then_raises_validation_error(bad_task: str) -> None:
    db = _db(_row())

    with pytest.raises(EvalSettingsValidationError, match=bad_task):
        await PlatformSettingsService(db).update_eval_settings(**_update_kwargs(enabled_tasks=[bad_task]))

    db.commit.assert_not_called()


async def test_update_eval_settings_when_student_text_task_enabled_without_acknowledgement_then_raises_validation_error() -> (
    None
):
    row = _row()
    db = _db(row)

    with pytest.raises(EvalSettingsValidationError, match="acknowledg"):
        await PlatformSettingsService(db).update_eval_settings(**_update_kwargs(enabled_tasks=[STUDENT_TEXT_TASK]))

    assert row.eval_enabled_tasks == []
    db.commit.assert_not_called()


async def test_update_eval_settings_when_acknowledged_then_records_actor_and_timestamp() -> None:
    row = _row()
    db = _db(row)

    settings = await PlatformSettingsService(db).update_eval_settings(
        **_update_kwargs(enabled_tasks=[STUDENT_TEXT_TASK], acknowledge_student_text_tasks=[STUDENT_TEXT_TASK])
    )

    ack = row.eval_student_text_ack[STUDENT_TEXT_TASK]
    assert ack["acknowledged_by"] == str(ACTOR_ID)
    assert ack["acknowledged_at"].endswith("+00:00")  # timezone-aware UTC ISO-8601
    assert settings.student_text_ack[STUDENT_TEXT_TASK] == ack


async def test_update_eval_settings_when_acknowledging_a_task_without_student_text_then_raises_validation_error() -> (
    None
):
    db = _db(_row())

    with pytest.raises(EvalSettingsValidationError, match="does not contain student text"):
        await PlatformSettingsService(db).update_eval_settings(
            **_update_kwargs(acknowledge_student_text_tasks=[NO_STUDENT_TEXT_TASK])
        )


async def test_update_eval_settings_when_acknowledging_a_task_not_being_enabled_then_raises_validation_error() -> None:
    db = _db(_row())

    with pytest.raises(EvalSettingsValidationError, match="not being enabled"):
        await PlatformSettingsService(db).update_eval_settings(
            **_update_kwargs(acknowledge_student_text_tasks=[STUDENT_TEXT_TASK])
        )


async def test_update_eval_settings_when_previously_acknowledged_task_reenabled_then_no_new_acknowledgement_needed() -> (
    None
):
    prior_ack = {
        STUDENT_TEXT_TASK: {"acknowledged_by": str(OTHER_ACTOR_ID), "acknowledged_at": "2026-10-01T00:00:00+00:00"}
    }
    row = _row(eval_student_text_ack=prior_ack)
    db = _db(row)

    await PlatformSettingsService(db).update_eval_settings(**_update_kwargs(enabled_tasks=[STUDENT_TEXT_TASK]))

    assert row.eval_enabled_tasks == [STUDENT_TEXT_TASK]
    assert row.eval_student_text_ack == prior_ack  # original actor and time are preserved


async def test_update_eval_settings_when_task_disabled_then_acknowledgement_history_is_kept() -> None:
    prior_ack = {
        STUDENT_TEXT_TASK: {"acknowledged_by": str(OTHER_ACTOR_ID), "acknowledged_at": "2026-10-01T00:00:00+00:00"}
    }
    row = _row(eval_enabled_tasks=[STUDENT_TEXT_TASK], eval_student_text_ack=prior_ack)
    db = _db(row)

    await PlatformSettingsService(db).update_eval_settings(**_update_kwargs(enabled_tasks=[]))

    assert row.eval_enabled_tasks == []
    assert row.eval_student_text_ack == prior_ack


async def test_update_eval_settings_when_called_twice_with_same_payload_then_idempotent() -> None:
    row = _row()
    db = _db(row)
    service = PlatformSettingsService(db)
    kwargs = _update_kwargs(enabled_tasks=[STUDENT_TEXT_TASK], acknowledge_student_text_tasks=[STUDENT_TEXT_TASK])

    first = await service.update_eval_settings(**kwargs)
    second = await service.update_eval_settings(**{**kwargs, "actor_id": OTHER_ACTOR_ID})

    assert second == first
    assert row.updated_by == ACTOR_ID  # a no-op update does not re-attribute the row
    assert row.eval_student_text_ack[STUDENT_TEXT_TASK]["acknowledged_by"] == str(ACTOR_ID)


async def test_update_eval_settings_when_duplicate_tasks_given_then_deduplicated_in_order() -> None:
    row = _row()
    db = _db(row)

    await PlatformSettingsService(db).update_eval_settings(
        **_update_kwargs(enabled_tasks=["question_quality", NO_STUDENT_TEXT_TASK, "question_quality"])
    )

    assert row.eval_enabled_tasks == ["question_quality", NO_STUDENT_TEXT_TASK]


async def test_update_eval_settings_when_changed_then_logs_transition_with_actor() -> None:
    row = _row(eval_monthly_budget_usd=Decimal("5.00"), eval_enabled_tasks=["question_quality"])
    db = _db(row)

    with patch("app.services.platform_settings_service.logger") as logger:
        await PlatformSettingsService(db).update_eval_settings(**_update_kwargs())

    logger.info.assert_called_once()
    event, fields = logger.info.call_args.args[0], logger.info.call_args.kwargs
    assert event == "platform_settings.eval_updated"
    assert fields["actor_id"] == str(ACTOR_ID)
    assert fields["previous_budget_usd"] == "5.00"
    assert fields["new_budget_usd"] == "25.00"
    assert fields["tasks_added"] == [NO_STUDENT_TEXT_TASK]
    assert fields["tasks_removed"] == ["question_quality"]


async def test_update_eval_settings_when_nothing_changed_then_no_log_and_no_write() -> None:
    row = _row(
        eval_monthly_budget_usd=Decimal("25.00"),
        eval_enabled_tasks=[NO_STUDENT_TEXT_TASK],
        eval_sample_size_per_task=40,
        eval_window_days=14,
        eval_include_indicative=True,
        updated_by=OTHER_ACTOR_ID,
    )
    db = _db(row)

    with patch("app.services.platform_settings_service.logger") as logger:
        await PlatformSettingsService(db).update_eval_settings(**_update_kwargs())

    logger.info.assert_not_called()
    assert row.updated_by == OTHER_ACTOR_ID


def test_tasks_with_student_text_when_checked_then_all_are_real_router_tasks() -> None:
    assert TASKS_WITH_STUDENT_TEXT <= set(TASK_MODEL_MAP)
    assert {"grade_open_answer", "explain_this", "concept_guide"} <= TASKS_WITH_STUDENT_TEXT
    assert "question_generation" not in TASKS_WITH_STUDENT_TEXT


def test_unpriced_call_cost_setting_when_negative_then_rejected_and_default_is_positive() -> None:
    assert Settings().eval_unpriced_call_cost_usd > 0  # deliberately conservative, never free
    with pytest.raises(ValidationError):
        Settings(eval_unpriced_call_cost_usd=-0.1)
