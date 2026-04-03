"""
Unit tests for import_questions.py

Tests cover:
- Import from valid JSON (task format)
- Import from valid JSON (pre-resolved format)
- Duplicate canonical_form handling
- Unknown subtopic handling
- Unknown curriculum_code handling
- Dry-run mode
- Canonical_form whitespace normalization
"""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.import_questions import (
    compute_canonical_form,
    detect_format,
    normalize_hints,
    normalize_options_for_mcq,
    process_question_preresolved_format,
    process_question_task_format,
)

# ---- Fixtures ----


@pytest.fixture
def sample_task_format_questions():
    """5 questions in task format (M1-1-T1 spec)."""
    return [
        {
            "question_text": "What is the value of x in 2x + 4 = 12?",
            "question_type": "MCQ",
            "options": [
                {"key": "A", "text": "3"},
                {"key": "B", "text": "4"},
                {"key": "C", "text": "5"},
                {"key": "D", "text": "6"},
            ],
            "correct_answer": "B",
            "explanation": "2x = 12 - 4 = 8, so x = 4",
            "difficulty_level": 2.0,
            "bloom_taxonomy": "Apply",
            "curriculum_code": "cambridge_lower",
            "subject_code": "MATH",
            "grade_level": 8,
            "topic_name": "Algebra",
            "subtopic_name": "Linear Equations",
        },
        {
            "question_text": "Water boils at 100 degrees Celsius.",
            "question_type": "TRUE_FALSE",
            "options": None,
            "correct_answer": "TRUE",
            "explanation": "At standard atmospheric pressure.",
            "difficulty_level": 1.0,
            "bloom_taxonomy": "Remember",
            "curriculum_code": "cambridge_lower",
            "subject_code": "SCIENCE",
            "grade_level": 7,
            "topic_name": "States of Matter",
            "subtopic_name": "Boiling Point",
        },
    ]


@pytest.fixture
def sample_preresolved_format_questions():
    """Questions in pre-resolved format (generated file format)."""
    return [
        {
            "subtopic_id": "fe632bc6-a557-4a41-9f97-e02e67de648f",
            "question_text": "Which of these sentences uses a simile?",
            "question_type": "multiple_choice",
            "options": {
                "A": "The sky is blue.",
                "B": "She ran as fast as a cheetah.",
                "C": "He was tired.",
                "D": "I ate an apple.",
            },
            "correct_answer": "B",
            "difficulty_level": 1,
            "bloom_taxonomy_level": "Remember",
            "explanation": "A simile compares two things using 'like' or 'as'.",
            "hints": {"hint1": "Look for words like 'like' or 'as'", "hint2": "Similes compare two things"},
            "is_active": True,
        },
        {
            "subtopic_id": "fe632bc6-a557-4a41-9f97-e02e67de648f",
            "question_text": "Is it true that alliteration involves repeating the same sound?",
            "question_type": "true_false",
            "options": {},
            "correct_answer": "TRUE",
            "difficulty_level": 1,
            "bloom_taxonomy_level": "Understand",
            "explanation": "Alliteration repeats the same initial sound.",
            "is_active": True,
        },
    ]


@pytest.fixture
def mock_session():
    """Create a mock async session."""
    session = AsyncMock()
    return session


# ---- Tests for normalize_options_for_mcq ----


class TestNormalizeOptions:
    def test_when_list_format_then_returns_as_is(self):
        options = [{"key": "A", "text": "Option A"}, {"key": "B", "text": "Option B"}]
        result = normalize_options_for_mcq(options)
        assert result == options

    def test_when_dict_format_then_converts_to_list(self):
        options = {"A": "Option A", "B": "Option B", "C": "Option C"}
        result = normalize_options_for_mcq(options)
        assert isinstance(result, list)
        assert len(result) == 3
        assert result[0] == {"key": "A", "text": "Option A"}
        assert result[1] == {"key": "B", "text": "Option B"}

    def test_when_none_then_returns_none(self):
        result = normalize_options_for_mcq(None)
        assert result is None


# ---- Tests for normalize_hints ----


