"""Characterization tests for the tutor prompt/params/parse path (T11, SD-10).

Written against the code BEFORE the seams were extracted and kept unchanged
afterwards. They pin, byte-for-byte, what the three tutor surfaces send to the
router (messages, temperature, max_tokens, task), the log events, and the edge
cases of ``_parse_mcq``. They drive the public service functions with the router
patched, so they hold for any internal refactor of those functions.
"""

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import concept_guide_service as svc

_EXPLAIN_SYSTEM_GOLDEN = (
    'You are a patient tutor helping a student understand one specific topic:\n"Photosynthesis" '
    "(part of Plant Biology, Science, Grade 8).\n\nThe student learns best through visual explanations.\n"
    "They are interested in sports_movement.\n\nRULES:\n- Only answer questions about Photosynthesis. If asked about "
    "anything else, redirect:\n  \"That's a great question for another time — let's focus on Photosynthesis "
    'for now."\n- Keep answers under 150 words unless the student explicitly asks for more detail.\n'
    "- Use one concrete example tied to sports_movement when it fits naturally.\n- Never give direct answers to "
    "exam-style questions — guide with a follow-up question instead.\n"
    "- Use simple language appropriate for a Grade 8 student."
)

_GUIDE_HEAD = (
    "You are Kaihle, a patient and encouraging AI tutor helping a student understand a concept they are "
    "struggling with.\n\n## Student context\n- Learning style: visual learner\n"
)
_GUIDE_TAIL_RULES = (
    "Keep your explanation under 200 words. Use plain, friendly language — no jargon without explanation.\n"
    "Do NOT use headers, bullet lists, or markdown formatting in the explanation. Write in flowing "
    "paragraphs.\n\nAfter your explanation, you MUST ask ONE multiple choice check question with exactly 4 "
    "options.\nReturn the check question as a JSON block on its own line in this exact format:\n"
    '{"question": "...", "options": ["A) ...", "B) ...", "C) ...", "D) ..."], "correct": "A"}\n\nRules:\n'
    "- Explain the concept only. Do not solve homework problems or write essays for the student.\n"
    '- Do not engage with questions unrelated to "Photosynthesis". If asked anything off-topic, respond:\n'
    "  \"I'm here to help you understand Photosynthesis — let's stay focused on that.\"\n"
    "- The check question must test understanding of the concept just explained, not rote recall."
)
_GUIDE_WITH_QUESTION_GOLDEN = (
    _GUIDE_HEAD + "- Interests: football, gaming\n- Prefers short, focused explanations\n"
    "- Learns best through examples and tasks\n\n## Subtopic\n**Name:** Photosynthesis\n"
    "**Description:** How plants make food.\n**Learning objective:** Explain light reactions.\n"
    "**Key terms:** chlorophyll, glucose\n\n## Task\n\nThe student has a specific question: "
    '"Why are leaves green?"\n\nAnswer their question directly, then provide a clear explanation of the '
    "concept.\n\n\n## Instructions\n1. Start with a clear, simple explanation (2-3 sentences)\n"
    "2. Give one concrete example — use football or a real-world scenario the student can relate to\n"
    "3. Highlight the 1-2 most important things to remember\n\n" + _GUIDE_TAIL_RULES
)
_GUIDE_EMPTY_PROFILE_GOLDEN = (
    _GUIDE_HEAD
    + "\n\n\n\n## Subtopic\n**Name:** Photosynthesis\n\n**Learning objective:** Explain light reactions.\n\n\n"
    "## Task\n\nExplain this concept clearly for a student who is currently struggling with it "
    "(mastery score below 70%).\n\n\n## Instructions\n1. Start with a clear, simple explanation "
    "(2-3 sentences)\n2. Give one concrete example\n3. Highlight the 1-2 most important things to "
    "remember\n\n" + _GUIDE_TAIL_RULES
)

_MCQ_CORRECT_GOLDEN = (
    'A student just answered a check question about "Photosynthesis" correctly.\n'
    "Question: What do plants release?\n"
    "Their answer: b (correct)\n\n"
    "Write a warm, encouraging 1-2 sentence acknowledgement. "
    "Then suggest they try an assessment to test their understanding further. "
    "Keep it brief and positive. No markdown."
)
_MCQ_INCORRECT_GOLDEN = (
    'A student answered a check question about "Photosynthesis" incorrectly.\n'
    "Question: What do plants release?\n"
    "Options:\nA) Carbon dioxide\nB) Oxygen\nC) Nitrogen\nD) Helium\n"
    "Their answer: a — Correct answer: B\n\n"
    "Re-explain the concept from a different angle in 2-3 sentences. "
    "Do NOT say 'wrong', 'incorrect', or 'that's not right'. "
    "Be encouraging and clarifying. No markdown."
)

