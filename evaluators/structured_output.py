"""
StructuredOutputEvaluator — reusable base for bots that return structured JSON.

Provides two deterministic (no-LLM) metrics:
  json_valid    PASS/FAIL — response is parseable JSON containing all required fields
  label_match   PASS/FAIL — the "label" field matches the test case's expected_output

Subclass this and override _on_parse_failure() and/or _evaluate_extra() to add
domain-specific metrics on top of these two base checks.

Example
-------
    class MyEvaluator(StructuredOutputEvaluator):
        REQUIRED_FIELDS = ("label", "confidence")   # override if needed

        def _evaluate_extra(self, test_case, parsed, results):
            confidence = parsed.get("confidence", 0)
            if confidence >= 0.9:
                results["confidence_check"] = _make("PASS", f"confidence={confidence}")
            else:
                results["confidence_check"] = _make("FAIL", f"confidence={confidence} < 0.9")
"""

import asyncio
import json

from evaluators.base import BaseEvaluator


def _make(score: str, reason: str, method: str = "rule-based") -> dict:
    """Build a standard metric result dict."""
    return {"score": score, "reason": reason, "method": method}


class StructuredOutputEvaluator(BaseEvaluator):
    """
    Base evaluator for bots that return structured JSON responses.

    Makes no LLM/API calls — all checks are deterministic rule-based.
    Still inherits BaseEvaluator to satisfy the framework interface (token
    usage tracking, retry config, etc.) even though those features are unused.

    Class attributes
    ----------------
    REQUIRED_FIELDS : tuple[str, ...]
        JSON fields that must be present for json_valid to PASS.
        Default: ("label",). Override in subclasses as needed.
    """

    REQUIRED_FIELDS: tuple = ("label",)

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _parse_response(self, bot_response: str):
        """
        Parse the bot's JSON response and validate required fields.

        Returns
        -------
        (parsed_dict, None)   — on success
        (None, error_message) — on failure
        """
        try:
            parsed = json.loads(bot_response)
        except json.JSONDecodeError as e:
            return None, f"JSON decode error: {e}. Raw (first 200 chars): {bot_response[:200]!r}"

        if not isinstance(parsed, dict):
            return None, f"Expected a JSON object, got {type(parsed).__name__}"

        missing = [f for f in self.REQUIRED_FIELDS if f not in parsed]
        if missing:
            return None, f"Missing required field(s): {', '.join(missing)}"

        return parsed, None

    def _on_parse_failure(self, results: dict) -> None:
        """
        Hook called when JSON parsing fails, after json_valid and label_match
        are already set to FAIL/ERROR in results.

        Override in subclasses to add ERROR entries for any extra metrics
        so the report always has a consistent set of columns.
        """

    def _evaluate_extra(self, test_case: dict, parsed: dict, results: dict) -> None:
        """
        Hook called after json_valid and label_match are resolved successfully.

        Override in subclasses to compute additional domain-specific metrics.
        Mutate results in-place.
        """

    # ------------------------------------------------------------------ #
    # Public interface
    # ------------------------------------------------------------------ #

    def evaluate(self, test_case: dict) -> dict:
        """
        Run json_valid + label_match, then call _evaluate_extra() for
        any subclass-specific metrics.

        Parameters
        ----------
        test_case : dict
            Must contain at minimum:
              bot_response   (str) — raw response from the bot under test
              expected_output (str) — expected label value (may be empty)

        Returns
        -------
        dict of metric_name -> {score, reason, method}
        """
        bot_response = test_case.get("bot_response", "")
        expected_label = (test_case.get("expected_output") or "").strip()

        results: dict = {}

        # ── Metric 1: json_valid ──────────────────────────────────────── #
        parsed, error = self._parse_response(bot_response)

        if error:
            results["json_valid"] = _make("FAIL", error)
            results["label_match"] = _make(
                "ERROR", "Could not evaluate — JSON parsing failed upstream"
            )
            self._on_parse_failure(results)
            return results

        results["json_valid"] = _make("PASS", "Response is valid JSON with required fields")

        # ── Metric 2: label_match ─────────────────────────────────────── #
        actual_label = parsed.get("label", "").strip()

        if not expected_label:
            results["label_match"] = _make(
                "N/A",
                "No expected_output set for this test case — skipping label check",
            )
        elif actual_label == expected_label:
            results["label_match"] = _make(
                "PASS",
                f"label '{actual_label}' matches expected '{expected_label}'",
            )
        else:
            results["label_match"] = _make(
                "FAIL",
                f"Expected label '{expected_label}' but got '{actual_label}'",
            )

        # ── Extra metrics (subclass hook) ─────────────────────────────── #
        self._evaluate_extra(test_case, parsed, results)

        return results

    async def async_evaluate(self, test_case: dict) -> dict:
        """Async wrapper. All checks are CPU-only so we offload to a thread."""
        return await asyncio.to_thread(self.evaluate, test_case)
