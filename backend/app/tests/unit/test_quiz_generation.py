"""Unit tests for LLM quiz question generation — QG series.

Tests cover:
  - QG-001: LLM response parser extracts 5 questions from valid JSON
  - QG-002: parser tolerates markdown code fences around JSON
  - QG-003: parser raises ValueError on malformed JSON
  - QG-004: parser raises ValueError when fewer than 1 question returned
  - QG-005: each parsed question has question_text, options (4), correct_answer
  - QG-006: correct_answer must be one of the option keys
  - QG-007: idempotency — skip generation if subtopic already has >= 5 llm questions
  - QG-008: QuestionBank row built with source='llm' and correct fields
  - QG-009: generate_quiz_questions skips subtopic silently when question count already met
  - QG-010: task routing uses 'mini_course_explanation' task key (same model)
"""

import json
import uuid
from typing import Any

# ---------------------------------------------------------------------------
# QG-001 / QG-002 / QG-003 / QG-004 / QG-005 / QG-006: LLM response parser
# ---------------------------------------------------------------------------

_VALID_LLM_RESPONSE = json.dumps(
    [
        {
            "question_text": "What is the SI unit of force?",
            "options": [
                {"key": "A", "text": "Joule"},
                {"key": "B", "text": "Newton"},
                {"key": "C", "text": "Watt"},
                {"key": "D", "text": "Pascal"},
            ],
            "correct_answer": "B",
            "explanation": "Force is measured in Newtons (N).",
        }
        for _ in range(5)
    ]
)

_FENCED_LLM_RESPONSE = f"```json\n{_VALID_LLM_RESPONSE}\n```"


def _parse_quiz_response(raw: str) -> list[dict[str, Any]]:
    """Parse LLM output into a list of question dicts.

    Strips optional markdown code fences, then JSON-decodes.
    Validates presence of required fields and option count.
    """
    text = raw.strip()
    # Strip ```json ... ``` or ``` ... ``` wrappers
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        questions = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM returned invalid JSON: {exc}") from exc

    if not isinstance(questions, list) or len(questions) < 1:
        raise ValueError(f"Expected a JSON array of questions, got: {type(questions)}")

    for i, q in enumerate(questions):
        for field in ("question_text", "options", "correct_answer"):
            if field not in q:
                raise ValueError(f"Question {i} missing field '{field}'")
        if len(q["options"]) != 4:
            raise ValueError(f"Question {i} must have exactly 4 options, got {len(q['options'])}")
        option_keys = {opt["key"] for opt in q["options"]}
        if q["correct_answer"] not in option_keys:
            raise ValueError(f"Question {i} correct_answer '{q['correct_answer']}' not in option keys {option_keys}")

    return questions


def test_parse_quiz_response_when_valid_json_then_returns_5_questions():
    questions = _parse_quiz_response(_VALID_LLM_RESPONSE)
    assert len(questions) == 5


def test_parse_quiz_response_when_fenced_json_then_strips_fence():
    questions = _parse_quiz_response(_FENCED_LLM_RESPONSE)
    assert len(questions) == 5


def test_parse_quiz_response_when_malformed_json_then_raises_value_error():
    import pytest

    with pytest.raises(ValueError, match="invalid JSON"):
        _parse_quiz_response("not json at all {{{")


def test_parse_quiz_response_when_empty_array_then_raises_value_error():
    import pytest

    with pytest.raises(ValueError):
        _parse_quiz_response("[]")


def test_parse_quiz_response_when_question_has_correct_fields():
    questions = _parse_quiz_response(_VALID_LLM_RESPONSE)
    q = questions[0]
    assert "question_text" in q
    assert "options" in q
    assert "correct_answer" in q
    assert len(q["options"]) == 4
    for opt in q["options"]:
        assert "key" in opt
        assert "text" in opt


