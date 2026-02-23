"""
Tests for the LLM Provider abstraction.

This module tests:
- LLMProvider factory function
- Provider-specific implementations
- Redis caching
- Structured logging
"""

import json
import pytest
from unittest.mock import Mock, MagicMock, patch
from uuid import uuid4

from app.services.llm.provider import (
    LLMResponse,
    BaseLLMProvider,
    RunPodProvider,
    AutoContentAPIProvider,
    GoogleGeminiProvider,
    OpenAIProvider,
    get_llm_provider,
)


class TestLLMResponse:
    """Tests for LLMResponse dataclass."""

    def test_llm_response_creation(self):
        """Test LLMResponse can be created with all fields."""
        response = LLMResponse(
            content='{"test": "data"}',
            prompt_tokens=100,
            completion_tokens=50,
            model="gpt-4o-mini",
            provider="openai",
            cached=False,
        )

        assert response.content == '{"test": "data"}'
        assert response.prompt_tokens == 100
        assert response.completion_tokens == 50
        assert response.model == "gpt-4o-mini"
        assert response.provider == "openai"
        assert response.cached is False

    def test_llm_response_cached_default(self):
        """Test LLMResponse cached defaults to False."""
        response = LLMResponse(
            content="test",
            prompt_tokens=0,
            completion_tokens=0,
            model="test",
            provider="test",
        )

        assert response.cached is False


class TestBaseLLMProvider:
    """Tests for BaseLLMProvider base class."""

    def test_complete_raises_not_implemented(self):
        """Test that complete() raises NotImplementedError."""
        provider = BaseLLMProvider()

        with pytest.raises(NotImplementedError):
            provider.complete("system", "user")

    def test_generate_cache_key_deterministic(self):
        """Test cache key generation is deterministic."""
        provider = BaseLLMProvider()

        key1 = provider._generate_cache_key("test_type", "system prompt", "user prompt")
        key2 = provider._generate_cache_key("test_type", "system prompt", "user prompt")

        assert key1 == key2

    def test_generate_cache_key_different_for_different_prompts(self):
        """Test cache key differs for different prompts."""
        provider = BaseLLMProvider()

        key1 = provider._generate_cache_key("test", "system1", "user1")
        key2 = provider._generate_cache_key("test", "system2", "user2")

        assert key1 != key2

    def test_generate_cache_key_format(self):
        """Test cache key follows correct format."""
        provider = BaseLLMProvider()

        key = provider._generate_cache_key("study_plan", "system", "user")

        assert key.startswith("kaihle:llm_cache:study_plan:")


class TestRunPodProvider:
    """Tests for RunPodProvider."""

    def test_init_requires_api_base(self):
        """Test RunPodProvider requires RUNPOD_API_BASE."""
        with patch.dict("os.environ", {"RUNPOD_API_BASE": "", "RUNPOD_API_KEY": "test"}):
            with patch("app.services.llm.provider.settings") as mock_settings:
                mock_settings.LLM_PROVIDER = "runpod"
                with pytest.raises(ValueError, match="RUNPOD_API_BASE"):
                    RunPodProvider()

    def test_init_requires_api_key(self):
        """Test RunPodProvider requires RUNPOD_API_KEY."""
        with patch.dict("os.environ", {"RUNPOD_API_BASE": "http://test", "RUNPOD_API_KEY": ""}):
            with pytest.raises(ValueError, match="RUNPOD_API_KEY"):
                RunPodProvider()


class TestAutoContentAPIProvider:
    """Tests for AutoContentAPIProvider."""

    def test_init_requires_base_url(self):
        """Test AutoContentAPIProvider requires AUTOCONTENTAPI_BASE_URL."""
        with patch.dict("os.environ", {"AUTOCONTENTAPI_BASE_URL": "", "AUTOCONTENTAPI_KEY": "test"}):
            with pytest.raises(ValueError, match="AUTOCONTENTAPI_BASE_URL"):
                AutoContentAPIProvider()

    def test_init_requires_api_key(self):
        """Test AutoContentAPIProvider requires AUTOCONTENTAPI_KEY."""
        with patch.dict("os.environ", {"AUTOCONTENTAPI_BASE_URL": "http://test", "AUTOCONTENTAPI_KEY": ""}):
            with pytest.raises(ValueError, match="AUTOCONTENTAPI_KEY"):
                AutoContentAPIProvider()


