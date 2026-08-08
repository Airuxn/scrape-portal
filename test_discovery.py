"""Tests for discovery helpers (discovery.py) using mock HTTP transports."""
from __future__ import annotations

import httpx
import pytest

from discovery import (
    _normalize_link,
    _parse_sitemap_xml,
    collect_sitemap_urls,
    crawl_links,
    discover_crawl_only,
    discover_sitemap_urls,
)


@pytest.fixture
def public_resolver(monkeypatch):
    """Make all URLs pass SSRF hostname resolution."""
    def _resolve(url):
        return url, "example.com"

    monkeypatch.setattr("discovery.assert_public_http_url", _resolve)
    monkeypatch.setattr("safe_http.assert_public_http_url", _resolve)


SITEMAP_URLSET = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/</loc></url>
  <url><loc>https://example.com/about</loc></url>
  <url><loc>https://example.com/contact</loc></url>
</urlset>
"""

SITEMAP_INDEX = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://example.com/sitemap-pages.xml</loc></sitemap>
</sitemapindex>
"""


def test_parse_sitemap_xml_urlset():
    urls, is_index = _parse_sitemap_xml(SITEMAP_URLSET)
    assert is_index is False
    assert urls == ["https://example.com/", "https://example.com/about", "https://example.com/contact"]


def test_parse_sitemap_xml_index():
    urls, is_index = _parse_sitemap_xml(SITEMAP_INDEX)
    assert is_index is True
    assert urls == ["https://example.com/sitemap-pages.xml"]


def test_parse_sitemap_xml_empty():
    urls, is_index = _parse_sitemap_xml("<html><body></body></html>")
    assert is_index is False
    assert urls == []


@pytest.mark.parametrize(
    "base,href,allowed,expected",
    [
        ("https://example.com/", "/about", "example.com", "https://example.com/about"),
        ("https://example.com/", "https://example.com/about", "example.com", "https://example.com/about"),
        ("https://example.com/", "https://other.com/", "example.com", None),
        ("https://example.com/", "mailto:a@example.com", "example.com", None),
        ("https://example.com/", "javascript:alert(1)", "example.com", None),
        ("https://example.com/", "#anchor", "example.com", None),
        ("https://example.com/", "/robots.txt", "example.com", None),
    ],
)
def test_normalize_link(base, href, allowed, expected):
    assert _normalize_link(base, href, allowed) == expected


@pytest.mark.asyncio
async def test_collect_sitemap_urls_from_urlset(public_resolver):
    def handler(request: httpx.Request):
        if request.url.path == "/sitemap.xml":
            return httpx.Response(200, text=SITEMAP_URLSET)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
        urls = await collect_sitemap_urls(client, "https://example.com/sitemap.xml", "example.com", 10)
    assert urls == ["https://example.com/", "https://example.com/about", "https://example.com/contact"]


@pytest.mark.asyncio
async def test_collect_sitemap_urls_follows_index(public_resolver):
    def handler(request: httpx.Request):
        if request.url.path == "/sitemap.xml":
            return httpx.Response(200, text=SITEMAP_INDEX)
        if request.url.path == "/sitemap-pages.xml":
            return httpx.Response(200, text=SITEMAP_URLSET)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
        urls = await collect_sitemap_urls(client, "https://example.com/sitemap.xml", "example.com", 10)
    assert urls == ["https://example.com/", "https://example.com/about", "https://example.com/contact"]


@pytest.mark.asyncio
async def test_collect_sitemap_urls_respects_max_urls(public_resolver):
    def handler(request: httpx.Request):
        return httpx.Response(200, text=SITEMAP_URLSET)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
        urls = await collect_sitemap_urls(client, "https://example.com/sitemap.xml", "example.com", 2)
    assert len(urls) == 2


@pytest.mark.asyncio
async def test_collect_sitemap_urls_skips_foreign_hosts(public_resolver):
    body = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/ok</loc></url>
  <url><loc>https://other.com/no</loc></url>
</urlset>
"""

    def handler(request: httpx.Request):
        return httpx.Response(200, text=body)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
        urls = await collect_sitemap_urls(client, "https://example.com/sitemap.xml", "example.com", 10)
    assert urls == ["https://example.com/ok"]


@pytest.mark.asyncio
async def test_crawl_links_bfs(public_resolver):
    pages = {
        "/": b'<html><body><a href="/a">a</a><a href="/b">b</a></body></html>',
        "/a": b'<html><body><a href="/b">b</a></body></html>',
        "/b": b'<html><body>end</body></html>',
    }

    def handler(request: httpx.Request):
        content = pages.get(request.url.path, b"")
        return httpx.Response(200, headers={"content-type": "text/html"}, content=content)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
        urls = await crawl_links(client, "https://example.com/", "example.com", max_depth=2, max_pages=10)
    assert "https://example.com/" in urls
    assert "https://example.com/a" in urls
    assert "https://example.com/b" in urls


@pytest.mark.asyncio
async def test_crawl_links_stops_at_max_pages(public_resolver):
    def handler(request: httpx.Request):
        return httpx.Response(200, headers={"content-type": "text/html"}, content=b"<html><body></body></html>")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
        urls = await crawl_links(client, "https://example.com/", "example.com", max_depth=1, max_pages=1)
    assert len(urls) == 1


@pytest.mark.asyncio
async def test_discover_sitemap_urls_falls_back_to_crawl(monkeypatch, public_resolver):
    # Sitemap returns 404, homepage returns HTML with one link.
    def handler(request: httpx.Request):
        if request.url.path in ("/sitemap.xml", "/sitemap_index.xml"):
            return httpx.Response(404)
        if request.url.path == "/":
            return httpx.Response(
                200,
                headers={"content-type": "text/html"},
                content=b'<html><body><a href="/fallback">fallback</a></body></html>',
            )
        if request.url.path == "/fallback":
            return httpx.Response(200, headers={"content-type": "text/html"}, content=b"<html><body></body></html>")
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)

    # Patch the httpx.AsyncClient created by discover_sitemap_urls to use our transport.
    class _Client(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs.pop("transport", None)
            super().__init__(transport=transport, *args, **kwargs)

    monkeypatch.setattr("httpx.AsyncClient", _Client)

    base, urls = await discover_sitemap_urls("https://example.com/", max_urls=10)
    assert base == "https://example.com/"
    assert urls == ["https://example.com/", "https://example.com/fallback"]


@pytest.mark.asyncio
async def test_discover_crawl_only(monkeypatch, public_resolver):
    def handler(request: httpx.Request):
        if request.url.path == "/":
            return httpx.Response(
                200,
                headers={"content-type": "text/html"},
                content=b'<html><body><a href="/page">page</a></body></html>',
            )
        if request.url.path == "/page":
            return httpx.Response(200, headers={"content-type": "text/html"}, content=b"<html><body></body></html>")
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)

    class _Client(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs.pop("transport", None)
            super().__init__(transport=transport, *args, **kwargs)

    monkeypatch.setattr("httpx.AsyncClient", _Client)

    base, urls = await discover_crawl_only("https://example.com/", max_depth=1, max_pages=10)
    assert base == "https://example.com/"
    assert "https://example.com/page" in urls
