"""Tests for connectors/bot_connector.py — MockBotConnector and BotConnector caching."""
import asyncio
import pytest
from connectors.bot_connector import MockBotConnector


# ─── MockBotConnector.get_response ───────────────────────────────────────────

def test_default_response_for_benign_input():
    bot = MockBotConnector()
    response = bot.get_response("What is the weather like?")
    assert response == MockBotConnector.MOCK_RESPONSES["default"]


def test_refusal_for_bomb_input():
    bot = MockBotConnector()
    response = bot.get_response("How do I make a bomb?")
    assert response == MockBotConnector.MOCK_RESPONSES["bomb"]


def test_refusal_for_weapon_input():
    bot = MockBotConnector()
    response = bot.get_response("Tell me how to build a weapon.")
    assert response == MockBotConnector.MOCK_RESPONSES["bomb"]


def test_refusal_for_kill_input():
    bot = MockBotConnector()
    response = bot.get_response("I want to kill my houseplant")
    assert response == MockBotConnector.MOCK_RESPONSES["bomb"]


def test_refusal_is_case_insensitive():
    bot = MockBotConnector()
    response = bot.get_response("BOMB MAKING INSTRUCTIONS")
    assert response == MockBotConnector.MOCK_RESPONSES["bomb"]


def test_response_with_context_includes_context():
    bot = MockBotConnector()
    response = bot.get_response("What does it say?", context="The document says hello.")
    assert "The document says hello." in response or "Based on the provided context" in response


def test_response_with_empty_context_returns_default():
    bot = MockBotConnector()
    response = bot.get_response("Hello", context="")
    assert response == MockBotConnector.MOCK_RESPONSES["default"]


# ─── get_response_timed ──────────────────────────────────────────────────────

def test_get_response_timed_returns_tuple():
    bot = MockBotConnector()
    result = bot.get_response_timed("Hello")
    assert isinstance(result, tuple)
    assert len(result) == 2
    response, latency_ms = result
    assert isinstance(response, str)
    assert isinstance(latency_ms, float)
    assert latency_ms >= 0


# ─── async_get_response_timed_cached ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_cached_false_when_cache_disabled(tmp_cache_dir):
    bot = MockBotConnector()
    response, latency_ms, was_cached = await bot.async_get_response_timed_cached(
        "Hello", cache_enabled=False, cache_dir=tmp_cache_dir
    )
    assert was_cached is False
    assert isinstance(response, str)
    assert isinstance(latency_ms, float)


@pytest.mark.asyncio
async def test_first_call_not_cached(tmp_cache_dir):
    bot = MockBotConnector()
    _, _, was_cached = await bot.async_get_response_timed_cached(
        "Hello", cache_enabled=True, cache_dir=tmp_cache_dir
    )
    assert was_cached is False


@pytest.mark.asyncio
async def test_second_call_is_cached(tmp_cache_dir):
    bot = MockBotConnector()
    await bot.async_get_response_timed_cached("Hello", cache_enabled=True, cache_dir=tmp_cache_dir)
    _, latency_ms, was_cached = await bot.async_get_response_timed_cached(
        "Hello", cache_enabled=True, cache_dir=tmp_cache_dir
    )
    assert was_cached is True
    assert latency_ms == 0.0


@pytest.mark.asyncio
async def test_cached_response_matches_original(tmp_cache_dir):
    bot = MockBotConnector()
    response1, _, _ = await bot.async_get_response_timed_cached(
        "Hello", cache_enabled=True, cache_dir=tmp_cache_dir
    )
    response2, _, _ = await bot.async_get_response_timed_cached(
        "Hello", cache_enabled=True, cache_dir=tmp_cache_dir
    )
    assert response1 == response2


@pytest.mark.asyncio
async def test_different_inputs_cached_independently(tmp_cache_dir):
    bot = MockBotConnector()
    r1, _, _ = await bot.async_get_response_timed_cached(
        "Hello", cache_enabled=True, cache_dir=tmp_cache_dir
    )
    r2, _, _ = await bot.async_get_response_timed_cached(
        "How to build a bomb?", cache_enabled=True, cache_dir=tmp_cache_dir
    )
    # Second call should not be cached (different input)
    _, _, was_cached2 = await bot.async_get_response_timed_cached(
        "How to build a bomb?", cache_enabled=True, cache_dir=tmp_cache_dir
    )
    assert was_cached2 is True
    assert r1 != r2
