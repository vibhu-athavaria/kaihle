"""Unit tests for LLM cost estimation.

The rule these pin down: NULL is a valid answer and a guess is not. A wrong cost figure is
worse than a missing one, because it looks like data and gets summed into a total.

No real model names appear here. Model names are env-driven throughout the project and must
not be written into the repo, tests included.
"""

import json
from decimal import Decimal
from unittest.mock import patch

import pytest

from app.ai.llm_cost import estimate_cost, reset_price_table_cache


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    """The price table is lru_cached; tests must not leak a table into each other."""
    reset_price_table_cache()


class TestLiteLlmTier:
    def test_estimate_cost_when_litellm_returns_value_then_uses_it(self) -> None:
        with patch("litellm.completion_cost", return_value=0.00421):
            assert estimate_cost("test/model-a", 100, 200, response=object()) == Decimal("0.00421")

    def test_estimate_cost_when_litellm_raises_then_falls_back_to_price_table(self, tmp_path) -> None:
        table = tmp_path / "prices.json"
        table.write_text(json.dumps({"test/model-a": {"input_per_1k": 1.0, "output_per_1k": 2.0}}))

        with (
            patch("litellm.completion_cost", side_effect=RuntimeError("unknown model")),
            patch("litellm.cost_per_token", side_effect=RuntimeError("unknown model")),
            patch("app.ai.llm_cost.settings.llm_price_table_path", str(table)),
        ):
            # 1000 in @ $1/1k + 2000 out @ $2/1k = 1.00 + 4.00
            assert estimate_cost("test/model-a", 1000, 2000) == Decimal("5.0")

    def test_estimate_cost_when_cost_per_token_returns_pair_then_summed(self) -> None:
        with patch("litellm.cost_per_token", return_value=(0.001, 0.002)):
            assert estimate_cost("test/model-a", 100, 200) == Decimal("0.003")


class TestUnpriceable:
    def test_estimate_cost_when_model_absent_from_table_then_returns_none(self, tmp_path) -> None:
        table = tmp_path / "prices.json"
        table.write_text(json.dumps({"test/other": {"input_per_1k": 1.0, "output_per_1k": 2.0}}))

        with (
            patch("litellm.completion_cost", side_effect=RuntimeError()),
            patch("litellm.cost_per_token", side_effect=RuntimeError()),
            patch("app.ai.llm_cost.settings.llm_price_table_path", str(table)),
        ):
            # Never borrows another model's price to fill the gap.
            assert estimate_cost("test/self-hosted", 100, 200) is None

    def test_estimate_cost_when_no_price_table_configured_then_returns_none(self) -> None:
        with (
            patch("litellm.completion_cost", side_effect=RuntimeError()),
            patch("litellm.cost_per_token", side_effect=RuntimeError()),
            patch("app.ai.llm_cost.settings.llm_price_table_path", ""),
        ):
            assert estimate_cost("test/model-a", 100, 200) is None

    def test_estimate_cost_when_price_table_path_missing_then_returns_none_and_does_not_raise(self) -> None:
        with (
            patch("litellm.completion_cost", side_effect=RuntimeError()),
            patch("litellm.cost_per_token", side_effect=RuntimeError()),
            patch("app.ai.llm_cost.settings.llm_price_table_path", "/nonexistent/prices.json"),
        ):
            assert estimate_cost("test/model-a", 100, 200) is None

    def test_estimate_cost_when_price_table_malformed_then_returns_none_and_does_not_raise(self, tmp_path) -> None:
        # A typo in a config file must not be able to break an LLM call.
        table = tmp_path / "prices.json"
        table.write_text("{ not json")
        with (
            patch("litellm.completion_cost", side_effect=RuntimeError()),
            patch("litellm.cost_per_token", side_effect=RuntimeError()),
            patch("app.ai.llm_cost.settings.llm_price_table_path", str(table)),
        ):
            assert estimate_cost("test/model-a", 100, 200) is None

    def test_estimate_cost_when_one_table_entry_invalid_then_others_still_usable(self, tmp_path) -> None:
        table = tmp_path / "prices.json"
        table.write_text(
            json.dumps(
                {
                    "test/broken": {"input_per_1k": "not-a-number"},
                    "test/good": {"input_per_1k": 1.0, "output_per_1k": 1.0},
                }
            )
        )
        with (
            patch("litellm.completion_cost", side_effect=RuntimeError()),
            patch("litellm.cost_per_token", side_effect=RuntimeError()),
            patch("app.ai.llm_cost.settings.llm_price_table_path", str(table)),
        ):
            assert estimate_cost("test/good", 1000, 1000) == Decimal("2.0")
            assert estimate_cost("test/broken", 1000, 1000) is None


class TestMissingTokenCounts:
    def test_estimate_cost_when_token_counts_are_none_then_returns_none(self) -> None:
        assert estimate_cost("test/model-a", None, None) is None

    def test_estimate_cost_when_only_prompt_tokens_known_then_returns_none_not_partial(self) -> None:
        # A cost from half the tokens is not a partial answer. It is a wrong one.
        with patch("litellm.completion_cost", return_value=0.5):
            assert estimate_cost("test/model-a", 100, None) is None

    def test_estimate_cost_when_only_completion_tokens_known_then_returns_none(self) -> None:
        assert estimate_cost("test/model-a", None, 200) is None

    def test_estimate_cost_when_zero_tokens_then_priceable_as_zero(self, tmp_path) -> None:
        # Zero tokens is a measurement, not a missing value.
        table = tmp_path / "prices.json"
        table.write_text(json.dumps({"test/model-a": {"input_per_1k": 1.0, "output_per_1k": 1.0}}))
        with (
            patch("litellm.completion_cost", side_effect=RuntimeError()),
            patch("litellm.cost_per_token", side_effect=RuntimeError()),
            patch("app.ai.llm_cost.settings.llm_price_table_path", str(table)),
        ):
            assert estimate_cost("test/model-a", 0, 0) == Decimal("0")
