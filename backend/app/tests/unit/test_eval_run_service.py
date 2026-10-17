"""Unit tests for `EvalRunService` (MLH-T18 slice 5b-i).

Collaborators are faked in memory: the sampler functions are patched on the service module, the
results store is a recording fake and the judge is a spy. Real-Postgres behaviour is covered by
`integration/test_eval_run_service.py`.
"""

import json
import uuid
from collections.abc import Callable, Collection
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.eval.rubric_core import RubricSpec
from app.core.config import settings
from app.models.eval_results import EvalRun
from app.services import eval_run_service
from app.services.eval_prod.sampler import SYSTEM_EVAL_ACTOR, SampledEvent, ScrubNames
from app.services.eval_prod.scrub import ScrubFailedError
from app.services.eval_results_service import CheckOutcome
from app.services.eval_run_service import (
    EVAL_PROD_SAMPLE_COMPONENT,
    EvalRunService,
    RunNotAllowedError,
    scheduled_window_and_seed,
)
from app.services.platform_settings_service import EvalSettings

TASK = "question_generation"
JUDGE = "judgevendor/judge-1"
SCHOOL_ID = uuid.uuid4()
NOW = datetime(2026, 10, 17, 9, 30, tzinfo=UTC)
GOOD = json.dumps({"pass": True, "answer": "A", "correct_options": ["A"], "evidence": "ok"})
PROMPT = "- Subject:   Mathematics (MATH)\n- Grade:   7\n- Subtopic:   Adding fractions\n"
JUDGE_CALLS_PER_EVENT = 7  # R1-R5, the one matching R6 variant, R7
DETERMINISTIC_PER_EVENT = 4


def _mcq(**overrides: Any) -> dict[str, Any]:
    question: dict[str, Any] = {
        "difficulty_level": 3,
        "question_type": "multiple_choice",
        "question_text": "What is 1/2 + 1/4?",
        "options": {"A": "3/4", "B": "2/6", "C": "1/8", "D": "1"},
        "correct_answer": "A",
        "learning_objectives": ["Add fractions"],
        "explanation": "A is right.",
    }
    question.update(overrides)
    return question


def _event(model: str = "other/gen-1", school_id: uuid.UUID | None = None, **mcq: Any) -> SampledEvent:
    return SampledEvent(
        id=uuid.uuid4(),
        task=TASK,
        model=model,
        component=None,
        school_id=school_id,
        prompt_text=PROMPT,
        response_text=json.dumps({"questions": [_mcq(**mcq)]}),
        created_at=NOW,
    )


class FakeResults:
    """Recording stand-in for EvalResultsService."""

    def __init__(self, run: EvalRun) -> None:
        self.run = run
        self.created = True
        self.recorded: list[tuple[uuid.UUID, list[CheckOutcome]]] = []
        self.finished: SimpleNamespace | None = None
        self.started_with: str | None = None

    async def get_run(self, run_id: uuid.UUID) -> EvalRun | None:
        return self.run if self.run.id == run_id else None

    async def create_run(self, **kwargs: Any) -> tuple[EvalRun, bool]:
        self.create_kwargs = kwargs
        return self.run, self.created

    async def mark_started(self, run_id: uuid.UUID, *, judge_model: str) -> None:
        self.started_with = judge_model
        self.run.status = "running"

    async def finish_run(self, run_id: uuid.UUID, **kwargs: Any) -> None:
        self.finished = SimpleNamespace(**kwargs)
        self.run.status = kwargs["status"]

    async def record_results(self, run_id: uuid.UUID, event_id: uuid.UUID, outcomes: Any) -> int:
        self.recorded.append((event_id, list(outcomes)))
        return len(outcomes)


class FakePlatform:
    def __init__(self, eval_settings: EvalSettings) -> None:
        self._settings = eval_settings

    async def get_eval_settings(self) -> EvalSettings:
        return self._settings


class Judge:
    """Judge spy: records prompts, can raise on a given call number."""

    def __init__(self, reply: str = GOOD, fail_on_call: int | None = None) -> None:
        self.reply, self.fail_on_call, self.prompts = reply, fail_on_call, []

    async def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if self.fail_on_call == len(self.prompts):
            raise RuntimeError("provider down")
        return self.reply


def _eval_settings(**overrides: Any) -> EvalSettings:
    values: dict[str, Any] = {
        "monthly_budget_usd": Decimal("10"),
        "enabled_tasks": [TASK],
        "sample_size_per_task": 5,
        "window_days": 7,
        "include_indicative": False,
        "student_text_ack": {},
        "updated_by": None,
        "updated_at": None,
    }
    values.update(overrides)
    return EvalSettings(**values)


