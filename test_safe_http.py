"""Tests for safe HTTP redirect handling (safe_http.py)."""
from __future__ import annotations

import httpx
import pytest

from safe_http import MAX_REDIRECTS, safe_get


def _transport_with_redirects():
    """Return a MockTransport that walks through a small redirect chain."""
    calls = []

    def handler(request: httpx.Request):
        calls.append(str(request.url))
        path = request.url.path
        if path == "/a":
            return httpx.Response(302, headers={"location": "/b"})
        if path == "/b":
            return httpx.Response(301, headers={"location": "/c"})
        if path == "/c":
            return httpx.Response(200, text="final")
        return httpx.Response(404)

    return httpx.MockTransport(handler), calls


@pytest.mark.asyncio
async def test_safe_get_follows_redirects(monkeypatch):
    # Avoid DNS in the redirect chain.
    monkeypatch.setattr("safe_http.assert_public_http_url", lambda url: (url, "example.com"))
    transport, calls = _transport_with_redirects()
    async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
        r = await safe_get(client, "https://example.com/a")
    assert r.status_code == 200
    assert r.text == "final"
    assert calls == ["https://example.com/a", "https://example.com/b", "https://example.com/c"]


@pytest.mark.asyncio
async def test_safe_get_returns_non_redirect(monkeypatch):
    monkeypatch.setattr("safe_http.assert_public_http_url", lambda url: (url, "example.com"))

    def handler(request: httpx.Request):
        return httpx.Response(200, text="ok")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
        r = await safe_get(client, "https://example.com/ok")
    assert r.status_code == 200
    assert r.text == "ok"


@pytest.mark.asyncio
async def test_safe_get_returns_response_without_location(monkeypatch):
    monkeypatch.setattr("safe_http.assert_public_http_url", lambda url: (url, "example.com"))

    def handler(request: httpx.Request):
        return httpx.Response(301)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
        r = await safe_get(client, "https://example.com/no-location")
    assert r.status_code == 301


@pytest.mark.asyncio
async def test_safe_get_raises_on_too_many_redirects(monkeypatch):
    monkeypatch.setattr("safe_http.assert_public_http_url", lambda url: (url, "example.com"))

    def handler(request: httpx.Request):
        return httpx.Response(302, headers={"location": str(request.url)})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
        with pytest.raises(ValueError, match="redirects"):
            await safe_get(client, "https://example.com/loop")


@pytest.mark.asyncio
async def test_safe_get_validates_each_hop(monkeypatch):
    """assert_public_http_url is called on every redirect target."""
    visited = []

    def validate(url):
        visited.append(url)
        return url, "example.com"

    monkeypatch.setattr("safe_http.assert_public_http_url", validate)

    def handler(request: httpx.Request):
        path = request.url.path
        if path == "/a":
            return httpx.Response(302, headers={"location": "/b"})
        return httpx.Response(200, text="done")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
        await safe_get(client, "https://example.com/a")
    assert visited == ["https://example.com/a", "https://example.com/b"]


def test_max_redirects_constant():
    assert MAX_REDIRECTS == 8
