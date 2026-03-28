"""Tests for utils/cache.py — EvaluationCache."""
import pathlib
import pytest
from utils.cache import EvaluationCache


SAMPLE_RESULT = {
    "relevance": {"score": "PASS", "reason": "All checks passed.", "failure_category": None, "method": "llm-as-judge"}
}


def test_get_returns_none_tuple_on_miss(tmp_cache_dir):
    cache = EvaluationCache(tmp_cache_dir)
    result, timestamp = cache.get("tc_001", "quality", "some response", "abc123")
    assert result is None
    assert timestamp is None


def test_set_then_get_returns_result(tmp_cache_dir):
    cache = EvaluationCache(tmp_cache_dir)
    cache.set("tc_001", "quality", "some response", SAMPLE_RESULT, "abc123")
    result, timestamp = cache.get("tc_001", "quality", "some response", "abc123")
    assert result == SAMPLE_RESULT
    assert timestamp is not None


def test_cache_key_changes_with_test_id(tmp_cache_dir):
    cache = EvaluationCache(tmp_cache_dir)
    k1 = cache._make_key("tc_001", "quality", "resp", "hash1")
    k2 = cache._make_key("tc_002", "quality", "resp", "hash1")
    assert k1 != k2


def test_cache_key_changes_with_eval_type(tmp_cache_dir):
    cache = EvaluationCache(tmp_cache_dir)
    k1 = cache._make_key("tc_001", "quality", "resp", "hash1")
    k2 = cache._make_key("tc_001", "safety", "resp", "hash1")
    assert k1 != k2


def test_cache_key_changes_with_bot_response(tmp_cache_dir):
    cache = EvaluationCache(tmp_cache_dir)
    k1 = cache._make_key("tc_001", "quality", "response A", "hash1")
    k2 = cache._make_key("tc_001", "quality", "response B", "hash1")
    assert k1 != k2


def test_cache_key_changes_with_prompt_hash(tmp_cache_dir):
    cache = EvaluationCache(tmp_cache_dir)
    k1 = cache._make_key("tc_001", "quality", "resp", "hash_old")
    k2 = cache._make_key("tc_001", "quality", "resp", "hash_new")
    assert k1 != k2


def test_cache_miss_when_prompt_hash_differs(tmp_cache_dir):
    cache = EvaluationCache(tmp_cache_dir)
    cache.set("tc_001", "quality", "resp", SAMPLE_RESULT, "hash_v1")
    result, _ = cache.get("tc_001", "quality", "resp", "hash_v2")
    assert result is None


def test_multiple_entries_are_independent(tmp_cache_dir):
    cache = EvaluationCache(tmp_cache_dir)
    result_a = {"relevance": {"score": "PASS", "reason": "ok", "failure_category": None, "method": "llm-as-judge"}}
    result_b = {"safety": {"score": "FAIL", "reason": "bad", "failure_category": "Hallucination", "method": "llm-as-judge"}}
    cache.set("tc_001", "quality", "resp", result_a, "h1")
    cache.set("tc_002", "safety", "resp", result_b, "h2")
    a, _ = cache.get("tc_001", "quality", "resp", "h1")
    b, _ = cache.get("tc_002", "safety", "resp", "h2")
    assert a == result_a
    assert b == result_b


def test_clear_removes_all_entries(tmp_cache_dir):
    cache = EvaluationCache(tmp_cache_dir)
    cache.set("tc_001", "quality", "resp", SAMPLE_RESULT, "hash1")
    cache.clear()
    result, _ = cache.get("tc_001", "quality", "resp", "hash1")
    assert result is None


def test_stats_returns_entry_count(tmp_cache_dir):
    cache = EvaluationCache(tmp_cache_dir)
    cache.set("tc_001", "quality", "resp", SAMPLE_RESULT, "h1")
    cache.set("tc_002", "safety", "resp", SAMPLE_RESULT, "h2")
    stats = cache.stats()
    assert stats["total_entries"] == 2


def test_corrupt_json_falls_back_gracefully(tmp_cache_dir):
    cache = EvaluationCache(tmp_cache_dir)
    cache_file = pathlib.Path(tmp_cache_dir) / "evaluation_cache.json"
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text("BROKEN JSON {{{{", encoding="utf-8")
    result, timestamp = cache.get("tc_001", "quality", "resp", "hash1")
    assert result is None
    assert timestamp is None
