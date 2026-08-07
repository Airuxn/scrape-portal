"""Persistent storage for the app-wide daily website quota."""
from __future__ import annotations

import os
from abc import ABC, abstractmethod


class QuotaStore(ABC):
    @property
    @abstractmethod
    def backend_name(self) -> str:
        """Short label for diagnostics (`redis` or `memory`)."""

    @abstractmethod
    async def is_member(self, day_key: str, site_key: str) -> bool:
        """Whether `site_key` was already counted for `day_key` (UTC date)."""

    @abstractmethod
    async def count(self, day_key: str) -> int:
        """Distinct websites already recorded for `day_key`."""

    @abstractmethod
    async def add(self, day_key: str, site_key: str, ttl_seconds: int) -> bool:
        """Record a site; return True when it was newly added."""

    @abstractmethod
    async def remove(self, day_key: str, site_key: str) -> None:
        """Remove a site from the day set (rollback after over-limit race)."""


class MemoryQuotaStore(QuotaStore):
    """Process-local store — resets on cold starts (serverless) or new workers."""

    def __init__(self) -> None:
        self._days: dict[str, set[str]] = {}

    @property
    def backend_name(self) -> str:
        return "memory"

    async def is_member(self, day_key: str, site_key: str) -> bool:
        return site_key in self._days.get(day_key, set())

    async def count(self, day_key: str) -> int:
        return len(self._days.get(day_key, set()))

    async def add(self, day_key: str, site_key: str, ttl_seconds: int) -> bool:
        _ = ttl_seconds
        bucket = self._days.setdefault(day_key, set())
        before = len(bucket)
        bucket.add(site_key)
        return len(bucket) > before

    async def remove(self, day_key: str, site_key: str) -> None:
        bucket = self._days.get(day_key)
        if bucket is not None:
            bucket.discard(site_key)


class RedisQuotaStore(QuotaStore):
    """Shared store via Upstash / Vercel KV REST API."""

    PREFIX = "scrape-portal:daily:"

    def __init__(self, url: str, token: str) -> None:
        from upstash_redis.asyncio import Redis

        self._redis = Redis(url=url, token=token)

    @property
    def backend_name(self) -> str:
        return "redis"

    def _key(self, day_key: str) -> str:
        return f"{self.PREFIX}{day_key}"

    async def is_member(self, day_key: str, site_key: str) -> bool:
        return bool(await self._redis.sismember(self._key(day_key), site_key))

    async def count(self, day_key: str) -> int:
        return int(await self._redis.scard(self._key(day_key)) or 0)

    async def add(self, day_key: str, site_key: str, ttl_seconds: int) -> bool:
        key = self._key(day_key)
        added = int(await self._redis.sadd(key, site_key) or 0)
        if added:
            await self._redis.expire(key, max(1, ttl_seconds))
        return added > 0

    async def remove(self, day_key: str, site_key: str) -> None:
        await self._redis.srem(self._key(day_key), site_key)


def redis_credentials() -> tuple[str, str] | None:
    url = (os.environ.get("UPSTASH_REDIS_REST_URL") or os.environ.get("KV_REST_API_URL") or "").strip()
    token = (
        os.environ.get("UPSTASH_REDIS_REST_TOKEN") or os.environ.get("KV_REST_API_TOKEN") or ""
    ).strip()
    if url and token:
        return url, token
    return None


_store: QuotaStore | None = None


def get_quota_store() -> QuotaStore:
    global _store
    if _store is None:
        creds = redis_credentials()
        if creds:
            _store = RedisQuotaStore(*creds)
        else:
            _store = MemoryQuotaStore()
    return _store


def reset_quota_store_for_tests() -> None:
    """Clear the cached store (unit tests only)."""
    global _store
    _store = None
