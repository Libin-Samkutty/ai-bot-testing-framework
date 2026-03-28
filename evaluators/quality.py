import json
from evaluators.base import BaseEvaluator

SYSTEM_PROMPT = """You are a strict AI quality evaluator. You give binary PASS or FAIL verdicts using explicit checklists.
{memory_block}{instructions_block}
SCORING RULE: Check every criterion in the checklist. If ANY criterion is FALSE → score is FAIL. Only if ALL criteria are TRUE → score is PASS.
In the reason field, list the specific criteria that failed (e.g. "Failed: criterion 2, criterion 4"). If all passed, write "All checks passed."
Always respond with valid JSON only. No extra text."""

USER_PROMPT_TEMPLATE = """Evaluate the following bot response against each checklist.

USER INPUT: {input}
EXPECTED OUTPUT (ground truth): {expected}
BOT RESPONSE: {response}

For each dimension, apply its checklist. FAIL if ANY criterion is false. PASS only if ALL are true.
When the score is FAIL, also return a failure_category chosen from:
  Hallucination | Faithfulness | Relevance | Boundary Violation | Accuracy | Incomplete | Appropriateness

--- RELEVANCE CHECKLIST ---
1. The response directly addresses the user's specific question or request (not a tangential topic)
2. All content in the response is relevant to the query — no unrelated asides or detours
3. The response does not evade, deflect, or answer a different (easier) question than what was asked
4. The scope of the response matches the scope of the question (no unexplained narrowing or broadening)

--- COHERENCE CHECKLIST ---
1. The response has a clear logical structure — ideas follow in a connected, natural order
2. There are no internal contradictions — the response does not make conflicting claims
3. Sentences and paragraphs connect smoothly with no jarring topic jumps
4. Terms and concepts are used consistently throughout (no contradictory restatements of the same idea)

--- ACCURACY CHECKLIST ---
Note: If no expected output is provided, evaluate all criteria against factual plausibility alone.
1. All factual claims are correct or consistent with the expected output
2. No statistics, dates, names, citations, or events are fabricated or clearly wrong
3. The response does not contradict the expected output on any key point
4. Any uncertainty or speculation is explicitly qualified — not presented as established fact

--- COMPLETENESS CHECKLIST ---
1. All distinct sub-questions or parts within the user's input are addressed
2. The response provides sufficient depth — not a surface-level answer to a complex question
3. The response does not cut off mid-thought or end abruptly
4. Important qualifications, caveats, or follow-up information a complete answer requires are not omitted

Return JSON in exactly this format:
{{
  "relevance":    {{"score": "PASS or FAIL", "reason": "<list failed criteria or 'All checks passed'>", "failure_category": "<category or null>"}},
  "coherence":    {{"score": "PASS or FAIL", "reason": "<list failed criteria or 'All checks passed'>", "failure_category": "<category or null>"}},
  "accuracy":     {{"score": "PASS or FAIL", "reason": "<list failed criteria or 'All checks passed'>", "failure_category": "<category or null>"}},
  "completeness": {{"score": "PASS or FAIL", "reason": "<list failed criteria or 'All checks passed'>", "failure_category": "<category or null>"}}
}}"""


class QualityEvaluator(BaseEvaluator):
    async def async_evaluate(self, test_case: dict) -> dict:
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
            raw = await self._async_judge(system, prompt)
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
                "relevance":    error,
                "coherence":    error,
                "accuracy":     error,
                "completeness": error,
            }
        except (KeyError, TypeError) as e:
            error = {"score": "ERROR", "reason": f"Malformed response: {str(e)[:100]}", "failure_category": None, "method": "llm-as-judge"}
            return {
                "relevance":    error,
                "coherence":    error,
                "accuracy":     error,
                "completeness": error,
            }
        except Exception as e:
            error = {"score": "ERROR", "reason": f"Evaluation error: {str(e)[:100]}", "failure_category": None, "method": "llm-as-judge"}
            return {
                "relevance":    error,
                "coherence":    error,
                "accuracy":     error,
                "completeness": error,
            }
