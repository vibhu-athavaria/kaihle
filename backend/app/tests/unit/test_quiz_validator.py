"""Unit tests for quiz_validator — M3-1-T3."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.services.quiz_validator import (
    MAX_QUESTION_WORDS,
    MIN_KEYWORD_MATCHES,
    QuizValidator,
    _extract_keywords,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_subtopic() -> MagicMock:
    """Mock Subtopic with name and learning_objective for keyword tests."""
    mock = MagicMock()
    mock.id = uuid4()
    mock.name = "Photosynthesis"
    mock.learning_objective = "Students understand how plants convert light into energy"
    return mock


@pytest.fixture
def mock_db_session(sample_subtopic) -> AsyncMock:
    """Async mock DB session returning the sample subtopic by default."""
    session = AsyncMock()

    async def fake_execute(stmt):
        result = MagicMock()
        result.scalar_one_or_none.return_value = sample_subtopic
        return result

    session.execute = fake_execute
    return session


@pytest.fixture
def mock_db_session_no_subtopic() -> AsyncMock:
    """Async mock DB session returning None (subtopic not found)."""
    session = AsyncMock()

    async def fake_execute(stmt):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        return result

    session.execute = fake_execute
    return session


# ---------------------------------------------------------------------------
# Test: _extract_keywords helper
# ---------------------------------------------------------------------------


class TestExtractKeywords:
    def test_extract_keywords_when_normal_text_then_removes_stop_words(self):
        result = _extract_keywords("What is the process of photosynthesis in plants")
        assert "photosynthesis" in result
        assert "plants" in result
        assert "process" in result
        # stop-words removed
        assert "the" not in result
        assert "is" not in result
        assert "of" not in result

    def test_extract_keywords_when_short_words_then_excluded(self):
        result = _extract_keywords("a an of")
        assert result == set()

    def test_extract_keywords_when_mixed_case_then_lowercased(self):
        result = _extract_keywords("Photosynthesis CHLOROPHYLL Sunlight")
        assert "photosynthesis" in result
        assert "chlorophyll" in result
        assert "sunlight" in result


# ---------------------------------------------------------------------------
# Test: QuizValidator.validate_question — keyword relevance gate
# ---------------------------------------------------------------------------


class TestValidateQuestion:
    @pytest.mark.asyncio
    async def test_validate_question_when_all_checks_pass_then_returns_valid(self, mock_db_session, sample_subtopic):
        """Question mentioning subtopic keyword passes all gates."""
        validator = QuizValidator(mock_db_session)
        is_valid, reason = await validator.validate_question(
            question_text="How does photosynthesis convert sunlight into energy?",
            subtopic_id=sample_subtopic.id,
            grade_level=8,
        )
        assert is_valid is True
        assert reason == ""

    @pytest.mark.asyncio
    async def test_validate_question_when_no_subtopic_keywords_in_text_then_fails(
        self, mock_db_session, sample_subtopic
    ):
        """Question with no keywords from subtopic name/objective is rejected."""
        validator = QuizValidator(mock_db_session)
        is_valid, reason = await validator.validate_question(
            question_text="What is the capital city of France and its population?",
            subtopic_id=sample_subtopic.id,
            grade_level=8,
        )
        assert is_valid is False
        assert "keywords" in reason.lower()

    @pytest.mark.asyncio
    async def test_validate_question_when_question_too_long_then_fails(self, mock_db_session, sample_subtopic):
        """Question exceeding MAX_QUESTION_WORDS is rejected."""
        # Build a question that mentions the subtopic but is too long
        long_question = "photosynthesis " + ("extra word " * 130)
        word_count = len(long_question.split())
        assert word_count > MAX_QUESTION_WORDS

        validator = QuizValidator(mock_db_session)
        is_valid, reason = await validator.validate_question(
            question_text=long_question,
            subtopic_id=sample_subtopic.id,
            grade_level=8,
        )
        assert is_valid is False
        assert "too long" in reason.lower()
        assert str(MAX_QUESTION_WORDS) in reason

    @pytest.mark.asyncio
    async def test_validate_question_when_answer_not_in_options_then_fails(self, mock_db_session, sample_subtopic):
        """Question where correct_answer key not in options is rejected."""
        validator = QuizValidator(mock_db_session)
        question = {
            "question_text": "What does photosynthesis produce?",
            "options": [{"key": "A", "text": "Glucose"}, {"key": "B", "text": "Water"}],
            "correct_answer": "C",  # Not in options
        }
        is_valid, reason = await validator.validate_question(
            question_text=str(question["question_text"]),
            subtopic_id=sample_subtopic.id,
            grade_level=8,
            question=question,
        )
        assert is_valid is False
        assert "correct_answer" in reason.lower() or "not in options" in reason.lower()

    @pytest.mark.asyncio
    async def test_validate_question_when_fewer_than_two_options_then_fails(self, mock_db_session, sample_subtopic):
        """Question with fewer than 2 options fails structural gate."""
        validator = QuizValidator(mock_db_session)
        question = {
            "question_text": "What does photosynthesis produce?",
            "options": [{"key": "A", "text": "Glucose"}],  # Only 1 option
            "correct_answer": "A",
        }
        is_valid, reason = await validator.validate_question(
            question_text=str(question["question_text"]),
            subtopic_id=sample_subtopic.id,
            grade_level=8,
            question=question,
        )
        assert is_valid is False
        assert "2" in reason

    @pytest.mark.asyncio
    async def test_validate_question_when_subtopic_not_found_then_passes_through(self, mock_db_session_no_subtopic):
        """If subtopic doesn't exist, pass through gracefully."""
        validator = QuizValidator(mock_db_session_no_subtopic)
        is_valid, reason = await validator.validate_question(
            question_text="Any question text here",
            subtopic_id=uuid4(),
            grade_level=8,
        )
        assert is_valid is True
        assert reason == ""


