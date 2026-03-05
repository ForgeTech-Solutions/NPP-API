"""Simple in-memory TTL cache for API responses."""
import time
import logging
from typing import Any, Optional
from functools import wraps

logger = logging.getLogger("nomenclature.cache")


class TTLCache:
    """Thread-safe TTL cache with manual invalidation support."""
    
    def __init__(self, default_ttl: int = 300):
        """
        Args:
            default_ttl: Default time-to-live in seconds (default: 5 minutes).
        """
        self._store: dict[str, tuple[Any, float]] = {}
        self.default_ttl = default_ttl
        self._hits = 0
        self._misses = 0
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired."""
        if key in self._store:
            value, expires_at = self._store[key]
            if time.time() < expires_at:
                self._hits += 1
                return value
            else:
                del self._store[key]
        self._misses += 1
        return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set value in cache with TTL."""
        ttl = ttl or self.default_ttl
        self._store[key] = (value, time.time() + ttl)
    
    def invalidate(self, pattern: Optional[str] = None):
        """Invalidate cache entries. If pattern is None, clear all."""
        if pattern is None:
            self._store.clear()
            logger.info("Cache fully invalidated")
        else:
            keys_to_remove = [k for k in self._store if pattern in k]
            for k in keys_to_remove:
                del self._store[k]
            logger.info(f"Cache invalidated: {len(keys_to_remove)} entries matching '{pattern}'")
    
    @property
    def stats(self) -> dict:
        """Return cache statistics."""
        total = self._hits + self._misses
        return {
            "entries": len(self._store),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{(self._hits / total * 100):.1f}%" if total > 0 else "N/A",
        }


# Global cache instance (5-minute TTL)
cache = TTLCache(default_ttl=300)
