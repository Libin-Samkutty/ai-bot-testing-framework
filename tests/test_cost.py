"""Tests for utils/cost.py — get_price_per_million, calculate_cost, format_cost_report."""
import pytest
from utils.cost import get_price_per_million, calculate_cost, format_cost_report


# ─── get_price_per_million ───────────────────────────────────────────────────

def test_known_model_uses_fallback_when_not_in_config():
    prices = get_price_per_million("gpt-4o", {})
    assert prices["input"] == 2.50
    assert prices["output"] == 10.00
    assert prices["unknown"] is False


def test_config_pricing_overrides_fallback():
    config = {"gpt-4o": {"input": 1.00, "output": 5.00}}
    prices = get_price_per_million("gpt-4o", config)
    assert prices["input"] == 1.00
    assert prices["output"] == 5.00
    assert prices["unknown"] is False


def test_unknown_model_returns_zero_with_flag():
    prices = get_price_per_million("some-unknown-model-xyz", {})
    assert prices["input"] == 0.0
    assert prices["output"] == 0.0
    assert prices["unknown"] is True


def test_none_config_treated_as_empty():
    prices = get_price_per_million("gpt-4o", None)
    assert prices["input"] == 2.50
    assert prices["unknown"] is False


def test_malformed_config_pricing_returns_zero():
    # Missing sub-keys
    prices = get_price_per_million("gpt-4o", {"gpt-4o": {"input": "bad_value"}})
    assert prices["input"] == 0.0
    assert prices["unknown"] is True


def test_gpt_4o_mini_fallback():
    prices = get_price_per_million("gpt-4o-mini", {})
    assert prices["input"] == 0.15
    assert prices["output"] == 0.60


# ─── calculate_cost ──────────────────────────────────────────────────────────

def test_calculate_cost_correct_arithmetic():
    # 1M input tokens at $2.50 + 1M output tokens at $10.00 = $12.50
    cost = calculate_cost(1_000_000, 1_000_000, "gpt-4o", {})
    assert cost["input_cost_usd"] == pytest.approx(2.50, rel=1e-4)
    assert cost["output_cost_usd"] == pytest.approx(10.00, rel=1e-4)
    assert cost["total_cost_usd"] == pytest.approx(12.50, rel=1e-4)


def test_calculate_cost_zero_tokens():
    cost = calculate_cost(0, 0, "gpt-4o", {})
    assert cost["total_cost_usd"] == 0.0


def test_calculate_cost_total_tokens_sum():
    cost = calculate_cost(500, 300, "gpt-4o", {})
    assert cost["total_tokens"] == 800


def test_calculate_cost_price_known_flag():
    cost = calculate_cost(100, 100, "gpt-4o", {})
    assert cost["price_known"] is True


def test_calculate_cost_price_known_false_for_unknown_model():
    cost = calculate_cost(100, 100, "unknown-model-xyz", {})
    assert cost["price_known"] is False
    assert cost["total_cost_usd"] == 0.0


def test_calculate_cost_small_amounts():
    # 1000 tokens at gpt-4o-mini: input $0.15/M → 1000/1M * 0.15 = $0.00000015 → rounds to small value
    cost = calculate_cost(1000, 500, "gpt-4o-mini", {})
    assert cost["total_cost_usd"] >= 0.0
    assert cost["prompt_tokens"] == 1000
    assert cost["completion_tokens"] == 500


# ─── format_cost_report ──────────────────────────────────────────────────────

def test_format_cost_report_returns_string():
    usage = {"quality": {"prompt_tokens": 1000, "completion_tokens": 500, "calls": 2}}
    report = format_cost_report(usage, "gpt-4o", {})
    assert isinstance(report, str)


def test_format_cost_report_contains_total():
    usage = {"quality": {"prompt_tokens": 1000, "completion_tokens": 500, "calls": 2}}
    report = format_cost_report(usage, "gpt-4o", {})
    assert "TOTAL" in report


def test_format_cost_report_contains_model_name():
    usage = {"quality": {"prompt_tokens": 1000, "completion_tokens": 500, "calls": 2}}
    report = format_cost_report(usage, "gpt-4o-mini", {})
    assert "gpt-4o-mini" in report


def test_format_cost_report_contains_evaluator_name():
    usage = {"safety": {"prompt_tokens": 200, "completion_tokens": 100, "calls": 1}}
    report = format_cost_report(usage, "gpt-4o", {})
    assert "safety" in report


def test_format_cost_report_unknown_model_shows_warning():
    usage = {"quality": {"prompt_tokens": 1000, "completion_tokens": 500, "calls": 2}}
    report = format_cost_report(usage, "unknown-model-xyz", {})
    assert "⚠️" in report or "Warning" in report or "not in pricing" in report


def test_format_cost_report_multiple_evaluators():
    usage = {
        "quality": {"prompt_tokens": 100, "completion_tokens": 50, "calls": 1},
        "safety":  {"prompt_tokens": 200, "completion_tokens": 80, "calls": 2},
    }
    report = format_cost_report(usage, "gpt-4o", {})
    assert "quality" in report
    assert "safety" in report