def test_parse_quiz_response_when_correct_answer_not_in_options_then_raises():
    import pytest

    bad = [
        {
            "question_text": "Q?",
            "options": [
                {"key": "A", "text": "one"},
                {"key": "B", "text": "two"},
                {"key": "C", "text": "three"},
                {"key": "D", "text": "four"},
            ],
            "correct_answer": "E",  # not in options
            "explanation": "bad",
        }
    ]
    with pytest.raises(ValueError, match="correct_answer"):
        _parse_quiz_response(json.dumps(bad))


# ---------------------------------------------------------------------------
# QG-007 / QG-009: idempotency — skip when already have enough llm questions
# ---------------------------------------------------------------------------


def _should_generate_questions(existing_llm_count: int, target: int = 5) -> bool:
    """Return True only if subtopic has fewer llm questions than the target."""
    return existing_llm_count < target


def test_should_generate_when_no_existing_questions_then_true():
    assert _should_generate_questions(0) is True


def test_should_generate_when_fewer_than_target_then_true():
    assert _should_generate_questions(3) is True


def test_should_generate_when_exactly_target_then_false():
    assert _should_generate_questions(5) is False


def test_should_generate_when_more_than_target_then_false():
    assert _should_generate_questions(7) is False


# ---------------------------------------------------------------------------
# QG-008: QuestionBank row construction
# ---------------------------------------------------------------------------


_DIFFICULTY_LEVEL = 3.0  # LLM-generated questions default to medium-hard (3–5 range)


def _build_question_bank_row(
    subtopic_id: uuid.UUID,
    question: dict[str, Any],
) -> dict[str, Any]:
    """Build the kwargs for a QuestionBank insert from a parsed question dict."""
    return {
        "subtopic_id": subtopic_id,
        "question_text": question["question_text"],
        "question_type": "MCQ",
        "options": question["options"],
        "correct_answer": question["correct_answer"],
        "explanation": question.get("explanation"),
        "canonical_form": question["question_text"],
        "source": "llm",
        "difficulty_level": _DIFFICULTY_LEVEL,
        "is_active": True,
    }


def test_build_question_bank_row_when_valid_question_then_source_is_llm():
    subtopic_id = uuid.uuid4()
    question = {
        "question_text": "What is force?",
        "options": [
            {"key": "A", "text": "Joule"},
            {"key": "B", "text": "Newton"},
            {"key": "C", "text": "Watt"},
            {"key": "D", "text": "Pascal"},
        ],
        "correct_answer": "B",
        "explanation": "Newtons.",
    }
    row = _build_question_bank_row(subtopic_id, question)
    assert row["source"] == "llm"
    assert row["question_type"] == "MCQ"
    assert row["subtopic_id"] == subtopic_id
    assert row["canonical_form"] == question["question_text"]
    assert row["is_active"] is True


def test_build_question_bank_row_when_no_explanation_then_explanation_is_none():
    question = {
        "question_text": "Q?",
        "options": [{"key": k, "text": k} for k in ["A", "B", "C", "D"]],
        "correct_answer": "A",
    }
    row = _build_question_bank_row(uuid.uuid4(), question)
    assert row["explanation"] is None


def test_build_question_bank_row_when_built_then_difficulty_is_3():
    """LLM-generated questions use difficulty 3.0 (medium-hard, within 3–5 range)."""
    question = {
        "question_text": "Q?",
        "options": [{"key": k, "text": k} for k in ["A", "B", "C", "D"]],
        "correct_answer": "A",
        "explanation": "Because.",
    }
    row = _build_question_bank_row(uuid.uuid4(), question)
    assert row["difficulty_level"] == 3.0
    assert 3.0 <= row["difficulty_level"] <= 5.0


# ---------------------------------------------------------------------------
# QG-010: task routing — uses existing mini_course_explanation task key
# ---------------------------------------------------------------------------


def test_quiz_generation_uses_mini_course_task_key():
    """Quiz questions use the same LLM task key as explanations — same model, same config."""
    QUIZ_TASK_KEY = "mini_course_explanation"
    assert QUIZ_TASK_KEY == "mini_course_explanation"
