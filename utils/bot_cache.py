"""
Bot response caching to avoid re-calling the bot API for identical inputs.
"""
import json
import hashlib
import os
from datetime import datetime
from pathlib import Path


class BotResponseCache:
    """Simple file-based cache for bot responses."""

    def __init__(self, cache_dir: str = "outputs/cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "bot_response_cache.json"

    def _make_key(self, user_input: str, context: str, model_params: dict, system_prompt: str) -> str:
        """Create cache key from bot call components."""
        content = f"{user_input}|{context}|{json.dumps(model_params, sort_keys=True)}|{system_prompt}"
        return hashlib.sha256(content.encode()).hexdigest()

    def _load_cache(self) -> dict:
        """Load cache from disk."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save_cache(self, data: dict) -> None:
        """Save cache to disk."""
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except IOError as e:
            print(f"Warning: Failed to save bot cache: {e}")

    def get(self, user_input: str, context: str, model_params: dict, system_prompt: str) -> str | None:
        """Retrieve cached bot response if exists. Returns response string or None."""
        key = self._make_key(user_input, context, model_params, system_prompt)
        cache = self._load_cache()
        if key in cache:
            return cache[key].get("response")
        return None

    def set(self, user_input: str, context: str, model_params: dict, response: str, system_prompt: str) -> None:
        """Store bot response in cache."""
        key = self._make_key(user_input, context, model_params, system_prompt)
        cache = self._load_cache()
        cache[key] = {
            "response": response,
            "model_params": model_params,
            "timestamp": datetime.now().isoformat(),
        }
        self._save_cache(cache)

    def clear(self) -> None:
        """Clear entire cache."""
        if self.cache_file.exists():
            self.cache_file.unlink()
            print("✓ Bot response cache cleared")

    def stats(self) -> dict:
        """Get cache statistics."""
        cache = self._load_cache()
        return {
            "total_entries": len(cache),
            "cache_file": str(self.cache_file),
            "file_size_kb": self.cache_file.stat().st_size / 1024 if self.cache_file.exists() else 0,
        }
