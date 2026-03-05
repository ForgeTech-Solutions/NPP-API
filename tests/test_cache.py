"""Tests for cache utility."""
import pytest
import time
from app.core.cache import TTLCache


class TestTTLCache:
    """Cache mechanism tests."""

    def test_set_and_get(self):
        """Test basic set/get."""
        c = TTLCache(default_ttl=60)
        c.set("key1", {"data": 123})
        assert c.get("key1") == {"data": 123}

    def test_expired_entry(self):
        """Test expired entries return None."""
        c = TTLCache(default_ttl=1)
        c.set("key1", "value", ttl=1)
        time.sleep(1.1)  # Wait for expiration
        assert c.get("key1") is None

    def test_invalidate_all(self):
        """Test clearing all cache entries."""
        c = TTLCache()
        c.set("a", 1)
        c.set("b", 2)
        c.invalidate()
        assert c.get("a") is None
        assert c.get("b") is None

    def test_invalidate_pattern(self):
        """Test invalidating entries by pattern."""
        c = TTLCache()
        c.set("stats:all", 1)
        c.set("stats:NOMENCLATURE", 2)
        c.set("dashboard", 3)
        c.invalidate("stats")
        assert c.get("stats:all") is None
        assert c.get("stats:NOMENCLATURE") is None
        assert c.get("dashboard") == 3  # Not affected

    def test_stats(self):
        """Test cache statistics."""
        c = TTLCache()
        c.set("key1", "val1")
        c.get("key1")   # hit
        c.get("key1")   # hit
        c.get("key2")   # miss
        stats = c.stats
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["entries"] == 1