_OPTIONS = ["A) Carbon dioxide", "B) Oxygen", "C) Nitrogen", "D) Helium"]


def _result(**methods: Any) -> MagicMock:
    result = MagicMock()
    for name, value in methods.items():
        getattr(result, name).return_value = value
    return result


def _subtopic_row() -> MagicMock:
    row = MagicMock()
    row.subtopic_name = "Photosynthesis"
    row.topic_name = "Plant Biology"
    row.subject_name = "Science"
    row.grade_level = 8
    return row


def _profile(modality_scores: dict[str, Any], interests: list[str] | None) -> MagicMock:
    profile = MagicMock()
    profile.modality_scores = modality_scores
    profile.interests = interests
    profile.work_style = {"short_sessions": True, "task_based": True}
    return profile


def _stream_recorder(calls: list[dict[str, Any]]) -> Any:
    def _fake(**kwargs: Any) -> AsyncGenerator[str, None]:
        calls.append(kwargs)

        async def _gen() -> AsyncGenerator[str, None]:
            yield "data: hi\n\n"

        return _gen()

    return _fake


async def _drain(gen: AsyncGenerator[str, None]) -> list[str]:
    return [chunk async for chunk in gen]


# ---------------------------------------------------------------------------
# explain_this (single-shot)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_explain_subtopic_question_when_streaming_then_sends_exact_messages_and_sampling() -> None:
    db = AsyncMock(spec=AsyncSession)
    db.execute.side_effect = [
        _result(one_or_none=_subtopic_row()),
        _result(scalar_one_or_none=_profile({"visual": 0.9, "auditory": 0.1}, ["sports_movement", "tech_gaming"])),
    ]
    calls: list[dict[str, Any]] = []

    with (
        patch.object(svc.llm_router, "stream_sse", side_effect=_stream_recorder(calls)),
        patch.object(svc, "logger") as mock_logger,
    ):
        gen = await svc.explain_subtopic_question(
            subtopic_id=uuid4(), student_id=uuid4(), school_id=uuid4(), question="Why?", db=db
        )
        chunks = await _drain(gen)

    assert chunks == ["data: hi\n\n"]
    assert calls == [
        {
            "task": "explain_this",
            "messages": [
                {"role": "system", "content": _EXPLAIN_SYSTEM_GOLDEN},
                {"role": "user", "content": "Why?"},
            ],
            "temperature": 0.6,
            "max_tokens": 400,
        }
    ]
    events = [c.args[0] for c in mock_logger.info.call_args_list]
    assert events == ["explain_this_stream_started", "explain_this_stream_started_inner"]
    started = mock_logger.info.call_args_list[0].kwargs
    # Raw enum key reaches the student-facing prompt (T11 finding F7, input side).
    assert started["interest_category"] == "sports_movement"
    assert started["dominant_modality"] == "visual"


@pytest.mark.asyncio
async def test_explain_subtopic_question_when_no_profile_then_uses_general_topics_and_visual() -> None:
    db = AsyncMock(spec=AsyncSession)
    db.execute.side_effect = [_result(one_or_none=_subtopic_row()), _result(scalar_one_or_none=None)]
    calls: list[dict[str, Any]] = []

    with patch.object(svc.llm_router, "stream_sse", side_effect=_stream_recorder(calls)):
        gen = await svc.explain_subtopic_question(
            subtopic_id=uuid4(), student_id=uuid4(), school_id=uuid4(), question="Why?", db=db
        )
        await _drain(gen)

    system = calls[0]["messages"][0]["content"]
    assert "The student learns best through visual explanations.\nThey are interested in general topics." in system
    assert "Use one concrete example tied to general topics when it fits naturally." in system


@pytest.mark.asyncio
async def test_explain_subtopic_question_when_interest_key_unmapped_then_falls_back_to_general_topics() -> None:
    db = AsyncMock(spec=AsyncSession)
    db.execute.side_effect = [
        _result(one_or_none=_subtopic_row()),
        _result(scalar_one_or_none=_profile({"visual": 1.0}, ["not_a_known_key"])),
    ]
    calls: list[dict[str, Any]] = []

    with patch.object(svc.llm_router, "stream_sse", side_effect=_stream_recorder(calls)):
        gen = await svc.explain_subtopic_question(
            subtopic_id=uuid4(), student_id=uuid4(), school_id=uuid4(), question="Why?", db=db
        )
        await _drain(gen)

    assert "They are interested in general topics." in calls[0]["messages"][0]["content"]


