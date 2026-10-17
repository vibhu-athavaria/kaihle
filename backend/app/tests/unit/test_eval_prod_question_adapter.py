"""Unit tests for the usage-event -> EvalQuestion adapter (MLH-T18 slice 5b-i)."""

import json
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest

from app.ai.eval.question_model import EvalQuestion
from app.services.eval_prod.question_adapter import (
    adapt_event,
    parse_batch,
    parse_context,
    scrub_question,
)
from app.services.eval_prod.sampler import SampledEvent

PROMPT = """You are an expert author.

CURRICULUM CONTEXT:
- Programme:          Cambridge Lower Secondary (CLS)
- Subject:            Mathematics (MATH)
- Grade:              7
- Topic:              Fractions
- Subtopic:           Adding fractions
- Learning objective: Add fractions with unlike denominators
"""


def _mcq(level: int = 3, **overrides: Any) -> dict[str, Any]:
    question: dict[str, Any] = {
        "difficulty_level": level,
        "question_type": "multiple_choice",
        "question_text": "What is 1/2 + 1/4?",
        "options": {"A": "3/4", "B": "2/6", "C": "1/8", "D": "1"},
        "correct_answer": "A",
        "learning_objectives": ["Add fractions"],
        "explanation": "A is right.",
    }
    question.update(overrides)
    return question


def _event(response: str, prompt: str | None = PROMPT) -> SampledEvent:
    return SampledEvent(
        id=uuid.uuid4(),
        task="question_generation",
        model="vendor/model",
        component=None,
        school_id=None,
        prompt_text=prompt,
        response_text=response,
        created_at=datetime.now(UTC),
    )


def _adapt(event: SampledEvent, seed: str = "s") -> EvalQuestion:
    question = adapt_event(event, seed=seed)
    assert question is not None
    return question


def test_parse_batch_when_fenced_json_then_returns_questions() -> None:
    text = "```json\n" + json.dumps({"questions": [_mcq()]}) + "\n```"
    assert parse_batch(text) == [_mcq()]


@pytest.mark.parametrize(
    "text",
    ["not json", "[]", '{"questions": []}', '{"questions": "x"}', '{"other": 1}', '{"questions": [1, 2]}'],
)
def test_parse_batch_when_unusable_then_returns_none(text: str) -> None:
    assert parse_batch(text) is None


def test_parse_context_when_prompt_has_curriculum_block_then_extracts_fields() -> None:
    context = parse_context(PROMPT)
    assert context is not None
    assert (context.grade_level, context.subject_code, context.subtopic_name) == (7, "MATH", "Adding fractions")


@pytest.mark.parametrize("prompt", [None, "", "no context here", "- Grade: seven\n- Subtopic: x\n- Subject: M (M)"])
def test_parse_context_when_missing_or_malformed_then_returns_none(prompt: str | None) -> None:
    assert parse_context(prompt) is None


def test_adapt_event_when_valid_batch_then_returns_one_question_with_context() -> None:
    event = _event(json.dumps({"questions": [_mcq(1), _mcq(5)]}))
    question = _adapt(event)
    assert question.grade_level == 7
    assert question.subject_code == "MATH"
    assert question.difficulty_band in ("foundational", "advanced")
    assert question.id.startswith(str(event.id))


def test_adapt_event_when_seed_same_then_same_question_and_seed_varies_the_pick() -> None:
    event = _event(json.dumps({"questions": [_mcq(1, question_text=f"Q{i}") for i in range(12)]}))
    assert _adapt(event, "s") == _adapt(event, "s")
    picks = {_adapt(event, str(i)).question_text for i in range(10)}
    assert len(picks) > 1


@pytest.mark.parametrize(
    ("level", "band"), [(1, "foundational"), (2, "foundational"), (3, "developing"), (4, "advanced"), (5, "advanced")]
)
def test_adapt_event_when_difficulty_level_given_then_band_matches(level: int, band: str) -> None:
    assert _adapt(_event(json.dumps({"questions": [_mcq(level)]}))).difficulty_band == band


def test_adapt_event_when_only_true_false_then_returns_none() -> None:
    batch = {"questions": [{"question_type": "true_false", "question_text": "True or False: x", "correct_answer": "T"}]}
    assert adapt_event(_event(json.dumps(batch)), seed="s") is None


def test_adapt_event_when_mcq_is_malformed_then_skips_it_and_uses_a_valid_one() -> None:
    batch = {"questions": [_mcq(options={"A": "x"}), _mcq(question_text="Valid one")]}
    assert _adapt(_event(json.dumps(batch))).question_text == "Valid one"


@pytest.mark.parametrize("response", ["garbage", '{"questions": []}'])
def test_adapt_event_when_response_unparseable_then_returns_none(response: str) -> None:
    assert adapt_event(_event(response), seed="s") is None


def test_adapt_event_when_prompt_has_no_context_then_returns_none() -> None:
    assert adapt_event(_event(json.dumps({"questions": [_mcq()]}), prompt=None), seed="s") is None


def test_scrub_question_when_pii_in_fields_then_all_text_fields_scrubbed_and_ids_kept() -> None:
    mcq = _mcq(question_text="Email bob@example.com now", explanation="Call Asha")
    question = _adapt(_event(json.dumps({"questions": [mcq]})))
    scrubbed = scrub_question(question, person_names=("Asha",), school_name=None)
    assert "bob@example.com" not in scrubbed.question_text and "[EMAIL]" in scrubbed.question_text
    assert "Asha" not in scrubbed.explanation
    assert scrubbed.id == question.id and scrubbed.correct_answer == question.correct_answer
