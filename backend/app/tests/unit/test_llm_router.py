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
    """Tests for embed() and embed_batch()."""

    @staticmethod
    def _response(*vectors: list[float], with_index: bool = False) -> MagicMock:
        mock_response = MagicMock()
        if with_index:
            mock_response.data = [{"embedding": v, "index": i} for i, v in enumerate(vectors)]
        else:
            mock_response.data = [{"embedding": v} for v in vectors]
        return mock_response

    @pytest.mark.asyncio
    async def test_embed_when_called_then_returns_float_list(self) -> None:
        """Test that embed() returns a list of floats."""
        with (
            patch("litellm.aembedding", new_callable=AsyncMock) as mock_embedding,
            patch("app.ai.providers.router.settings.llm_embeddings_dimensions", 3),
        ):
            mock_embedding.return_value = self._response([0.1, 0.2, 0.3])

            from app.ai.providers.router import embed

            result = await embed("Test text to embed")

            mock_embedding.assert_called_once()
            call_kwargs = mock_embedding.call_args.kwargs
            # embed() delegates to embed_batch(), so the payload is always a list.
            assert call_kwargs["input"] == ["Test text to embed"]
            assert result == [0.1, 0.2, 0.3]
            assert all(isinstance(x, float) for x in result)

    @pytest.mark.asyncio
    async def test_embed_when_dimensions_configured_then_passed_to_provider(self) -> None:
        """The vector width must match the vector(N) columns, so it is requested explicitly."""
        with (
            patch("litellm.aembedding", new_callable=AsyncMock) as mock_embedding,
            patch("app.ai.providers.router.settings.llm_embeddings_dimensions", 3),
        ):
            mock_embedding.return_value = self._response([0.1, 0.2, 0.3])

            from app.ai.providers.router import embed

            await embed("text")

            assert mock_embedding.call_args.kwargs["dimensions"] == 3

    @pytest.mark.asyncio
    async def test_embed_when_dimensions_unset_then_omitted_from_request(self) -> None:
        """Fixed-width models reject an unsupported dimensions argument."""
        with (
            patch("litellm.aembedding", new_callable=AsyncMock) as mock_embedding,
            patch("app.ai.providers.router.settings.llm_embeddings_dimensions", None),
        ):
            mock_embedding.return_value = self._response([0.1, 0.2])

            from app.ai.providers.router import embed

            await embed("text")

            assert "dimensions" not in mock_embedding.call_args.kwargs

    @pytest.mark.asyncio
    async def test_embed_when_provider_returns_wrong_width_then_raises(self) -> None:
        """Catch the mismatch here — pgvector's own error is opaque, and a truncated
        vector written silently would corrupt similarity search."""
        with (
            patch("litellm.aembedding", new_callable=AsyncMock) as mock_embedding,
            patch("app.ai.providers.router.settings.llm_embeddings_dimensions", 768),
        ):
            mock_embedding.return_value = self._response([0.1, 0.2, 0.3])

            from app.ai.providers.router import embed

            with pytest.raises(ValueError, match="returned 3 dimensions, expected 768"):
                await embed("text")

    @pytest.mark.asyncio
    async def test_embed_batch_when_given_texts_then_returns_vectors_in_input_order(self) -> None:
        """Providers order results by an explicit index, not by position. A silent
        misalignment would attach every embedding to the wrong objective."""
        with (
            patch("litellm.aembedding", new_callable=AsyncMock) as mock_embedding,
            patch("app.ai.providers.router.settings.llm_embeddings_dimensions", 2),
        ):
            response = MagicMock()
            response.data = [
                {"embedding": [0.3, 0.3], "index": 2},
                {"embedding": [0.1, 0.1], "index": 0},
                {"embedding": [0.2, 0.2], "index": 1},
            ]
            mock_embedding.return_value = response

            from app.ai.providers.router import embed_batch

            result = await embed_batch(["a", "b", "c"])

            assert result == [[0.1, 0.1], [0.2, 0.2], [0.3, 0.3]]

    @pytest.mark.asyncio
    async def test_embed_batch_when_provider_returns_wrong_count_then_raises(self) -> None:
        with (
            patch("litellm.aembedding", new_callable=AsyncMock) as mock_embedding,
            patch("app.ai.providers.router.settings.llm_embeddings_dimensions", 2),
        ):
            mock_embedding.return_value = self._response([0.1, 0.1], with_index=True)

            from app.ai.providers.router import embed_batch

            with pytest.raises(ValueError, match="returned 1 vectors for 2 inputs"):
                await embed_batch(["a", "b"])

    @pytest.mark.asyncio
    async def test_embed_batch_when_texts_empty_then_raises(self) -> None:
        from app.ai.providers.router import embed_batch

        with pytest.raises(ValueError, match="non-empty list"):
            await embed_batch([])

    @pytest.mark.asyncio
    async def test_embed_batch_when_any_text_blank_then_raises(self) -> None:
        from app.ai.providers.router import embed_batch

        with pytest.raises(ValueError, match="non-empty string"):
            await embed_batch(["valid", "   "])


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
