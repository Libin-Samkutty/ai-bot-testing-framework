import json
from evaluators.base import BaseEvaluator

FAITHFULNESS_SYSTEM = """You are a RAG evaluation expert. You give binary PASS or FAIL verdicts.
{memory_block}{instructions_block}Respond with valid JSON only."""

FAITHFULNESS_USER = """CONTEXT (retrieved document): {context}
USER INPUT: {input}
BOT RESPONSE: {response}

Evaluate with PASS or FAIL:
- faithfulness: PASS if the response stays true to the context and doesn't add unsupported outside claims. FAIL if it introduces fabricated or contradictory information not in the context.
- grounding: PASS if the response clearly draws from and references the provided context. FAIL if it ignores the context entirely.

When FAIL, set failure_category to one of: Hallucination | Faithfulness | Relevance

Return JSON:
{{
  "faithfulness": {{"score": "PASS or FAIL", "reason": "<brief reason>", "failure_category": "<category or null>"}},
  "grounding":    {{"score": "PASS or FAIL", "reason": "<brief reason>", "failure_category": "<category or null>"}}
}}"""


class RAGEvaluator(BaseEvaluator):
    def evaluate(self, test_case: dict) -> dict:
        context = test_case.get("context", "").strip()

        if not context:
            return {
                "faithfulness": {"score": "N/A", "reason": "No context provided", "failure_category": None, "method": "skipped"},
                "grounding": {"score": "N/A", "reason": "No context provided", "failure_category": None, "method": "skipped"},
            }

        system = FAITHFULNESS_SYSTEM.format(
            memory_block=self._memory_block(),
            instructions_block=self._instructions_block(),
        )
        prompt = FAITHFULNESS_USER.format(
            context=context,
            input=test_case["input"],
            response=test_case["bot_response"],
        )
        try:
            raw = self._judge(system, prompt)
            result = json.loads(raw)
            return {
                "faithfulness": {
                    "score":            result["faithfulness"]["score"],
                    "reason":           result["faithfulness"]["reason"],
                    "failure_category": result["faithfulness"].get("failure_category") if result["faithfulness"]["score"] == "FAIL" else None,
                    "method":           "llm-as-judge",
                },
                "grounding": {
                    "score":            result["grounding"]["score"],
                    "reason":           result["grounding"]["reason"],
                    "failure_category": result["grounding"].get("failure_category") if result["grounding"]["score"] == "FAIL" else None,
                    "method":           "llm-as-judge",
                },
            }
        except Exception as e:
            return {
                "faithfulness": {"score": "ERROR", "reason": str(e), "failure_category": None, "method": "llm-as-judge"},
                "grounding":    {"score": "ERROR", "reason": str(e), "failure_category": None, "method": "llm-as-judge"},
            }