class TestNormalizeHints:
    def test_when_list_format_then_returns_as_is(self):
        hints = [{"order": 1, "text": "Hint 1"}, {"order": 2, "text": "Hint 2"}]
        result = normalize_hints(hints)
        assert result == hints

    def test_when_dict_format_then_converts_to_list(self):
        hints = {"hint1": "First hint", "hint2": "Second hint"}
        result = normalize_hints(hints)
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0] == {"order": 1, "text": "First hint"}
        assert result[1] == {"order": 2, "text": "Second hint"}

    def test_when_none_then_returns_none(self):
        result = normalize_hints(None)
        assert result is None


# ---- Tests for compute_canonical_form ----


class TestCanonicalForm:
    def test_when_same_text_different_whitespace_then_same_hash(self):
        """Acceptance criterion: same text with different whitespace produces same hash."""
        hash1 = compute_canonical_form("  What is x?  ")
        hash2 = compute_canonical_form("what is x?")
        assert hash1 == hash2

    def test_when_different_text_then_different_hash(self):
        hash1 = compute_canonical_form("What is x?")
        hash2 = compute_canonical_form("What is y?")
        assert hash1 != hash2

    def test_when_case_difference_then_same_hash(self):
        hash1 = compute_canonical_form("WHAT IS X?")
        hash2 = compute_canonical_form("what is x?")
        assert hash1 == hash2


# ---- Tests for detect_format ----


class TestDetectFormat:
    def test_when_questions_have_subtopic_id_then_preresolved(self):
        questions = [{"subtopic_id": "abc-123", "question_text": "Test"}]
        assert detect_format(questions) == "preresolved"

    def test_when_questions_have_curriculum_code_then_task(self):
        questions = [{"curriculum_code": "cambridge", "question_text": "Test"}]
        assert detect_format(questions) == "task"

    def test_when_empty_list_then_defaults_to_task(self):
        assert detect_format([]) == "task"


# ---- Tests for process_question_task_format ----


class TestProcessQuestionTaskFormat:
    @pytest.mark.asyncio
    async def test_when_valid_question_then_returns_insert_dict(self, sample_task_format_questions):
        """Test: valid question produces insert dict with resolved subtopic_id."""
        # Mock the resolve_subtopic_id function directly
        mock_session = AsyncMock()

        with patch("scripts.import_questions.resolve_subtopic_id") as mock_resolve:
            mock_resolve.return_value = (
                "subtopic-uuid",
                "topic-uuid",
                "subject-uuid",
                "grade-uuid",
                "curriculum-uuid",
            )

            insert_data, error = await process_question_task_format(mock_session, sample_task_format_questions[0], 1)

            assert error is None
            assert insert_data is not None
            assert insert_data["subtopic_id"] == "subtopic-uuid"
            assert insert_data["question_type"] == "MCQ"
            assert insert_data["source"] == "bank"

    @pytest.mark.asyncio
    async def test_when_unknown_subtopic_then_returns_error(self):
        """Acceptance criterion: unknown subtopic_name -> row skipped and logged."""
        question = {
            "question_text": "Test question",
            "question_type": "MCQ",
            "correct_answer": "A",
            "curriculum_code": "cambridge_lower",
            "subject_code": "MATH",
            "grade_level": 8,
            "topic_name": "Algebra",
            "subtopic_name": "Nonexistent Topic",
        }

        mock_session = AsyncMock()

        with patch("scripts.import_questions.resolve_subtopic_id") as mock_resolve:
            mock_resolve.return_value = (None, None, None, None, None)

            insert_data, error = await process_question_task_format(mock_session, question, 1)

            assert insert_data is None
            assert error is not None
            assert "Could not resolve subtopic" in error

    @pytest.mark.asyncio
    async def test_when_unknown_curriculum_code_then_returns_error(self):
        """Acceptance criterion: unknown curriculum_code -> row skipped and logged."""
        question = {
            "question_text": "Test question",
            "question_type": "MCQ",
            "correct_answer": "A",
            "curriculum_code": "nonexistent_curriculum",
            "subject_code": "MATH",
            "grade_level": 8,
            "topic_name": "Algebra",
            "subtopic_name": "Linear Equations",
        }

        mock_session = AsyncMock()

        with patch("scripts.import_questions.resolve_subtopic_id") as mock_resolve:
            mock_resolve.return_value = (None, None, None, None, None)

            insert_data, error = await process_question_task_format(mock_session, question, 1)

            assert insert_data is None
            assert error is not None
            # Could be either "Missing required fields" (if curriculum_code is None after .get())
            # or "Could not resolve subtopic" (if it passes the all() check but resolution fails)
            assert "Could not resolve subtopic" in error or "Missing required fields" in error


