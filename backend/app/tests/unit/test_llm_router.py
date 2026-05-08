"""Unit tests for the LiteLLM provider router (M0-9-T6 Fix 2).

Tests verify the LiteLLM-based router handles task routing, model selection,
API base configuration, and error handling correctly.

Run with: pytest backend/app/tests/unit/test_llm_router.py -v
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestComplete:
    """Tests for the complete() function."""

    @pytest.mark.asyncio
    async def test_complete_when_valid_task_then_calls_litellm_with_correct_model(self) -> None:
        """Test that complete() calls litellm.acompletion with correct model from settings."""
        mock_response = MagicMock()
        mock_response.usage = MagicMock(total_tokens=150)
        mock_response.choices = [MagicMock(message=MagicMock(content="Test response"))]

        with patch("litellm.acompletion", new_callable=AsyncMock) as mock_complete:
            mock_complete.return_value = mock_response

            from app.ai.providers.router import complete

            messages = [{"role": "user", "content": "Hello"}]
            result = await complete("gap_classification", messages)

            mock_complete.assert_called_once()
            call_kwargs = mock_complete.call_args.kwargs
            assert call_kwargs["model"] is not None
            assert call_kwargs["messages"] == messages
            assert result == "Test response"

    @pytest.mark.asyncio
    async def test_complete_when_unknown_task_then_raises_value_error(self) -> None:
        """Test that complete() raises ValueError for unknown task."""
        from app.ai.providers.router import complete

        messages = [{"role": "user", "content": "Hello"}]

        with pytest.raises(ValueError) as exc_info:
            await complete("unknown_task", messages)

        assert "Unknown LLM task" in str(exc_info.value)
        assert "unknown_task" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_complete_with_custom_api_base_uses_that_base(self) -> None:
        """Test that when api_base is set in settings, it's passed to litellm."""
        mock_response = MagicMock()
        mock_response.usage = MagicMock(total_tokens=150)
        mock_response.choices = [MagicMock(message=MagicMock(content="Test response"))]

        with patch("litellm.acompletion", new_callable=AsyncMock) as mock_complete:
            mock_complete.return_value = mock_response
            with patch("app.ai.providers.router.TASK_API_BASE_MAP", {"gap_classification": "http://custom:8000"}):
                from app.ai.providers.router import complete

                messages = [{"role": "user", "content": "Hello"}]
                await complete("gap_classification", messages)

                call_kwargs = mock_complete.call_args.kwargs
                assert call_kwargs["api_base"] == "http://custom:8000"

    @pytest.mark.asyncio
    async def test_complete_with_none_api_base_passes_none_to_litellm(self) -> None:
        """Test that None api_base passes None to litellm (uses provider default)."""
        mock_response = MagicMock()
        mock_response.usage = MagicMock(total_tokens=150)
        mock_response.choices = [MagicMock(message=MagicMock(content="Test response"))]

        with patch("litellm.acompletion", new_callable=AsyncMock) as mock_complete:
            mock_complete.return_value = mock_response
            with patch("app.ai.providers.router.TASK_API_BASE_MAP", {"gap_classification": None}):
                from app.ai.providers.router import complete

                messages = [{"role": "user", "content": "Hello"}]
                await complete("gap_classification", messages)

                call_kwargs = mock_complete.call_args.kwargs
                assert call_kwargs["api_base"] is None


class TestEmbed:
    """Tests for the embed() function."""

    @pytest.mark.asyncio
    async def test_embed_when_called_then_returns_float_list(self) -> None:
        """Test that embed() returns a list of floats."""
        mock_response = MagicMock()
        mock_response.data = [{"embedding": [0.1, 0.2, 0.3]}]

        with patch("litellm.aembedding", new_callable=AsyncMock) as mock_embedding:
            mock_embedding.return_value = mock_response

            from app.ai.providers.router import embed

            result = await embed("Test text to embed")

            mock_embedding.assert_called_once()
            call_kwargs = mock_embedding.call_args.kwargs
            assert call_kwargs["input"] == "Test text to embed"
            assert result == [0.1, 0.2, 0.3]
            assert isinstance(result, list)
            assert all(isinstance(x, float) for x in result)


class TestTaskModelMap:
    """Tests for TASK_MODEL_MAP configuration."""

    def test_task_model_map_has_all_required_tasks(self) -> None:
        """Test that TASK_MODEL_MAP contains all required task keys."""
        from app.ai.providers.router import TASK_MODEL_MAP

        required_tasks = {"gap_classification", "study_plan", "lesson_plan", "embeddings"}
        assert required_tasks.issubset(TASK_MODEL_MAP.keys())

    def test_task_api_base_map_has_all_required_tasks(self) -> None:
        """Test that TASK_API_BASE_MAP contains all required task keys."""
        from app.ai.providers.router import TASK_API_BASE_MAP

        required_tasks = {"gap_classification", "study_plan", "lesson_plan", "embeddings"}
        assert required_tasks.issubset(TASK_API_BASE_MAP.keys())

    def test_task_model_map_values_are_strings(self) -> None:
        """Test that all TASK_MODEL_MAP values are strings (empty when not configured via env vars)."""
        from app.ai.providers.router import TASK_MODEL_MAP

        for task, model in TASK_MODEL_MAP.items():
            assert isinstance(model, str), f"Task {task} has non-string model: {model}"

    def test_task_api_base_map_values_are_strings_or_none(self) -> None:
        """Test that all TASK_API_BASE_MAP values are strings or None."""
        from app.ai.providers.router import TASK_API_BASE_MAP

        for task, api_base in TASK_API_BASE_MAP.items():
            assert api_base is None or isinstance(api_base, str), (
                f"Task {task} has invalid api_base type: {type(api_base)}"
            )


class TestRouterModuleStructure:
    """Tests for router module structure and exports."""

    def test_complete_function_exists_and_is_async(self) -> None:
        """Test that complete function exists and is async."""
        import asyncio

        from app.ai.providers.router import complete

        assert callable(complete)
        assert asyncio.iscoroutinefunction(complete)

    def test_embed_function_exists_and_is_async(self) -> None:
        """Test that embed function exists and is async."""
        import asyncio

        from app.ai.providers.router import embed

        assert callable(embed)
        assert asyncio.iscoroutinefunction(embed)
