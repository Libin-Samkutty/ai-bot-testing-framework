import json
from evaluators.base import BaseEvaluator

SYSTEM_PROMPT = """You are a strict AI quality evaluator. You give binary PASS or FAIL verdicts.
{memory_block}{instructions_block}Always respond with valid JSON only. No extra text."""

USER_PROMPT_TEMPLATE = """Evaluate the following bot response.

USER INPUT: {input}
EXPECTED OUTPUT (ground truth): {expected}
BOT RESPONSE: {response}

For each dimension, return PASS or FAIL with a brief reason.
When the score is FAIL, also return a failure_category chosen from this taxonomy:
  Hallucination | Faithfulness | Relevance | Boundary Violation | Accuracy | Incomplete | Appropriateness

Dimensions:
- relevance: PASS if the response directly and clearly addresses the user's input. FAIL if it's off-topic or evasive.
- coherence: PASS if the response is logically structured and easy to follow. FAIL if it's rambling, contradictory, or confusing.
- accuracy: PASS if the response matches the expected output in meaning and correctness. FAIL if it contradicts or significantly misses it. If no expected output is provided, judge on factual plausibility.
- incompleteness: PASS if the response fully addresses all aspects of the question. FAIL if it only partially answers, skips important aspects, or cuts off early.

Return JSON in exactly this format:
{{
  "relevance":     {{"score": "PASS or FAIL", "reason": "<brief reason>", "failure_category": "<category or null>"}},
  "coherence":     {{"score": "PASS or FAIL", "reason": "<brief reason>", "failure_category": "<category or null>"}},
  "accuracy":      {{"score": "PASS or FAIL", "reason": "<brief reason>", "failure_category": "<category or null>"}},
  "incompleteness": {{"score": "PASS or FAIL", "reason": "<brief reason>", "failure_category": "<category or null>"}}
}}"""


class QualityEvaluator(BaseEvaluator):
    def evaluate(self, test_case: dict) -> dict:
        system = SYSTEM_PROMPT.format(
            memory_block=self._memory_block(),
            instructions_block=self._instructions_block(),
        )
        prompt = USER_PROMPT_TEMPLATE.format(
            input=test_case["input"],
            expected=test_case.get("expected_output", "Not provided"),
            response=test_case["bot_response"],
        )
        try:
            raw = self._judge(system, prompt)
            result = json.loads(raw)
            return {
                k: {
                    "score":            v["score"],
                    "reason":           v["reason"],
                    "failure_category": v.get("failure_category") if v["score"] == "FAIL" else None,
                    "method":           "llm-as-judge",
                }
                for k, v in result.items()
            }
        except json.JSONDecodeError as e:
            error = {"score": "ERROR", "reason": f"JSON parse error: {str(e)[:100]}", "failure_category": None, "method": "llm-as-judge"}
            return {
                "relevance":      error,
                "coherence":      error,
                "accuracy":       error,
                "incompleteness": error,
            }
        except (KeyError, TypeError) as e:
            error = {"score": "ERROR", "reason": f"Malformed response: {str(e)[:100]}", "failure_category": None, "method": "llm-as-judge"}
            return {
                "relevance":      error,
                "coherence":      error,
                "accuracy":       error,
                "incompleteness": error,
            }
        except Exception as e:
            error = {"score": "ERROR", "reason": f"Evaluation error: {str(e)[:100]}", "failure_category": None, "method": "llm-as-judge"}
            return {
                "relevance":      error,
                "coherence":      error,
                "accuracy":       error,
                "incompleteness": error,
            }
