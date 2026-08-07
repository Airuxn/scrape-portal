"""Tests for daily website quota (memory backend)."""
from __future__ import annotations

import asyncio

import pytest

from quota_store import MemoryQuotaStore
from rate_limit import DailyWebsiteQuota, RateLimitExceeded, reset_daily_quota_for_tests, website_key


@pytest.fixture(autouse=True)
def _reset_store():
    reset_daily_quota_for_tests()
    yield
    reset_daily_quota_for_tests()


def test_website_key_normalizes_www():
    assert website_key("https://www.example.be/path") == "example.be"
    assert website_key("https://example.be/") == "example.be"


@pytest.mark.asyncio
async def test_discover_same_site_before_scrape_does_not_consume_slot():
    store = MemoryQuotaStore()
    quota = DailyWebsiteQuota(2, store=store)
    await quota.check_allowed("https://www.foo.be/")
    await quota.check_allowed("https://foo.be/nl")
    assert await store.count(quota._utc_day()) == 0


@pytest.mark.asyncio
async def test_site_can_only_be_scraped_once_per_day():
    store = MemoryQuotaStore()
    quota = DailyWebsiteQuota(2, store=store)
    used1, _ = await quota.reserve("https://www.foo.be/")
    assert used1 == 1
    with pytest.raises(RateLimitExceeded, match="al gescraped"):
        await quota.reserve("https://foo.be/contact")


@pytest.mark.asyncio
async def test_distinct_sites_hit_limit():
    store = MemoryQuotaStore()
    quota = DailyWebsiteQuota(2, store=store)
    await quota.reserve("https://a.be/")
    await quota.reserve("https://b.be/")
    with pytest.raises(RateLimitExceeded):
        await quota.check_allowed("https://c.be/")


@pytest.mark.asyncio
async def test_memory_store_is_shared_across_quota_instances():
    store = MemoryQuotaStore()
    quota_a = DailyWebsiteQuota(2, store=store)
    quota_b = DailyWebsiteQuota(2, store=store)
    await quota_a.reserve("https://a.be/")
    await quota_b.reserve("https://b.be/")
    with pytest.raises(RateLimitExceeded):
        await quota_b.check_allowed("https://c.be/")


def test_memory_store_add_idempotent():
    async def run():
        store = MemoryQuotaStore()
        day = "2026-08-05"
        assert await store.add(day, "foo.be", 3600) is True
        assert await store.add(day, "foo.be", 3600) is False
        assert await store.count(day) == 1
        assert await store.is_member(day, "foo.be") is True

    asyncio.run(run())
