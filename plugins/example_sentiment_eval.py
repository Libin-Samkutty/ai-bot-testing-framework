"""
Example custom evaluator: Sentiment evaluation.

This evaluator checks if the bot response maintains an appropriate tone
for a medical assistant (professional, empathetic, not rude).

Usage:
  1. Copy this file to a custom evaluators directory
  2. Run: python run_eval.py --csv tests.csv --custom-eval-dir ./my_evaluators
  3. In your CSV, use eval_types: "sentiment" to use this evaluator
"""
import json
from evaluators.base import BaseEvaluator


SENTIMENT_SYSTEM = """You are a tone and sentiment analyzer for chatbot responses.
{memory_block}{instructions_block}
Respond with valid JSON only."""

SENTIMENT_USER = """Analyze the tone of this bot response:

USER INPUT: {input}
BOT RESPONSE: {response}

Evaluate:
- tone: PASS if the response is professional, helpful, and appropriate for a medical/support context.
        FAIL if the response is rude, dismissive, or inappropriate.
- empathy: PASS if the response shows understanding of the user's concern.
          FAIL if the response is cold or dismissive of the user's feelings.

Return JSON:
{{
  "tone": {{"score": "PASS or FAIL", "reason": "<brief reason>"}},
  "empathy": {{"score": "PASS or FAIL", "reason": "<brief reason>"}}
}}"""


class SentimentEvaluator(BaseEvaluator):
    """Custom evaluator for tone and empathy."""

    def evaluate(self, test_case: dict) -> dict:
        system = SENTIMENT_SYSTEM.format(
            memory_block=self._memory_block(),
            instructions_block=self._instructions_block(),
        )
        prompt = SENTIMENT_USER.format(
            input=test_case["input"],
            response=test_case["bot_response"],
        )

        try:
            raw = self._judge(system, prompt)
            result = json.loads(raw)

            return {
                "tone": {
                    "score": result["tone"]["score"],
                    "reason": result["tone"]["reason"],
                    "method": "llm-as-judge",
                },
                "empathy": {
                    "score": result["empathy"]["score"],
                    "reason": result["empathy"]["reason"],
                    "method": "llm-as-judge",
                },
            }
        except json.JSONDecodeError as e:
            error = {
                "score": "ERROR",
                "reason": f"JSON parse error: {str(e)[:100]}",
                "method": "llm-as-judge",
            }
            return {"tone": error, "empathy": error}
        except (KeyError, TypeError) as e:
            error = {
                "score": "ERROR",
                "reason": f"Malformed response: {str(e)[:100]}",
                "method": "llm-as-judge",
            }
            return {"tone": error, "empathy": error}
        except Exception as e:
            error = {
                "score": "ERROR",
                "reason": f"Evaluation error: {str(e)[:100]}",
                "method": "llm-as-judge",
            }
            return {"tone": error, "empathy": error}
