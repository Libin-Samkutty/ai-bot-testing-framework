import asyncio
import logging
from abc import ABC, abstractmethod
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class BaseEvaluator(ABC):
    def __init__(
        self,
        async_client: AsyncOpenAI,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 512,
        memory: str = "",
        instructions: str = "",
        max_retries: int = 3,
        backoff_base: float = 2.0,
    ):
        self.async_client = async_client
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.memory = memory.strip()
        self.instructions = instructions.strip()
        self.max_retries = max_retries
        self.backoff_base = backoff_base

        # Token usage accumulated across all calls made by this evaluator instance
        self.usage = {"prompt_tokens": 0, "completion_tokens": 0, "calls": 0}
        # Lock for thread-safe usage updates in async context (created lazily inside event loop)
        self._usage_lock: asyncio.Lock = None

    def _memory_block(self) -> str:
        if not self.memory:
            return ""
        return f"\n--- BOT CONTEXT (use this to calibrate your evaluation) ---\n{self.memory}\n---\n\n"

    def _instructions_block(self) -> str:
        if not self.instructions:
            return ""
        return f"\n--- CUSTOM EVALUATION RULES ---\n{self.instructions}\n---\n\n"

    async def _async_judge(self, system_prompt: str, user_prompt: str) -> str:
        """Async LLM judge call with retry and thread-safe usage tracking."""
        if self._usage_lock is None:
            self._usage_lock = asyncio.Lock()
        last_exc = None
        for attempt in range(self.max_retries + 1):
            try:
                response = await self.async_client.chat.completions.create(
                    model=self.model,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user",   "content": user_prompt},
                    ],
                )
                async with self._usage_lock:
                    if response.usage:
                        self.usage["prompt_tokens"]     += response.usage.prompt_tokens
                        self.usage["completion_tokens"] += response.usage.completion_tokens
                        self.usage["calls"]             += 1
                return response.choices[0].message.content.strip()
            except Exception as e:
                last_exc = e
                if attempt < self.max_retries:
                    wait = self.backoff_base ** attempt
                    logger.warning(
                        f"[{self.__class__.__name__}] Async API call failed "
                        f"(attempt {attempt + 1}/{self.max_retries + 1}): {e}. "
                        f"Retrying in {wait:.1f}s..."
                    )
                    await asyncio.sleep(wait)
        raise last_exc

    def get_usage(self) -> dict:
        """Return a copy of the accumulated token usage for this evaluator."""
        return dict(self.usage)

    @abstractmethod
    async def async_evaluate(self, test_case: dict) -> dict:
        """
        Accepts a test_case dict with keys:
          test_id, input, expected_output, context, bot_response
        Returns a dict of metric_name -> {score, reason, failure_category, method}
        All scores must be: "PASS", "FAIL", "N/A", or "ERROR"
        """
        pass
