"""Characterization tests for scripts/validate_and_fix_questions.py.

`validate_subtopic_batch` is exercised with the router `complete` mocked. These
tests pin the behaviour of the production question-quality judge call so that the
response-parsing extraction (EVAL-MASTER-PLAN SD-10) can be shown to preserve it.
"""

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from scripts import validate_and_fix_questions as vfq

CHUNK = 15


def _group(n_questions: int) -> dict[str, Any]:
    return {
        "subtopic_info": {
            "subtopic_name": "Adding fractions",
            "subject_name": "Mathematics",
            "topic_name": "Fractions",
            "learning_objective": "Add fractions with unlike denominators",
            "subject_code": "MATH",
            "grade_level": 7,
        },
        "questions": [{"question_text": f"Q{i}", "correct_answer": "A"} for i in range(n_questions)],
    }


def _verdict(index: int, overall_pass: bool = True) -> dict[str, Any]:
    return {
        "index": index,
        "overall_pass": overall_pass,
        "validations": {"factual_accuracy": {"pass": overall_pass}},
        "corrected_question": None,
        "changes_made": [],
    }


async def _run(group: dict[str, Any]) -> dict[str, Any]:
    return await vfq.validate_subtopic_batch(group, asyncio.Semaphore(1), dry_run=False)


@pytest.mark.asyncio
async def test_validate_subtopic_batch_when_llm_returns_valid_dict_then_results_returned_with_pass_rate() -> None:
    reply = json.dumps({"questions": [_verdict(0)]})
    with patch("scripts.validate_and_fix_questions.complete", new_callable=AsyncMock, return_value=reply):
        result = await _run(_group(1))

    assert result["pass_rate"] == "1/1"
    assert result["questions"][0]["index"] == 0
    assert result["questions"][0]["overall_pass"] is True


@pytest.mark.asyncio
async def test_validate_subtopic_batch_when_llm_returns_bare_list_then_accepted() -> None:
    reply = json.dumps([_verdict(0)])
    with patch("scripts.validate_and_fix_questions.complete", new_callable=AsyncMock, return_value=reply):
        result = await _run(_group(1))

    assert result["pass_rate"] == "1/1"
    assert len(result["questions"]) == 1


@pytest.mark.asyncio
async def test_validate_subtopic_batch_when_response_is_markdown_fenced_then_fences_stripped() -> None:
    reply = "```json\n" + json.dumps({"questions": [_verdict(0)]}) + "\n```"
    with patch("scripts.validate_and_fix_questions.complete", new_callable=AsyncMock, return_value=reply):
        result = await _run(_group(1))

    assert result["pass_rate"] == "1/1"
    assert "error" not in result["questions"][0]


@pytest.mark.asyncio
async def test_validate_subtopic_batch_when_json_malformed_then_every_question_marked_failed_with_parse_error() -> None:
    with patch("scripts.validate_and_fix_questions.complete", new_callable=AsyncMock, return_value="not json"):
        result = await _run(_group(3))

    assert result["pass_rate"] == "0/3"
    assert [q["index"] for q in result["questions"]] == [0, 1, 2]
    for q in result["questions"]:
        assert q["overall_pass"] is False
        assert q["error"] == "Failed to parse validation response"


@pytest.mark.asyncio
async def test_validate_subtopic_batch_when_llm_call_raises_then_every_question_marked_failed_with_call_error() -> None:
    with patch(
        "scripts.validate_and_fix_questions.complete",
        new_callable=AsyncMock,
        side_effect=RuntimeError("boom"),
    ):
        result = await _run(_group(2))

    assert result["pass_rate"] == "0/2"
    for q in result["questions"]:
        assert q["overall_pass"] is False
        assert q["error"].startswith("LLM call failed")
        assert "boom" in q["error"]


@pytest.mark.asyncio
async def test_validate_subtopic_batch_when_more_than_chunk_size_then_indices_remapped_to_global_positions() -> None:
    # Each chunk reply uses chunk-local indices, as the prompt asks the model to.
    replies = [
        json.dumps({"questions": [_verdict(i) for i in range(CHUNK)]}),
        json.dumps({"questions": [_verdict(i) for i in range(5)]}),
    ]
    mock = AsyncMock(side_effect=replies)
    with patch("scripts.validate_and_fix_questions.complete", mock):
        result = await _run(_group(20))

    assert mock.await_count == 2
    assert [q["index"] for q in result["questions"]] == list(range(20))
    assert result["pass_rate"] == "20/20"