class TestGoogleGeminiProvider:
    """Tests for GoogleGeminiProvider."""

    def test_init_requires_api_key(self):
        """Test GoogleGeminiProvider requires GOOGLE_API_KEY."""
        with patch.dict("os.environ", {"GOOGLE_API_KEY": ""}):
            with pytest.raises(ValueError, match="GOOGLE_API_KEY"):
                GoogleGeminiProvider()


class TestOpenAIProvider:
    """Tests for OpenAIProvider."""

    def test_init_requires_api_key(self):
        """Test OpenAIProvider requires OPENAI_API_KEY."""
        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}):
            with pytest.raises(ValueError, match="OPENAI_API_KEY"):
                OpenAIProvider()


class TestGetLLMProvider:
    """Tests for get_llm_provider factory function."""

    def test_returns_openai_provider(self):
        """Test get_llm_provider returns OpenAIProvider for 'openai'."""
        with patch("app.services.llm.provider.settings") as mock_settings:
            mock_settings.LLM_PROVIDER = "openai"
            mock_settings.OPENAI_API_KEY = "test-key"

            with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
                provider = get_llm_provider()
                assert isinstance(provider, OpenAIProvider)

    def test_returns_runpod_provider(self):
        """Test get_llm_provider returns RunPodProvider for 'runpod'."""
        with patch("app.services.llm.provider.settings") as mock_settings:
            mock_settings.LLM_PROVIDER = "runpod"

            with patch.dict("os.environ", {
                "RUNPOD_API_BASE": "http://test",
                "RUNPOD_API_KEY": "test-key",
            }):
                provider = get_llm_provider()
                assert isinstance(provider, RunPodProvider)

    def test_returns_autocontentapi_provider(self):
        """Test get_llm_provider returns AutoContentAPIProvider for 'autocontentapi'."""
        with patch("app.services.llm.provider.settings") as mock_settings:
            mock_settings.LLM_PROVIDER = "autocontentapi"

            with patch.dict("os.environ", {
                "AUTOCONTENTAPI_BASE_URL": "http://test",
                "AUTOCONTENTAPI_KEY": "test-key",
            }):
                provider = get_llm_provider()
                assert isinstance(provider, AutoContentAPIProvider)

    def test_returns_google_provider(self):
        """Test get_llm_provider returns GoogleGeminiProvider for 'google'."""
        with patch("app.services.llm.provider.settings") as mock_settings:
            mock_settings.LLM_PROVIDER = "google"

            with patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"}):
                provider = get_llm_provider()
                assert isinstance(provider, GoogleGeminiProvider)

    def test_raises_for_unknown_provider(self):
        """Test get_llm_provider raises ValueError for unknown provider."""
        with patch("app.services.llm.provider.settings") as mock_settings:
            mock_settings.LLM_PROVIDER = "unknown_provider"

            with pytest.raises(ValueError, match="Unknown LLM provider"):
                get_llm_provider()


