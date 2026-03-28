"""Tests for run_eval._apply_filters and _compute_exit_status."""
import sys
import os

# Allow importing from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from run_eval import _apply_filters, _compute_exit_status


# ─── Fixtures ────────────────────────────────────────────────────────────────

def make_test_cases():
    return [
        {"test_id": "tc_001", "input": "q1", "eval_types": ["quality", "safety"], "severity": "Critical"},
        {"test_id": "tc_002", "input": "q2", "eval_types": ["safety", "refusal"],  "severity": "Major"},
        {"test_id": "tc_003", "input": "q3", "eval_types": ["rag"],                "severity": "Minor"},
        {"test_id": "tc_004", "input": "q4", "eval_types": ["quality"],            "severity": ""},
    ]


def make_metric(score: str) -> dict:
    return {"score": score, "reason": "test", "failure_category": None, "method": "llm-as-judge"}


def make_result(test_id: str, severity: str, metrics: dict) -> dict:
    return {"test_id": test_id, "severity": severity, "metrics": metrics}


# ─── _apply_filters ──────────────────────────────────────────────────────────

def test_no_filters_returns_all():
    cases = make_test_cases()
    result = _apply_filters(cases)
    assert len(result) == 4


def test_filter_by_test_id_single():
    cases = make_test_cases()
    result = _apply_filters(cases, test_id_filter="tc_001")
    assert [tc["test_id"] for tc in result] == ["tc_001"]


def test_filter_by_test_id_multiple():
    cases = make_test_cases()
    result = _apply_filters(cases, test_id_filter="tc_001,tc_003")
    assert {tc["test_id"] for tc in result} == {"tc_001", "tc_003"}


def test_filter_by_test_id_nonexistent_returns_empty():
    cases = make_test_cases()
    result = _apply_filters(cases, test_id_filter="tc_999")
    assert result == []


def test_filter_by_severity_critical():
    cases = make_test_cases()
    result = _apply_filters(cases, severity_filter="Critical")
    assert all(tc["severity"] == "Critical" for tc in result)
    assert len(result) == 1


def test_filter_by_severity_multiple():
    cases = make_test_cases()
    result = _apply_filters(cases, severity_filter="Critical,Major")
    severities = {tc["severity"] for tc in result}
    assert severities == {"Critical", "Major"}


def test_filter_by_eval_type_narrows_types():
    cases = make_test_cases()
    result = _apply_filters(cases, eval_type_filter="safety")
    # tc_001 and tc_002 have safety; tc_003 and tc_004 do not
    assert len(result) == 2
    for tc in result:
        assert tc["eval_types"] == ["safety"]


def test_filter_by_eval_type_drops_test_with_no_match():
    cases = make_test_cases()
    result = _apply_filters(cases, eval_type_filter="rag")
    # Only tc_003 has rag
    assert len(result) == 1
    assert result[0]["test_id"] == "tc_003"


def test_filter_by_eval_type_multiple_types():
    cases = make_test_cases()
    result = _apply_filters(cases, eval_type_filter="quality,safety")
    # tc_001: both, tc_002: safety only, tc_004: quality only — all 3 survive
    assert len(result) == 3


def test_combined_filters():
    cases = make_test_cases()
    result = _apply_filters(cases, severity_filter="Critical", eval_type_filter="safety")
    # tc_001 is Critical and has safety
    assert len(result) == 1
    assert result[0]["test_id"] == "tc_001"
    assert result[0]["eval_types"] == ["safety"]


def test_filter_does_not_mutate_original():
    cases = make_test_cases()
    original_eval_types = [list(tc["eval_types"]) for tc in cases]
    _apply_filters(cases, eval_type_filter="safety")
    for i, tc in enumerate(cases):
        assert tc["eval_types"] == original_eval_types[i]


# ─── _compute_exit_status ────────────────────────────────────────────────────

def test_exit_0_when_no_thresholds():
    results = [make_result("tc_001", "Critical", {"relevance": make_metric("FAIL")})]
    code, _ = _compute_exit_status(results)
    assert code == 0


def test_exit_0_when_pass_rate_above_threshold():
    results = [
        make_result("tc_001", "", {"m1": make_metric("PASS")}),
        make_result("tc_002", "", {"m2": make_metric("PASS")}),
    ]
    code, _ = _compute_exit_status(results, min_pass_rate=0.8)
    assert code == 0


def test_exit_1_when_pass_rate_below_threshold():
    results = [
        make_result("tc_001", "", {"m1": make_metric("PASS")}),
        make_result("tc_002", "", {"m2": make_metric("FAIL")}),
        make_result("tc_003", "", {"m3": make_metric("FAIL")}),
        make_result("tc_004", "", {"m4": make_metric("FAIL")}),
    ]
    code, msg = _compute_exit_status(results, min_pass_rate=0.8)
    assert code == 1
    assert "25.0%" in msg or "0.25" in msg or "1/4" in msg


def test_exit_0_when_pass_rate_exactly_meets_threshold():
    results = [
        make_result("tc_001", "", {"m1": make_metric("PASS")}),
        make_result("tc_002", "", {"m2": make_metric("FAIL")}),
    ]
    # Pass rate = 0.5, threshold = 0.5 → should pass (not strictly less than)
    code, _ = _compute_exit_status(results, min_pass_rate=0.5)
    assert code == 0


def test_fail_on_critical_exit_1_when_critical_fails():
    results = [
        make_result("tc_001", "Critical", {"relevance": make_metric("FAIL")}),
    ]
    code, msg = _compute_exit_status(results, fail_on_critical=True)
    assert code == 1
    assert "tc_001" in msg


def test_fail_on_critical_exit_0_when_critical_passes():
    results = [
        make_result("tc_001", "Critical", {"relevance": make_metric("PASS")}),
        make_result("tc_002", "Major",    {"safety":    make_metric("FAIL")}),
    ]
    code, _ = _compute_exit_status(results, fail_on_critical=True)
    assert code == 0


def test_fail_on_critical_ignores_non_critical_fails():
    results = [
        make_result("tc_001", "Major", {"m1": make_metric("FAIL")}),
        make_result("tc_002", "Minor", {"m2": make_metric("FAIL")}),
    ]
    code, _ = _compute_exit_status(results, fail_on_critical=True)
    assert code == 0


def test_na_scores_are_not_counted():
    results = [
        make_result("tc_001", "", {"m_pass": make_metric("PASS"), "m_na": make_metric("N/A")}),
    ]
    code, msg = _compute_exit_status(results, min_pass_rate=1.0)
    # Only 1 scored metric (PASS), so pass rate = 1.0
    assert code == 0


def test_empty_results_pass_rate_zero():
    code, msg = _compute_exit_status([], min_pass_rate=0.5)
    # 0 / 0 → pass_rate = 0.0 → below threshold
    assert code == 1
