"""Tests for daily website quota (memory backend)."""
from __future__ import annotations

import asyncio

import pytest

from quota_store import MemoryQuotaStore, reset_quota_store_for_tests
from rate_limit import DailyWebsiteQuota, RateLimitExceeded, website_key


@pytest.fixture(autouse=True)
def _reset_store():
    reset_quota_store_for_tests()
    yield
    reset_quota_store_for_tests()


def test_website_key_normalizes_www():
    assert website_key("https://www.example.be/path") == "example.be"
    assert website_key("https://example.be/") == "example.be"


@pytest.mark.asyncio
async def test_same_site_does_not_consume_extra_slot():
    store = MemoryQuotaStore()
    quota = DailyWebsiteQuota(2, store=store)
    await quota.reserve("https://www.foo.be/")
    used1, _ = await quota.reserve("https://foo.be/nl")
    used2, _ = await quota.reserve("https://www.foo.be/contact")
    assert used1 == 1
    assert used2 == 1


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
