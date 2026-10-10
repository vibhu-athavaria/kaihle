"""Characterization tests for scripts/generate_gap_questions.py generate_for_subtopic.

These pin the CURRENT behaviour of the LLM call and response handling so the
generation seams can be extracted without changing it (EVAL-MASTER-PLAN SD-10).
All offline: ``complete`` and ``asyncio.sleep`` are mocked.
"""

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from scripts import generate_gap_questions as gen

MODULE = "scripts.generate_gap_questions"


def _subtopic() -> dict[str, Any]:
    return {
        "subject_code": "MATH",
        "grade_level": 7,
        "subtopic_name": "Angles in triangles",
        "topic_name": "Geometry",
        "subject_name": "Mathematics",
        "curriculum_name": "Cambridge",
        "curriculum_code": "CAIE",
        "learning_objective": "Find unknown angles in triangles",
    }


def _mcq(level: int = 1, text: str = "Which statement about triangle angles is correct?") -> dict[str, Any]:
    return {
        "difficulty_level": level,
        "question_type": "multiple_choice",
        "question_text": text,
        "options": {"A": "They sum to 90", "B": "They sum to 180", "C": "They sum to 270", "D": "They sum to 360"},
        "correct_answer": "B",
        "bloom_taxonomy_level": "Remember",
        "estimated_time_seconds": 30,
        "learning_objectives": ["Recall the angle sum"],
        "explanation": "B is correct because the angles of a triangle sum to 180 degrees.",
        "hints": {"hint1": "Think", "hint2": "Consider", "hint3": "It is 180"},
    }


def _true_false(level: int = 2) -> dict[str, Any]:
    return {
        "difficulty_level": level,
        "question_type": "true_false",
        "question_text": "True or False: A triangle can have two right angles.",
        "correct_answer": "false ",
        "bloom_taxonomy_level": "Understand",
        "estimated_time_seconds": 45,
        "learning_objectives": ["Understand angle sum"],
        "explanation": "This is FALSE because two right angles already sum to 180.",
        "hints": {"hint1": "Add", "hint2": "Compare", "hint3": "Too large"},
    }


async def _run(
    responses: list[Any],
    fill_plan: dict[int, int] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int], AsyncMock, AsyncMock]:
    complete_mock = AsyncMock(side_effect=responses)
    sleep_mock = AsyncMock()
    with patch(f"{MODULE}.complete", complete_mock), patch(f"{MODULE}.asyncio.sleep", sleep_mock):
        accepted, stats = await gen.generate_for_subtopic(
            _subtopic(), asyncio.Semaphore(1), dry_run=False, fill_plan=fill_plan
        )
    return accepted, stats, complete_mock, sleep_mock


@pytest.mark.asyncio
async def test_generate_for_subtopic_when_response_valid_then_questions_accepted_and_tf_normalised() -> None:
    payload = json.dumps({"questions": [_mcq(1), _true_false(2)]})

    accepted, stats, complete_mock, sleep_mock = await _run([payload], fill_plan={1: 1, 2: 1})

    assert [q["question_type"] for q in accepted] == ["multiple_choice", "true_false"]
    assert accepted[1]["correct_answer"] == "FALSE"
    assert "options" not in accepted[1]
    assert stats["llm_calls"] == 1
    assert stats["questions_accepted"] == 2
    assert complete_mock.await_count == 1
    sleep_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_generate_for_subtopic_when_response_markdown_fenced_then_questions_accepted() -> None:
    payload = "```json\n" + json.dumps({"questions": [_mcq(1)]}) + "\n```"

    accepted, stats, complete_mock, _ = await _run([payload], fill_plan={1: 1})

    assert len(accepted) == 1
    assert stats["llm_calls"] == 1
    assert complete_mock.await_count == 1


@pytest.mark.asyncio
async def test_generate_for_subtopic_when_json_malformed_then_retries_with_backoff_and_recovers() -> None:
    good = json.dumps({"questions": [_mcq(1)]})

    with patch(f"{MODULE}.log") as log_mock:
        accepted, stats, complete_mock, sleep_mock = await _run(["{not json", good], fill_plan={1: 1})

    assert len(accepted) == 1
    assert stats["llm_calls"] == 2
    assert complete_mock.await_count == 2
    sleep_mock.assert_awaited_once_with(2)
    event_names = [c.args[0] for c in log_mock.error.call_args_list]
    assert event_names == ["json_parse_failed"]
    assert log_mock.error.call_args.kwargs["preview"] == "{not json"


