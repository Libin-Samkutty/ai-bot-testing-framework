"""Tests for utils/bot_cache.py — BotResponseCache."""
import json
import pytest
from utils.bot_cache import BotResponseCache


def test_get_returns_none_on_miss(tmp_cache_dir):
    cache = BotResponseCache(tmp_cache_dir)
    result = cache.get("hello", "", {}, "")
    assert result is None


def test_set_then_get_returns_response(tmp_cache_dir):
    cache = BotResponseCache(tmp_cache_dir)
    cache.set("hello", "", {"model": "gpt-4o"}, "Hi there!", "You are helpful.")
    result = cache.get("hello", "", {"model": "gpt-4o"}, "You are helpful.")
    assert result == "Hi there!"


def test_key_is_deterministic(tmp_cache_dir):
    cache = BotResponseCache(tmp_cache_dir)
    k1 = cache._make_key("hello", "ctx", {"model": "x"}, "sys")
    k2 = cache._make_key("hello", "ctx", {"model": "x"}, "sys")
    assert k1 == k2


def test_different_inputs_produce_different_keys(tmp_cache_dir):
    cache = BotResponseCache(tmp_cache_dir)
    k1 = cache._make_key("hello", "", {}, "")
    k2 = cache._make_key("world", "", {}, "")
    assert k1 != k2


def test_different_model_params_produce_different_keys(tmp_cache_dir):
    cache = BotResponseCache(tmp_cache_dir)
    k1 = cache._make_key("hello", "", {"model": "gpt-4o"}, "")
    k2 = cache._make_key("hello", "", {"model": "gpt-4o-mini"}, "")
    assert k1 != k2


def test_model_params_key_is_order_independent(tmp_cache_dir):
    cache = BotResponseCache(tmp_cache_dir)
    k1 = cache._make_key("hi", "", {"a": 1, "b": 2}, "")
    k2 = cache._make_key("hi", "", {"b": 2, "a": 1}, "")
    assert k1 == k2


def test_different_system_prompts_produce_different_keys(tmp_cache_dir):
    cache = BotResponseCache(tmp_cache_dir)
    k1 = cache._make_key("hi", "", {}, "You are helpful.")
    k2 = cache._make_key("hi", "", {}, "You are strict.")
    assert k1 != k2


def test_different_contexts_produce_different_keys(tmp_cache_dir):
    cache = BotResponseCache(tmp_cache_dir)
    k1 = cache._make_key("hi", "context A", {}, "")
    k2 = cache._make_key("hi", "context B", {}, "")
    assert k1 != k2


def test_cache_miss_after_different_params(tmp_cache_dir):
    cache = BotResponseCache(tmp_cache_dir)
    cache.set("hello", "", {"model": "gpt-4o"}, "response A", "")
    result = cache.get("hello", "", {"model": "gpt-4o-mini"}, "")
    assert result is None


def test_stats_returns_entry_count(tmp_cache_dir):
    cache = BotResponseCache(tmp_cache_dir)
    cache.set("hello", "", {}, "resp1", "")
    cache.set("world", "", {}, "resp2", "")
    stats = cache.stats()
    assert stats["total_entries"] == 2


def test_stats_empty_cache(tmp_cache_dir):
    cache = BotResponseCache(tmp_cache_dir)
    stats = cache.stats()
    assert stats["total_entries"] == 0


def test_clear_removes_entries(tmp_cache_dir):
    cache = BotResponseCache(tmp_cache_dir)
    cache.set("hello", "", {}, "response", "")
    cache.clear()
    result = cache.get("hello", "", {}, "")
    assert result is None


def test_corrupt_json_falls_back_gracefully(tmp_cache_dir, tmp_path):
    cache = BotResponseCache(tmp_cache_dir)
    # Write corrupt JSON to the cache file
    import pathlib
    cache_file = pathlib.Path(tmp_cache_dir) / "bot_response_cache.json"
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text("NOT VALID JSON", encoding="utf-8")
    # Should not raise; should return None
    result = cache.get("hello", "", {}, "")
    assert result is None


def test_multiple_entries_independent(tmp_cache_dir):
    cache = BotResponseCache(tmp_cache_dir)
    cache.set("q1", "", {}, "answer1", "")
    cache.set("q2", "", {}, "answer2", "")
    assert cache.get("q1", "", {}, "") == "answer1"
    assert cache.get("q2", "", {}, "") == "answer2"
