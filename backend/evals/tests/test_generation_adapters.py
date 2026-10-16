"""Offline tests for the question-bank generation adapter. complete() is mocked; nothing is networked."""

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from evals.calibration_set.build import SHIPPED_PATH, load_calibration_cases
from evals.question_generation import (
    SPECS_PATH,
    GenerationSpec,
    generate_bank_outcome,
    load_generation_specs,
    prompt_subtopic,
)
from scripts.generate_gap_questions import GENERATION_MAX_TOKENS, GENERATION_SYSTEM_PROMPT, GENERATION_TEMPERATURE

SPEC = load_generation_specs()[0]
_VALID = load_calibration_cases(SHIPPED_PATH)[0].question.to_bank_dict()


def _bank_question(stem: str = "What is 2 + 3 x 4?", **overrides: Any) -> dict[str, Any]:
    return {**_VALID, "question_text": stem, **overrides}


def _reply(*questions: dict[str, Any]) -> str:
    return json.dumps({"questions": list(questions)})


async def _run(reply: str, spec: GenerationSpec = SPEC) -> Any:
    with patch("evals.question_generation.complete", new_callable=AsyncMock, return_value=reply):
        return await generate_bank_outcome(spec)


async def test_bank_path_when_spec_given_then_prompt_built_by_production_build_prompt() -> None:
    with (
        patch("evals.question_generation.complete", new_callable=AsyncMock, return_value=_reply()) as complete,
        patch("evals.question_generation.build_prompt", return_value="PROD PROMPT") as build,
    ):
        await generate_bank_outcome(SPEC)

    assert build.call_args.args[0] == prompt_subtopic(SPEC)
    assert prompt_subtopic(SPEC)["learning_objective"] == SPEC.learning_objective
    kwargs = complete.call_args.kwargs
    assert kwargs["task"] == "question_generation"
    assert kwargs["messages"] == [
        {"role": "system", "content": GENERATION_SYSTEM_PROMPT},
        {"role": "user", "content": "PROD PROMPT"},
    ]
    assert kwargs["temperature"] == GENERATION_TEMPERATURE
    assert kwargs["max_tokens"] == GENERATION_MAX_TOKENS


async def test_bank_path_when_response_contains_true_false_then_excluded_from_mcq_set_and_counted() -> None:
    true_false = {**_bank_question("True or False: 7 is prime."), "question_type": "true_false"}

    outcome = await _run(_reply(_bank_question(), true_false))

    assert outcome.status == "ok"
    assert [q.question_text for q in outcome.questions] == ["What is 2 + 3 x 4?"]
    assert outcome.true_false_count == 1
    assert outcome.schema_failures == []


async def test_bank_path_when_question_fails_validate_question_then_schema_errors_recorded() -> None:
    broken = _bank_question("Broken one", options={"A": "1", "B": "2"})

    outcome = await _run(_reply(_bank_question(), broken))

    assert len(outcome.questions) == 1
    assert len(outcome.schema_failures) == 1
    assert "options" in outcome.schema_failures[0]


async def test_bank_path_when_reply_is_not_json_then_structural_outcome_without_raising() -> None:
    with patch("evals.question_generation.logger") as log:
        outcome = await _run("not json at all")

    assert outcome.status == "unparseable"
    assert outcome.questions == []
    log.warning.assert_called_once()


async def test_bank_path_when_reply_is_a_bare_list_then_structural_outcome_without_raising() -> None:
    outcome = await _run(json.dumps([_bank_question()]))

    assert outcome.status == "unparseable"


async def test_bank_path_when_questions_array_empty_then_no_questions_outcome() -> None:
    outcome = await _run(_reply())

    assert outcome.status == "no_questions"


async def test_bank_path_when_router_raises_then_exception_propagates() -> None:
    with (
        patch("evals.question_generation.complete", new_callable=AsyncMock, side_effect=RuntimeError("boom")),
        pytest.raises(RuntimeError, match="boom"),
    ):
        await generate_bank_outcome(SPEC)


def test_generation_specs_when_loaded_then_cover_all_three_subjects_grades_6_to_10_and_three_mastery_bands() -> None:
    specs = load_generation_specs(SPECS_PATH)

    assert len(specs) >= 12
    assert {s.subject_code for s in specs} == {"MATH", "SCI", "ENG"}
    assert {s.grade_level for s in specs} >= {6, 7, 8, 9, 10}
    assert {s.mastery for s in specs} == {"low", "mid", "high"}
    assert len({s.spec_id for s in specs}) == len(specs)
    assert all(s.topic_name and s.subject_name and s.learning_objective for s in specs)


def test_load_generation_specs_when_unknown_field_then_raises_naming_the_spec(tmp_path: Any) -> None:
    row = SPECS_PATH.read_text(encoding="utf-8").splitlines()[0]
    bad = tmp_path / "bad.jsonl"
    bad.write_text(row[:-1] + ', "student_name": "x"}\n', encoding="utf-8")

    with pytest.raises(ValueError, match="gen-001"):
        load_generation_specs(bad)
