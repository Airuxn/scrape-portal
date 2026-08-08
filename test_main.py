"""Tests for main.py utility functions (no live network)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from main import _backoff_seconds, _quota_http_error, _robots_sync, check_urls_with_robots
from rate_limit import RateLimitExceeded


@pytest.mark.parametrize(
    "attempt,transient,expected",
    [
        (0, False, 3.0),  # 2**0 + 2
        (1, False, 4.0),  # 2**1 + 2
        (2, True, 9.0),   # 2**2 + 5
        (10, False, 120.0),  # capped
    ],
)
def test_backoff_seconds(attempt, transient, expected):
    assert _backoff_seconds(attempt, transient) == expected


def test_quota_http_error_includes_retry_after():
    exc = RateLimitExceeded("busy", retry_after_seconds=123)
    http_exc = _quota_http_error(exc)
    assert http_exc.status_code == 429
    assert http_exc.detail == "busy"
    assert http_exc.headers.get("Retry-After") == "123"


def test_quota_http_error_without_retry_after():
    exc = RateLimitExceeded("busy")
    http_exc = _quota_http_error(exc)
    assert http_exc.status_code == 429
    assert http_exc.headers.get("Retry-After") is None


def test_robots_sync_returns_none_on_exception():
    with patch("main.build_parser", side_effect=RuntimeError("network down")):
        assert _robots_sync("https://example.com/") is None


def test_robots_sync_returns_parser():
    rp = MagicMock()
    with patch("main.build_parser", return_value=rp):
        assert _robots_sync("https://example.com/") is rp


@pytest.mark.asyncio
async def test_check_urls_with_robots():
    rp = MagicMock()
    rp.can_fetch = MagicMock(return_value=True)
    with patch("main._robots_sync", return_value=rp):
        with patch("main.assert_public_http_url", return_value=("https://example.com/", "example.com")):
            out = await check_urls_with_robots(
                "https://example.com/",
                ["https://example.com/", "https://other.com/secret"],
            )
    assert len(out) == 2
    assert out[0]["selectable"] is True
    assert out[1]["selectable"] is False
    assert out[1]["reason"] == "andere host dan start-URL"
