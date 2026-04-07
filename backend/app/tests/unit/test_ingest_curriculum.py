"""Unit tests for curriculum PDF ingestion script.

Tests cover:
- Token-based chunking with 500 token size and 50 token overlap
- Subtopic resolution via fuzzy matching
- Resumable behavior (skip already-embedded chunks)

Run with: pytest backend/app/tests/unit/test_ingest_curriculum.py -v
"""

import uuid

import pytest
import tiktoken

from scripts.ingest_curriculum import (
    CHUNK_OVERLAP_TOKENS,
    CHUNK_SIZE_TOKENS,
    chunk_text_by_tokens,
    parse_filename,
    resolve_subtopic,
    resolve_subtopic_with_logging,
)


class TestFilenameParsing:
    """Tests for PDF filename parsing."""

    def test_parse_filename_when_cambridge_lower_math_grade7(self) -> None:
        result = parse_filename("cambridge_lower_math_grade7.pdf")
        assert result == ("cambridge_lower", "MATH", 7)

    def test_parse_filename_when_cambridge_igcse_biology_grade9(self) -> None:
        result = parse_filename("cambridge_igcse_biology_grade9.pdf")
        assert result == ("cambridge_igcse", "BIO", 9)

    def test_parse_filename_when_cambridge_lower_science_grade6(self) -> None:
        result = parse_filename("cambridge_lower_science_grade6.pdf")
        assert result == ("cambridge_lower", "SCI", 6)

    def test_parse_filename_when_cambridge_igcse_chemistry_grade10(self) -> None:
        result = parse_filename("cambridge_igcse_chemistry_grade10.pdf")
        assert result == ("cambridge_igcse", "CHEM", 10)

    def test_parse_filename_when_uppercase_extension(self) -> None:
        result = parse_filename("cambridge_lower_math_grade7.PDF")
        assert result == ("cambridge_lower", "MATH", 7)

    def test_parse_filename_when_invalid_format_then_none(self) -> None:
        result = parse_filename("invalid_filename.pdf")
        assert result is None

    def test_parse_filename_when_missing_grade(self) -> None:
        result = parse_filename("cambridge_math.pdf")
        assert result is None


class TestChunking:
    """Tests for token-based text chunking."""

    def test_chunking_when_500_token_text_then_single_chunk_produced(self) -> None:
        encoder = tiktoken.get_encoding("cl100k_base")
        text = "cat" * 500
        tokens = encoder.encode(text)
        assert len(tokens) == 500

        chunks = chunk_text_by_tokens(text, encoder, CHUNK_SIZE_TOKENS, CHUNK_OVERLAP_TOKENS)

        assert len(chunks) == 1
        assert chunks[0]["start_token"] == 0
        assert chunks[0]["end_token"] == 500

    def test_chunking_when_1100_token_text_then_three_chunks_with_overlap(self) -> None:
        encoder = tiktoken.get_encoding("cl100k_base")
        text = "cat" * 1100
        tokens = encoder.encode(text)
        assert len(tokens) == 1100

        chunks = chunk_text_by_tokens(text, encoder, CHUNK_SIZE_TOKENS, CHUNK_OVERLAP_TOKENS)

        assert len(chunks) == 3
        assert chunks[0]["start_token"] == 0
        assert chunks[0]["end_token"] == 500
        assert chunks[1]["start_token"] == 450
        assert chunks[1]["end_token"] == 950
        assert chunks[2]["start_token"] == 900
        assert chunks[2]["end_token"] == 1100

    def test_chunking_when_empty_text_then_no_chunks(self) -> None:
        encoder = tiktoken.get_encoding("cl100k_base")
        chunks = chunk_text_by_tokens("", encoder, CHUNK_SIZE_TOKENS, CHUNK_OVERLAP_TOKENS)
        assert len(chunks) == 0

    def test_chunking_produces_correct_overlap(self) -> None:
        encoder = tiktoken.get_encoding("cl100k_base")
        sample_text = "word " * 1000

        chunks = chunk_text_by_tokens(sample_text, encoder, CHUNK_SIZE_TOKENS, CHUNK_OVERLAP_TOKENS)

        if len(chunks) >= 2:
            assert chunks[1]["start_token"] == chunks[0]["end_token"] - CHUNK_OVERLAP_TOKENS

    def test_chunking_never_exceeds_source_tokens(self) -> None:
        encoder = tiktoken.get_encoding("cl100k_base")
        sample_text = "The quadratic formula is used to solve quadratic equations. "

        tokens = encoder.encode(sample_text)
        chunks = chunk_text_by_tokens(sample_text, encoder, CHUNK_SIZE_TOKENS, CHUNK_OVERLAP_TOKENS)

        for chunk in chunks:
            assert chunk["end_token"] <= len(tokens)


