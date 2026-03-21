"""LiteLLM-based provider router.

All LLM calls in Kaihle go through this module. No feature code imports
provider SDKs directly — all routing, retries, and provider switching
are handled here via configuration.

To switch a task to a different provider or to a self-hosted LLM server,
change the corresponding environment variable — no code change required.
"""

from typing import Any

import litellm
import structlog

from app.core.config import settings

logger = structlog.get_logger()

# Task → model mapping, fully config-driven.
# These map task names to the environment variable values.
# To route lesson_plan to a self-hosted server:
#   LLM_LESSON_PLAN_MODEL=openai/your-model-name
#   LLM_LESSON_PLAN_API_BASE=http://your-server:8000
TASK_MODEL_MAP: dict[str, str] = {
    "gap_classification": settings.llm_gap_classification_model,
    "study_plan": settings.llm_study_plan_model,
    "lesson_plan": settings.llm_lesson_plan_model,
    "embeddings": settings.llm_embeddings_model,
}

TASK_API_BASE_MAP: dict[str, str | None] = {
    "gap_classification": settings.llm_gap_classification_api_base,
    "study_plan": settings.llm_study_plan_api_base,
    "lesson_plan": settings.llm_lesson_plan_api_base,
    "embeddings": settings.llm_embeddings_api_base,
}


async def complete(
    task: str,
    messages: list[dict[str, Any]],
    temperature: float = 0.7,
    max_tokens: int = 2000,
) -> str:
    """Call the configured LLM for the given task. Provider-agnostic.

    Args:
        task: One of "gap_classification", "study_plan", "lesson_plan"
        messages: OpenAI-format message list [{"role": "...", "content": "..."}]
        temperature: Sampling temperature (default 0.7)
        max_tokens: Maximum tokens in response (default 2000)

    Returns:
        The model's text response as a string.

    Raises:
        ValueError: If task is not in TASK_MODEL_MAP
        litellm.exceptions.APIError: On provider API errors (caller handles retries)
    """
    if task not in TASK_MODEL_MAP:
        raise ValueError(f"Unknown LLM task: {task!r}. Valid tasks: {list(TASK_MODEL_MAP)}")

    model = TASK_MODEL_MAP[task]
    api_base = TASK_API_BASE_MAP.get(task)

    logger.info("llm_call_started", task=task, model=model, has_custom_api_base=api_base is not None)

    response = await litellm.acompletion(
        model=model,
        api_base=api_base or None,  # None tells LiteLLM to use the provider's default endpoint
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    logger.info(
        "llm_call_completed",
        task=task,
        model=model,
        tokens_used=response.usage.total_tokens if response.usage else None,
    )

    # Handle potential empty choices or None content (e.g., tool calls, non-text responses)
    if not response.choices:
        raise ValueError("LLM response has no choices. The model may have returned an empty response.")
    content = response.choices[0].message.content
    if content is None:
        raise ValueError(
            "LLM response content is None. The model may have returned a tool call "
            "or non-text response. Ensure the model is configured for text output."
        )
    return content


async def embed(text: str) -> list[float]:
    """Generate an embedding vector for the given text. Provider-agnostic.

    Args:
        text: The text to embed.

    Returns:
        A list of floats representing the embedding vector.

    Raises:
        ValueError: If text is empty.
    """
    if not text or not text.strip():
        raise ValueError("text must be a non-empty string for embedding generation")

    model = TASK_MODEL_MAP["embeddings"]
    api_base = TASK_API_BASE_MAP.get("embeddings")

    response = await litellm.aembedding(
        model=model,
        api_base=api_base or None,
        input=text,
    )

    # Validate response structure before accessing
    if not response.data or len(response.data) == 0:
        raise ValueError("Embedding API returned empty data array")

    embedding = response.data[0].get("embedding")
    if embedding is None:
        raise ValueError("Embedding API response missing 'embedding' field")

    return embedding
