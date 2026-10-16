"""Unit tests for the pure tutor seams extracted from concept_guide_service (T11 slice 1).

The seams let the eval harness render the exact production prompts and messages
and use the exact production sampling values without a database or HTTP.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.services import concept_guide_service as svc

_REDIRECT = "That's a great question for another time — let's focus on Photosynthesis for now."


def _system_prompt() -> str:
    return svc.render_explain_this_system_prompt(
        subtopic_name="Photosynthesis",
        topic_name="Plant Biology",
        subject_name="Science",
        grade_level=8,
        dominant_modality="visual",
        interest_category="sports_movement",
    )


def _guide_prompt(question: str | None, interests: list[str] | None = None) -> str:
    return svc.render_concept_guide_prompt(
        subtopic_name="Photosynthesis",
        description="How plants make food.",
        learning_objective="Explain light reactions.",
        keywords=["chlorophyll"],
        dominant_modality="visual",
        interests=["football"] if interests is None else interests,
        work_style={},
        question=question,
    )


def test_render_explain_this_system_prompt_when_called_then_contains_subtopic_grade_and_redirect_rule() -> None:
    prompt = _system_prompt()

    assert '"Photosynthesis" (part of Plant Biology, Science, Grade 8)' in prompt
    assert "Grade 8 student" in prompt
    assert _REDIRECT in prompt


def test_build_explain_this_messages_when_prior_turns_given_then_order_is_system_prior_user() -> None:
    prior = [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}]

    messages = svc.build_explain_this_messages(system_prompt="SYS", prior_messages=prior, question="Q")

    assert messages == [{"role": "system", "content": "SYS"}, *prior, {"role": "user", "content": "Q"}]


def test_build_explain_this_messages_when_no_prior_turns_then_system_then_user() -> None:
    messages = svc.build_explain_this_messages(system_prompt="SYS", prior_messages=[], question="Q")

    assert messages == [{"role": "system", "content": "SYS"}, {"role": "user", "content": "Q"}]


def test_render_concept_guide_prompt_when_question_given_then_question_is_quoted_in_prompt() -> None:
    prompt = _guide_prompt("Why are leaves green?")

    assert 'The student has a specific question: "Why are leaves green?"' in prompt


def test_render_concept_guide_prompt_when_no_question_then_struggling_student_branch_used() -> None:
    prompt = _guide_prompt(None)

    assert "currently struggling with it (mastery score below 70%)" in prompt
    assert "The student has a specific question" not in prompt


def test_render_concept_guide_prompt_when_interests_given_then_rendered_as_given() -> None:
    prompt = _guide_prompt(None, interests=["sports_movement", "tech_gaming"])

    assert "- Interests: sports_movement, tech_gaming" in prompt


def test_build_mcq_feedback_prompt_when_correct_then_suggests_assessment_and_omits_options() -> None:
    prompt = svc.build_mcq_feedback_prompt(
        subtopic_name="Photosynthesis",
        question="Q?",
        options=["A) one", "B) two"],
        correct="A",
        student_answer="A",
        is_correct=True,
    )

    assert "try an assessment" in prompt
    assert "A) one" not in prompt
    assert "Their answer: A (correct)" in prompt


def test_build_mcq_feedback_prompt_when_incorrect_then_includes_options_and_forbids_negative_words() -> None:
    prompt = svc.build_mcq_feedback_prompt(
        subtopic_name="Photosynthesis",
        question="Q?",
        options=["A) one", "B) two"],
        correct="B",
        student_answer="A",
        is_correct=False,
    )

    assert "Options:\nA) one\nB) two\n" in prompt
    assert "Correct answer: B" in prompt
    assert "Do NOT say 'wrong', 'incorrect', or 'that's not right'." in prompt


def test_tutor_constants_when_imported_then_match_production_sampling_values() -> None:
    assert (svc.EXPLAIN_THIS_TEMPERATURE, svc.EXPLAIN_THIS_MAX_TOKENS) == (0.6, 400)
    assert (svc.CONCEPT_GUIDE_TEMPERATURE, svc.CONCEPT_GUIDE_MAX_TOKENS) == (0.6, 600)
    assert (svc.MCQ_FEEDBACK_TEMPERATURE, svc.MCQ_FEEDBACK_MAX_TOKENS) == (0.5, 150)


@pytest.mark.asyncio
async def test_request_concept_guide_completion_when_called_then_single_user_message_with_production_params() -> None:
    with patch.object(svc.llm_router, "complete", new=AsyncMock(return_value="out")) as mock_complete:
        result = await svc.request_concept_guide_completion("PROMPT")

    assert result == "out"
    mock_complete.assert_awaited_once_with(
        task="concept_guide",
        messages=[{"role": "user", "content": "PROMPT"}],
        temperature=0.6,
        max_tokens=600,
    )


@pytest.mark.asyncio
async def test_request_mcq_feedback_completion_when_called_then_uses_feedback_params_on_concept_guide_task() -> None:
    with patch.object(svc.llm_router, "complete", new=AsyncMock(return_value="out")) as mock_complete:
        result = await svc.request_mcq_feedback_completion("PROMPT")

    assert result == "out"
    mock_complete.assert_awaited_once_with(
        task="concept_guide",
        messages=[{"role": "user", "content": "PROMPT"}],
        temperature=0.5,
        max_tokens=150,
    )