class TestLLMCache:
    """Tests for LLM caching functionality."""

    def test_check_cache_returns_none_when_no_redis(self):
        """Test check_cache returns None when Redis is unavailable."""
        provider = BaseLLMProvider()

        with patch.object(provider, "_get_redis_client", return_value=None):
            result = provider.check_cache("test_key")
            assert result is None

    def test_check_cache_returns_cached_data(self):
        """Test check_cache returns cached data when available."""
        provider = BaseLLMProvider()
        mock_client = MagicMock()
        mock_client.get.return_value = '{"content": "cached"}'
        mock_client.close = MagicMock()

        cached_data = {"content": "cached", "prompt_tokens": 10, "completion_tokens": 5}

        with patch.object(provider, "_get_redis_client", return_value=mock_client):
            with patch("app.services.llm.provider.json.loads", return_value=cached_data):
                result = provider.check_cache("test_key")

        mock_client.get.assert_called_once_with("test_key")
        assert result == cached_data

    def test_store_cache_stores_data(self):
        """Test store_cache stores data in Redis."""
        provider = BaseLLMProvider()
        mock_client = MagicMock()
        mock_client.setex = MagicMock()
        mock_client.close = MagicMock()

        response = {"content": "test", "prompt_tokens": 10, "completion_tokens": 5}

        with patch.object(provider, "_get_redis_client", return_value=mock_client):
            provider.store_cache("test_key", response)

        mock_client.setex.assert_called_once()
        args = mock_client.setex.call_args[0]
        assert args[0] == "test_key"


class TestOpenAIProviderComplete:
    """Tests for OpenAIProvider.complete() with caching."""

    def test_complete_returns_cached_response(self):
        """Test complete returns cached response when available."""
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            provider = OpenAIProvider()

            cached_data = {
                "content": '{"test": "cached"}',
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "model": "gpt-4o-mini",
            }

            with patch.object(provider, "check_cache", return_value=cached_data):
                response = provider.complete("system", "user")

            assert response.cached is True
            assert response.content == '{"test": "cached"}'

    def test_complete_calls_openai_api_when_not_cached(self):
        """Test complete calls OpenAI API when not cached."""
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            provider = OpenAIProvider()

            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = '{"test": "response"}'
            mock_response.usage.prompt_tokens = 50
            mock_response.usage.completion_tokens = 25

            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = mock_response

            with patch.object(provider, "check_cache", return_value=None):
                with patch.object(provider, "store_cache") as mock_store:
                    with patch("app.services.llm.provider.OpenAI", return_value=mock_client):
                        response = provider.complete("system", "user")

            assert response.cached is False
            assert response.content == '{"test": "response"}'
            assert response.prompt_tokens == 50
            mock_store.assert_called_once()


class TestProviderSwitching:
    """Tests for provider switching without code changes."""

    def test_provider_switching_openai_to_gemini(self):
        """Test switching from OpenAI to Gemini provider."""
        with patch("app.services.llm.provider.settings") as mock_settings:
            mock_settings.LLM_PROVIDER = "openai"
            mock_settings.OPENAI_API_KEY = "test-key"

            with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
                provider1 = get_llm_provider()
                assert isinstance(provider1, OpenAIProvider)

            mock_settings.LLM_PROVIDER = "google"

            with patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"}):
                provider2 = get_llm_provider()
                assert isinstance(provider2, GoogleGeminiProvider)


class TestCacheKeyFormat:
    """Tests for Redis key format compliance per AGENTS.md."""

    def test_cache_key_follows_kaihle_prefix(self):
        """Test cache key follows kaihle:{service}:{entity}:{identifier} format."""
        provider = BaseLLMProvider()
        key = provider._generate_cache_key("study_plan", "system", "user")

        assert key.startswith("kaihle:")
        parts = key.split(":")
        assert parts[0] == "kaihle"
        assert parts[1] == "llm_cache"
        assert parts[2] == "study_plan"


