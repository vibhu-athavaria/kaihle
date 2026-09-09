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

from app.ai.llm_cost import estimate_cost
from app.ai.usage_context import current_component, current_school_id
from app.ai.usage_sink import prompt_text_from_messages, record_usage
from app.core.config import settings

logger = structlog.get_logger()

# LiteLLM reads provider API keys from os.environ directly.
# Pydantic Settings loads .env into Python attributes but never writes to os.environ,
# so we bridge them here — the one place all LLM calls originate.
_KEY_MAP = {
    "OPENAI_API_KEY": settings.openai_api_key,
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
    "quiz_generation": settings.llm_quiz_generation_model,
    "lo_matching": settings.llm_lo_matching_model,
    "question_quality": settings.llm_question_quality_model,
    "student_pack": settings.llm_student_pack_model,
    "embeddings": settings.llm_embeddings_model,
    "concept_guide": settings.llm_concept_guide_model,
    "explain_this": settings.llm_explain_this_model,
    "mini_course_explanation": settings.llm_mini_course_model,
    "content_seed": settings.llm_content_seed_model,
    "transfer_question": settings.llm_transfer_question_model,
    "grade_open_answer": settings.llm_grade_open_answer_model,
}

TASK_API_BASE_MAP: dict[str, str | None] = {
    "gap_classification": settings.llm_gap_classification_api_base,
    "study_plan": settings.llm_study_plan_api_base,
    "lesson_plan": settings.llm_lesson_plan_api_base,
    "question_generation": settings.llm_question_generation_api_base,
    "quiz_generation": settings.llm_quiz_generation_api_base,
    "lo_matching": settings.llm_lo_matching_api_base,
    "question_quality": settings.llm_question_quality_api_base,
    "student_pack": settings.llm_student_pack_api_base,
    "embeddings": settings.llm_embeddings_api_base,
    "concept_guide": settings.llm_concept_guide_api_base,
    "explain_this": settings.llm_explain_this_api_base,
    "mini_course_explanation": settings.llm_mini_course_api_base,
    "content_seed": settings.llm_content_seed_api_base,
    "transfer_question": settings.llm_transfer_question_api_base,
    "grade_open_answer": settings.llm_grade_open_answer_api_base,
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


async def _log_completed(
    task: str,
    model: str,
    t0: float,
    prompt_tokens: int | None,
    completion_tokens: int | None,
    total_tokens: int | None,
    streamed: bool = False,
    response: Any | None = None,
    prompt_text: str | None = None,
    response_text: str | None = None,
) -> None:
    """Log the call and persist a usage row.

    Both happen here because this is the single point every successful LLM call passes
    through. `record_usage` never raises, so awaiting it cannot fail the call — see
    ai/usage_sink.py.
    """
    latency_ms = int((time.monotonic() - t0) * 1000)
    # Guarded: estimate_cost reaches into LiteLLM's pricing tables and a config file, and
    # this runs on the success path of every LLM call. Unguarded, a pricing bug would fail a
    # student's request — breaking the invariant that telemetry never fails inference.
    # An unpriceable call is already a supported state (NULL cost), so a raising pricer
    # degrades to exactly that.
    try:
        cost = estimate_cost(model, prompt_tokens, completion_tokens, response)
    except Exception as exc:
        logger.warning("llm_cost_estimation_failed", task=task, model=model, error=str(exc), exc_info=True)
        cost = None
    logger.info(
        "llm_call_completed",
        task=task,
        model=model,
        latency_ms=latency_ms,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        component=current_component(),
        estimated_cost_usd=float(cost) if cost is not None else None,
    )
    await record_usage(
        task=task,
        model=model,
        latency_ms=latency_ms,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=cost,
        streamed=streamed,
        school_id=current_school_id(),
        prompt_text=prompt_text,
        response_text=response_text,
    )


async def _log_failed(
    task: str,
    model: str,
    t0: float,
    exc: Exception,
    streamed: bool = False,
    prompt_text: str | None = None,
) -> None:
    """Record a failed call.

    Failures cost money and latency too. A report that counts only successes understates
    spend and hides a provider that is erroring expensively.
    """
    latency_ms = int((time.monotonic() - t0) * 1000)
    logger.warning(
        "llm_call_failed",
        task=task,
        model=model,
        latency_ms=latency_ms,
        error_type=type(exc).__name__,
        error=str(exc),
        component=current_component(),
    )
    await record_usage(
        task=task,
        model=model,
        latency_ms=latency_ms,
        streamed=streamed,
        succeeded=False,
        error_type=type(exc).__name__,
        error_detail=str(exc),
        school_id=current_school_id(),
        prompt_text=prompt_text,
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

    try:
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
    except Exception as exc:
        # Record and re-raise. Retry policy stays with the caller (see module docstring);
        # this only ensures a failed call is not invisible in the cost report.
        await _log_failed(task, model, t0, exc, streamed=stream, prompt_text=prompt_text_from_messages(messages))
        raise

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
        await _log_completed(
            task,
            model,
            t0,
            prompt_tokens,
            completion_tokens,
            total_tokens,
            streamed=True,
            prompt_text=prompt_text_from_messages(messages),
            response_text=text,
        )
        return text

    usage = response.usage if hasattr(response, "usage") else None
    # Extracted tolerantly (None on empty choices) so telemetry still fires even when the
    # strict validation below is about to raise — usage_sink's invariant is that recording
    # usage must never depend on the call's own success/shape.
    response_text = response.choices[0].message.content if response.choices else None
    await _log_completed(
        task,
        model,
        t0,
        prompt_tokens=usage.prompt_tokens if usage else None,
        completion_tokens=usage.completion_tokens if usage else None,
        total_tokens=usage.total_tokens if usage else None,
        response=response,
        prompt_text=prompt_text_from_messages(messages),
        response_text=response_text,
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

    try:
        response = await litellm.acompletion(
            model=model,
            api_base=api_base or None,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            stream_options={"include_usage": True},
        )
    except Exception as exc:
        await _log_failed(task, model, t0, exc, streamed=True, prompt_text=prompt_text_from_messages(messages))
        raise

    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    chunks: list[str] = []

    async for chunk in response:
        if not chunk.choices:
            if hasattr(chunk, "usage") and chunk.usage:
                prompt_tokens = chunk.usage.prompt_tokens
                completion_tokens = chunk.usage.completion_tokens
                total_tokens = chunk.usage.total_tokens
            continue
        delta = chunk.choices[0].delta.content
        if delta is not None:
            chunks.append(delta)
            yield f"data: {delta}\n\n"

    await _log_completed(
        task,
        model,
        t0,
        prompt_tokens,
        completion_tokens,
        total_tokens,
        streamed=True,
        prompt_text=prompt_text_from_messages(messages),
        response_text="".join(chunks),
    )
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

    return (await embed_batch([text]))[0]


async def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed several texts in one request. Provider-agnostic.

    Embedding a whole curriculum one string at a time is dominated by round-trip
    latency, so the batch form is the primary implementation and embed() delegates
    to it.

    Args:
        texts: Non-empty strings to embed.

    Returns:
        Vectors in the same order as the inputs.

    Raises:
        ValueError: If texts is empty, any entry is blank, the provider returns the
            wrong number of vectors, or a vector has an unexpected dimensionality.
    """
    if not texts:
        raise ValueError("texts must be a non-empty list for embedding generation")
    if any(not t or not t.strip() for t in texts):
        raise ValueError("every entry in texts must be a non-empty string")

    model = TASK_MODEL_MAP["embeddings"]
    api_base = TASK_API_BASE_MAP.get("embeddings")
    dimensions = settings.llm_embeddings_dimensions

    kwargs: dict[str, Any] = {"model": model, "api_base": api_base or None, "input": texts}
    if dimensions is not None:
        kwargs["dimensions"] = dimensions

    t0 = _log_started("embeddings", model, stream=False, api_base=api_base)
    try:
        response = await litellm.aembedding(**kwargs)
    except Exception as exc:
        await _log_failed("embeddings", model, t0, exc, prompt_text="\n\n".join(texts))
        raise

    if not response.data or len(response.data) == 0:
        raise ValueError("Embedding API returned empty data array")
    if len(response.data) != len(texts):
        raise ValueError(f"Embedding API returned {len(response.data)} vectors for {len(texts)} inputs")

    # Providers order results by an explicit index, not by position. Sorting on it
    # keeps vectors aligned with their inputs; a silent misalignment here would
    # attach every embedding to the wrong objective.
    ordered = sorted(response.data, key=lambda d: d.get("index", 0))

    vectors: list[list[float]] = []
    for item in ordered:
        vector = item.get("embedding")
        if vector is None:
            raise ValueError("Embedding API response missing 'embedding' field")
        # Fail here rather than at INSERT time: pgvector rejects a mismatched width
        # with an opaque error, and a silently truncated vector would corrupt search.
        if dimensions is not None and len(vector) != dimensions:
            raise ValueError(
                f"Embedding model {model!r} returned {len(vector)} dimensions, expected {dimensions}. "
                "Set LLM_EMBEDDINGS_DIMENSIONS to match the model, or use a model that "
                "supports the requested dimensionality."
            )
        vectors.append(vector)

    # Embedding runs are a real cost centre — a curriculum-wide re-embed is thousands of
    # calls — and were previously invisible. Providers report prompt_tokens only; there is
    # no completion side, so completion_tokens is 0 rather than None so the call remains
    # priceable.
    usage = getattr(response, "usage", None)
    await _log_completed(
        "embeddings",
        model,
        t0,
        prompt_tokens=getattr(usage, "prompt_tokens", None) if usage else None,
        completion_tokens=0 if usage else None,
        total_tokens=getattr(usage, "total_tokens", None) if usage else None,
        response=response,
        prompt_text="\n\n".join(texts),
    )

    return vectors