def _build(
    monkeypatch: pytest.MonkeyPatch,
    events: list[SampledEvent],
    judge: Judge | None = None,
    *,
    eval_settings: EvalSettings | None = None,
    judge_model: str = JUDGE,
    tracking: bool = True,
    status_of: Callable[[RubricSpec], str] = lambda spec: "CALIBRATED",
    names: dict[uuid.UUID, ScrubNames] | None = None,
    price: Decimal | None = Decimal("0.01"),
    task: str = TASK,
    default_completion: bool = False,
) -> tuple[EvalRunService, FakeResults, Judge]:
    judge = judge or Judge()
    run = EvalRun(
        id=uuid.uuid4(),
        task=task,
        window_start=NOW - timedelta(days=7),
        window_end=NOW,
        seed="seed-1",
        trigger="manual",
        status="pending",
        include_indicative=False,
    )
    results = FakeResults(run)

    async def fake_sample(*args: Any, **kwargs: Any) -> list[SampledEvent]:
        return events

    async def fake_names(db: Any, actor: Any, school_ids: Collection[uuid.UUID]) -> dict[uuid.UUID, ScrubNames]:
        return names or {}

    async def fake_spend(*args: Any, **kwargs: Any) -> Decimal:
        return Decimal("0")

    monkeypatch.setattr(eval_run_service, "sample_usage_events", fake_sample)
    monkeypatch.setattr(eval_run_service, "load_scrub_names", fake_names)
    monkeypatch.setattr(eval_run_service, "month_spend_usd", fake_spend)
    config = settings.model_copy(
        update={
            "llm_eval_judge_model": judge_model,
            "llm_usage_tracking_enabled": tracking,
            "eval_unpriced_call_cost_usd": 0.5,
        }
    )
    service = EvalRunService(
        MagicMock(spec=AsyncSession),
        config=config,
        status_of=status_of,
        completion_factory=None if default_completion else (lambda run_id: judge),
        price_estimator=lambda model, prompt_tokens, completion_tokens: price,
        clock=lambda: NOW,
        results=results,
        platform_settings=FakePlatform(eval_settings or _eval_settings()),
    )
    return service, results, judge


async def _execute(service: EvalRunService, results: FakeResults) -> EvalRun:
    return await service.execute_run(results.run.id, SYSTEM_EVAL_ACTOR)


def _names(results: FakeResults) -> list[str]:
    return [o.check_name for _, outcomes in results.recorded for o in outcomes]


async def test_run_when_sample_scrubbed_then_judge_receives_scrubbed_text_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event = _event(school_id=SCHOOL_ID, question_text="Write to bob@example.com about Asha's 1/2 + 1/4")
    names = {SCHOOL_ID: ScrubNames(person_names=("Asha",), school_name="Greenfield")}
    service, results, judge = _build(monkeypatch, [event], names=names)
    await _execute(service, results)
    sent = "\n".join(judge.prompts)
    assert judge.prompts, "the judge should have been called"
    assert "bob@example.com" not in sent and "Asha" not in sent
    assert "[EMAIL]" in sent and "[NAME]" in sent


async def test_run_when_scrub_fails_then_row_skipped_and_never_sent_to_judge(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*args: Any, **kwargs: Any) -> Any:
        raise ScrubFailedError("nope")

    monkeypatch.setattr(eval_run_service, "scrub_question", boom)
    service, results, judge = _build(monkeypatch, [_event(), _event()])
    run = await _execute(service, results)
    assert judge.prompts == [] and results.recorded == []
    assert results.finished is not None
    assert results.finished.counts.skipped_scrub_failed == 2 and results.finished.counts.evaluated == 0
    assert run.status == "completed"