class TestRedisClientHandling:
    """Tests for Redis client handling."""

    def test_get_redis_client_success(self):
        """Test _get_redis_client returns client when Redis is available."""
        provider = BaseLLMProvider()

        with patch.dict("os.environ", {"REDIS_URL": "redis://localhost:6379/0"}):
            with patch("app.services.llm.provider.redis.from_url") as mock_from_url:
                mock_client = MagicMock()
                mock_from_url.return_value = mock_client

                client = provider._get_redis_client()

                mock_from_url.assert_called_once()
                assert client == mock_client

    def test_get_redis_client_returns_none_on_error(self):
        """Test _get_redis_client returns None when connection fails."""
        provider = BaseLLMProvider()

        with patch.dict("os.environ", {"REDIS_URL": "redis://localhost:6379/0"}):
            with patch("app.services.llm.provider.redis.from_url") as mock_from_url:
                mock_from_url.side_effect = Exception("Connection refused")

                client = provider._get_redis_client()

                assert client is None

    def test_check_cache_handles_exception(self):
        """Test check_cache handles exceptions gracefully."""
        provider = BaseLLMProvider()
        mock_client = MagicMock()
        mock_client.get.side_effect = Exception("Redis error")
        mock_client.close = MagicMock()

        with patch.object(provider, "_get_redis_client", return_value=mock_client):
            result = provider.check_cache("test_key")

        assert result is None
        mock_client.close.assert_called_once()

    def test_store_cache_handles_exception(self):
        """Test store_cache handles exceptions gracefully."""
        provider = BaseLLMProvider()
        mock_client = MagicMock()
        mock_client.setex.side_effect = Exception("Redis error")
        mock_client.close = MagicMock()

        with patch.object(provider, "_get_redis_client", return_value=mock_client):
            provider.store_cache("test_key", {"test": "data"})

        mock_client.close.assert_called_once()


class TestGoogleGeminiProviderComplete:
    """Tests for GoogleGeminiProvider.complete()."""

    def test_complete_returns_cached_response(self):
        """Test complete returns cached response when available."""
        with patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"}):
            provider = GoogleGeminiProvider()

            cached_data = {
                "content": '{"test": "cached"}',
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "model": "gemini-1.5-flash",
            }

            with patch.object(provider, "check_cache", return_value=cached_data):
                response = provider.complete("system", "user")

            assert response.cached is True
            assert response.content == '{"test": "cached"}'


class TestRunPodProviderComplete:
    """Tests for RunPodProvider.complete()."""

    def test_complete_returns_cached_response(self):
        """Test complete returns cached response when available."""
        with patch.dict("os.environ", {
            "RUNPOD_API_BASE": "http://test",
            "RUNPOD_API_KEY": "test-key",
        }):
            provider = RunPodProvider()

            cached_data = {
                "content": '{"test": "cached"}',
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "model": "llama-3",
            }

            with patch.object(provider, "check_cache", return_value=cached_data):
                response = provider.complete("system", "user")

            assert response.cached is True


class TestAutoContentAPIProviderComplete:
    """Tests for AutoContentAPIProvider.complete()."""

    def test_complete_returns_cached_response(self):
        """Test complete returns cached response when available."""
        with patch.dict("os.environ", {
            "AUTOCONTENTAPI_BASE_URL": "http://test",
            "AUTOCONTENTAPI_KEY": "test-key",
        }):
            provider = AutoContentAPIProvider()

            cached_data = {
                "content": '{"test": "cached"}',
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "model": "gpt-4o-mini",
            }

            with patch.object(provider, "check_cache", return_value=cached_data):
                response = provider.complete("system", "user")

            assert response.cached is True


