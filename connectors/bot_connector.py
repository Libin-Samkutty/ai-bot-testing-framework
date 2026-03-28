import time
import asyncio
from abc import ABC, abstractmethod
import requests
from utils.bot_cache import BotResponseCache


class BotConnector(ABC):
    """Abstract base class. Implement this to connect your real bot."""

    @abstractmethod
    def get_response(self, user_input: str, context: str = "") -> str:
        pass

    async def async_get_response(self, user_input: str, context: str = "") -> str:
        """Async version of get_response(). Override in subclass for true async support."""
        # Default: run sync get_response in thread pool to avoid blocking
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.get_response, user_input, context)

    def get_response_timed(self, user_input: str, context: str = "") -> tuple:
        """Returns (response_text, latency_ms). Times the underlying get_response() call."""
        start = time.perf_counter()
        response = self.get_response(user_input, context)
        latency_ms = round((time.perf_counter() - start) * 1000, 1)
        return response, latency_ms

    async def async_get_response_timed(self, user_input: str, context: str = "") -> tuple:
        """Async version. Returns (response_text, latency_ms)."""
        start = time.perf_counter()
        response = await self.async_get_response(user_input, context)
        latency_ms = round((time.perf_counter() - start) * 1000, 1)
        return response, latency_ms

    async def async_get_response_timed_cached(
        self, user_input: str, context: str = "", cache_enabled: bool = True, cache_dir: str = "outputs/cache"
    ) -> tuple:
        """
        Async version with optional caching.
        Returns (response_text, latency_ms, was_cached).

        Parameters
        ----------
        user_input : str
            User's message/prompt
        context : str
            Optional context
        cache_enabled : bool
            Whether to use cache (default: True)
        cache_dir : str
            Cache directory path (default: outputs/cache)

        Returns
        -------
        tuple
            (response_text, latency_ms, was_cached)
        """
        if not cache_enabled:
            response, latency_ms = await self.async_get_response_timed(user_input, context)
            return response, latency_ms, False

        # Try cache first
        cache = BotResponseCache(cache_dir)
        model_params = self._get_model_params()
        system_prompt = getattr(self, "system_prompt", "")

        cached_response = cache.get(user_input, context, model_params, system_prompt)
        if cached_response:
            return cached_response, 0.0, True  # Return cached response with 0ms latency, was_cached=True

        # Not in cache, call API and cache result
        response, latency_ms = await self.async_get_response_timed(user_input, context)
        cache.set(user_input, context, model_params, response, system_prompt)
        return response, latency_ms, False

    def _get_model_params(self) -> dict:
        """Get model parameters for cache key. Override in subclasses."""
        return {}


class MockBotConnector(BotConnector):
    """
    Mock bot for framework testing.
    Replace with HTTPBotConnector or your own implementation.
    """

    MOCK_RESPONSES = {
        "default": "This is a mock response from the bot under test.",
        "bomb": "I'm sorry, I can't help with that.",
    }

    def get_response(self, user_input: str, context: str = "") -> str:
        lowered = user_input.lower()
        if any(w in lowered for w in ["bomb", "weapon", "kill", "attack"]):
            return self.MOCK_RESPONSES["bomb"]
        if context:
            return f"Based on the provided context: {context[:120]}... [mock answer to: {user_input}]"
        return self.MOCK_RESPONSES["default"]


class HTTPBotConnector(BotConnector):
    """
    Plug in your HTTP endpoint.
    Usage: HTTPBotConnector(url="https://your-bot/api/chat")
    """

    def __init__(self, url: str, headers: dict = None, input_key="message", output_key="response"):
        self.url = url
        self.headers = headers or {"Content-Type": "application/json"}
        self.input_key = input_key
        self.output_key = output_key

    def get_response(self, user_input: str, context: str = "") -> str:
        try:
            payload = {self.input_key: user_input}
            if context:
                payload["context"] = context
            resp = requests.post(self.url, json=payload, headers=self.headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            if self.output_key not in data:
                raise KeyError(f"Response missing expected key '{self.output_key}'")
            return data[self.output_key]
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Bot API error: {e}") from e
        except (ValueError, KeyError) as e:
            raise RuntimeError(f"Invalid bot API response: {e}") from e
