"""Unit tests for LLM router streaming support."""

from unittest.mock import AsyncMock, MagicMock, patch  # noqa: F401

import pytest


@pytest.mark.asyncio
async def test_complete_when_stream_true_then_collects_chunks_and_returns_string() -> None:
    """When stream=True, complete() collects streamed chunks and returns the combined string."""
    chunk1 = MagicMock()
    chunk1.choices = [MagicMock()]
    chunk1.choices[0].delta.content = '{"lesson_hook": '

    chunk2 = MagicMock()
    chunk2.choices = [MagicMock()]
    chunk2.choices[0].delta.content = '"hello world"}'

    async def mock_stream(*args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        for chunk in [chunk1, chunk2]:
            yield chunk

    with patch("app.ai.providers.router.litellm") as mock_litellm:
        mock_litellm.acompletion = AsyncMock(return_value=mock_stream())
        from app.ai.providers.router import complete

        result = await complete(
            task="lesson_plan",
            messages=[{"role": "user", "content": "test"}],
            stream=True,
        )

    assert result == '{"lesson_hook": "hello world"}'


@pytest.mark.asyncio
async def test_complete_when_stream_true_and_chunk_content_is_none_then_skipped() -> None:
    """When stream=True, None delta.content chunks are skipped (not concatenated)."""
    chunk_none = MagicMock()
    chunk_none.choices = [MagicMock()]
    chunk_none.choices[0].delta.content = None

    chunk_real = MagicMock()
    chunk_real.choices = [MagicMock()]
    chunk_real.choices[0].delta.content = "result"

    async def mock_stream(*args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        for chunk in [chunk_none, chunk_real]:
            yield chunk

    with patch("app.ai.providers.router.litellm") as mock_litellm:
        mock_litellm.acompletion = AsyncMock(return_value=mock_stream())
        from app.ai.providers.router import complete

        result = await complete(
            task="lesson_plan",
            messages=[{"role": "user", "content": "test"}],
            stream=True,
        )

    assert result == "result"


@pytest.mark.asyncio
async def test_complete_when_stream_true_and_choices_empty_then_chunk_skipped() -> None:
    """When stream=True, chunks with empty choices list are skipped without IndexError."""
    chunk_empty_choices = MagicMock()
    chunk_empty_choices.choices = []

    chunk_real = MagicMock()
    chunk_real.choices = [MagicMock()]
    chunk_real.choices[0].delta.content = "output"

    async def mock_stream(*args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        for chunk in [chunk_empty_choices, chunk_real]:
            yield chunk

    with patch("app.ai.providers.router.litellm") as mock_litellm:
        mock_litellm.acompletion = AsyncMock(return_value=mock_stream())
        from app.ai.providers.router import complete

        result = await complete(
            task="lesson_plan",
            messages=[{"role": "user", "content": "test"}],
            stream=True,
        )

    assert result == "output"


@pytest.mark.asyncio
async def test_complete_when_stream_false_then_uses_standard_response() -> None:
    """When stream=False (default), complete() returns response.choices[0].message.content."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "standard response"
    mock_response.usage = MagicMock(total_tokens=10)

    with patch("app.ai.providers.router.litellm") as mock_litellm:
        mock_litellm.acompletion = AsyncMock(return_value=mock_response)
        from app.ai.providers.router import complete

        result = await complete(
            task="lesson_plan",
            messages=[{"role": "user", "content": "test"}],
            stream=False,
        )

    assert result == "standard response"
    call_kwargs = mock_litellm.acompletion.call_args.kwargs
    assert call_kwargs.get("stream") is False