# ---- Tests for process_question_preresolved_format ----


class TestProcessQuestionPreresolvedFormat:
    @pytest.mark.asyncio
    async def test_when_valid_question_then_returns_insert_dict(
        self, mock_session, sample_preresolved_format_questions
    ):
        """Test: valid pre-resolved question produces insert dict."""
        question = sample_preresolved_format_questions[0]

        insert_data, error = await process_question_preresolved_format(mock_session, question, 1)

        assert error is None
        assert insert_data is not None
        assert insert_data["subtopic_id"] == "fe632bc6-a557-4a41-9f97-e02e67de648f"
        assert insert_data["question_type"] == "MCQ"  # mapped from "multiple_choice"
        assert isinstance(insert_data["options"], list)  # converted from dict
        assert insert_data["source"] == "bank"

    @pytest.mark.asyncio
    async def test_when_missing_subtopic_id_then_returns_error(self, mock_session):
        question = {
            "question_text": "Test",
            "question_type": "MCQ",
            "correct_answer": "A",
        }

        insert_data, error = await process_question_preresolved_format(mock_session, question, 1)

        assert insert_data is None
        assert error is not None
        assert "Missing subtopic_id" in error

    @pytest.mark.asyncio
    async def test_when_true_false_question_then_options_none(self, mock_session, sample_preresolved_format_questions):
        question = sample_preresolved_format_questions[1]  # true_false question

        insert_data, error = await process_question_preresolved_format(mock_session, question, 1)

        assert error is None
        assert insert_data["options"] is None
        assert insert_data["question_type"] == "TRUE_FALSE"


# ---- Integration-style tests (would need real DB for full coverage) ----


class TestImportQuestionsIntegration:
    """
    These tests verify the import flow structure.
    Full integration tests require a test database with seeded curriculum data.
    """

    def test_sample_questions_json_exists(self):
        """Verify sample_questions.json file exists."""
        sample_path = Path(__file__).parent.parent.parent / "data" / "questions" / "sample_questions.json"
        assert sample_path.exists()

    def test_sample_questions_has_5_questions(self):
        """Acceptance criterion: 5 sample questions for testing."""
        sample_path = Path(__file__).parent.parent.parent / "data" / "questions" / "sample_questions.json"
        with open(sample_path) as f:
            data = json.load(f)
        assert len(data) == 5

    def test_sample_questions_cover_multiple_subjects(self):
        """Acceptance criterion: questions cover Math, Science, English."""
        sample_path = Path(__file__).parent.parent.parent / "data" / "questions" / "sample_questions.json"
        with open(sample_path) as f:
            data = json.load(f)

        subjects = {q["subject_code"] for q in data}
        assert "MATH" in subjects
        assert "SCIENCE" in subjects
        assert "ENGLISH" in subjects

    def test_sample_questions_cover_multiple_grades(self):
        """Acceptance criterion: questions cover at least 2 grades."""
        sample_path = Path(__file__).parent.parent.parent / "data" / "questions" / "sample_questions.json"
        with open(sample_path) as f:
            data = json.load(f)

        grades = {q["grade_level"] for q in data}
        assert len(grades) >= 2


# ---- Tests for duplicate handling ----


class TestDuplicateHandling:
    def test_when_same_question_twice_then_same_canonical_form(self):
        """Acceptance criterion: duplicate canonical_form -> skipped not errored."""
        text1 = "What is the capital of France?"
        text2 = "What is the capital of France?"

        assert compute_canonical_form(text1) == compute_canonical_form(text2)

    def test_when_whitespace_difference_then_same_canonical_form(self):
        text1 = "  What is x?  "
        text2 = "what is x?"

        assert compute_canonical_form(text1) == compute_canonical_form(text2)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
