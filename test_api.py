"""FastAPI route tests (validation, static routes, scrape stream shape)."""
from __future__ import annotations

import json

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_index_serves_ui():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")


def test_favicon_returns_no_content():
    assert client.get("/favicon.ico").status_code == 204


def test_discover_rejects_localhost():
    response = client.post("/api/discover", json={"url": "http://localhost/"})
    assert response.status_code == 400
    assert "niet toegestaan" in response.json()["detail"].lower()


def test_discover_rejects_invalid_scheme():
    response = client.post("/api/discover", json={"url": "file:///etc/passwd"})
    assert response.status_code == 400


def test_scrape_rejects_private_base_url():
    response = client.post(
        "/api/scrape",
        json={"base_url": "http://192.168.0.1/", "urls": ["http://192.168.0.1/page"]},
    )
    assert response.status_code == 400


def test_scrape_empty_urls_streams_ndjson():
    response = client.post(
        "/api/scrape",
        json={"base_url": "https://example.com", "urls": []},
    )
    assert response.status_code == 200
    assert "application/x-ndjson" in response.headers.get("content-type", "")

    lines = [line for line in response.text.strip().split("\n") if line]
    assert len(lines) == 2
    start = json.loads(lines[0])
    done = json.loads(lines[1])
    assert start["type"] == "start"
    assert start["total"] == 0
    assert done["type"] == "done"
    assert done["pages"] == []