# ---------------------------------------------------------------------------
# explain_this (multi-turn chat)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stream_chat_reply_when_prior_turns_then_order_is_system_prior_user_with_same_sampling() -> None:
    db = AsyncMock(spec=AsyncSession)
    db.execute.side_effect = [
        _result(one_or_none=_subtopic_row()),
        _result(scalar_one_or_none=_profile({"visual": 0.9, "auditory": 0.1}, ["sports_movement"])),
    ]
    prior = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]
    calls: list[dict[str, Any]] = []

    with patch.object(svc.llm_router, "stream_sse", side_effect=_stream_recorder(calls)):
        chunks = await _drain(
            svc.stream_chat_reply(
                subtopic_id=uuid4(),
                student_id=uuid4(),
                school_id=uuid4(),
                question="Why?",
                prior_messages=prior,
                db=db,
            )
        )

    assert chunks == ["data: hi\n\n"]
    assert calls == [
        {
            "task": "explain_this",
            "messages": [
                {"role": "system", "content": _EXPLAIN_SYSTEM_GOLDEN},
                *prior,
                {"role": "user", "content": "Why?"},
            ],
            "temperature": 0.6,
            "max_tokens": 400,
        }
    ]


@pytest.mark.asyncio
async def test_stream_chat_reply_when_no_prior_turns_then_system_then_user_only() -> None:
    db = AsyncMock(spec=AsyncSession)
    db.execute.side_effect = [_result(one_or_none=_subtopic_row()), _result(scalar_one_or_none=None)]
    calls: list[dict[str, Any]] = []

    with patch.object(svc.llm_router, "stream_sse", side_effect=_stream_recorder(calls)):
        await _drain(
            svc.stream_chat_reply(
                subtopic_id=uuid4(),
                student_id=uuid4(),
                school_id=uuid4(),
                question="Why?",
                prior_messages=[],
                db=db,
            )
        )

    assert [m["role"] for m in calls[0]["messages"]] == ["system", "user"]
    assert calls[0]["messages"][1]["content"] == "Why?"


# ---------------------------------------------------------------------------
# concept_guide
# ---------------------------------------------------------------------------


def _guide_subtopic() -> MagicMock:
    subtopic = MagicMock()
    subtopic.name = "Photosynthesis"
    subtopic.description = "How plants make food."
    subtopic.learning_objective = "Explain light reactions."
    subtopic.keywords = ["chlorophyll", "glucose"]
    return subtopic


@pytest.mark.asyncio
async def test_generate_concept_explanation_when_question_given_then_sends_exact_prompt_and_sampling() -> None:
    db = AsyncMock(spec=AsyncSession)
    db.execute.side_effect = [
        _result(scalar_one_or_none=_guide_subtopic()),
        _result(scalar_one_or_none=_profile({"visual": 0.9}, ["football", "gaming", "chess"])),
    ]
    reply = 'Plants are green.\n{"question": "Q?", "options": ["A) 1", "B) 2", "C) 3", "D) 4"], "correct": "B"}'

    with (
        patch.object(svc.llm_router, "complete", new=AsyncMock(return_value=reply)) as mock_complete,
        patch.object(svc, "logger") as mock_logger,
    ):
        result = await svc.generate_concept_explanation(
            student=MagicMock(id=uuid4()), subtopic_id=uuid4(), question="Why are leaves green?", db=db
        )

    mock_complete.assert_awaited_once_with(
        task="concept_guide",
        messages=[{"role": "user", "content": _GUIDE_WITH_QUESTION_GOLDEN}],
        temperature=0.6,
        max_tokens=600,
    )
    assert result["explanation"] == "Plants are green."
    assert result["subtopic_name"] == "Photosynthesis"
    assert result["check_question"] == {
        "question": "Q?",
        "options": ["A) 1", "B) 2", "C) 3", "D) 4"],
        "correct": "B",
    }
    assert [c.args[0] for c in mock_logger.info.call_args_list] == [
        "concept_guide_generation_started",
        "concept_guide_generation_completed",
    ]


@pytest.mark.asyncio
async def test_generate_concept_explanation_when_no_profile_and_no_question_then_struggling_branch_prompt() -> None:
    subtopic = _guide_subtopic()
    subtopic.description = None
    subtopic.keywords = []
    db = AsyncMock(spec=AsyncSession)
    db.execute.side_effect = [_result(scalar_one_or_none=subtopic), _result(scalar_one_or_none=None)]

    with patch.object(svc.llm_router, "complete", new=AsyncMock(return_value="Just text")) as mock_complete:
        result = await svc.generate_concept_explanation(
            student=MagicMock(id=uuid4()), subtopic_id=uuid4(), question=None, db=db
        )

    mock_complete.assert_awaited_once_with(
        task="concept_guide",
        messages=[{"role": "user", "content": _GUIDE_EMPTY_PROFILE_GOLDEN}],
        temperature=0.6,
        max_tokens=600,
    )
    assert result["check_question"] is None
    assert result["explanation"] == "Just text"


