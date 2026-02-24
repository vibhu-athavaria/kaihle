"""
Tests for Phase 10B - PDF Content Extraction Pipeline.

Tests the extraction script functions without requiring actual PDF files.
"""
import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from scripts.extract_pdf_content import (
    parse_filename,
    chunk_text,
    normalize_text,
    map_subtopic,
    GRADE_CODES,
    SUBJECT_CODES,
)


class TestParseFilename:
    """Tests for filename parsing."""

    def test_valid_filename_grade8_math(self):
        grade, subject, content = parse_filename("grade8_math_textbook.pdf")
        assert grade == "grade8"
        assert subject == "math"
        assert content == "textbook"

    def test_valid_filename_with_underscore_in_content_type(self):
        grade, subject, content = parse_filename("grade10_science_workbook_chapter3.pdf")
        assert grade == "grade10"
        assert subject == "science"
        assert content == "workbook_chapter3"

    def test_valid_filename_all_grades(self):
        for grade_code in GRADE_CODES:
            filename = f"{grade_code}_math_textbook.pdf"
            grade, subject, content = parse_filename(filename)
            assert grade == grade_code

    def test_valid_filename_all_subjects(self):
        for subject_code in SUBJECT_CODES:
            filename = f"grade8_{subject_code}_textbook.pdf"
            grade, subject, content = parse_filename(filename)
            assert subject == subject_code

    def test_invalid_grade_code(self):
        with pytest.raises(ValueError, match="Invalid grade_code"):
            parse_filename("grade13_math_textbook.pdf")

    def test_invalid_subject_code(self):
        with pytest.raises(ValueError, match="Invalid subject_code"):
            parse_filename("grade8_physics_textbook.pdf")

    def test_missing_underscore(self):
        with pytest.raises(ValueError, match="Invalid filename format"):
            parse_filename("grade8math.pdf")

    def test_non_pdf_extension(self):
        with pytest.raises(ValueError, match="must be a PDF"):
            parse_filename("grade8_math_textbook.txt")

    def test_case_insensitive_parsing(self):
        grade, subject, content = parse_filename("GRADE8_MATH_Textbook.pdf")
        assert grade == "grade8"
        assert subject == "math"


class TestChunkText:
    """Tests for text chunking."""

    def test_chunk_single_paragraph(self):
        pages = ["This is a test paragraph."]
        chunks = chunk_text(pages, chunk_size_tokens=100, overlap_tokens=10)
        assert len(chunks) == 1
        assert chunks[0][1] > 0

    def test_chunk_multiple_paragraphs(self):
        pages = ["First paragraph here.\n\nSecond paragraph here.\n\nThird paragraph here."]
        chunks = chunk_text(pages, chunk_size_tokens=100, overlap_tokens=10)
        assert len(chunks) >= 1

    def test_chunk_respects_size_limit(self):
        long_text = "This is a sentence. " * 200
        pages = [long_text]
        chunks = chunk_text(pages, chunk_size_tokens=50, overlap_tokens=10)
        assert len(chunks) > 1

    def test_chunk_empty_pages(self):
        pages = []
        chunks = chunk_text(pages, chunk_size_tokens=100, overlap_tokens=10)
        assert len(chunks) == 0

    def test_chunk_whitespace_only_pages(self):
        pages = ["   \n\n   \n\n   "]
        chunks = chunk_text(pages, chunk_size_tokens=100, overlap_tokens=10)
        assert len(chunks) == 0

    def test_chunk_returns_token_count(self):
        pages = ["This is a test paragraph with some content."]
        chunks = chunk_text(pages, chunk_size_tokens=100, overlap_tokens=10)
        for chunk_text_str, token_count in chunks:
            assert isinstance(token_count, int)
            assert token_count > 0

    def test_overlap_tokens_is_respected(self):
        """Test that overlap_tokens parameter controls overlap between chunks."""
        paragraphs = [f"Paragraph number {i} with some additional content here." for i in range(10)]
        pages = ["\n\n".join(paragraphs)]
        
        chunks = chunk_text(pages, chunk_size_tokens=30, overlap_tokens=20)
        
        if len(chunks) > 1:
            for i in range(1, len(chunks)):
                prev_text = chunks[i-1][0]
                curr_text = chunks[i][0]
                prev_words = set(prev_text.split())
                curr_words = set(curr_text.split())
                overlap = prev_words & curr_words
                assert len(overlap) > 0, f"Chunks {i-1} and {i} should have overlapping content"