async def test_run_when_judge_called_then_component_is_eval_prod_sample(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def fake_router_completion(run_id: str | None = None, component: str = "") -> Judge:
        seen.update(run_id=run_id, component=component)
        return Judge()

    monkeypatch.setattr(eval_run_service, "router_completion", fake_router_completion)
    service, results, _ = _build(monkeypatch, [_event()], default_completion=True)
    await _execute(service, results)
    assert seen == {"run_id": str(results.run.id), "component": EVAL_PROD_SAMPLE_COMPONENT}
    assert EVAL_PROD_SAMPLE_COMPONENT == "eval_prod_sample"


async def test_run_when_judge_raises_then_run_marked_failed_and_partial_results_kept(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, results, _ = _build(monkeypatch, [_event(), _event()], Judge(fail_on_call=3))
    run = await _execute(service, results)
    assert run.status == "failed"
    assert results.finished is not None and results.finished.error_type == "RuntimeError"
    assert len(results.recorded) == 1  # the interrupted event's partial outcomes are kept
    assert len(results.recorded[0][1]) == DETERMINISTIC_PER_EVENT + 2
    assert results.finished.counts.evaluated == 0


async def test_run_when_verdict_unparseable_then_result_marked_indeterminate_not_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, results, _ = _build(monkeypatch, [_event()], Judge(reply="no json here"))
    run = await _execute(service, results)
    judged = [o for _, outcomes in results.recorded for o in outcomes if o.kind == "judge"]
    assert len(judged) == JUDGE_CALLS_PER_EVENT
    assert all(o.passed is None for o in judged)  # indeterminate, never a pass
    assert run.status == "completed"


async def test_run_when_budget_exhausted_midway_then_status_budget_exhausted_and_partial_results_kept(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, results, judge = _build(
        monkeypatch, [_event(), _event()], eval_settings=_eval_settings(monthly_budget_usd=Decimal("0.03"))
    )
    run = await _execute(service, results)
    assert run.status == "budget_exhausted"
    assert len(judge.prompts) == 3  # the 4th call would exceed 0.03 at 0.01 each
    assert results.finished is not None and results.finished.spend_usd == Decimal("0.03")
    assert len(results.recorded) == 1 and len(results.recorded[0][1]) == DETERMINISTIC_PER_EVENT + 3


async def test_run_when_sample_empty_then_status_empty_and_warning_logged(monkeypatch: pytest.MonkeyPatch) -> None:
    warning = MagicMock()
    monkeypatch.setattr(eval_run_service.logger, "warning", warning)
    service, results, judge = _build(monkeypatch, [])
    run = await _execute(service, results)
    assert run.status == "empty" and judge.prompts == []
    warning.assert_called_once()
    assert warning.call_args.args[0] == "eval_run.empty_sample"


async def test_run_when_completed_then_results_contain_no_prompt_or_response_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "ZEBRA-STEM-TEXT"
    service, results, _ = _build(monkeypatch, [_event(question_text=secret, explanation="EXPLAIN-TEXT")])
    await _execute(service, results)
    dump = repr(results.recorded) + repr(results.finished)
    assert secret not in dump and "EXPLAIN-TEXT" not in dump
    assert all(isinstance(o, CheckOutcome) for _, outcomes in results.recorded for o in outcomes)


async def test_run_when_completed_then_counts_spend_and_judge_model_recorded(monkeypatch: pytest.MonkeyPatch) -> None:
    service, results, _ = _build(monkeypatch, [_event(), _event()])
    await _execute(service, results)
    assert results.started_with == JUDGE
    assert results.finished is not None
    assert results.finished.counts.sampled == 2 and results.finished.counts.evaluated == 2
    assert results.finished.spend_usd == Decimal("0.01") * JUDGE_CALLS_PER_EVENT * 2


async def test_run_when_row_model_matches_judge_or_vendor_then_skipped_and_counted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events = [_event(model=JUDGE), _event(model="judgevendor/other"), _event(model="other/gen-1")]
    service, results, _ = _build(monkeypatch, events)
    await _execute(service, results)
    assert results.finished is not None
    assert results.finished.counts.skipped_not_independent == 2
    assert results.finished.counts.evaluated == 1


async def test_run_when_event_not_adaptable_then_counted_skipped_unsupported(monkeypatch: pytest.MonkeyPatch) -> None:
    bad = _event()
    bad = SampledEvent(**{**bad.__dict__, "response_text": "garbage"})
    service, results, _ = _build(monkeypatch, [bad, _event()])
    await _execute(service, results)
    assert results.finished is not None
    assert results.finished.counts.skipped_unsupported == 1 and results.finished.counts.evaluated == 1


async def test_run_when_task_has_no_registered_evaluators_then_all_rows_unsupported_and_judge_unused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, results, judge = _build(
        monkeypatch, [_event(), _event()], task="tutor_chat", eval_settings=_eval_settings(enabled_tasks=["tutor_chat"])
    )
    run = await _execute(service, results)
    assert run.status == "completed" and judge.prompts == []
    assert results.finished is not None and results.finished.counts.skipped_unsupported == 2


async def test_run_when_rubrics_not_trusted_then_only_deterministic_checks_run(monkeypatch: pytest.MonkeyPatch) -> None:
    service, results, judge = _build(monkeypatch, [_event()], status_of=lambda spec: "MISSING")
    await _execute(service, results)
    assert judge.prompts == [] and len(_names(results)) == DETERMINISTIC_PER_EVENT
    assert results.finished is not None and results.finished.spend_usd == Decimal("0")


async def test_run_when_band_given_then_only_matching_r6_variant_is_run(monkeypatch: pytest.MonkeyPatch) -> None:
    service, results, _ = _build(monkeypatch, [_event(difficulty_level=1), _event(difficulty_level=4)])
    await _execute(service, results)
    r6 = sorted(name for name in _names(results) if name.startswith("R6_"))
    assert r6 == ["R6_understanding_not_recall_applied", "R6_understanding_not_recall_foundational"]
    assert [n for n in _names(results)].count("R7_explanation_quality_bank") == 2


@pytest.mark.parametrize(
    ("overrides", "error_type"),
    [
        ({"eval_settings": _eval_settings(monthly_budget_usd=Decimal("0"))}, "BudgetRefusedError"),
        ({"tracking": False}, "BudgetRefusedError"),
        ({"judge_model": ""}, "BudgetRefusedError"),
        ({"price": None}, "BudgetRefusedError"),
        ({"eval_settings": _eval_settings(enabled_tasks=[])}, "RunNotAllowedError"),
    ],
)
async def test_run_when_refused_at_start_then_run_failed_and_judge_never_called(
    monkeypatch: pytest.MonkeyPatch, overrides: dict[str, Any], error_type: str
) -> None:
    service, results, judge = _build(monkeypatch, [_event()], **overrides)
    run = await _execute(service, results)
    assert run.status == "failed" and judge.prompts == []
    assert results.finished is not None and results.finished.error_type == error_type
    assert results.started_with is None


async def test_run_when_already_started_then_second_execute_is_a_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    service, results, judge = _build(monkeypatch, [_event()])
    await _execute(service, results)
    calls = len(judge.prompts)
    again = await _execute(service, results)
    assert again.status == "completed" and len(judge.prompts) == calls


async def test_run_when_run_missing_then_lookup_error(monkeypatch: pytest.MonkeyPatch) -> None:
    service, _, _ = _build(monkeypatch, [])
    with pytest.raises(LookupError):
        await service.execute_run(uuid.uuid4(), SYSTEM_EVAL_ACTOR)


async def test_request_run_when_same_task_window_seed_repeated_then_returns_existing_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, results, _ = _build(monkeypatch, [])
    kwargs: dict[str, Any] = {
        "task": TASK,
        "window_start": NOW - timedelta(days=7),
        "window_end": NOW,
        "seed": "seed-1",
        "trigger": "manual",
    }
    first, created_first = await service.request_run(**kwargs)
    results.created = False
    second, created_second = await service.request_run(**kwargs)
    assert first is second and created_first and not created_second


async def test_request_run_when_task_not_enabled_then_not_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    service, _, _ = _build(monkeypatch, [], eval_settings=_eval_settings(enabled_tasks=[]))
    with pytest.raises(RunNotAllowedError, match="not enabled"):
        await service.request_run(
            task=TASK, window_start=NOW - timedelta(days=1), window_end=NOW, seed="s", trigger="manual"
        )


async def test_request_run_when_student_text_task_unacknowledged_then_not_allowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _, _ = _build(monkeypatch, [], eval_settings=_eval_settings(enabled_tasks=["grade_open_answer"]))
    with pytest.raises(RunNotAllowedError, match="acknowledgement"):
        await service.request_run(
            task="grade_open_answer", window_start=NOW - timedelta(days=1), window_end=NOW, seed="s", trigger="manual"
        )


async def test_request_run_when_allowed_then_snapshots_include_indicative_and_requester(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, results, _ = _build(monkeypatch, [], eval_settings=_eval_settings(include_indicative=True))
    requester = uuid.uuid4()
    await service.request_run(
        task=TASK,
        window_start=NOW - timedelta(days=1),
        window_end=NOW,
        seed="s",
        trigger="manual",
        requested_by=requester,
    )
    assert results.create_kwargs["include_indicative"] is True
    assert results.create_kwargs["requested_by"] == requester


def test_scheduled_window_and_seed_when_called_twice_same_day_then_identical() -> None:
    first = scheduled_window_and_seed(NOW, window_days=7)
    second = scheduled_window_and_seed(NOW + timedelta(hours=5), window_days=7)
    assert first == second
    start, end, seed = first
    assert end == datetime(2026, 10, 17, tzinfo=UTC) and end - start == timedelta(days=7)
    assert seed == "scheduled-2026-10-17"