# ---------------------------------------------------------------------------
# MCQ feedback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_evaluate_mcq_answer_when_correct_then_sends_exact_prompt_and_sampling() -> None:
    with (
        patch.object(svc.llm_router, "complete", new=AsyncMock(return_value="  Great!  ")) as mock_complete,
        patch.object(svc, "logger") as mock_logger,
    ):
        result = await svc.evaluate_mcq_answer(
            subtopic_name="Photosynthesis",
            question="What do plants release?",
            options=_OPTIONS,
            correct="B",
            student_answer="b",
        )

    mock_complete.assert_awaited_once_with(
        task="concept_guide",
        messages=[{"role": "user", "content": _MCQ_CORRECT_GOLDEN}],
        temperature=0.5,
        max_tokens=150,
    )
    assert result == {"is_correct": "true", "response": "Great!"}
    mock_logger.info.assert_called_once_with(
        "concept_guide_mcq_evaluated", subtopic_name="Photosynthesis", is_correct=True
    )


@pytest.mark.asyncio
async def test_evaluate_mcq_answer_when_incorrect_then_sends_exact_prompt_with_raw_student_answer() -> None:
    with patch.object(svc.llm_router, "complete", new=AsyncMock(return_value="Think again")) as mock_complete:
        result = await svc.evaluate_mcq_answer(
            subtopic_name="Photosynthesis",
            question="What do plants release?",
            options=_OPTIONS,
            correct="B",
            student_answer="a",
        )

    mock_complete.assert_awaited_once_with(
        task="concept_guide",
        messages=[{"role": "user", "content": _MCQ_INCORRECT_GOLDEN}],
        temperature=0.5,
        max_tokens=150,
    )
    assert result == {"is_correct": "false", "response": "Think again"}


@pytest.mark.asyncio
async def test_evaluate_mcq_answer_when_answer_not_a_to_d_then_raises_before_calling_router() -> None:
    with patch.object(svc.llm_router, "complete", new=AsyncMock()) as mock_complete:
        with pytest.raises(ValueError, match="must be one of A, B, C, D"):
            await svc.evaluate_mcq_answer(
                subtopic_name="x", question="q", options=_OPTIONS, correct="A", student_answer="E"
            )

    mock_complete.assert_not_awaited()


# ---------------------------------------------------------------------------
# _parse_mcq edge cases (what production accepts and rejects today)
# ---------------------------------------------------------------------------


def test_parse_mcq_when_correct_letter_outside_a_to_d_then_still_accepted_unvalidated() -> None:
    raw = 'Text.\n{"question": "Q", "options": ["1", "2", "3", "4"], "correct": "Z"}'

    explanation, mcq = svc._parse_mcq(raw)

    assert explanation == "Text."
    assert mcq == {"question": "Q", "options": ["1", "2", "3", "4"], "correct": "Z"}


def test_parse_mcq_when_options_lack_letter_labels_then_still_accepted_unvalidated() -> None:
    raw = '{"question": "Q", "options": ["x", "y", "z", "w"], "correct": "A"}'

    explanation, mcq = svc._parse_mcq(raw)

    assert explanation == ""
    assert mcq is not None


@pytest.mark.parametrize("option_count", [0, 3, 5])
def test_parse_mcq_when_option_count_not_four_then_returns_full_text_and_none(option_count: int) -> None:
    options = ", ".join('"o"' for _ in range(option_count))
    raw = f'Text. {{"question": "Q", "options": [{options}], "correct": "A"}}'

    assert svc._parse_mcq(raw) == (raw.strip(), None)


def test_parse_mcq_when_options_not_a_list_then_returns_full_text_and_none() -> None:
    raw = 'Text. {"question": "Q", "options": "ABCD", "correct": "A"}'

    assert svc._parse_mcq(raw) == (raw.strip(), None)


def test_parse_mcq_when_unbalanced_braces_then_returns_full_text_and_none() -> None:
    raw = 'Text. {"question": "Q", "options": ["a","b","c","d"], "correct": "A"'

    assert svc._parse_mcq(raw) == (raw.strip(), None)


def test_parse_mcq_when_two_json_blocks_then_only_first_block_is_used() -> None:
    first = '{"question": "Q1", "options": ["a","b","c","d"], "correct": "A"}'
    second = '{"question": "Q2", "options": ["a","b","c","d"], "correct": "B"}'

    explanation, mcq = svc._parse_mcq(f"Intro {first} then {second}")

    assert explanation == "Intro"
    assert mcq is not None and mcq["question"] == "Q1"


def test_parse_mcq_when_text_follows_block_then_trailing_text_is_dropped() -> None:
    raw = 'Intro {"question": "Q", "options": ["a","b","c","d"], "correct": "A"} trailing words'

    explanation, mcq = svc._parse_mcq(raw)

    assert explanation == "Intro"
    assert mcq is not None
