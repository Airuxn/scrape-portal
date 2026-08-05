"""App-wide limits: daily unique-website quota (shared by all users on this instance)."""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse


class RateLimitExceeded(Exception):
    """Raised when a limit would be exceeded."""

    def __init__(self, detail: str, *, retry_after_seconds: int | None = None) -> None:
        self.detail = detail
        self.retry_after_seconds = retry_after_seconds
        super().__init__(detail)


def website_key(url: str) -> str:
    """Stable per-site key (apex host, no www)."""
    host = (urlparse(url).hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return host or url.lower()


class DailyWebsiteQuota:
    """
    Max N distinct websites per UTC calendar day, app-wide on this process.

  On serverless hosts each warm instance keeps its own counter; for a single
  global cap use Vercel KV / edge rate limiting in front of the app.
    """

    def __init__(self, max_per_day: int) -> None:
        self.max_per_day = max(1, max_per_day)
        self._lock = asyncio.Lock()
        self._day = ""
        self._sites: set[str] = set()

    def _utc_day(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _seconds_until_utc_midnight(self) -> int:
        now = datetime.now(timezone.utc)
        tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if now.hour or now.minute or now.second or now.microsecond:
            tomorrow = tomorrow + timedelta(days=1)
        return max(1, int((tomorrow - now).total_seconds()))

    async def _reset_day_if_needed(self) -> None:
        today = self._utc_day()
        if today != self._day:
            self._day = today
            self._sites.clear()

    async def check_allowed(self, url: str) -> None:
        """Fail fast before expensive work if a new site would exceed the cap."""
        key = website_key(url)
        async with self._lock:
            await self._reset_day_if_needed()
            if key in self._sites:
                return
            if len(self._sites) >= self.max_per_day:
                raise RateLimitExceeded(
                    (
                        f"Daglimiet bereikt: maximaal {self.max_per_day} verschillende websites "
                        "per dag voor deze applicatie. Dezelfde site opnieuw scrapen mag wel; "
                        "probeer morgen opnieuw voor een nieuwe site."
                    ),
                    retry_after_seconds=self._seconds_until_utc_midnight(),
                )

    async def commit(self, url: str) -> tuple[int, int]:
        """Record a successfully processed site (idempotent per day)."""
        key = website_key(url)
        async with self._lock:
            await self._reset_day_if_needed()
            self._sites.add(key)
            return len(self._sites), self.max_per_day

    async def reserve(self, url: str) -> tuple[int, int]:
        """Check + commit in one step (used by tests)."""
        await self.check_allowed(url)
        return await self.commit(url)


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
    """Check + commit in one step."""
    return await get_daily_website_quota().reserve(url)
