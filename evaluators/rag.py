import json
from evaluators.base import BaseEvaluator

FAITHFULNESS_SYSTEM = """You are a RAG evaluation expert. You give binary PASS or FAIL verdicts using explicit checklists.
{memory_block}{instructions_block}
SCORING RULE: Check every criterion. If ANY criterion is FALSE → score is FAIL. Only if ALL are TRUE → score is PASS.
In the reason field, list the specific criteria that failed. If all passed, write "All checks passed."
Respond with valid JSON only. No extra text."""

FAITHFULNESS_USER = """CONTEXT (retrieved document): {context}
USER INPUT: {input}
BOT RESPONSE: {response}

Apply each checklist. FAIL if ANY criterion is false. PASS only if ALL are true.
When FAIL, set failure_category to one of: Hallucination | Faithfulness | Relevance

--- FAITHFULNESS CHECKLIST ---
(Does every claim in the response stay within what the context supports?)
1. Every factual claim in the response can be directly traced to a specific statement in the provided context
2. The response does not introduce external facts or knowledge that contradict or override the context
3. No claim in the response goes beyond what the context explicitly states or clearly entails
4. The context's tentative or qualified statements are not upgraded to definitive facts in the response
5. No examples, statistics, or details appear in the response that are absent from the context

--- GROUNDING CHECKLIST ---
(Does the response demonstrably use the provided context rather than ignoring it?)
1. Key facts in the response correspond to specific passages in the retrieved context
2. The response does not answer entirely from background knowledge while ignoring the context
3. If the context lacks information needed to fully answer, the response acknowledges this gap — it does not invent details to fill it
4. The response does not contradict specific facts that are clearly stated in the context

Return JSON:
{{
  "faithfulness": {{"score": "PASS or FAIL", "reason": "<list failed criteria or 'All checks passed'>", "failure_category": "<category or null>"}},
  "grounding":    {{"score": "PASS or FAIL", "reason": "<list failed criteria or 'All checks passed'>", "failure_category": "<category or null>"}}
}}"""


class RAGEvaluator(BaseEvaluator):
    async def async_evaluate(self, test_case: dict) -> dict:
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
            raw = await self._async_judge(system, prompt)
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
