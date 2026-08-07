"""App-wide limits: daily unique-website quota (shared by all users on this deployment)."""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta, timezone

from quota_store import QuotaStore, get_quota_store, reset_quota_store_for_tests


class RateLimitExceeded(Exception):
    """Raised when a limit would be exceeded."""

    def __init__(self, detail: str, *, retry_after_seconds: int | None = None) -> None:
        self.detail = detail
        self.retry_after_seconds = retry_after_seconds
        super().__init__(detail)


def website_key(url: str) -> str:
    """Stable per-site key (apex host, no www)."""
    from urllib.parse import urlparse

    host = (urlparse(url).hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return host or url.lower()


def quota_backend_name() -> str:
    return get_quota_store().backend_name


class DailyWebsiteQuota:
    """
    Max N distinct websites per UTC calendar day, shared app-wide.

    Claiming happens when a site is discovered (scan start). Each site may be
    claimed at most once per UTC day. Scraping the same claimed site again the
    same day is allowed (batched export) and does not consume an extra slot.

    Uses Upstash / Vercel KV when `UPSTASH_REDIS_REST_*` or `KV_REST_API_*` are set.
    Otherwise falls back to in-memory state (not reliable on serverless).
    """

    def __init__(self, max_per_day: int, store: QuotaStore | None = None) -> None:
        self.max_per_day = max(1, max_per_day)
        self._store = store or get_quota_store()
        self._lock = asyncio.Lock()

    def _utc_day(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _seconds_until_utc_midnight(self) -> int:
        now = datetime.now(timezone.utc)
        tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if now.hour or now.minute or now.second or now.microsecond:
            tomorrow = tomorrow + timedelta(days=1)
        return max(1, int((tomorrow - now).total_seconds()))

    def _quota_ttl_seconds(self) -> int:
        """Keep keys until after UTC midnight so late requests still see today's set."""
        return self._seconds_until_utc_midnight() + 86_400

    def _already_msg(self) -> RateLimitExceeded:
        return RateLimitExceeded(
            (
                "Deze website is vandaag al gescand. "
                "Elke site mag maximaal één keer per dag (voor iedereen); probeer morgen opnieuw."
            ),
            retry_after_seconds=self._seconds_until_utc_midnight(),
        )

    def _limit_msg(self) -> RateLimitExceeded:
        return RateLimitExceeded(
            (
                f"Daglimiet bereikt: maximaal {self.max_per_day} websites "
                "per dag voor deze applicatie (voor iedereen). Probeer morgen opnieuw."
            ),
            retry_after_seconds=self._seconds_until_utc_midnight(),
        )

    async def check_allowed(self, url: str) -> None:
        """Fail fast if this site is already claimed or the daily cap is full."""
        key = website_key(url)
        day = self._utc_day()
        try:
            if await self._store.is_member(day, key):
                raise self._already_msg()
            count = await self._store.count(day)
            if count >= self.max_per_day:
                raise self._limit_msg()
        except RateLimitExceeded:
            raise
        except Exception as e:
            raise RateLimitExceeded(
                "Daglimiet kon niet worden gecontroleerd (opslag tijdelijk niet bereikbaar). "
                "Probeer het later opnieuw.",
                retry_after_seconds=60,
            ) from e

    async def _claim_new(self, url: str) -> tuple[int, int]:
        """Atomically claim a new site for today. Fails if already claimed or over cap."""
        key = website_key(url)
        day = self._utc_day()
        async with self._lock:
            try:
                added = await self._store.add(day, key, self._quota_ttl_seconds())
                if not added:
                    raise self._already_msg()
                used = await self._store.count(day)
                if used > self.max_per_day:
                    await self._store.remove(day, key)
                    raise self._limit_msg()
                return used, self.max_per_day
            except RateLimitExceeded:
                raise
            except Exception as e:
                raise RateLimitExceeded(
                    "Daglimiet kon niet worden bijgewerkt (opslag tijdelijk niet bereikbaar). "
                    "Probeer het later opnieuw.",
                    retry_after_seconds=60,
                ) from e

    async def claim(self, url: str) -> tuple[int, int]:
        """
        Claim a website for today (discover/scan).

        Fails if the site was already claimed today or the app-wide daily cap is full.
        """
        return await self._claim_new(url)

    async def ensure(self, url: str) -> tuple[int, int]:
        """
        Ensure the site is claimed for scrape/export.

        If already claimed today, succeed without double-counting (batch continuation).
        Otherwise claim it under the same once-per-day / max-N rules.
        """
        key = website_key(url)
        day = self._utc_day()
        try:
            if await self._store.is_member(day, key):
                used = await self._store.count(day)
                return used, self.max_per_day
        except RateLimitExceeded:
            raise
        except Exception as e:
            raise RateLimitExceeded(
                "Daglimiet kon niet worden gecontroleerd (opslag tijdelijk niet bereikbaar). "
                "Probeer het later opnieuw.",
                retry_after_seconds=60,
            ) from e
        return await self._claim_new(url)

    async def commit(self, url: str) -> tuple[int, int]:
        """Backward-compatible alias: claim a new site (reject if already used today)."""
        return await self.claim(url)

    async def reserve(self, url: str) -> tuple[int, int]:
        """Backward-compatible alias for scrape start: ensure claimed."""
        return await self.ensure(url)

    async def usage(self) -> tuple[int, int]:
        used = await self._store.count(self._utc_day())
        return used, self.max_per_day


_quota: DailyWebsiteQuota | None = None


def get_daily_website_quota() -> DailyWebsiteQuota:
    global _quota
    if _quota is None:
        limit = int(os.environ.get("SCRAPE_PORTAL_DAILY_WEBSITES", "20"))
        _quota = DailyWebsiteQuota(limit)
    return _quota


async def check_website_allowed(url: str) -> None:
    await get_daily_website_quota().check_allowed(url)


async def claim_website_slot(url: str) -> tuple[int, int]:
    return await get_daily_website_quota().claim(url)


async def commit_website_slot(url: str) -> tuple[int, int]:
    return await get_daily_website_quota().commit(url)


async def reserve_website_slot(url: str) -> tuple[int, int]:
    """Scrape path: allow same site again today (batches), claim if new."""
    return await get_daily_website_quota().ensure(url)


async def quota_usage() -> tuple[int, int]:
    return await get_daily_website_quota().usage()


def reset_daily_quota_for_tests() -> None:
    """Clear cached quota (unit/integration tests only)."""
    global _quota
    _quota = None
    reset_quota_store_for_tests()
