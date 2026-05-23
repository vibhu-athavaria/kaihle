"""LiteLLM-based provider router.

All LLM calls in Kaihle go through this module. No feature code imports
provider SDKs directly — all routing, retries, and provider switching
are handled here via configuration.

To switch a task to a different provider or to a self-hosted LLM server,
change the corresponding environment variable — no code change required.
"""

import os
import time
from collections.abc import AsyncGenerator
from typing import Any

import litellm
import structlog

from app.core.config import settings

logger = structlog.get_logger()

# LiteLLM reads provider API keys from os.environ directly.
# Pydantic Settings loads .env into Python attributes but never writes to os.environ,
# so we bridge them here — the one place all LLM calls originate.
_KEY_MAP = {
    "OPENAI_API_KEY": settings.openai_api_key,
    "GOOGLE_API_KEY": settings.google_api_key,
    "OPENROUTER_API_KEY": settings.openrouter_api_key,
    "ANTHROPIC_API_KEY": settings.anthropic_api_key,
}
for _env_var, _value in _KEY_MAP.items():
    if _value:
        os.environ[_env_var] = _value

# Task → model mapping, fully config-driven.
# These map task names to the environment variable values.
# To route lesson_plan to a self-hosted server:
#   LLM_LESSON_PLAN_MODEL=openai/your-model-name
#   LLM_LESSON_PLAN_API_BASE=http://your-server:8000
TASK_MODEL_MAP: dict[str, str] = {
    "gap_classification": settings.llm_gap_classification_model,
    "study_plan": settings.llm_study_plan_model,
    "lesson_plan": settings.llm_lesson_plan_model,
    "question_generation": settings.llm_question_generation_model,
    "student_pack": settings.llm_student_pack_model,
    "embeddings": settings.llm_embeddings_model,
    "concept_guide": settings.llm_concept_guide_model,
    "explain_this": settings.llm_explain_this_model,
    "mini_course_explanation": settings.llm_mini_course_model,
    "content_seed": settings.llm_content_seed_model,
}

TASK_API_BASE_MAP: dict[str, str | None] = {
    "gap_classification": settings.llm_gap_classification_api_base,
    "study_plan": settings.llm_study_plan_api_base,
    "lesson_plan": settings.llm_lesson_plan_api_base,
    "question_generation": settings.llm_question_generation_api_base,
    "student_pack": settings.llm_student_pack_api_base,
    "embeddings": settings.llm_embeddings_api_base,
    "concept_guide": settings.llm_concept_guide_api_base,
    "explain_this": settings.llm_explain_this_api_base,
    "mini_course_explanation": settings.llm_mini_course_api_base,
    "content_seed": settings.llm_content_seed_api_base,
}


def _log_started(task: str, model: str, stream: bool, api_base: str | None) -> float:
    """Emit llm_call_started and return monotonic start time."""
    logger.info(
        "llm_call_started",
        task=task,
        model=model,
        stream=stream,
        has_custom_api_base=api_base is not None,
    )
    return time.monotonic()


def _log_completed(
    task: str,
    model: str,
    t0: float,
    prompt_tokens: int | None,
    completion_tokens: int | None,
    total_tokens: int | None,
) -> None:
    logger.info(
        "llm_call_completed",
        task=task,
        model=model,
        latency_ms=int((time.monotonic() - t0) * 1000),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
    )


async def complete(
    task: str,
    messages: list[dict[str, Any]],
    temperature: float = 0.7,
    max_tokens: int = 2000,
    stream: bool = False,
) -> str:
    """Call the configured LLM for the given task. Provider-agnostic.

    Args:
        task: One of the keys in TASK_MODEL_MAP
        messages: OpenAI-format message list [{"role": "...", "content": "..."}]
        temperature: Sampling temperature (default 0.7)
        max_tokens: Maximum tokens in response (default 2000)
        stream: If True, collect streamed chunks into a single string (default False)

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
    t0 = _log_started(task, model, stream=stream, api_base=api_base)

    response = await litellm.acompletion(
        model=model,
        api_base=api_base or None,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=stream,
        # Request usage stats in the final streaming chunk where supported
        **({"stream_options": {"include_usage": True}} if stream else {}),
    )

    if stream:
        chunks: list[str] = []
        prompt_tokens: int | None = None
        completion_tokens: int | None = None
        total_tokens: int | None = None
        async for chunk in response:
            if not chunk.choices:
                # Final usage-only chunk from providers that support include_usage
                if hasattr(chunk, "usage") and chunk.usage:
                    prompt_tokens = chunk.usage.prompt_tokens
                    completion_tokens = chunk.usage.completion_tokens
                    total_tokens = chunk.usage.total_tokens
                continue
            delta = chunk.choices[0].delta.content
            if delta is not None:
                chunks.append(delta)
        text = "".join(chunks)
        _log_completed(task, model, t0, prompt_tokens, completion_tokens, total_tokens)
        return text

    usage = response.usage if hasattr(response, "usage") else None
    _log_completed(
        task,
        model,
        t0,
        prompt_tokens=usage.prompt_tokens if usage else None,
        completion_tokens=usage.completion_tokens if usage else None,
        total_tokens=usage.total_tokens if usage else None,
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


async def stream_sse(
    task: str,
    messages: list[dict[str, Any]],
    temperature: float = 0.7,
    max_tokens: int = 2000,
) -> AsyncGenerator[str, None]:
    """Stream SSE-formatted chunks for the given task. Provider-agnostic.

    Yields Server-Sent Event strings ("data: <chunk>\\n\\n") as they arrive,
    then a final "data: [DONE]\\n\\n" sentinel. All LLM routing, logging,
    and token counting go through this single choke point.

    Use this for HTTP streaming endpoints (EventSourceResponse / StreamingResponse).
    Use complete() for non-streaming calls that need the full response as a string.

    Args:
        task: One of the keys in TASK_MODEL_MAP
        messages: OpenAI-format message list
        temperature: Sampling temperature (default 0.7)
        max_tokens: Maximum tokens in response (default 2000)

    Yields:
        SSE-formatted strings: "data: <text>\\n\\n" and finally "data: [DONE]\\n\\n"

    Raises:
        ValueError: If task is not in TASK_MODEL_MAP
    """
    if task not in TASK_MODEL_MAP:
        raise ValueError(f"Unknown LLM task: {task!r}. Valid tasks: {list(TASK_MODEL_MAP)}")

    model = TASK_MODEL_MAP[task]
    api_base = TASK_API_BASE_MAP.get(task)
    t0 = _log_started(task, model, stream=True, api_base=api_base)

    response = await litellm.acompletion(
        model=model,
        api_base=api_base or None,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
        stream_options={"include_usage": True},
    )

    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None

    async for chunk in response:
        if not chunk.choices:
            if hasattr(chunk, "usage") and chunk.usage:
                prompt_tokens = chunk.usage.prompt_tokens
                completion_tokens = chunk.usage.completion_tokens
                total_tokens = chunk.usage.total_tokens
            continue
        delta = chunk.choices[0].delta.content
        if delta is not None:
            yield f"data: {delta}\n\n"

    _log_completed(task, model, t0, prompt_tokens, completion_tokens, total_tokens)
    yield "data: [DONE]\n\n"


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
