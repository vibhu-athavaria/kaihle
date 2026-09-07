"""Estimate the dollar cost of an LLM call.

Three tiers, in order, and the third one is the important one:

  1. LiteLLM's own calculator. It maintains an upstream price table for hosted models and
     tracks provider price changes, which a table in this repo never would.
  2. A configured override file. The only way a self-hosted endpoint gets a cost — LiteLLM
     has no prices for an arbitrary vLLM server. Ships EMPTY: no model names in the repo.
  3. NULL.

NULL is a real answer, not a failure. A wrong cost figure is worse than a missing one because
it looks like data and gets summed into a total. Nothing here ever guesses a price, and never
borrows another model's price for an unknown one.

SELF-HOSTED COSTS ARE NOT PROVIDER BILLING. For a self-hosted endpoint the real cost is
GPU-hour amortisation, not per-token. A price supplied in the override file for such a model
is a synthetic rate the operator chose, and the report labels those rows accordingly.
"""

import json
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path
from typing import Any

import litellm
import structlog

from app.core.config import settings

logger = structlog.get_logger()

# Prices are quoted per 1,000 tokens in the override file — the unit every provider
# publishes — and converted here.
TOKENS_PER_PRICE_UNIT = Decimal(1000)


@lru_cache(maxsize=1)
def _price_table() -> dict[str, dict[str, Decimal]]:
    """Load the override price table once.

    Cached because this is consulted on every LLM call and the file does not change within a
    process. A malformed file yields an empty table and a warning rather than an exception:
    telemetry configuration must never be able to break inference.
    """
    path = settings.llm_price_table_path
    if not path:
        return {}

    file_path = Path(path)
    if not file_path.exists():
        logger.warning("llm_price_table_missing", path=path, effect="costs will be NULL for self-hosted models")
        return {}

    try:
        raw = json.loads(file_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("llm_price_table_unreadable", path=path, error=str(exc))
        return {}

    table: dict[str, dict[str, Decimal]] = {}
    for model, prices in raw.items():
        try:
            table[model] = {
                "input_per_1k": Decimal(str(prices["input_per_1k"])),
                "output_per_1k": Decimal(str(prices["output_per_1k"])),
            }
        except (KeyError, TypeError, InvalidOperation) as exc:
            # Skip the bad entry, keep the rest. One malformed line should not silently
            # un-price every other model in the file.
            logger.warning("llm_price_table_entry_invalid", model=model, error=str(exc))
    return table


def _from_price_table(model: str, prompt_tokens: int, completion_tokens: int) -> Decimal | None:
    entry = _price_table().get(model)
    if entry is None:
        return None
    return (Decimal(prompt_tokens) * entry["input_per_1k"] + Decimal(completion_tokens) * entry["output_per_1k"]) / (
        TOKENS_PER_PRICE_UNIT
    )


def estimate_cost(
    model: str,
    prompt_tokens: int | None,
    completion_tokens: int | None,
    response: Any | None = None,
) -> Decimal | None:
    """Best available cost for one call, or None when the model is not priceable.

    Args:
        model: Resolved model string as sent to the provider.
        prompt_tokens: Input token count, or None if the provider did not report it.
        completion_tokens: Output token count, or None.
        response: The raw provider response, if available. LiteLLM's calculator reads
            provider-specific fields from it that a token count alone cannot supply.

    Returns:
        Cost in USD, or None. None is returned whenever either token count is missing —
        a cost computed from half the tokens is not a partial answer, it is a wrong one.
    """
    if prompt_tokens is None or completion_tokens is None:
        return None

    if response is not None:
        try:
            whole_call_cost = litellm.completion_cost(completion_response=response)
            if whole_call_cost:
                return Decimal(str(whole_call_cost))
        except Exception as exc:
            # LiteLLM raises for models it does not know, which is expected for self-hosted
            # endpoints. Debug, not warning: the override table is the designed next step.
            logger.debug("litellm_cost_unavailable", model=model, error=str(exc))

    try:
        per_token = litellm.cost_per_token(
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        if per_token:
            prompt_cost, completion_cost = per_token
            total = Decimal(str(prompt_cost)) + Decimal(str(completion_cost))
            if total > 0:
                return total
    except Exception as exc:
        logger.debug("litellm_cost_per_token_unavailable", model=model, error=str(exc))

    return _from_price_table(model, prompt_tokens, completion_tokens)


def reset_price_table_cache() -> None:
    """Clear the cached table. For tests, and for a long-lived process after a config change."""
    _price_table.cache_clear()
