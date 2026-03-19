"""
Evaluation result caching to avoid re-running identical evaluations.
"""
import json
import hashlib
import os
from datetime import datetime
from pathlib import Path


class EvaluationCache:
    """File-backed in-memory cache for evaluation results.

    The cache is loaded from disk once at init, kept in memory during the run,
    and flushed back to disk via flush(). This avoids repeated file I/O and
    is safe to use with parallel (async) evaluation.
    """

    def __init__(self, cache_dir: str = "outputs/cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "evaluation_cache.json"
        self._memory: dict = self._load_cache()
        self._dirty: bool = False

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

    def get(self, test_id: str, eval_type: str, bot_response: str) -> tuple:
        """Retrieve cached result if exists."""
        key = self._make_key(test_id, eval_type, bot_response)
        if key in self._memory:
            cached = self._memory[key]
            return cached.get("result"), cached.get("timestamp")
        return None, None

    def set(self, test_id: str, eval_type: str, bot_response: str, result: dict) -> None:
        """Store evaluation result in memory (call flush() to persist to disk)."""
        key = self._make_key(test_id, eval_type, bot_response)
        self._memory[key] = {
            "test_id": test_id,
            "eval_type": eval_type,
            "result": result,
            "timestamp": datetime.now().isoformat(),
        }
        self._dirty = True

    def flush(self) -> None:
        """Write in-memory cache to disk. Call once at the end of a run."""
        if self._dirty:
            self._save_cache(self._memory)
            self._dirty = False

    def clear(self) -> None:
        """Clear entire cache from both memory and disk."""
        if self.cache_file.exists():
            self.cache_file.unlink()
            print("✓ Cache cleared")
        self._memory = {}
        self._dirty = False

    def stats(self) -> dict:
        """Get cache statistics."""
        return {
            "total_entries": len(self._memory),
            "cache_file": str(self.cache_file),
            "file_size_kb": self.cache_file.stat().st_size / 1024 if self.cache_file.exists() else 0,
        }
