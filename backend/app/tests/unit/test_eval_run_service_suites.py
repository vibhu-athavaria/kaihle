"""Per-task suite dispatch in `EvalRunService` (MLH-T18 slice 5c).

Part 1 characterises `question_generation` behaviour the dispatch seam must not change. Part 2 covers
the `grade_open_answer` suite, whose rows carry STUDENT-TYPED text: deterministic checks read the stored
reply, while the adapter and every judge call see scrubbed text only. Helpers come from
`test_eval_run_service` (same fakes: in-memory results store, judge spy, patched sampler).
"""

import json
import uuid
from dataclasses import replace
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.ai.eval.grade_rubrics import CONSTRUCTIVE_ID, NO_REVEAL_ID
from app.ai.eval.rubric_core import RubricSpec
from app.services import eval_run_service
from app.services.eval_prod import grade_suite
from app.services.eval_prod.grade_evaluators import GRADE_CHECKS, GRADE_TASK
from app.services.eval_prod.sampler import SampledEvent, ScrubNames
from app.services.eval_prod.scrub import ScrubFailedError
from app.services.eval_run_service import EvalRunService
from app.services.mini_course_service import render_grade_prompt
from app.services.platform_settings_service import EvalSettings
from app.tests.unit.test_eval_run_service import (
    DETERMINISTIC_PER_EVENT,
    NOW,
    SCHOOL_ID,
    FakeResults,
    Judge,
    _build,
    _eval_settings,
    _event,
    _execute,
    _names,
)

STUDENT_EMAIL = "kid.typed@example.com"
STUDENT_NAME = "Asha"
QUESTION = "Explain why ice floats on water."
GRADE_CHECK_NAMES = list(GRADE_CHECKS)
GOOD_VERDICT = json.dumps({"pass": True, "evidence": "ok"})


def _calibrated(spec: RubricSpec) -> str:
    return "CALIBRATED"


def _missing(spec: RubricSpec) -> str:
    return "MISSING"


def _grade_settings(**overrides: Any) -> EvalSettings:
    return _eval_settings(enabled_tasks=[GRADE_TASK], student_text_ack={GRADE_TASK: {"by": "admin"}}, **overrides)


def _grade_prompt(answer: str) -> str:
    # Rendered by the REAL template so a template change fails here instead of misparsing production rows.
    return render_grade_prompt("Density", "Describe density.", QUESTION, answer)


def _reply(grade: str = "partial", feedback: str = "Good start. What happens as water freezes?") -> str:
    return json.dumps({"grade": grade, "feedback": feedback})


def _grade_event(
    *,
    answer: str = "Because ice is less dense than liquid water.",
    reply: str | None = None,
    prompt: str | None = None,
    model: str = "other/gen-1",
    school_id: uuid.UUID | None = None,
) -> SampledEvent:
    return SampledEvent(
        id=uuid.uuid4(),
        task=GRADE_TASK,
        model=model,
        component=None,
        school_id=school_id,
        prompt_text=_grade_prompt(answer) if prompt is None else prompt,
        response_text=_reply() if reply is None else reply,
        created_at=NOW,
    )


def _grade_build(
    monkeypatch: pytest.MonkeyPatch, events: list[SampledEvent], **kwargs: Any
) -> tuple[EvalRunService, FakeResults, Judge]:
    kwargs.setdefault("eval_settings", _grade_settings())
    kwargs.setdefault("judge", Judge(reply=GOOD_VERDICT))
    judge = kwargs.pop("judge")
    return _build(monkeypatch, events, judge, task=GRADE_TASK, **kwargs)


# --- part 1: question_generation characterisation (passes before and after the seam) -----------------


async def test_question_run_when_rubrics_untrusted_and_event_unadaptable_then_row_counted_unsupported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bad = SampledEvent(**{**_event().__dict__, "response_text": "garbage"})
    service, results, judge = _build(monkeypatch, [bad, _event()], status_of=_missing)
    await _execute(service, results)
    assert results.finished is not None
    assert results.finished.counts.skipped_unsupported == 1 and results.finished.counts.evaluated == 1
    assert judge.prompts == []


async def test_question_run_when_no_judge_rubric_selected_then_scrubbing_is_never_attempted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(*args: Any, **kwargs: Any) -> Any:
        raise ScrubFailedError("must not be called")

    monkeypatch.setattr(eval_run_service, "scrub_question", boom)
    service, results, _ = _build(monkeypatch, [_event()], status_of=_missing)
    await _execute(service, results)
    assert results.finished is not None
    assert results.finished.counts.skipped_scrub_failed == 0 and results.finished.counts.evaluated == 1
    assert len(_names(results)) == DETERMINISTIC_PER_EVENT