class TestAllProvidersCanBeInstantiated:
    """Tests verifying all providers can be instantiated correctly."""

    def test_openai_provider_with_defaults(self):
        """Test OpenAIProvider initializes with default values."""
        with patch.dict("os.environ", {
            "OPENAI_API_KEY": "test-key",
            "LLM_MODEL": "gpt-4o-mini",
            "LLM_MAX_TOKENS": "4000",
            "LLM_TIMEOUT_SECONDS": "90",
        }):
            provider = OpenAIProvider()

            assert provider.model == "gpt-4o-mini"
            assert provider.max_tokens == 4000
            assert provider.timeout == 90

    def test_google_provider_with_defaults(self):
        """Test GoogleGeminiProvider initializes with default values."""
        with patch.dict("os.environ", {
            "GOOGLE_API_KEY": "test-key",
            "GOOGLE_MODEL": "gemini-1.5-flash",
            "LLM_MAX_TOKENS": "4000",
        }):
            provider = GoogleGeminiProvider()

            assert provider.model == "gemini-1.5-flash"
            assert provider.max_tokens == 4000

    def test_runpod_provider_with_defaults(self):
        """Test RunPodProvider initializes with default values."""
        with patch.dict("os.environ", {
            "RUNPOD_API_BASE": "http://test",
            "RUNPOD_API_KEY": "test-key",
            "RUNPOD_MODEL": "llama-3",
            "LLM_MAX_TOKENS": "4000",
            "LLM_TIMEOUT_SECONDS": "90",
        }):
            provider = RunPodProvider()

            assert provider.model == "llama-3"
            assert provider.max_tokens == 4000

    def test_autocontentapi_provider_with_defaults(self):
        """Test AutoContentAPIProvider initializes with default values."""
        with patch.dict("os.environ", {
            "AUTOCONTENTAPI_BASE_URL": "http://test",
            "AUTOCONTENTAPI_KEY": "test-key",
            "AUTOCONTENTAPI_MODEL": "gpt-4o-mini",
            "LLM_MAX_TOKENS": "4000",
            "LLM_TIMEOUT_SECONDS": "90",
        }):
            provider = AutoContentAPIProvider()

            assert provider.model == "gpt-4o-mini"
            assert provider.max_tokens == 4000


class TestRunPodProviderAPICall:
    """Tests for RunPodProvider complete() API calls."""

    def test_complete_calls_runpod_api(self):
        """Test complete calls RunPod API when not cached."""
        with patch.dict("os.environ", {
            "RUNPOD_API_BASE": "http://test",
            "RUNPOD_API_KEY": "test-key",
            "RUNPOD_MODEL": "llama-3",
        }):
            provider = RunPodProvider()

            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = '{"test": "response"}'
            mock_response.usage.prompt_tokens = 50
            mock_response.usage.completion_tokens = 25

            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = mock_response

            with patch.object(provider, "check_cache", return_value=None):
                with patch.object(provider, "store_cache") as mock_store:
                    with patch("app.services.llm.provider.OpenAI", return_value=mock_client):
                        response = provider.complete("system", "user")

            assert response.cached is False
            assert response.content == '{"test": "response"}'
            assert response.prompt_tokens == 50
            assert response.provider == "runpod"
            mock_store.assert_called_once()


class TestAutoContentAPIProviderAPICall:
    """Tests for AutoContentAPIProvider complete() API calls."""

    def test_complete_calls_autocontentapi_api(self):
        """Test complete calls AutoContent API when not cached."""
        with patch.dict("os.environ", {
            "AUTOCONTENTAPI_BASE_URL": "http://test",
            "AUTOCONTENTAPI_KEY": "test-key",
            "AUTOCONTENTAPI_MODEL": "gpt-4o-mini",
        }):
            provider = AutoContentAPIProvider()

            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = '{"test": "response"}'
            mock_response.usage.prompt_tokens = 60
            mock_response.usage.completion_tokens = 30

            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = mock_response

            with patch.object(provider, "check_cache", return_value=None):
                with patch.object(provider, "store_cache") as mock_store:
                    with patch("app.services.llm.provider.OpenAI", return_value=mock_client):
                        response = provider.complete("system", "user")

            assert response.cached is False
            assert response.content == '{"test": "response"}'
            assert response.prompt_tokens == 60
            assert response.provider == "autocontentapi"
            mock_store.assert_called_once()


class TestGoogleGeminiProviderAPICall:
    """Tests for GoogleGeminiProvider complete() API calls."""

    def test_complete_returns_cached_response(self):
        """Test complete returns cached response when available."""
        with patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"}):
            provider = GoogleGeminiProvider()

            cached_data = {
                "content": '{"test": "cached"}',
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "model": "gemini-1.5-flash",
            }

            with patch.object(provider, "check_cache", return_value=cached_data):
                response = provider.complete("system", "user")

            assert response.cached is True
            assert response.content == '{"test": "cached"}'
            assert response.provider == "google"