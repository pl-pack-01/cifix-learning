"""Tests for cifix.cache — local disk cache for log downloads."""

import json
import os
from unittest.mock import patch

import pytest

from cifix import cache


@pytest.fixture
def fake_cache_dir(tmp_path):
    """Redirect cache operations to a temporary directory."""
    with patch.object(cache, "get_cache_dir", return_value=tmp_path):
        yield tmp_path


SAMPLE_LOGS = [
    ("job1/step1.txt", "Step 1 output\nAll good"),
    ("job1/step2.txt", "Error: something failed\nexit code 1"),
]


class TestCacheKey:
    def test_safe_filename(self):
        key = cache._cache_key("owner/repo", "12345")
        assert "/" not in key
        assert key.endswith(".json")

    def test_different_repos_different_keys(self):
        k1 = cache._cache_key("owner/repo-a", "1")
        k2 = cache._cache_key("owner/repo-b", "1")
        assert k1 != k2

    def test_different_run_ids_different_keys(self):
        k1 = cache._cache_key("owner/repo", "1")
        k2 = cache._cache_key("owner/repo", "2")
        assert k1 != k2


class TestGetCacheDir:
    def test_returns_path_and_creates_it(self, tmp_path):
        base = str(tmp_path / "custom_cache")
        env_var = "LOCALAPPDATA" if os.name == "nt" else "XDG_CACHE_HOME"
        with patch.dict("os.environ", {env_var: base}):
            result = cache.get_cache_dir()
            assert result.exists()
            assert result.is_dir()
            assert "cifix" in str(result)


class TestPutAndGet:
    def test_roundtrip(self, fake_cache_dir):
        cache.put("owner/repo", "99", SAMPLE_LOGS)
        result = cache.get("owner/repo", "99")
        assert result == SAMPLE_LOGS

    def test_miss_returns_none(self, fake_cache_dir):
        assert cache.get("owner/repo", "nonexistent") is None

    def test_corrupted_file_returns_none(self, fake_cache_dir):
        key = cache._cache_key("owner/repo", "bad")
        (fake_cache_dir / key).write_text("not valid json", encoding="utf-8")
        assert cache.get("owner/repo", "bad") is None

    def test_corrupted_file_is_deleted(self, fake_cache_dir):
        key = cache._cache_key("owner/repo", "bad")
        path = fake_cache_dir / key
        path.write_text("{}", encoding="utf-8")
        cache.get("owner/repo", "bad")
        assert not path.exists()

    def test_preserves_tuple_structure(self, fake_cache_dir):
        cache.put("o/r", "1", SAMPLE_LOGS)
        result = cache.get("o/r", "1")
        for entry in result:
            assert isinstance(entry, tuple)
            assert len(entry) == 2


class TestClear:
    def test_clear_specific_entry(self, fake_cache_dir):
        cache.put("owner/repo", "1", SAMPLE_LOGS)
        cache.put("owner/repo", "2", SAMPLE_LOGS)
        removed = cache.clear("owner/repo", "1")
        assert removed == 1
        assert cache.get("owner/repo", "1") is None
        assert cache.get("owner/repo", "2") is not None

    def test_clear_all_for_repo(self, fake_cache_dir):
        cache.put("owner/repo", "1", SAMPLE_LOGS)
        cache.put("owner/repo", "2", SAMPLE_LOGS)
        cache.put("other/repo", "3", SAMPLE_LOGS)
        removed = cache.clear("owner/repo")
        assert removed == 2
        assert cache.get("other/repo", "3") is not None

    def test_clear_everything(self, fake_cache_dir):
        cache.put("owner/repo", "1", SAMPLE_LOGS)
        cache.put("other/repo", "2", SAMPLE_LOGS)
        removed = cache.clear()
        assert removed == 2
        assert list(fake_cache_dir.glob("*.json")) == []

    def test_clear_nonexistent_returns_zero(self, fake_cache_dir):
        assert cache.clear("no/repo", "999") == 0
