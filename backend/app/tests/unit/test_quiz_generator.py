"""Unit tests for quiz_generator — M3-1-T2 + M3-1-T3 integration."""

from __future__ import annotations

import json as json_lib
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch
from uuid import uuid4

import pytest

from app.ai.quiz_generator import (
    GeneratedQuiz,
    QuestionType,
    QuizGenerationError,
    QuizQuestion,
    _build_prompt,
    _extract_json,
    _mastery_to_difficulty_label,
    _parse_questions,
    generate_quiz,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_subtopic() -> MagicMock:
    """Mock Subtopic with a 768-dim embedding (via PropertyMock)."""
    mock = MagicMock()
    mock.id = uuid4()
    mock.name = "Photosynthesis"
    mock.learning_objective = "Explain the process of photosynthesis"
    mock.subject_name = "Biology"
    mock.curriculum_code = "CAMBRIDGE"
    mock.subject_code = "BIOLOGY"
    # PropertyMock ensures .embedding returns a real list, not a MagicMock
    type(mock).embedding = PropertyMock(return_value=[0.1] * 768)
    return mock


@pytest.fixture
def sample_student_id() -> MagicMock:
    return uuid4()


@pytest.fixture
def mock_db_session(sample_subtopic: MagicMock) -> AsyncMock:
    """Async mock DB session that returns fixtures for all queries."""
    session = AsyncMock()
    mock_profile = MagicMock()
    mock_profile.interests = ["sports", "gaming"]
    mock_content = MagicMock()
    mock_content.approved_explanation = "Approved explanation text."

    async def mock_get(model, ident):
        model_name = getattr(model, "__name__", str(model))
        if model_name == "SubtopicContent":
            return mock_content
        if model_name == "StudentLearningProfile":
            return mock_profile
        return None

    async def mock_execute(stmt):
        result = MagicMock()
        result.scalar_one_or_none.return_value = sample_subtopic
        return result

    session.get = mock_get
    session.execute = mock_execute
    return session


@pytest.fixture
def sample_questions() -> list[dict]:
    return [
        {
            "question_text": "What is the primary product of photosynthesis?",
            "type": "MCQ",
            "options": [
                {"key": "A", "text": "Carbon dioxide"},
                {"key": "B", "text": "Oxygen"},
                {"key": "C", "text": "Nitrogen"},
                {"key": "D", "text": "Hydrogen"},
            ],
            "correct_answer": "B",
            "explanation": "Oxygen is released as a byproduct.",
        },
        {
            "question_text": "Which organelle is responsible for photosynthesis?",
            "type": "MCQ",
            "options": [
                {"key": "A", "text": "Mitochondria"},
                {"key": "B", "text": "Chloroplast"},
                {"key": "C", "text": "Nucleus"},
                {"key": "D", "text": "Ribosome"},
            ],
            "correct_answer": "B",
            "explanation": "Chloroplasts contain chlorophyll.",
        },
        {
            "question_text": "What is required for photosynthesis?",
            "type": "MCQ",
            "options": [
                {"key": "A", "text": "Only oxygen"},
                {"key": "B", "text": "Only water"},
                {"key": "C", "text": "Sunlight, water, and carbon dioxide"},
                {"key": "D", "text": "Only carbon dioxide"},
            ],
            "correct_answer": "C",
            "explanation": "Photosynthesis requires sunlight, water, and CO2.",
        },
        {
            "question_text": "What happens to glucose produced in photosynthesis?",
            "type": "MCQ",
            "options": [
                {"key": "A", "text": "It is exhaled"},
                {"key": "B", "text": "It is stored or used for energy"},
                {"key": "C", "text": "It evaporates"},
                {"key": "D", "text": "It becomes oxygen"},
            ],
            "correct_answer": "B",
            "explanation": "Glucose is used for energy or stored as starch.",
        },
        {
            "question_text": "What role does chlorophyll play in photosynthesis?",
            "type": "MCQ",
            "options": [
                {"key": "A", "text": "Absorbs light energy"},
                {"key": "B", "text": "Produces water"},
                {"key": "C", "text": "Creates carbon dioxide"},
                {"key": "D", "text": "Stores glucose"},
            ],
            "correct_answer": "A",
            "explanation": "Chlorophyll absorbs sunlight to drive photosynthesis.",
        },
    ]


# ---------------------------------------------------------------------------
# Test: _mastery_to_difficulty_label
# ---------------------------------------------------------------------------


class TestMasteryToDifficultyLabel:
    def test_low_mastery_foundation(self):
        assert _mastery_to_difficulty_label(0.2) == ("foundational — focus on basic recall and understanding")

    def test_low_mastery_boundary(self):
        assert _mastery_to_difficulty_label(0.39) == ("foundational — focus on basic recall and understanding")

    def test_mid_mastery_developing(self):
        assert _mastery_to_difficulty_label(0.5) == ("developing — include application and simple problem solving")

    def test_mid_mastery_upper_boundary(self):
        assert _mastery_to_difficulty_label(0.69) == ("developing — include application and simple problem solving")

    def test_high_mastery_advanced(self):
        assert _mastery_to_difficulty_label(0.8) == ("advanced — focus on analysis, evaluation, and novel problems")

    def test_high_mastery_boundary(self):
        assert _mastery_to_difficulty_label(0.7) == ("advanced — focus on analysis, evaluation, and novel problems")


# ---------------------------------------------------------------------------
# Test: _extract_json
# ---------------------------------------------------------------------------


class TestExtractJson:
    def test_direct_json(self):
        data = {"questions": [{"type": "MCQ", "options": [{"key": "A", "text": "x"}] * 4}]}
        result = _extract_json(json_lib.dumps(data))
        assert result == data

    def test_markdown_fenced_json(self):
        data = {"questions": []}
        result = _extract_json('```json\n{"questions": []}\n```')
        assert result == data

    def test_braces_extraction(self):
        data = {"questions": [], "count": 42}
        result = _extract_json('Some preamble {"questions": [], "count": 42} more text')
        assert result == data

    def test_invalid_json_raises(self):
        with pytest.raises(QuizGenerationError, match="Could not extract valid JSON"):
            _extract_json("not json at all {{{{[[[")


# ---------------------------------------------------------------------------
# Test: _parse_questions
# ---------------------------------------------------------------------------


class TestParseQuestions:
    def test_valid_questions(self, sample_questions):
        questions = _parse_questions({"questions": sample_questions})
        assert len(questions) == 5
        assert all(q.type == QuestionType.MCQ for q in questions)
        assert all(len(q.options) == 4 for q in questions)

    def test_wrong_count_raises(self, sample_questions):
        with pytest.raises(QuizGenerationError, match="Expected 5 questions"):
            _parse_questions({"questions": sample_questions[:3]})

    def test_non_mcq_raises(self, sample_questions):
        sample_questions[0]["type"] = "SHORT_ANSWER"
        with pytest.raises(QuizGenerationError, match="Expected all 5 MCQ"):
            _parse_questions({"questions": sample_questions})

    def test_wrong_option_count_raises(self, sample_questions):
        sample_questions[0]["options"] = [{"key": "A", "text": "x"}]
        with pytest.raises(QuizGenerationError, match="expected 4"):
            _parse_questions({"questions": sample_questions})


# ---------------------------------------------------------------------------
# Test: QuizQuestion dataclass
# ---------------------------------------------------------------------------


class TestQuizQuestion:
    def test_to_dict(self):
        q = QuizQuestion(
            question_text="What is 2+2?",
            type=QuestionType.MCQ,
            options=[
                {"key": "A", "text": "3"},
                {"key": "B", "text": "4"},
                {"key": "C", "text": "5"},
                {"key": "D", "text": "6"},
            ],
            correct_answer="B",
            explanation="2+2=4",
        )
        d = q.to_dict()
        assert d["question_text"] == "What is 2+2?"
        assert d["type"] == "MCQ"
        assert d["correct_answer"] == "B"

    def test_from_dict(self):
        d = {
            "question_text": "What is 2+2?",
            "type": "MCQ",
            "options": [
                {"key": "A", "text": "3"},
                {"key": "B", "text": "4"},
                {"key": "C", "text": "5"},
                {"key": "D", "text": "6"},
            ],
            "correct_answer": "B",
            "explanation": "2+2=4",
        }
        q = QuizQuestion.from_dict(d)
        assert q.question_text == "What is 2+2?"
        assert q.type == QuestionType.MCQ


# ---------------------------------------------------------------------------
# Test: GeneratedQuiz dataclass
# ---------------------------------------------------------------------------


class TestGeneratedQuiz:
    def test_to_dict(self, sample_questions):
        subtopic_id = uuid4()
        quiz = GeneratedQuiz(
            subtopic_id=subtopic_id,
            questions=[QuizQuestion.from_dict(q) for q in sample_questions[:5]],
            interests_used=["sports", "gaming"],
        )
        d = quiz.to_dict()
        assert d["subtopic_id"] == str(subtopic_id)
        assert len(d["questions"]) == 5
        assert d["interests_used"] == ["sports", "gaming"]
        assert "generated_at" in d

    def test_default_generated_at(self):
        quiz = GeneratedQuiz(subtopic_id=uuid4())
        assert quiz.generated_at is not None
        from datetime import datetime

        assert isinstance(quiz.generated_at, datetime)


# ---------------------------------------------------------------------------
# Test: _build_prompt
# ---------------------------------------------------------------------------


class TestBuildPrompt:
    def test_prompt_contains_key_elements(self):
        prompt = _build_prompt(
            curriculum_code="CAMBRIDGE",
            subject_name="Biology",
            subtopic_name="Photosynthesis",
            mastery_pct=65,
            difficulty_label="developing — include application",
            learning_objectives="Explain the process of photosynthesis",
            subtopic_context="Photosynthesis occurs in chloroplasts...",
            top_2_interests=["sports", "gaming"],
        )
        assert "CAMBRIDGE" in prompt
        assert "Biology" in prompt
        assert "Photosynthesis" in prompt
        assert "65" in prompt
        assert "developing" in prompt
        assert "sports, gaming" in prompt

    def test_prompt_no_interests(self):
        prompt = _build_prompt(
            curriculum_code="CAMBRIDGE",
            subject_name="Biology",
            subtopic_name="Photosynthesis",
            mastery_pct=65,
            difficulty_label="developing",
            learning_objectives="Explain photosynthesis",
            subtopic_context="Photosynthesis occurs...",
            top_2_interests=[],
        )
        assert "Personalisation" not in prompt or "sports" not in prompt


# ---------------------------------------------------------------------------
# Test: generate_quiz (with M3-1-T3 validation integration)
# ---------------------------------------------------------------------------


class TestGenerateQuiz:
    @pytest.mark.asyncio
    async def test_generate_quiz_success(self, sample_subtopic, sample_student_id, mock_db_session, sample_questions):
        """Full flow: context loaded, interests filtered, LLM called, validated."""
        with (
            patch(
                "app.ai.quiz_generator.complete",
                new_callable=AsyncMock,
                return_value=json_lib.dumps({"questions": sample_questions}),
            ),
            patch(
                "app.ai.quiz_generator.get_compatible_interests",
                return_value=["sports", "gaming"],
            ),
        ):
            quiz = await generate_quiz(
                subtopic=sample_subtopic,
                student_mastery=0.65,
                student_id=sample_student_id,
                db=mock_db_session,
            )

            assert len(quiz.questions) == 5
            assert quiz.interests_used == ["sports", "gaming"]

    @pytest.mark.asyncio
    async def test_generate_quiz_llm_failure_then_success(
        self, sample_subtopic, sample_student_id, mock_db_session, sample_questions
    ):
        """LLM fails first attempt, succeeds on retry."""
        call_count = 0

        async def fake_complete(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("LLM timeout")
            return json_lib.dumps({"questions": sample_questions})

        with patch("app.ai.quiz_generator.complete", new_callable=AsyncMock, side_effect=fake_complete):
            quiz = await generate_quiz(
                subtopic=sample_subtopic,
                student_mastery=0.5,
                student_id=sample_student_id,
                db=mock_db_session,
            )
            assert call_count == 2
            assert len(quiz.questions) == 5

    @pytest.mark.asyncio
    async def test_generate_quiz_llm_always_fails(self, sample_subtopic, sample_student_id, mock_db_session):
        """Both LLM attempts fail → QuizGenerationError."""
        with patch(
            "app.ai.quiz_generator.complete",
            new_callable=AsyncMock,
            side_effect=Exception("Network error"),
        ):
            with pytest.raises(QuizGenerationError, match="failed after 2 attempts"):
                await generate_quiz(
                    subtopic=sample_subtopic,
                    student_mastery=0.5,
                    student_id=sample_student_id,
                    db=mock_db_session,
                )

    @pytest.mark.asyncio
    async def test_generate_quiz_invalid_json_raises(self, sample_subtopic, sample_student_id, mock_db_session):
        """LLM returns non-JSON → QuizGenerationError."""
        with patch(
            "app.ai.quiz_generator.complete",
            new_callable=AsyncMock,
            return_value="This is not JSON!",
        ):
            with pytest.raises(QuizGenerationError, match="Could not extract valid JSON"):
                await generate_quiz(
                    subtopic=sample_subtopic,
                    student_mastery=0.5,
                    student_id=sample_student_id,
                    db=mock_db_session,
                )

    @pytest.mark.asyncio
    async def test_generate_quiz_no_profile_no_crash(
        self, sample_subtopic, sample_student_id, mock_db_session, sample_questions
    ):
        """No StudentLearningProfile → empty interests, quiz still generates."""

        # Override session.get to return None for profile
        async def get_without_profile(model, ident):
            model_name = getattr(model, "__name__", str(model))
            if model_name == "SubtopicContent":
                content = MagicMock()
                content.approved_explanation = "Approved explanation text."
                return content
            return None

        mock_db_session.get = get_without_profile

        with patch(
            "app.ai.quiz_generator.complete",
            new_callable=AsyncMock,
            return_value=json_lib.dumps({"questions": sample_questions}),
        ):
            quiz = await generate_quiz(
                subtopic=sample_subtopic,
                student_mastery=0.5,
                student_id=sample_student_id,
                db=mock_db_session,
            )
            assert quiz.interests_used == []

    @pytest.mark.asyncio
    async def test_generate_quiz_low_mastery_foundation_prompt(
        self, sample_subtopic, sample_student_id, mock_db_session, sample_questions
    ):
        """Low mastery (0.25) → foundational difficulty label in prompt."""
        captured_prompt = None

        async def capture_complete(*args, **kwargs):
            nonlocal captured_prompt
            messages = kwargs.get("messages", [])
            captured_prompt = messages[0].get("content", "") if messages else ""
            return json_lib.dumps({"questions": sample_questions})

        with patch("app.ai.quiz_generator.complete", new_callable=AsyncMock, side_effect=capture_complete):
            await generate_quiz(
                subtopic=sample_subtopic,
                student_mastery=0.25,
                student_id=sample_student_id,
                db=mock_db_session,
            )

        assert "foundational" in captured_prompt