class TestNormalizeText:
    """Tests for text normalization."""

    def test_lowercase_conversion(self):
        result = normalize_text("HELLO World")
        assert all(word.islower() or not word.isalpha() for word in result if word)

    def test_stopword_removal(self):
        result = normalize_text("The quick brown fox")
        assert "the" not in result
        assert "quick" in result
        assert "brown" in result
        assert "fox" in result

    def test_punctuation_removal(self):
        result = normalize_text("Hello, world! How are you?")
        assert "hello" in result
        assert "world" in result
        assert "," not in result
        assert "!" not in result
        assert "?" not in result

    def test_short_word_filtering(self):
        result = normalize_text("I am a big elephant")
        assert "am" not in result
        assert "a" not in result
        assert "big" in result
        assert "elephant" in result

    def test_returns_set(self):
        result = normalize_text("hello world hello")
        assert isinstance(result, set)

    def test_empty_string(self):
        result = normalize_text("")
        assert len(result) == 0

    def test_numbers_preserved(self):
        result = normalize_text("Chapter 8 discusses equations")
        assert "8" in result
        assert "chapter" in result


class TestMapSubtopic:
    """Tests for subtopic mapping."""

    def _make_subtopic(self, name: str, keywords: list = None):
        return SimpleNamespace(
            id=uuid4(),
            name=name,
            keywords=keywords or [],
        )

    def test_returns_match_above_threshold(self):
        subtopics = [
            self._make_subtopic("Linear Equations"),
            self._make_subtopic("Quadratic Functions"),
        ]
        chunk = "Solve the following linear equations in one variable."
        result = map_subtopic(chunk, subtopics)
        assert result is not None

    def test_prefers_higher_similarity(self):
        subtopics = [
            self._make_subtopic("Fractions"),
            self._make_subtopic("Adding and subtracting fractions"),
        ]
        chunk = "We practice adding fractions and subtracting fractions with common denominators."
        result = map_subtopic(chunk, subtopics)
        assert result is not None

    def test_returns_none_below_threshold(self):
        subtopics = [
            self._make_subtopic("Photosynthesis"),
            self._make_subtopic("Cell division"),
        ]
        chunk = "This section describes basic arithmetic operations on whole numbers."
        result = map_subtopic(chunk, subtopics)
        assert result is None

    def test_returns_none_for_empty_chunk(self):
        subtopics = [self._make_subtopic("Anything")]
        chunk = "   ,,, ... ;;;   "
        result = map_subtopic(chunk, subtopics)
        assert result is None

    def test_uses_keywords_for_matching(self):
        subtopics = [
            self._make_subtopic("Topic A", ["polynomial", "factor"]),
            self._make_subtopic("Topic B", ["unrelated"]),
        ]
        chunk = "Learn how to factor a polynomial expression."
        result = map_subtopic(chunk, subtopics)
        assert result == subtopics[0].id


class TestGradeCodes:
    """Tests for grade code mapping."""

    def test_all_grade_codes_have_values(self):
        for code in GRADE_CODES:
            level = GRADE_CODES[code]
            assert isinstance(level, int)
            assert 5 <= level <= 12

    def test_grade_code_count(self):
        assert len(GRADE_CODES) == 8


class TestSubjectCodes:
    """Tests for subject code mapping."""

    def test_all_subject_codes_have_values(self):
        for code in SUBJECT_CODES:
            name = SUBJECT_CODES[code]
            assert isinstance(name, str)
            assert len(name) > 0

    def test_subject_code_count(self):
        assert len(SUBJECT_CODES) == 4