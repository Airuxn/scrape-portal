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
async def test_claim_on_discover_consumes_slot():
    store = MemoryQuotaStore()
    quota = DailyWebsiteQuota(2, store=store)
    used, limit = await quota.claim("https://www.foo.be/")
    assert used == 1
    assert limit == 2
    assert await store.count(quota._utc_day()) == 1
    with pytest.raises(RateLimitExceeded, match="al gescand"):
        await quota.claim("https://foo.be/nl")


@pytest.mark.asyncio
async def test_scrape_ensure_allows_same_site_batches():
    store = MemoryQuotaStore()
    quota = DailyWebsiteQuota(2, store=store)
    await quota.claim("https://www.foo.be/")
    used1, _ = await quota.ensure("https://foo.be/")
    used2, _ = await quota.ensure("https://foo.be/contact")
    assert used1 == 1
    assert used2 == 1
    assert await store.count(quota._utc_day()) == 1


@pytest.mark.asyncio
async def test_scrape_ensure_claims_when_not_yet_discovered():
    store = MemoryQuotaStore()
    quota = DailyWebsiteQuota(2, store=store)
    used, _ = await quota.ensure("https://a.be/")
    assert used == 1
    with pytest.raises(RateLimitExceeded, match="al gescand"):
        await quota.claim("https://a.be/")


@pytest.mark.asyncio
async def test_distinct_sites_hit_limit():
    store = MemoryQuotaStore()
    quota = DailyWebsiteQuota(2, store=store)
    await quota.claim("https://a.be/")
    await quota.claim("https://b.be/")
    with pytest.raises(RateLimitExceeded, match="Daglimiet"):
        await quota.claim("https://c.be/")
    with pytest.raises(RateLimitExceeded, match="Daglimiet"):
        await quota.ensure("https://c.be/")


@pytest.mark.asyncio
async def test_memory_store_is_shared_across_quota_instances():
    store = MemoryQuotaStore()
    quota_a = DailyWebsiteQuota(2, store=store)
    quota_b = DailyWebsiteQuota(2, store=store)
    await quota_a.claim("https://a.be/")
    await quota_b.claim("https://b.be/")
    with pytest.raises(RateLimitExceeded):
        await quota_b.check_allowed("https://c.be/")


@pytest.mark.asyncio
async def test_over_limit_add_is_rolled_back():
    store = MemoryQuotaStore()
    day = "2099-01-01"
    # Pretend day is full without going through quota day helper: fill via store
    for i in range(2):
        await store.add(day, f"site{i}.be", 3600)
    quota = DailyWebsiteQuota(2, store=store)

    # Force same day key by patching
    quota._utc_day = lambda: day  # type: ignore[method-assign]
    with pytest.raises(RateLimitExceeded, match="Daglimiet"):
        await quota.claim("https://new.be/")
    assert await store.is_member(day, "new.be") is False
    assert await store.count(day) == 2


def test_memory_store_add_idempotent():
    async def run():
        store = MemoryQuotaStore()
        day = "2026-08-05"
        assert await store.add(day, "foo.be", 3600) is True
        assert await store.add(day, "foo.be", 3600) is False
        assert await store.count(day) == 1
        assert await store.is_member(day, "foo.be") is True
        await store.remove(day, "foo.be")
        assert await store.is_member(day, "foo.be") is False

    asyncio.run(run())
