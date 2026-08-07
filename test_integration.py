"""Integration tests with mocked discovery/fetch (no live network)."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_discover_success_with_mocked_sitemap():
    urls = ["https://example.com/", "https://example.com/about"]
    with patch(
        "main.discover_sitemap_urls",
        new=AsyncMock(return_value=("https://example.com/", urls)),
    ):
        response = client.post(
            "/api/discover",
            json={"url": "https://example.com/", "mode": "sitemap"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["base_url"] == "https://example.com/"
    assert body["count"] == len(urls)
    assert all(item["selectable"] for item in body["urls"])


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
