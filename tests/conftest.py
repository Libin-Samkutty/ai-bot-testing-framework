import pytest


@pytest.fixture
def tmp_cache_dir(tmp_path):
    """Provide a temporary cache directory that is cleaned up after each test."""
    return str(tmp_path / "cache")
