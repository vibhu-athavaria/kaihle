"""Unit tests for the learning-objective creation helpers.

Covers the pure logic: text normalisation (the exact-match de-duplication key),
canonical code generation (uniqueness and column width), and cosine similarity.
"""

import pytest

from scripts.create_learning_objectives import (
    CANONICAL_CODE_MAX_LEN,
    build_canonical_code,
    cosine_similarity,
    normalise_text,
)


class TestNormaliseText:
    """normalise_text produces the key used for exact-match de-duplication."""

    def test_normalise_when_case_differs_then_keys_match(self) -> None:
        assert normalise_text("Ordering Decimals") == normalise_text("ordering decimals")

    def test_normalise_when_punctuation_differs_then_keys_match(self) -> None:
        assert normalise_text("Add, subtract; integers.") == normalise_text("Add subtract integers")

    def test_normalise_when_whitespace_differs_then_keys_match(self) -> None:
        assert normalise_text("  add   integers \n") == normalise_text("add integers")

    def test_normalise_when_accented_then_folds_to_ascii(self) -> None:
        assert normalise_text("café") == "cafe"

    def test_normalise_when_texts_genuinely_differ_then_keys_differ(self) -> None:
        assert normalise_text("Order decimals") != normalise_text("Order fractions")


class TestBuildCanonicalCode:
    """Codes are human-readable identifiers; the schema enforces uniqueness."""

    def test_code_when_built_then_prefixed_with_subject_and_uppercased(self) -> None:
        code = build_canonical_code("math", "Order and use negative numbers", set())
        assert code.startswith("MATH-")
        assert code == code.upper()

    def test_code_when_built_then_drops_scaffolding_words(self) -> None:
        # "use", "and", "the" carry no signal — nearly every objective contains them.
        code = build_canonical_code("MATH", "Use and order the negative numbers", set())
        assert "USE" not in code.split("-")
        assert "THE" not in code.split("-")
        assert "NEGATIVE" in code

    def test_code_when_objective_is_long_then_respects_column_width(self) -> None:
        code = build_canonical_code("SCI", " ".join(["photosynthesis"] * 20), set())
        assert len(code) <= CANONICAL_CODE_MAX_LEN

    def test_code_when_already_taken_then_gets_numeric_suffix(self) -> None:
        taken: set[str] = set()
        first = build_canonical_code("MATH", "Order negative numbers", taken)
        second = build_canonical_code("MATH", "Order negative numbers", taken)
        assert first != second
        assert second.endswith("-2")

    def test_code_when_many_collisions_then_all_remain_unique(self) -> None:
        taken: set[str] = set()
        codes = [build_canonical_code("MATH", "Order negative numbers", taken) for _ in range(25)]
        assert len(set(codes)) == 25

    def test_code_when_suffixed_then_still_respects_column_width(self) -> None:
        """The suffix must displace characters, not overflow the column."""
        taken: set[str] = set()
        long_objective = " ".join(["photosynthesis", "respiration", "transpiration"])
        codes = [build_canonical_code("SCI", long_objective, taken) for _ in range(15)]
        assert all(len(c) <= CANONICAL_CODE_MAX_LEN for c in codes)
        assert len(set(codes)) == 15

    def test_code_when_objective_is_only_stop_words_then_still_produces_code(self) -> None:
        code = build_canonical_code("ENG", "the and of to", set())
        assert code.startswith("ENG-")
        assert len(code) > len("ENG-")


class TestCosineSimilarity:
    def test_similarity_when_vectors_identical_then_one(self) -> None:
        assert cosine_similarity([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == pytest.approx(1.0)

    def test_similarity_when_vectors_orthogonal_then_zero(self) -> None:
        assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)

    def test_similarity_when_vector_is_zero_then_zero_not_division_error(self) -> None:
        assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0

    def test_similarity_when_magnitudes_differ_then_direction_only(self) -> None:
        """Cosine ignores magnitude — a scaled vector is still identical in direction."""
        assert cosine_similarity([1.0, 1.0], [5.0, 5.0]) == pytest.approx(1.0)

    def test_similarity_when_lengths_mismatch_then_raises(self) -> None:
        # Silently comparing different widths would produce a meaningless score.
        with pytest.raises(ValueError):
            cosine_similarity([1.0, 2.0], [1.0, 2.0, 3.0])
