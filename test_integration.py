"""Integration tests with mocked discovery/fetch (no live network)."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app
from rate_limit import reset_daily_quota_for_tests

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_store():
    reset_daily_quota_for_tests()
    yield
    reset_daily_quota_for_tests()


def test_discover_claims_site_and_blocks_second_discover():
    urls = ["https://example.com/", "https://example.com/about"]
    with patch(
        "main.discover_sitemap_urls",
        new=AsyncMock(return_value=("https://example.com/", urls)),
    ):
        first = client.post(
            "/api/discover",
            json={"url": "https://example.com/", "mode": "sitemap"},
        )
        second = client.post(
            "/api/discover",
            json={"url": "https://www.example.com/", "mode": "sitemap"},
        )

    assert first.status_code == 200
    body = first.json()
    assert body["base_url"] == "https://example.com/"
    assert body["count"] == len(urls)
    assert all(item["selectable"] for item in body["urls"])
    assert body["daily_websites_used"] == 1
    assert second.status_code == 429
    assert "al gescand" in second.json()["detail"].lower()


def test_scrape_allows_batched_same_site_after_claim():
    with patch("main.safe_get", new=AsyncMock()) as mock_get:
        mock_resp = AsyncMock()
        mock_resp.status_code = 200
        mock_resp.content = b"<html><title>t</title><body>hi</body></html>"
        mock_resp.headers = {"content-type": "text/html"}
        mock_resp.text = "<html><title>t</title><body>hi</body></html>"
        mock_resp.url = "https://example.com/"
        mock_resp.raise_for_status = lambda: None
        mock_get.return_value = mock_resp

        first = client.post(
            "/api/scrape",
            json={"base_url": "https://example.com/", "urls": ["https://example.com/"]},
        )
        assert first.status_code == 200

        second = client.post(
            "/api/scrape",
            json={"base_url": "https://example.com/", "urls": ["https://example.com/about"]},
        )
    assert second.status_code == 200


def test_scrape_rejects_offsite_url_in_batch():
    response = client.post(
        "/api/scrape",
        json={
            "base_url": "https://example.com/",
            "urls": ["https://evil.example/other"],
        },
    )
    assert response.status_code == 200
    payload = response.text
    assert "andere host" in payload or '"error"' in payload