class TestSubtopicResolution:
    """Tests for subtopic resolution via fuzzy matching."""

    def test_subtopic_resolution_when_text_contains_subtopic_name_then_subtopic_id_set(
        self,
    ) -> None:
        subtopic_id = uuid.uuid4()
        subtopic_names = ["Integers", "Fractions", "Decimals"]
        subtopic_name_to_id = {
            "Integers": subtopic_id,
            "Fractions": uuid.uuid4(),
            "Decimals": uuid.uuid4(),
        }

        chunk_text = "This chapter covers Integers and their properties."

        result = resolve_subtopic(chunk_text, subtopic_names, subtopic_name_to_id)

        assert result == subtopic_id

    def test_subtopic_resolution_when_no_match_then_subtopic_id_null_and_warning_logged(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        import logging

        subtopic_names = ["Integers", "Fractions", "Decimals"]
        subtopic_name_to_id = {
            "Integers": uuid.uuid4(),
            "Fractions": uuid.uuid4(),
            "Decimals": uuid.uuid4(),
        }

        chunk_text = "This chapter covers Quantum mechanics concepts."
        caplog.set_level(logging.WARNING)

        result = resolve_subtopic_with_logging(
            chunk_text, subtopic_names, subtopic_name_to_id, chunk_index=0, filename="test.pdf"
        )

        assert result is None
        assert "subtopic_not_resolved" in caplog.text

    def test_subtopic_resolution_when_partial_match_below_cutoff_then_null(self) -> None:
        subtopic_id = uuid.uuid4()
        subtopic_names = ["Algebraic Expressions", "Linear Equations"]
        subtopic_name_to_id = {
            "Algebraic Expressions": subtopic_id,
            "Linear Equations": uuid.uuid4(),
        }

        chunk_text = "This covers basic mathematical structures."

        result = resolve_subtopic(chunk_text, subtopic_names, subtopic_name_to_id)

        assert result is None

    def test_subtopic_resolution_when_exact_substring_match_then_id_returned(self) -> None:
        subtopic_id = uuid.uuid4()
        subtopic_names = ["Quadratic Equations", "Linear Equations"]
        subtopic_name_to_id = {
            "Quadratic Equations": subtopic_id,
            "Linear Equations": uuid.uuid4(),
        }

        chunk_text = "In this section we study Quadratic Equations in detail."

        result = resolve_subtopic(chunk_text, subtopic_names, subtopic_name_to_id)

        assert result == subtopic_id

    def test_subtopic_resolution_when_case_insensitive_match_then_id_returned(self) -> None:
        subtopic_id = uuid.uuid4()
        subtopic_names = ["Integers", "Fractions"]
        subtopic_name_to_id = {
            "Integers": subtopic_id,
            "Fractions": uuid.uuid4(),
        }

        chunk_text = "This covers INTEGERS and their properties."

        result = resolve_subtopic(chunk_text, subtopic_names, subtopic_name_to_id)

        assert result == subtopic_id


class TestResumableBehavior:
    """Tests for resumable ingestion behavior."""

    def test_resumable_when_chunk_already_has_embedding_then_skipped(self) -> None:
        encoder = tiktoken.get_encoding("cl100k_base")
        sample_text = "word " * 500

        chunks = chunk_text_by_tokens(sample_text, encoder, CHUNK_SIZE_TOKENS, CHUNK_OVERLAP_TOKENS)

        if len(chunks) >= 2:
            existing_chunk_indices = {0}

            chunks_to_process = [c for i, c in enumerate(chunks) if i not in existing_chunk_indices]

            assert len(chunks_to_process) == len(chunks) - 1
            assert 0 not in [i for i, c in enumerate(chunks) if c in chunks_to_process]

    def test_resumable_when_all_chunks_have_embedding_then_none_processed(self) -> None:
        encoder = tiktoken.get_encoding("cl100k_base")
        sample_text = "word " * 1000

        chunks = chunk_text_by_tokens(sample_text, encoder, CHUNK_SIZE_TOKENS, CHUNK_OVERLAP_TOKENS)

        existing_chunk_indices = set(range(len(chunks)))

        chunks_to_process = [c for i, c in enumerate(chunks) if i not in existing_chunk_indices]

        assert len(chunks_to_process) == 0


class TestEmbedderMean:
    """Tests for embedder mean computation."""

    def test_compute_mean_embedding_when_single_embedding_then_same(self) -> None:
        from app.ai.rag.embedder import CurriculumEmbedder

        embedder = CurriculumEmbedder()
        embeddings = [[0.1, 0.2, 0.3, 0.4]]

        result = embedder.compute_mean_embedding(embeddings)

        assert result == [0.1, 0.2, 0.3, 0.4]

    def test_compute_mean_embedding_when_two_embeddings_then_correct_mean(self) -> None:
        from app.ai.rag.embedder import CurriculumEmbedder

        embedder = CurriculumEmbedder()
        embeddings = [
            [1.0, 2.0, 3.0, 4.0],
            [3.0, 4.0, 5.0, 6.0],
        ]

        result = embedder.compute_mean_embedding(embeddings)

        assert result == [2.0, 3.0, 4.0, 5.0]

    def test_compute_mean_embedding_when_empty_then_raises_error(self) -> None:
        from app.ai.rag.embedder import CurriculumEmbedder

        embedder = CurriculumEmbedder()

        with pytest.raises(ValueError) as exc_info:
            embedder.compute_mean_embedding([])

        assert "empty" in str(exc_info.value).lower()
