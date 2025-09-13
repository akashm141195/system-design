import asyncio
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Optional

try:
    import redis.asyncio as aioredis  # type: ignore
except Exception:  # pragma: no cover - optional dependency path
    aioredis = None

from .settings import settings


class CacheBackend:
    async def get(self, key: str) -> Optional[Any]:  # pragma: no cover - interface
        raise NotImplementedError

    async def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:  # pragma: no cover - interface
        raise NotImplementedError


@dataclass
class _Entry:
    value: Any
    expires_at: Optional[float]


class MemoryTTLCache(CacheBackend):
    def __init__(self, max_items: int = 1024):
        self._store: "OrderedDict[str, _Entry]" = OrderedDict()
        self._lock = asyncio.Lock()
        self._max_items = max_items

    def _evict_if_needed(self) -> None:
        while len(self._store) > self._max_items:
            self._store.popitem(last=False)

    def _purge_expired(self) -> None:
        now = time.time()
        keys_to_delete = [k for k, e in self._store.items() if e.expires_at is not None and e.expires_at <= now]
        for k in keys_to_delete:
            self._store.pop(k, None)

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            self._purge_expired()
            if key in self._store:
                entry = self._store.pop(key)
                # move to end for LRU behavior
                self._store[key] = entry
                return entry.value
            return None

    async def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        expires_at = time.time() + ttl_seconds if ttl_seconds else None
        async with self._lock:
            if key in self._store:
                self._store.pop(key)
            self._store[key] = _Entry(value=value, expires_at=expires_at)
            self._evict_if_needed()


class RedisCache(CacheBackend):
    def __init__(self, url: str):
        if aioredis is None:
            raise RuntimeError("redis.asyncio not available. Ensure 'redis' package is installed.")
        self._client = aioredis.from_url(url, decode_responses=True)

    async def get(self, key: str) -> Optional[Any]:
        return await self._client.get(key)

    async def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        if ttl_seconds:
            await self._client.set(key, value, ex=ttl_seconds)
        else:
            await self._client.set(key, value)


_cache: Optional[CacheBackend] = None


def get_cache() -> CacheBackend:
    global _cache
    if _cache is not None:
        return _cache
    if settings.cache_backend.lower() == "redis" and settings.redis_url:
        _cache = RedisCache(settings.redis_url)
    else:
        _cache = MemoryTTLCache()
    return _cache
