"""
Evaluation result caching to avoid re-running identical evaluations.
"""
import json
import hashlib
import os
from datetime import datetime
from pathlib import Path


class EvaluationCache:
    """Simple file-based cache for evaluation results."""

    def __init__(self, cache_dir: str = "outputs/cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "evaluation_cache.json"

    def _make_key(self, test_id: str, eval_type: str, bot_response: str) -> str:
        """Create cache key from test components."""
        content = f"{test_id}|{eval_type}|{bot_response}"
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
            print(f"Warning: Failed to save cache: {e}")

    def get(self, test_id: str, eval_type: str, bot_response: str) -> dict | None:
        """Retrieve cached result if exists."""
        key = self._make_key(test_id, eval_type, bot_response)
        cache = self._load_cache()
        if key in cache:
            cached = cache[key]
            # Return result and metadata
            return cached.get("result"), cached.get("timestamp")
        return None, None

    def set(self, test_id: str, eval_type: str, bot_response: str, result: dict) -> None:
        """Store evaluation result in cache."""
        key = self._make_key(test_id, eval_type, bot_response)
        cache = self._load_cache()
        cache[key] = {
            "test_id": test_id,
            "eval_type": eval_type,
            "result": result,
            "timestamp": datetime.now().isoformat(),
        }
        self._save_cache(cache)

    def clear(self) -> None:
        """Clear entire cache."""
        if self.cache_file.exists():
            self.cache_file.unlink()
            print("✓ Cache cleared")

    def stats(self) -> dict:
        """Get cache statistics."""
        cache = self._load_cache()
        return {
            "total_entries": len(cache),
            "cache_file": str(self.cache_file),
            "file_size_kb": self.cache_file.stat().st_size / 1024 if self.cache_file.exists() else 0,
        }