# --- part 2: dispatch ---------------------------------------------------------------------------------


async def test_run_when_task_is_grade_then_grade_suite_checks_run_not_question_checks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, results, _ = _grade_build(monkeypatch, [_grade_event()], status_of=_missing)
    await _execute(service, results)
    assert _names(results) == GRADE_CHECK_NAMES


async def test_run_when_task_is_question_generation_then_question_suite_checks_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, results, _ = _build(monkeypatch, [_event()], status_of=_missing)
    await _execute(service, results)
    assert not set(_names(results)) & (set(GRADE_CHECK_NAMES) - {"no_compliance_language"})
    assert len(_names(results)) == DETERMINISTIC_PER_EVENT


# --- part 2: grade run, rubrics excluded (the real state until G1/G2 are calibrated) ------------------


async def test_grade_run_when_rubrics_missing_then_no_judge_call_and_deterministic_results_recorded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events = [_grade_event(), _grade_event(reply=_reply("correct", "Well done."))]
    service, results, judge = _grade_build(monkeypatch, events, status_of=_missing)
    run = await _execute(service, results)
    assert judge.prompts == []
    assert run.status == "completed"
    assert results.finished is not None
    counts = results.finished.counts
    assert counts.sampled == 2 and counts.evaluated == 2 and counts.skipped_unsupported == 0
    assert results.finished.spend_usd == 0
    assert all(o.kind == "deterministic" for _, outcomes in results.recorded for o in outcomes)


async def test_grade_run_when_rubrics_missing_then_unparseable_reply_still_yields_parse_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, results, _ = _grade_build(monkeypatch, [_grade_event(reply="not json at all")], status_of=_missing)
    await _execute(service, results)
    assert [(o.check_name, o.passed) for _, outcomes in results.recorded for o in outcomes] == [
        ("grade_reply_parses", False)
    ]
    assert results.finished is not None and results.finished.counts.evaluated == 1


async def test_grade_run_when_rubrics_missing_then_prompt_is_not_inspected_or_scrubbed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(*args: Any, **kwargs: Any) -> Any:
        raise ScrubFailedError("must not be called")

    monkeypatch.setattr(grade_suite, "scrub_text", boom)
    service, results, _ = _grade_build(monkeypatch, [_grade_event(prompt="unparseable prompt")], status_of=_missing)
    await _execute(service, results)
    assert results.finished is not None
    counts = results.finished.counts
    assert counts.evaluated == 1 and counts.skipped_scrub_failed == 0 and counts.skipped_unsupported == 0


# --- part 2: grade run with trusted rubrics -----------------------------------------------------------


async def test_grade_run_when_rubrics_trusted_then_judge_only_ever_receives_scrubbed_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answer = f"I think so, ask {STUDENT_NAME} or mail {STUDENT_EMAIL}"
    reply = _reply("partial", f"Nice try {STUDENT_NAME}, think about density.")
    event = _grade_event(answer=answer, reply=reply, school_id=SCHOOL_ID)
    names = {SCHOOL_ID: ScrubNames(person_names=(STUDENT_NAME,), school_name="Greenfield")}
    service, results, judge = _grade_build(monkeypatch, [event], status_of=_calibrated, names=names)
    await _execute(service, results)
    sent = "\n".join(judge.prompts)
    assert len(judge.prompts) == 2  # G1 and G2 (partial grade)
    assert STUDENT_EMAIL not in sent and STUDENT_NAME not in sent
    assert "[EMAIL]" in sent and "[NAME]" in sent
    judged = {o.check_name for _, outcomes in results.recorded for o in outcomes if o.kind == "judge"}
    assert judged == {CONSTRUCTIVE_ID, NO_REVEAL_ID}


async def test_grade_run_when_rubrics_trusted_then_deterministic_checks_use_the_stored_reply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The stored feedback has a banned phrase; scrubbing must not be what the checks read, and the
    # check result must be recorded against the stored (unscrubbed) reply.
    reply = _reply("partial", f"{STUDENT_NAME}, this is Cambridge-compliant work.")
    event = _grade_event(reply=reply, school_id=SCHOOL_ID)
    names = {SCHOOL_ID: ScrubNames(person_names=(STUDENT_NAME,), school_name=None)}
    service, results, _ = _grade_build(monkeypatch, [event], status_of=_calibrated, names=names)
    await _execute(service, results)
    by_name = {o.check_name: o.passed for _, outcomes in results.recorded for o in outcomes}
    assert by_name["no_compliance_language"] is False and by_name["grade_reply_parses"] is True


