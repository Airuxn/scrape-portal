"""App-wide rate limiting (single shared bucket, not per IP or client)."""
from __future__ import annotations

import asyncio
import os
import time
from contextlib import asynccontextmanager

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class GlobalRateLimiter:
    """Token bucket shared by all requests to this deployment instance."""

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        self.max_requests = max(1, max_requests)
        self.window_seconds = max(1.0, window_seconds)
        self._lock = asyncio.Lock()
        self._timestamps: list[float] = []

    async def acquire(self) -> bool:
        async with self._lock:
            now = time.monotonic()
            cutoff = now - self.window_seconds
            self._timestamps = [t for t in self._timestamps if t > cutoff]
            if len(self._timestamps) >= self.max_requests:
                return False
            self._timestamps.append(now)
            return True

    @property
    def retry_after_seconds(self) -> int:
        return max(1, int(self.window_seconds))


_limiter: GlobalRateLimiter | None = None
_heavy_sem: asyncio.Semaphore | None = None
_HEAVY_SLOT_WAIT = float(os.environ.get("SCRAPE_PORTAL_HEAVY_WAIT", "10"))
_HEAVY_BUSY_MSG = (
    "De applicatie verwerkt al het maximum aantal taken. Probeer later opnieuw."
)


def get_rate_limiter() -> GlobalRateLimiter:
    global _limiter
    if _limiter is None:
        max_req = int(os.environ.get("SCRAPE_PORTAL_RATE_LIMIT", "30"))
        window = float(os.environ.get("SCRAPE_PORTAL_RATE_WINDOW", "60"))
        _limiter = GlobalRateLimiter(max_req, window)
    return _limiter


def get_heavy_semaphore() -> asyncio.Semaphore:
    """Limits concurrent discover/scrape jobs app-wide (not per IP)."""
    global _heavy_sem
    if _heavy_sem is None:
        slots = max(1, int(os.environ.get("SCRAPE_PORTAL_MAX_CONCURRENT", "6")))
        _heavy_sem = asyncio.Semaphore(slots)
    return _heavy_sem


class RateLimitExceeded(Exception):
    """Raised when a heavy job cannot acquire a concurrency slot."""

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


async def acquire_heavy_slot() -> None:
    """Wait briefly for a heavy-job slot or raise RateLimitExceeded."""
    heavy_sem = get_heavy_semaphore()
    try:
        await asyncio.wait_for(heavy_sem.acquire(), timeout=_HEAVY_SLOT_WAIT)
    except TimeoutError:
        raise RateLimitExceeded(_HEAVY_BUSY_MSG) from None


def release_heavy_slot() -> None:
    get_heavy_semaphore().release()


@asynccontextmanager
async def heavy_task_slot():
    """Acquire a heavy-job slot or raise RateLimitExceeded."""
    await acquire_heavy_slot()
    try:
        yield
    finally:
        release_heavy_slot()


class GlobalRateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method == "OPTIONS":
            return await call_next(request)

        limiter = get_rate_limiter()
        if not await limiter.acquire():
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Te veel verzoeken voor deze applicatie. Probeer later opnieuw.",
                },
                headers={"Retry-After": str(limiter.retry_after_seconds)},
            )
        return await call_next(request)