# ---------------------------------------------------------------------------
# Test: QuizValidator.validate_batch
# ---------------------------------------------------------------------------


class TestValidateBatch:
    @pytest.mark.asyncio
    async def test_validate_batch_when_all_valid_then_all_returned(self, mock_db_session, sample_subtopic):
        """When all questions mention topic keywords, all are returned."""
        questions = [
            {
                "question_text": f"How does photosynthesis work in step {i}?",
                "options": [{"key": "A", "text": "Yes"}, {"key": "B", "text": "No"}],
                "correct_answer": "A",
            }
            for i in range(3)
        ]
        validator = QuizValidator(mock_db_session)
        result = await validator.validate_batch(
            questions=questions,
            subtopic_id=sample_subtopic.id,
            grade_level=8,
        )
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_validate_batch_when_some_invalid_then_only_valid_returned(self, mock_db_session, sample_subtopic):
        """Off-topic questions are removed from the batch."""
        questions = [
            {
                "question_text": "What does photosynthesis produce in plants?",
                "options": [{"key": "A", "text": "Glucose"}, {"key": "B", "text": "CO2"}],
                "correct_answer": "A",
            },
            {
                "question_text": "What is the capital city of France and its river?",
                "options": [{"key": "A", "text": "Paris"}, {"key": "B", "text": "Lyon"}],
                "correct_answer": "A",
            },
        ]
        validator = QuizValidator(mock_db_session)
        result = await validator.validate_batch(
            questions=questions,
            subtopic_id=sample_subtopic.id,
            grade_level=8,
        )
        assert len(result) == 1
        assert "photosynthesis" in result[0]["question_text"].lower()

    @pytest.mark.asyncio
    async def test_validate_batch_when_none_valid_then_returns_empty_list(self, mock_db_session, sample_subtopic):
        """When all questions fail validation, empty list is returned."""
        questions = [
            {
                "question_text": "What is the weather forecast for tomorrow?",
                "options": [{"key": "A", "text": "Sunny"}, {"key": "B", "text": "Rainy"}],
                "correct_answer": "A",
            },
        ]
        validator = QuizValidator(mock_db_session)
        result = await validator.validate_batch(
            questions=questions,
            subtopic_id=sample_subtopic.id,
            grade_level=8,
        )
        assert result == []


# ---------------------------------------------------------------------------
# Test: Constants
# ---------------------------------------------------------------------------


class TestConstants:
    def test_max_question_words_value(self):
        assert MAX_QUESTION_WORDS == 120

    def test_min_keyword_matches_value(self):
        assert MIN_KEYWORD_MATCHES == 1