async def test_grade_run_when_grade_correct_then_no_reveal_rubric_not_run(monkeypatch: pytest.MonkeyPatch) -> None:
    service, results, judge = _grade_build(
        monkeypatch, [_grade_event(reply=_reply("correct", "Well done!"))], status_of=_calibrated
    )
    await _execute(service, results)
    assert len(judge.prompts) == 1
    judged = [o.check_name for _, outcomes in results.recorded for o in outcomes if o.kind == "judge"]
    assert judged == [CONSTRUCTIVE_ID]


async def test_grade_run_when_judge_reply_unusable_then_result_is_indeterminate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, results, _ = _grade_build(
        monkeypatch, [_grade_event()], judge=Judge(reply="no json"), status_of=_calibrated
    )
    await _execute(service, results)
    judged = [o for _, outcomes in results.recorded for o in outcomes if o.kind == "judge"]
    assert len(judged) == 2 and all(o.passed is None for o in judged)


async def test_grade_run_when_scrub_fails_then_row_skipped_counted_and_never_reaches_judge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(*args: Any, **kwargs: Any) -> Any:
        raise ScrubFailedError("nope")

    monkeypatch.setattr(grade_suite, "scrub_text", boom)
    service, results, judge = _grade_build(monkeypatch, [_grade_event(), _grade_event()], status_of=_calibrated)
    run = await _execute(service, results)
    assert judge.prompts == [] and results.recorded == []
    assert results.finished is not None
    counts = results.finished.counts
    assert counts.skipped_scrub_failed == 2 and counts.evaluated == 0
    assert run.status == "completed"


@pytest.mark.parametrize(
    "event",
    [
        _grade_event(prompt="a prompt that is not the grading template"),
        replace(_grade_event(), prompt_text=None),
        _grade_event(reply="not json at all"),
        _grade_event(reply=json.dumps({"grade": "excellent", "feedback": "x"})),
    ],
    ids=["prompt_no_markers", "prompt_missing", "reply_not_json", "grade_not_recognised"],
)
async def test_grade_run_when_row_not_parseable_then_counted_unsupported_and_judge_unused(
    monkeypatch: pytest.MonkeyPatch, event: SampledEvent
) -> None:
    service, results, judge = _grade_build(monkeypatch, [event, _grade_event()], status_of=_calibrated)
    await _execute(service, results)
    assert results.finished is not None
    counts = results.finished.counts
    assert counts.skipped_unsupported == 1 and counts.evaluated == 1
    assert len(judge.prompts) == 2  # only the supported row reached the judge


async def test_grade_run_when_rows_unsupported_then_reasons_logged_without_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    info = MagicMock()
    monkeypatch.setattr(eval_run_service.logger, "info", info)
    events = [_grade_event(prompt="SECRET-PROMPT-TEXT"), _grade_event(reply="SECRET-REPLY-TEXT")]
    service, results, _ = _grade_build(monkeypatch, events, status_of=_calibrated)
    await _execute(service, results)
    calls = [c for c in info.call_args_list if c.args and c.args[0] == "eval_run.rows_unsupported"]
    assert len(calls) == 1
    assert calls[0].kwargs["reasons"] == {"prompt_unparseable": 1, "reply_unparseable": 1}
    assert "SECRET" not in repr(info.call_args_list)


async def test_grade_run_when_row_model_matches_judge_then_skipped_not_independent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events = [_grade_event(model="judgevendor/judge-1"), _grade_event(model="judgevendor/other"), _grade_event()]
    service, results, _ = _grade_build(monkeypatch, events, status_of=_calibrated)
    await _execute(service, results)
    assert results.finished is not None
    assert results.finished.counts.skipped_not_independent == 2 and results.finished.counts.evaluated == 1


async def test_grade_run_when_budget_exhausted_then_status_budget_exhausted(monkeypatch: pytest.MonkeyPatch) -> None:
    service, results, judge = _grade_build(
        monkeypatch,
        [_grade_event(), _grade_event()],
        status_of=_calibrated,
        eval_settings=_grade_settings(monthly_budget_usd=Decimal("0.015")),
    )
    run = await _execute(service, results)
    assert run.status == "budget_exhausted" and len(judge.prompts) == 1


async def test_grade_run_when_completed_then_results_hold_ids_and_verdicts_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "ZEBRA-STUDENT-ANSWER"
    service, results, _ = _grade_build(
        monkeypatch, [_grade_event(answer=secret, reply=_reply("partial", "FEEDBACK-SECRET"))], status_of=_calibrated
    )
    await _execute(service, results)
    dump = repr(results.recorded) + repr(results.finished)
    assert secret not in dump and "FEEDBACK-SECRET" not in dump
