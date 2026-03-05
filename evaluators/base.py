from abc import ABC, abstractmethod
from openai import OpenAI


class BaseEvaluator(ABC):
    def __init__(
        self,
        client: OpenAI,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 512,
        memory: str = "",
        instructions: str = "",
    ):
        self.client = client
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.memory = memory.strip()
        self.instructions = instructions.strip()

        # Token usage accumulated across all calls made by this evaluator instance
        self.usage = {"prompt_tokens": 0, "completion_tokens": 0, "calls": 0}

    def _memory_block(self) -> str:
        if not self.memory:
            return ""
        return f"\n--- BOT CONTEXT (use this to calibrate your evaluation) ---\n{self.memory}\n---\n\n"

    def _instructions_block(self) -> str:
        if not self.instructions:
            return ""
        return f"\n--- CUSTOM EVALUATION RULES ---\n{self.instructions}\n---\n\n"

    def _judge(self, system_prompt: str, user_prompt: str) -> str:
        """Call the LLM judge and accumulate token usage."""
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
        )
        if response.usage:
            self.usage["prompt_tokens"]     += response.usage.prompt_tokens
            self.usage["completion_tokens"] += response.usage.completion_tokens
            self.usage["calls"]             += 1
        return response.choices[0].message.content.strip()

    def get_usage(self) -> dict:
        """Return a copy of the accumulated token usage for this evaluator."""
        return dict(self.usage)

    @abstractmethod
    def evaluate(self, test_case: dict) -> dict:
        """
        Accepts a test_case dict with keys:
          test_id, input, expected_output, context, bot_response
        Returns a dict of metric_name -> {score, reason, failure_category, method}
        All scores must be: "PASS", "FAIL", "N/A", or "ERROR"
        """
        pass
