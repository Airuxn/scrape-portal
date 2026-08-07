"""App-wide limits: daily unique-website quota (shared by all users on this deployment)."""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta, timezone

from quota_store import QuotaStore, get_quota_store


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
    Max N distinct websites scraped per UTC calendar day, shared app-wide.

    A site is counted only when a scrape starts (not on discover). Each site may
    be scraped at most once per UTC day.

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

    async def check_allowed(self, url: str) -> None:
        """Fail fast before discover/scrape if this site is blocked for today."""
        key = website_key(url)
        day = self._utc_day()
        try:
            if await self._store.is_member(day, key):
                raise RateLimitExceeded(
                    (
                        "Deze website is vandaag al gescraped. "
                        "Elke site mag maximaal één keer per dag; probeer morgen opnieuw."
                    ),
                    retry_after_seconds=self._seconds_until_utc_midnight(),
                )
            count = await self._store.count(day)
            if count >= self.max_per_day:
                raise RateLimitExceeded(
                    (
                        f"Daglimiet bereikt: maximaal {self.max_per_day} verschillende websites "
                        "per dag voor deze applicatie. Probeer morgen opnieuw voor een nieuwe site."
                    ),
                    retry_after_seconds=self._seconds_until_utc_midnight(),
                )
        except RateLimitExceeded:
            raise
        except Exception as e:
            raise RateLimitExceeded(
                "Daglimiet kon niet worden gecontroleerd (opslag tijdelijk niet bereikbaar). "
                "Probeer het later opnieuw.",
                retry_after_seconds=60,
            ) from e

    async def commit(self, url: str) -> tuple[int, int]:
        """Record that a scrape for this site has started (once per UTC day)."""
        key = website_key(url)
        day = self._utc_day()
        async with self._lock:
            try:
                if await self._store.is_member(day, key):
                    raise RateLimitExceeded(
                        (
                            "Deze website is vandaag al gescraped. "
                            "Elke site mag maximaal één keer per dag; probeer morgen opnieuw."
                        ),
                        retry_after_seconds=self._seconds_until_utc_midnight(),
                    )
                count = await self._store.count(day)
                if count >= self.max_per_day:
                    raise RateLimitExceeded(
                        (
                            f"Daglimiet bereikt: maximaal {self.max_per_day} verschillende websites "
                            "per dag voor deze applicatie. Probeer morgen opnieuw voor een nieuwe site."
                        ),
                        retry_after_seconds=self._seconds_until_utc_midnight(),
                    )
                await self._store.add(day, key, self._quota_ttl_seconds())
                used = await self._store.count(day)
                return used, self.max_per_day
            except RateLimitExceeded:
                raise
            except Exception as e:
                raise RateLimitExceeded(
                    "Daglimiet kon niet worden bijgewerkt (opslag tijdelijk niet bereikbaar). "
                    "Probeer het later opnieuw.",
                    retry_after_seconds=60,
                ) from e

    async def reserve(self, url: str) -> tuple[int, int]:
        """Check + commit in one step when a scrape starts."""
        return await self.commit(url)

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


async def commit_website_slot(url: str) -> tuple[int, int]:
    return await get_daily_website_quota().commit(url)


async def reserve_website_slot(url: str) -> tuple[int, int]:
    return await get_daily_website_quota().reserve(url)


async def quota_usage() -> tuple[int, int]:
    return await get_daily_website_quota().usage()


def reset_daily_quota_for_tests() -> None:
    """Clear cached quota (unit/integration tests only)."""
    global _quota
    _quota = None
    reset_quota_store_for_tests()
