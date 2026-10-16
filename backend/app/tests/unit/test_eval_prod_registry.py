"""Unit tests for the production-evaluation evaluator registry (MLH-T18 slice 4, decisions D4-D6, D14).

Calibration status is injected (`status_of`), so no files are read; the default file-backed resolver
has its own tests at the bottom using `tmp_path`.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from app.ai.eval.calibration import CalibrationResult, save_calibration
from app.ai.eval.judge_config import JudgeNotConfiguredError
from app.ai.eval.judge_guards import require_judge_configured
from app.ai.eval.rubric_core import RubricSpec
from app.ai.eval_metrics import rate
from app.services.eval_prod.registry import (
    Evaluator,
    EvaluatorRegistry,
    calibration_status_from_files,
    filter_independent,
    task_enablement_problem,
)
from app.services.eval_prod.sampler import SampledEvent
from app.services.platform_settings_service import EvalSettings

TASK = "question_generation"
RUBRIC = RubricSpec("R1_test", "Is it fine?", "Judge strictly.", ("stem",))
CHECK = Evaluator(name="options_unique", kind="deterministic")
JUDGE_EVAL = Evaluator(name=RUBRIC.id, kind="judge", rubric=RUBRIC)


def _registry() -> EvaluatorRegistry:
    registry = EvaluatorRegistry()
    registry.register(TASK, CHECK)
    registry.register(TASK, JUDGE_EVAL)
    return registry


def _selected_names(status: str, include_indicative: bool = False) -> tuple[list[str], list[str]]:
    plan = _registry().plan_for(TASK, include_indicative=include_indicative, status_of=lambda spec: status)
    return [s.evaluator.name for s in plan.selected], [e.evaluator.name for e in plan.excluded]


def test_registry_when_task_has_deterministic_checks_then_they_always_run() -> None:
    for status in ("MISSING", "STALE", "NOT_CALIBRATED", "CALIBRATED"):
        selected, _ = _selected_names(status)
        assert CHECK.name in selected


def test_registry_when_rubric_calibrated_for_current_hash_then_included() -> None:
    selected, excluded = _selected_names("CALIBRATED")
    assert RUBRIC.id in selected
    assert excluded == []


def test_registry_when_rubric_human_validated_then_included() -> None:
    selected, _ = _selected_names("HUMAN_VALIDATED")
    assert RUBRIC.id in selected


def test_registry_when_rubric_indicative_and_flag_off_then_excluded() -> None:
    selected, excluded = _selected_names("INDICATIVE", include_indicative=False)
    assert RUBRIC.id not in selected
    assert excluded == [RUBRIC.id]


def test_registry_when_rubric_indicative_and_flag_on_then_included_and_marked_indicative() -> None:
    plan = _registry().plan_for(TASK, include_indicative=True, status_of=lambda spec: "INDICATIVE")
    chosen = {s.evaluator.name: s for s in plan.selected}
    assert chosen[RUBRIC.id].indicative is True
    assert chosen[RUBRIC.id].rubric_status == "INDICATIVE"
    assert chosen[RUBRIC.id].rubric_hash == RUBRIC.text_hash
    assert chosen[CHECK.name].indicative is False
    assert chosen[CHECK.name].rubric_hash is None


@pytest.mark.parametrize("status", ["STALE", "MISSING", "NOT_CALIBRATED", "INSUFFICIENT_N"])
def test_registry_when_rubric_untrusted_then_excluded_even_with_indicative_flag(status: str) -> None:
    selected, excluded = _selected_names(status, include_indicative=True)
    assert RUBRIC.id not in selected
    assert excluded == [RUBRIC.id]


def test_registry_when_rubric_hash_stale_then_excluded_via_file_resolver(tmp_path: Path) -> None:
    result = CalibrationResult(
        criterion=RUBRIC.id,
        subset="computed",
        rubric_hash="hash-of-an-older-wording",
        recall=rate(40, 40),
        false_alarm=rate(0, 40),
        indeterminate=rate(0, 40),
        crosstalk={},
    )
    save_calibration(result, tmp_path)
    assert calibration_status_from_files(RUBRIC, tmp_path) == "STALE"
    plan = _registry().plan_for(
        TASK, include_indicative=True, status_of=lambda spec: calibration_status_from_files(spec, tmp_path)
    )
    assert [s.evaluator.name for s in plan.selected] == [CHECK.name]


def test_calibration_status_from_files_when_current_hash_and_strong_then_calibrated(tmp_path: Path) -> None:
    result = CalibrationResult(
        criterion=RUBRIC.id,
        subset="computed",
        rubric_hash=RUBRIC.text_hash,
        recall=rate(60, 60),
        false_alarm=rate(0, 60),
        indeterminate=rate(0, 60),
        crosstalk={},
    )
    save_calibration(result, tmp_path)
    assert calibration_status_from_files(RUBRIC, tmp_path) == "CALIBRATED"


def test_calibration_status_from_files_when_no_file_then_missing(tmp_path: Path) -> None:
    assert calibration_status_from_files(RUBRIC, tmp_path) == "MISSING"


def test_registry_when_task_unknown_then_no_evaluators_and_row_counted_unsupported() -> None:
    registry = _registry()
    plan = registry.plan_for("never_registered", include_indicative=True, status_of=lambda spec: "CALIBRATED")
    assert plan.selected == ()
    assert plan.excluded == ()
    assert plan.supported is False
    assert registry.supports("never_registered") is False
    assert registry.supports(TASK) is True


def test_registry_when_evaluator_name_registered_twice_for_task_then_raises() -> None:
    registry = _registry()
    with pytest.raises(ValueError, match="already registered"):
        registry.register(TASK, CHECK)


def test_evaluator_when_judge_has_no_rubric_or_check_has_one_then_raises() -> None:
    with pytest.raises(ValueError, match="rubric"):
        Evaluator(name="x", kind="judge")
    with pytest.raises(ValueError, match="rubric"):
        Evaluator(name="x", kind="deterministic", rubric=RUBRIC)
    with pytest.raises(ValueError, match="kind"):
        Evaluator(name="x", kind="other")


def test_registry_when_task_carries_student_text_then_flag_comes_from_platform_settings_source() -> None:
    registry = EvaluatorRegistry()
    assert registry.contains_student_text("grade_open_answer") is True
    assert registry.contains_student_text("question_generation") is False


def _settings(enabled: list[str], ack: dict[str, dict[str, str]] | None = None) -> EvalSettings:
    return EvalSettings(
        monthly_budget_usd=Decimal("5"),
        enabled_tasks=enabled,
        sample_size_per_task=50,
        window_days=7,
        include_indicative=False,
        student_text_ack=ack or {},
        updated_by=None,
        updated_at=None,
    )


def test_task_enablement_when_task_not_on_allowlist_then_problem_reported() -> None:
    assert "not enabled" in (task_enablement_problem(TASK, _settings([])) or "")


def test_task_enablement_when_student_text_task_enabled_without_acknowledgement_then_problem_reported() -> None:
    problem = task_enablement_problem("grade_open_answer", _settings(["grade_open_answer"]))
    assert problem is not None
    assert "acknowledg" in problem


def test_task_enablement_when_student_text_task_acknowledged_then_no_problem() -> None:
    ack = {"grade_open_answer": {"acknowledged_by": str(uuid.uuid4()), "acknowledged_at": "2026-10-16T00:00:00+00:00"}}
    assert task_enablement_problem("grade_open_answer", _settings(["grade_open_answer"], ack)) is None


def test_task_enablement_when_plain_task_enabled_then_no_problem() -> None:
    assert task_enablement_problem(TASK, _settings([TASK])) is None


def _event(model: str, task: str = TASK) -> SampledEvent:
    return SampledEvent(
        id=uuid.uuid4(),
        task=task,
        model=model,
        component=None,
        school_id=None,
        prompt_text=None,
        response_text="r",
        created_at=datetime.now(UTC),
    )


def test_independence_when_row_model_equals_judge_then_row_skipped_and_counted() -> None:
    split = filter_independent([_event("vendor-j/judge-1"), _event("vendor-g/model")], "vendor-j/judge-1")
    assert [e.model for e in split.kept] == ["vendor-g/model"]
    assert split.skipped_not_independent == 1


def test_independence_when_row_model_same_vendor_as_judge_then_row_skipped_and_counted() -> None:
    split = filter_independent([_event("openrouter/vendor-j/old-model")], "vendor-j/judge-1")
    assert split.kept == ()
    assert split.skipped_not_independent == 1


def test_independence_when_row_model_blank_then_skipped_because_it_cannot_be_verified() -> None:
    split = filter_independent([_event("")], "vendor-j/judge-1")
    assert split.kept == ()
    assert split.skipped_not_independent == 1


def test_independence_when_each_row_has_its_own_model_then_each_checked_against_its_own() -> None:
    events = [_event("vendor-g/a"), _event("vendor-j/b"), _event("vendor-h/c")]
    split = filter_independent(events, "vendor-j/judge-1")
    assert [e.model for e in split.kept] == ["vendor-g/a", "vendor-h/c"]
    assert split.skipped_not_independent == 1


def test_independence_when_judge_unset_then_run_refused() -> None:
    with pytest.raises(JudgeNotConfiguredError, match="LLM_EVAL_JUDGE_MODEL"):
        require_judge_configured("")
    with pytest.raises(JudgeNotConfiguredError):
        filter_independent([_event("vendor-g/a")], "")
    require_judge_configured("vendor-j/judge-1")
