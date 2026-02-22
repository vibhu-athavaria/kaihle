"""
LLMProvider — unified interface for all LLM backends.

Usage in Celery tasks:
    from app.services.llm.provider import get_llm_provider
    llm = get_llm_provider()
    response = llm.complete(system_prompt, user_prompt)

Never instantiate a provider client directly in business logic.
"""

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

import redis

from app.core.config import settings

logger = logging.getLogger(__name__)

LLM_CACHE_KEY_PREFIX = "kaihle:llm_cache"
LLM_CACHE_TTL_SECONDS = 7 * 24 * 60 * 60


@dataclass
class LLMResponse:
    """Standard response from any LLM provider."""
    content: str
    prompt_tokens: int
    completion_tokens: int
    model: str
    provider: str
    cached: bool = False


class BaseLLMProvider:
    """Base class for all LLM providers."""

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> LLMResponse:
        """
        Send a completion request to the LLM.

        Args:
            system_prompt: System message for context
            user_prompt: User message with the actual request

        Returns:
            LLMResponse with content and token counts

        Raises:
            Exception: If the LLM call fails
        """
        raise NotImplementedError("Subclasses must implement complete()")

    def _get_redis_client(self) -> Optional[redis.Redis]:
        """Get Redis client for caching."""
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        try:
            return redis.from_url(redis_url, decode_responses=True)
        except Exception as e:
            logger.warning("Failed to connect to Redis for LLM caching: %s", e)
            return None

    def _generate_cache_key(self, prompt_type: str, system_prompt: str, user_prompt: str) -> str:
        """Generate a deterministic cache key for the prompt."""
        combined = system_prompt + user_prompt
        hash_value = hashlib.sha256(combined.encode()).hexdigest()[:32]
        return f"{LLM_CACHE_KEY_PREFIX}:{prompt_type}:{hash_value}"

    def check_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Check if a cached response exists."""
        client = self._get_redis_client()
        if not client:
            return None

        try:
            cached = client.get(cache_key)
            if cached:
                logger.info("LLM cache hit for key: %s", cache_key)
                return json.loads(cached)
            return None
        except Exception as e:
            logger.warning("Error checking LLM cache: %s", e)
            return None
        finally:
            client.close()

    def store_cache(self, cache_key: str, response: Dict[str, Any]) -> None:
        """Store response in cache."""
        client = self._get_redis_client()
        if not client:
            return

        try:
            client.setex(cache_key, LLM_CACHE_TTL_SECONDS, json.dumps(response))
            logger.info("Stored LLM response in cache: %s", cache_key)
        except Exception as e:
            logger.warning("Error storing LLM cache: %s", e)
        finally:
            client.close()


class RunPodProvider(BaseLLMProvider):
    """Uses OpenAI-compatible client pointed at RunPod endpoint."""

    def __init__(self):
        self.api_base = os.environ.get("RUNPOD_API_BASE")
        self.api_key = os.environ.get("RUNPOD_API_KEY")
        self.model = os.environ.get("RUNPOD_MODEL", "llama-3")
        self.max_tokens = int(os.environ.get("LLM_MAX_TOKENS", "4000"))
        self.timeout = int(os.environ.get("LLM_TIMEOUT_SECONDS", "90"))

        if not self.api_base or not self.api_key:
            raise ValueError("RUNPOD_API_BASE and RUNPOD_API_KEY must be set")

    def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        from openai import OpenAI

        cache_key = self._generate_cache_key("runpod", system_prompt, user_prompt)
        cached = self.check_cache(cache_key)
        if cached:
            return LLMResponse(
                content=cached["content"],
                prompt_tokens=cached.get("prompt_tokens", 0),
                completion_tokens=cached.get("completion_tokens", 0),
                model=cached.get("model", self.model),
                provider="runpod",
                cached=True,
            )

        client = OpenAI(
            base_url=self.api_base,
            api_key=self.api_key,
        )

        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=self.max_tokens,
            timeout=self.timeout,
        )

        content = response.choices[0].message.content
        prompt_tokens = response.usage.prompt_tokens if response.usage else 0
        completion_tokens = response.usage.completion_tokens if response.usage else 0

        self.store_cache(cache_key, {
            "content": content,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "model": self.model,
        })

        return LLMResponse(
            content=content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            model=self.model,
            provider="runpod",
            cached=False,
        )


class AutoContentAPIProvider(BaseLLMProvider):
    """Uses OpenAI-compatible client pointed at AutoContent API endpoint."""

    def __init__(self):
        self.api_base = os.environ.get("AUTOCONTENTAPI_BASE_URL")
        self.api_key = os.environ.get("AUTOCONTENTAPI_KEY")
        self.model = os.environ.get("AUTOCONTENTAPI_MODEL", "gpt-4o-mini")
        self.max_tokens = int(os.environ.get("LLM_MAX_TOKENS", "4000"))
        self.timeout = int(os.environ.get("LLM_TIMEOUT_SECONDS", "90"))

        if not self.api_base or not self.api_key:
            raise ValueError("AUTOCONTENTAPI_BASE_URL and AUTOCONTENTAPI_KEY must be set")

    def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        from openai import OpenAI

        cache_key = self._generate_cache_key("autocontentapi", system_prompt, user_prompt)
        cached = self.check_cache(cache_key)
        if cached:
            return LLMResponse(
                content=cached["content"],
                prompt_tokens=cached.get("prompt_tokens", 0),
                completion_tokens=cached.get("completion_tokens", 0),
                model=cached.get("model", self.model),
                provider="autocontentapi",
                cached=True,
            )

        client = OpenAI(
            base_url=self.api_base,
            api_key=self.api_key,
        )

        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=self.max_tokens,
            timeout=self.timeout,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        prompt_tokens = response.usage.prompt_tokens if response.usage else 0
        completion_tokens = response.usage.completion_tokens if response.usage else 0

        self.store_cache(cache_key, {
            "content": content,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "model": self.model,
        })

        return LLMResponse(
            content=content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            model=self.model,
            provider="autocontentapi",
            cached=False,
        )


class GoogleGeminiProvider(BaseLLMProvider):
    """Uses google-generativeai SDK."""

    def __init__(self):
        self.api_key = os.environ.get("GOOGLE_API_KEY")
        self.model = os.environ.get("GOOGLE_MODEL", "gemini-1.5-flash")
        self.max_tokens = int(os.environ.get("LLM_MAX_TOKENS", "4000"))

        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY must be set")

    def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        cache_key = self._generate_cache_key("google", system_prompt, user_prompt)
        cached = self.check_cache(cache_key)
        if cached:
            return LLMResponse(
                content=cached["content"],
                prompt_tokens=cached.get("prompt_tokens", 0),
                completion_tokens=cached.get("completion_tokens", 0),
                model=cached.get("model", self.model),
                provider="google",
                cached=True,
            )

        import google.generativeai as genai

        genai.configure(api_key=self.api_key)
        model = genai.GenerativeModel(
            self.model,
            system_instruction=system_prompt,
        )

        response = model.generate_content(
            user_prompt,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=self.max_tokens,
            ),
        )

        content = response.text
        prompt_tokens = response.usage_metadata.prompt_token_count if response.usage_metadata else 0
        completion_tokens = response.usage_metadata.candidates_token_count if response.usage_metadata else 0

        self.store_cache(cache_key, {
            "content": content,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "model": self.model,
        })

        return LLMResponse(
            content=content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            model=self.model,
            provider="google",
            cached=False,
        )


class OpenAIProvider(BaseLLMProvider):
    """Uses OpenAI API directly (for backwards compatibility)."""

    def __init__(self):
        self.api_key = os.environ.get("OPENAI_API_KEY")
        self.model = os.environ.get("LLM_MODEL", "gpt-4o-mini")
        self.max_tokens = int(os.environ.get("LLM_MAX_TOKENS", "4000"))
        self.timeout = int(os.environ.get("LLM_TIMEOUT_SECONDS", "90"))

        if not self.api_key:
            raise ValueError("OPENAI_API_KEY must be set")

    def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        from openai import OpenAI

        cache_key = self._generate_cache_key("openai", system_prompt, user_prompt)
        cached = self.check_cache(cache_key)
        if cached:
            return LLMResponse(
                content=cached["content"],
                prompt_tokens=cached.get("prompt_tokens", 0),
                completion_tokens=cached.get("completion_tokens", 0),
                model=cached.get("model", self.model),
                provider="openai",
                cached=True,
            )

        client = OpenAI(api_key=self.api_key)

        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=self.max_tokens,
            timeout=self.timeout,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        prompt_tokens = response.usage.prompt_tokens if response.usage else 0
        completion_tokens = response.usage.completion_tokens if response.usage else 0

        self.store_cache(cache_key, {
            "content": content,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "model": self.model,
        })

        return LLMResponse(
            content=content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            model=self.model,
            provider="openai",
            cached=False,
        )


def get_llm_provider() -> BaseLLMProvider:
    """
    Factory function. Reads LLM_PROVIDER from settings.
    Returns the correct provider instance.
    Raises ValueError for unknown provider values.
    """
    provider = settings.LLM_PROVIDER.lower()

    if provider == "runpod":
        return RunPodProvider()
    elif provider == "autocontentapi":
        return AutoContentAPIProvider()
    elif provider == "google":
        return GoogleGeminiProvider()
    elif provider == "openai":
        return OpenAIProvider()
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")