@pytest.mark.asyncio
async def test_validate_subtopic_batch_when_one_chunk_fails_then_error_records_carry_global_indices() -> None:
    replies = [json.dumps({"questions": [_verdict(i) for i in range(CHUNK)]}), "garbage"]
    with patch("scripts.validate_and_fix_questions.complete", AsyncMock(side_effect=replies)):
        result = await _run(_group(20))

    tail = result["questions"][CHUNK:]
    assert [q["index"] for q in tail] == [15, 16, 17, 18, 19]
    assert all(q["error"] == "Failed to parse validation response" for q in tail)
    assert result["pass_rate"] == "15/20"


@pytest.mark.asyncio
async def test_validate_subtopic_batch_when_questions_value_not_a_list_then_chunk_yields_no_results() -> None:
    reply = json.dumps({"questions": "nope"})
    with patch("scripts.validate_and_fix_questions.complete", new_callable=AsyncMock, return_value=reply):
        result = await _run(_group(1))

    assert result["questions"] == []
    assert result["pass_rate"] == "0/0"


@pytest.mark.asyncio
async def test_validate_subtopic_batch_when_non_dict_items_in_response_then_they_are_skipped() -> None:
    reply = json.dumps([1, _verdict(0)])
    with patch("scripts.validate_and_fix_questions.complete", new_callable=AsyncMock, return_value=reply):
        result = await _run(_group(1))

    assert len(result["questions"]) == 1
    assert result["questions"][0]["index"] == 0


@pytest.mark.asyncio
async def test_validate_subtopic_batch_when_called_then_uses_question_quality_task_with_fixed_params() -> None:
    reply = json.dumps({"questions": [_verdict(0)]})
    mock = AsyncMock(return_value=reply)
    with patch("scripts.validate_and_fix_questions.complete", mock):
        await _run(_group(1))

    assert mock.await_args is not None
    kwargs = mock.await_args.kwargs
    assert kwargs["task"] == "question_quality"
    assert kwargs["temperature"] == 0.2
    assert kwargs["max_tokens"] == 20000
    assert kwargs["messages"][0]["role"] == "system"
    assert "re-solve every question independently" in kwargs["messages"][0]["content"]


def test_parse_validation_response_when_dict_with_questions_then_returns_list() -> None:
    text = json.dumps({"questions": [{"index": 0}, {"index": 1}]})

    assert vfq.parse_validation_response(text) == [{"index": 0}, {"index": 1}]


def test_parse_validation_response_when_bare_list_then_returns_list() -> None:
    assert vfq.parse_validation_response('[{"index": 0}]') == [{"index": 0}]


def test_parse_validation_response_when_fenced_then_strips_fences() -> None:
    assert vfq.parse_validation_response('```json\n[{"index": 0}]\n```') == [{"index": 0}]
    assert vfq.parse_validation_response('```\n{"questions": [{"index": 2}]}\n```') == [{"index": 2}]


def test_parse_validation_response_when_non_dict_items_then_skipped() -> None:
    assert vfq.parse_validation_response('[1, {"index": 0}]') == [{"index": 0}]


def test_parse_validation_response_when_questions_value_not_a_list_then_returns_empty() -> None:
    assert vfq.parse_validation_response('{"questions": "nope"}') == []


def test_parse_validation_response_when_top_level_is_scalar_or_dict_without_questions_then_returns_empty() -> None:
    assert vfq.parse_validation_response("42") == []
    assert vfq.parse_validation_response('{"other": 1}') == []


def test_parse_validation_response_when_undecodable_then_raises_validation_response_error() -> None:
    with pytest.raises(vfq.ValidationResponseError):
        vfq.parse_validation_response("not json")


def test_validation_response_error_when_raised_then_is_a_value_error() -> None:
    assert issubclass(vfq.ValidationResponseError, ValueError)


def test_quality_constants_when_imported_then_match_production_values() -> None:
    assert vfq.QUALITY_TEMPERATURE == 0.2
    assert vfq.QUALITY_MAX_TOKENS == 20000
    assert "re-solve every question independently" in vfq.QUALITY_SYSTEM_PROMPT