@pytest.mark.asyncio
async def test_generate_for_subtopic_when_json_always_malformed_then_returns_nothing_after_max_retries() -> None:
    accepted, stats, complete_mock, sleep_mock = await _run(["nope"] * gen.MAX_RETRIES, fill_plan={1: 1})

    assert accepted == []
    assert stats["llm_calls"] == gen.MAX_RETRIES
    assert complete_mock.await_count == gen.MAX_RETRIES
    assert [c.args[0] for c in sleep_mock.await_args_list] == [2, 4]


@pytest.mark.asyncio
async def test_generate_for_subtopic_when_questions_empty_then_retries_and_recovers() -> None:
    good = json.dumps({"questions": [_mcq(1)]})

    accepted, stats, _, sleep_mock = await _run([json.dumps({"questions": []}), good], fill_plan={1: 1})

    assert len(accepted) == 1
    assert stats["llm_calls"] == 2
    sleep_mock.assert_awaited_once_with(2)


@pytest.mark.asyncio
async def test_generate_for_subtopic_when_bare_list_response_then_attribute_error_propagates() -> None:
    # Characterized current behaviour: no list-or-dict tolerance. A bare JSON list
    # reaches ``batch.get`` and raises AttributeError, which is NOT retried.
    payload = json.dumps([_mcq(1)])

    complete_mock = AsyncMock(return_value=payload)
    sleep_mock = AsyncMock()
    with patch(f"{MODULE}.complete", complete_mock), patch(f"{MODULE}.asyncio.sleep", sleep_mock):
        with pytest.raises(AttributeError):
            await gen.generate_for_subtopic(_subtopic(), asyncio.Semaphore(1), dry_run=False, fill_plan={1: 1})

    assert complete_mock.await_count == 1
    sleep_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_generate_for_subtopic_when_called_then_llm_params_match_production() -> None:
    payload = json.dumps({"questions": [_mcq(1)]})

    _, _, complete_mock, _ = await _run([payload], fill_plan={1: 1})

    assert complete_mock.await_args is not None
    kwargs = complete_mock.await_args.kwargs
    assert kwargs["task"] == "question_generation"
    assert kwargs["temperature"] == 0.4
    assert kwargs["max_tokens"] == 20000
    system, user = kwargs["messages"]
    assert system == {
        "role": "system",
        "content": (
            "You are an expert Cambridge curriculum assessment author. "
            "Output valid JSON only. "
            "No markdown fences. No text outside the JSON object. "
            "No HTML tags, no LaTeX, no markdown inside string values. "
            "DO use Unicode maths characters (x² ½ × ÷ ≤ √ ° π) — the "
            "student app renders them correctly and they make questions "
            "readable."
        ),
    }
    assert user["role"] == "user"
    assert "Angles in triangles" in user["content"]


def test_parse_generation_response_when_plain_json_then_decoded() -> None:
    assert gen.parse_generation_response('{"questions": [1]}') == {"questions": [1]}


def test_parse_generation_response_when_fenced_with_language_tag_then_fences_stripped() -> None:
    assert gen.parse_generation_response('  ```json\n{"questions": []}\n```  ') == {"questions": []}


def test_parse_generation_response_when_fenced_without_language_tag_then_fences_stripped() -> None:
    assert gen.parse_generation_response('```\n{"a": 1}\n```') == {"a": 1}


def test_parse_generation_response_when_malformed_then_json_decode_error_carries_stripped_text() -> None:
    with pytest.raises(json.JSONDecodeError) as exc_info:
        gen.parse_generation_response("```json\n{broken\n```")

    assert exc_info.value.doc == "{broken"


def test_parse_generation_response_when_bare_list_then_returned_untouched() -> None:
    # No list-or-dict tolerance by design (behaviour-preserving extraction).
    assert gen.parse_generation_response("[1, 2]") == [1, 2]


def test_generation_constants_when_imported_then_match_production_values() -> None:
    assert gen.GENERATION_TEMPERATURE == 0.4
    assert gen.GENERATION_MAX_TOKENS == 20000
    assert gen.GENERATION_SYSTEM_PROMPT.startswith("You are an expert Cambridge curriculum assessment author. ")
    assert gen.GENERATION_SYSTEM_PROMPT.endswith("they make questions readable.")
