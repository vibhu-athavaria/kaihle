"""Unit tests for the LiteLLM provider router (M0-9-T6 Fix 2).

Tests verify the LiteLLM-based router handles task routing, model selection,
API base configuration, and error handling correctly.

Run with: pytest backend/app/tests/unit/test_llm_router.py -v
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ai.providers import router
from app.ai.usage_context import current_component, llm_component


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


class TestUsageAccounting:
    """MLH-T2. Every LLM call records a usage row — and telemetry can never break inference.

    That last property is the one that matters: a student waiting on an explanation does not
    get an error because a usage insert failed.
    """

    @pytest.mark.asyncio
    async def test_complete_when_tracking_enabled_then_usage_recorded_once(self) -> None:
        response = MagicMock()
        response.choices = [MagicMock(message=MagicMock(content="text"))]
        response.usage = MagicMock(prompt_tokens=10, completion_tokens=20, total_tokens=30)

        with (
            patch("litellm.acompletion", new_callable=AsyncMock, return_value=response),
            patch("app.ai.providers.router.record_usage", new_callable=AsyncMock) as record,
            patch("app.ai.providers.router.TASK_MODEL_MAP", {"lesson_plan": "test/model-a"}),
        ):
            await router.complete("lesson_plan", [{"role": "user", "content": "hi"}])

        record.assert_awaited_once()
        assert record.await_args is not None
        kwargs = record.await_args.kwargs
        assert kwargs["task"] == "lesson_plan"
        assert kwargs["prompt_tokens"] == 10
        # The success path relies on record_usage's default rather than passing it
        # explicitly; the failure path below is what sets it False.
        assert kwargs.get("succeeded", True) is True

    @pytest.mark.asyncio
    async def test_complete_when_provider_raises_then_usage_recorded_with_succeeded_false(self) -> None:
        with (
            patch("litellm.acompletion", new_callable=AsyncMock, side_effect=RuntimeError("429 rate limited")),
            patch("app.ai.providers.router.record_usage", new_callable=AsyncMock) as record,
            patch("app.ai.providers.router.TASK_MODEL_MAP", {"lesson_plan": "test/model-a"}),
            pytest.raises(RuntimeError),
        ):
            await router.complete("lesson_plan", [{"role": "user", "content": "hi"}])

        # Failed calls cost money and latency; a report counting only successes understates.
        record.assert_awaited_once()
        assert record.await_args is not None
        assert record.await_args.kwargs["succeeded"] is False
        assert record.await_args.kwargs["error_type"] == "RuntimeError"

    @pytest.mark.asyncio
    async def test_complete_when_usage_sink_raises_then_llm_response_still_returned(self) -> None:
        # The core invariant. record_usage swallows internally, but even if it did not,
        # a broken sink must not surface as a failed LLM call.
        response = MagicMock()
        response.choices = [MagicMock(message=MagicMock(content="the answer"))]
        response.usage = MagicMock(prompt_tokens=1, completion_tokens=1, total_tokens=2)

        with (
            patch("litellm.acompletion", new_callable=AsyncMock, return_value=response),
            patch("app.ai.providers.router.TASK_MODEL_MAP", {"lesson_plan": "test/model-a"}),
            patch("app.ai.usage_sink.settings.llm_usage_tracking_enabled", True),
            patch("app.ai.usage_sink.CeleryAsyncSessionLocal", side_effect=RuntimeError("db gone")),
        ):
            result = await router.complete("lesson_plan", [{"role": "user", "content": "hi"}])

        assert result == "the answer"

    @pytest.mark.asyncio
    async def test_complete_when_cost_estimation_raises_then_call_still_succeeds(self) -> None:
        """A pricing bug must not fail a student's request.

        estimate_cost reads LiteLLM's pricing tables and a config file on the success path of
        every call. Before this was guarded, a raising pricer propagated straight out of
        complete() — telemetry failing inference, which is the one thing this design forbids.
        An unpriceable call is already a supported state, so the degraded result is a NULL
        cost, not an error.
        """
        response = MagicMock()
        response.choices = [MagicMock(message=MagicMock(content="ok"))]
        response.usage = MagicMock(prompt_tokens=1, completion_tokens=1, total_tokens=2)

        with (
            patch("litellm.acompletion", new_callable=AsyncMock, return_value=response),
            patch("app.ai.providers.router.TASK_MODEL_MAP", {"lesson_plan": "test/model-a"}),
            patch("app.ai.providers.router.estimate_cost", side_effect=RuntimeError("pricing blew up")),
            patch("app.ai.providers.router.record_usage", new_callable=AsyncMock) as record,
        ):
            result = await router.complete("lesson_plan", [{"role": "user", "content": "hi"}])

        assert result == "ok"
        assert record.await_args is not None
        assert record.await_args.kwargs["estimated_cost_usd"] is None

    @pytest.mark.asyncio
    async def test_complete_when_school_bound_then_recorded_on_usage_row(self) -> None:
        """A call made while serving a student is attributable to their school.

        Without this, every interactive call would record NULL and the column's meaning
        ("platform-level work") would be destroyed.
        """
        import uuid as _uuid

        from structlog.contextvars import bind_contextvars, clear_contextvars

        school = _uuid.uuid4()
        response = MagicMock()
        response.choices = [MagicMock(message=MagicMock(content="x"))]
        response.usage = MagicMock(prompt_tokens=1, completion_tokens=1, total_tokens=2)

        try:
            bind_contextvars(school_id=str(school))
            with (
                patch("litellm.acompletion", new_callable=AsyncMock, return_value=response),
                patch("app.ai.providers.router.TASK_MODEL_MAP", {"lesson_plan": "test/model-a"}),
                patch("app.ai.providers.router.record_usage", new_callable=AsyncMock) as record,
            ):
                await router.complete("lesson_plan", [{"role": "user", "content": "hi"}])
        finally:
            clear_contextvars()

        assert record.await_args is not None
        assert record.await_args.kwargs["school_id"] == school

    @pytest.mark.asyncio
    async def test_complete_when_no_school_bound_then_school_id_is_none(self) -> None:
        """Batch and curriculum-scope work binds nothing — that is what makes NULL mean
        'platform-level' rather than 'we forgot'."""
        response = MagicMock()
        response.choices = [MagicMock(message=MagicMock(content="x"))]
        response.usage = MagicMock(prompt_tokens=1, completion_tokens=1, total_tokens=2)

        with (
            patch("litellm.acompletion", new_callable=AsyncMock, return_value=response),
            patch("app.ai.providers.router.TASK_MODEL_MAP", {"lesson_plan": "test/model-a"}),
            patch("app.ai.providers.router.record_usage", new_callable=AsyncMock) as record,
        ):
            await router.complete("lesson_plan", [{"role": "user", "content": "hi"}])

        assert record.await_args is not None
        assert record.await_args.kwargs["school_id"] is None

    @pytest.mark.asyncio
    async def test_complete_when_component_bound_then_passed_through_context(self) -> None:
        response = MagicMock()
        response.choices = [MagicMock(message=MagicMock(content="x"))]
        response.usage = MagicMock(prompt_tokens=1, completion_tokens=1, total_tokens=2)

        captured: dict[str, str | None] = {}

        async def _capture(**kwargs: object) -> None:
            captured["component"] = current_component()

        with (
            patch("litellm.acompletion", new_callable=AsyncMock, return_value=response),
            patch("app.ai.providers.router.TASK_MODEL_MAP", {"lesson_plan": "test/model-a"}),
            patch("app.ai.providers.router.record_usage", new=_capture),
            llm_component("celery:test_task"),
        ):
            await router.complete("lesson_plan", [{"role": "user", "content": "hi"}])

        assert captured["component"] == "celery:test_task"


class TestPromptResponseTextCapture:
    """LLM Logs (the per-call admin viewer) needs the full prompt/response text, not just
    token counts. These pin that `complete()`/`stream_sse()` forward it to `record_usage`
    without changing any existing return value or raise behaviour."""

    @pytest.mark.asyncio
    async def test_complete_when_non_streaming_then_prompt_and_response_text_recorded(self) -> None:
        response = MagicMock()
        response.choices = [MagicMock(message=MagicMock(content="the answer"))]
        response.usage = MagicMock(prompt_tokens=1, completion_tokens=1, total_tokens=2)

        with (
            patch("litellm.acompletion", new_callable=AsyncMock, return_value=response),
            patch("app.ai.providers.router.TASK_MODEL_MAP", {"lesson_plan": "test/model-a"}),
            patch("app.ai.providers.router.record_usage", new_callable=AsyncMock) as record,
        ):
            result = await router.complete("lesson_plan", [{"role": "user", "content": "hi"}])

        assert result == "the answer"
        assert record.await_args is not None
        kwargs = record.await_args.kwargs
        assert kwargs["prompt_text"] == "[user] hi"
        assert kwargs["response_text"] == "the answer"

    @pytest.mark.asyncio
    async def test_complete_when_streaming_then_full_assembled_text_recorded(self) -> None:
        async def _chunks():
            for delta in ["Hel", "lo"]:
                chunk = MagicMock()
                chunk.choices = [MagicMock(delta=MagicMock(content=delta))]
                yield chunk
            final = MagicMock()
            final.choices = []
            final.usage = MagicMock(prompt_tokens=1, completion_tokens=1, total_tokens=2)
            yield final

        with (
            patch("litellm.acompletion", new_callable=AsyncMock, return_value=_chunks()),
            patch("app.ai.providers.router.TASK_MODEL_MAP", {"lesson_plan": "test/model-a"}),
            patch("app.ai.providers.router.record_usage", new_callable=AsyncMock) as record,
        ):
            result = await router.complete("lesson_plan", [{"role": "user", "content": "hi"}], stream=True)

        assert result == "Hello"
        assert record.await_args is not None
        kwargs = record.await_args.kwargs
        assert kwargs["prompt_text"] == "[user] hi"
        assert kwargs["response_text"] == "Hello"

    @pytest.mark.asyncio
    async def test_complete_when_provider_raises_then_prompt_text_still_recorded(self) -> None:
        with (
            patch("litellm.acompletion", new_callable=AsyncMock, side_effect=RuntimeError("429")),
            patch("app.ai.providers.router.TASK_MODEL_MAP", {"lesson_plan": "test/model-a"}),
            patch("app.ai.providers.router.record_usage", new_callable=AsyncMock) as record,
            pytest.raises(RuntimeError),
        ):
            await router.complete("lesson_plan", [{"role": "user", "content": "hi"}])

        assert record.await_args is not None
        assert record.await_args.kwargs["prompt_text"] == "[user] hi"
        # A failed call never produced a response — there is nothing honest to record here.
        assert record.await_args.kwargs.get("response_text") is None

    @pytest.mark.asyncio
    async def test_complete_when_response_has_no_choices_then_telemetry_still_recorded_before_raise(self) -> None:
        """Extraction for telemetry must be tolerant even when the strict validation right
        after it is about to raise — usage_sink's invariant is that recording usage never
        depends on the call's own shape being valid."""
        response = MagicMock()
        response.choices = []
        response.usage = MagicMock(prompt_tokens=1, completion_tokens=0, total_tokens=1)

        with (
            patch("litellm.acompletion", new_callable=AsyncMock, return_value=response),
            patch("app.ai.providers.router.TASK_MODEL_MAP", {"lesson_plan": "test/model-a"}),
            patch("app.ai.providers.router.record_usage", new_callable=AsyncMock) as record,
            pytest.raises(ValueError, match="no choices"),
        ):
            await router.complete("lesson_plan", [{"role": "user", "content": "hi"}])

        record.assert_awaited_once()
        assert record.await_args is not None
        assert record.await_args.kwargs["response_text"] is None
