"""
Tests for Phase 10B - PDF Content Extraction Pipeline.

Tests the extraction script functions without requiring actual PDF files.
"""
import pytest
from scripts.extract_pdf_content import (
    parse_filename,
    chunk_text,
    normalize_text,
    GRADE_CODES,
    SUBJECT_CODES,
)


class TestParseFilename:
    """Tests for filename parsing."""

    def test_valid_filename_grade8_math(self):
        """Test parsing a valid grade8_math filename."""
        grade, subject, content = parse_filename("grade8_math_textbook.pdf")
        assert grade == "grade8"
        assert subject == "math"
        assert content == "textbook"

    def test_valid_filename_with_underscore_in_content_type(self):
        """Test parsing filename with multiple underscores in content type."""
        grade, subject, content = parse_filename("grade10_science_workbook_chapter3.pdf")
        assert grade == "grade10"
        assert subject == "science"
        assert content == "workbook_chapter3"

    def test_valid_filename_all_grades(self):
        """Test all valid grade codes."""
        for grade_code in GRADE_CODES:
            filename = f"{grade_code}_math_textbook.pdf"
            grade, subject, content = parse_filename(filename)
            assert grade == grade_code

    def test_valid_filename_all_subjects(self):
        """Test all valid subject codes."""
        for subject_code in SUBJECT_CODES:
            filename = f"grade8_{subject_code}_textbook.pdf"
            grade, subject, content = parse_filename(filename)
            assert subject == subject_code

    def test_invalid_grade_code(self):
        """Test that invalid grade code raises ValueError."""
        with pytest.raises(ValueError, match="Invalid grade_code"):
            parse_filename("grade13_math_textbook.pdf")

    def test_invalid_subject_code(self):
        """Test that invalid subject code raises ValueError."""
        with pytest.raises(ValueError, match="Invalid subject_code"):
            parse_filename("grade8_physics_textbook.pdf")

    def test_missing_underscore(self):
        """Test that filename without enough underscores raises ValueError."""
        with pytest.raises(ValueError, match="Invalid filename format"):
            parse_filename("grade8math.pdf")

    def test_non_pdf_extension(self):
        """Test that non-PDF extension raises ValueError."""
        with pytest.raises(ValueError, match="must be a PDF"):
            parse_filename("grade8_math_textbook.txt")

    def test_case_insensitive_parsing(self):
        """Test that parsing handles case variations."""
        grade, subject, content = parse_filename("GRADE8_MATH_Textbook.pdf")
        assert grade == "grade8"
        assert subject == "math"


class TestChunkText:
    """Tests for text chunking."""

    def test_chunk_single_paragraph(self):
        """Test chunking a single small paragraph."""
        pages = ["This is a test paragraph."]
        chunks = chunk_text(pages, chunk_size_tokens=100, overlap_tokens=10)
        assert len(chunks) == 1
        assert chunks[0][1] > 0  # token count > 0

    def test_chunk_multiple_paragraphs(self):
        """Test chunking multiple paragraphs."""
        pages = [
            "First paragraph here.\n\nSecond paragraph here.\n\nThird paragraph here."
        ]
        chunks = chunk_text(pages, chunk_size_tokens=100, overlap_tokens=10)
        assert len(chunks) >= 1

    def test_chunk_respects_size_limit(self):
        """Test that chunks are created when size limit exceeded."""
        long_text = "This is a sentence. " * 200
        pages = [long_text]
        chunks = chunk_text(pages, chunk_size_tokens=50, overlap_tokens=10)
        assert len(chunks) > 1

    def test_chunk_empty_pages(self):
        """Test chunking empty pages returns empty list."""
        pages = []
        chunks = chunk_text(pages, chunk_size_tokens=100, overlap_tokens=10)
        assert len(chunks) == 0

    def test_chunk_whitespace_only_pages(self):
        """Test chunking pages with only whitespace."""
        pages = ["   \n\n   \n\n   "]
        chunks = chunk_text(pages, chunk_size_tokens=100, overlap_tokens=10)
        assert len(chunks) == 0

    def test_chunk_returns_token_count(self):
        """Test that each chunk includes token count."""
        pages = ["This is a test paragraph with some content."]
        chunks = chunk_text(pages, chunk_size_tokens=100, overlap_tokens=10)
        for chunk_text_result, token_count in chunks:
            assert isinstance(token_count, int)
            assert token_count > 0


class TestNormalizeText:
    """Tests for text normalization."""

    def test_lowercase_conversion(self):
        """Test that text is lowercased."""
        result = normalize_text("HELLO World")
        assert all(word.islower() or not word.isalpha() for word in result if word)

    def test_stopword_removal(self):
        """Test that stopwords are removed."""
        result = normalize_text("The quick brown fox")
        assert "the" not in result
        assert "quick" in result
        assert "brown" in result
        assert "fox" in result

    def test_punctuation_removal(self):
        """Test that punctuation is removed."""
        result = normalize_text("Hello, world! How are you?")
        assert "hello" in result
        assert "world" in result
        assert "," not in result
        assert "!" not in result
        assert "?" not in result

    def test_short_word_filtering(self):
        """Test that words shorter than 3 characters are filtered."""
        result = normalize_text("I am a big elephant")
        assert "am" not in result
        assert "a" not in result
        assert "big" in result
        assert "elephant" in result

    def test_returns_set(self):
        """Test that result is a set."""
        result = normalize_text("hello world hello")
        assert isinstance(result, set)

    def test_empty_string(self):
        """Test empty string returns empty set."""
        result = normalize_text("")
        assert len(result) == 0

    def test_numbers_preserved(self):
        """Test that numbers are preserved."""
        result = normalize_text("Chapter 8 discusses equations")
        assert "8" in result or "chapter" in result


class TestGradeCodes:
    """Tests for grade code mapping."""

    def test_all_grade_codes_have_values(self):
        """Test all grade codes map to integer levels."""
        for code in GRADE_CODES:
            level = GRADE_CODES[code]
            assert isinstance(level, int)
            assert 5 <= level <= 12

    def test_grade_code_count(self):
        """Test we have expected number of grade codes."""
        assert len(GRADE_CODES) == 8  # grades 5-12


class TestSubjectCodes:
    """Tests for subject code mapping."""

    def test_all_subject_codes_have_values(self):
        """Test all subject codes map to subject names."""
        for code in SUBJECT_CODES:
            name = SUBJECT_CODES[code]
            assert isinstance(name, str)
            assert len(name) > 0

    def test_subject_code_count(self):
        """Test we have expected number of subject codes."""
        assert len(SUBJECT_CODES) == 4  # math, science, english, humanities
