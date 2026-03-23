"""App-wide rate limiting (single shared bucket, not per IP or client)."""
from __future__ import annotations

import asyncio
import os
import time

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
        slots = max(1, int(os.environ.get("SCRAPE_PORTAL_MAX_CONCURRENT", "2")))
        _heavy_sem = asyncio.Semaphore(slots)
    return _heavy_sem


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
