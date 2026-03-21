"""Sitemap discovery and optional BFS crawl (same host only)."""
from __future__ import annotations

from collections import deque
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from http_config import SSL_VERIFY
from ssrf import assert_public_http_url, same_site

USER_AGENT = "ScrapePortal/1.0 (+public research; respects robots.txt)"


async def _fetch(client: httpx.AsyncClient, url: str) -> str:
    r = await client.get(url, follow_redirects=True)
    r.raise_for_status()
    return r.text


def _parse_sitemap_xml(xml: str) -> tuple[list[str], bool]:
    """Return (loc urls, is_index)."""
    soup = BeautifulSoup(xml, "xml")
    root = soup.find(["sitemapindex", "urlset"])
    if root and root.name == "sitemapindex":
        out: list[str] = []
        for loc in soup.find_all("loc"):
            t = loc.get_text(strip=True)
            if t:
                out.append(t)
        return out, True
    urls: list[str] = []
    for loc in soup.find_all("loc"):
        t = loc.get_text(strip=True)
        if t and t not in urls:
            urls.append(t)
    return urls, False


async def collect_sitemap_urls(
    client: httpx.AsyncClient,
    start_sitemap: str,
    allowed_host: str,
    max_urls: int,
) -> list[str]:
    seen_sitemaps: set[str] = set()
    out: list[str] = []
    queue: deque[str] = deque([start_sitemap])

    while queue and len(out) < max_urls:
        sm = queue.popleft()
        if sm in seen_sitemaps:
            continue
        seen_sitemaps.add(sm)
        try:
            body = await _fetch(client, sm)
        except Exception:
            continue
        urls, is_index = _parse_sitemap_xml(body)
        if is_index:
            for u in urls:
                if u not in seen_sitemaps:
                    queue.append(u)
        else:
            for u in urls:
                if len(out) >= max_urls:
                    break
                try:
                    p = urlparse(u)
                    if p.scheme not in ("http", "https"):
                        continue
                    if not same_site(u, allowed_host):
                        continue
                except Exception:
                    continue
                out.append(u)
    return out


def _normalize_link(base: str, href: str, allowed_host: str) -> str | None:
    if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
        return None
    joined = urljoin(base, href)
    p = urlparse(joined)
    if p.scheme not in ("http", "https"):
        return None
    if not same_site(joined, allowed_host):
        return None
    # fragment-only normalized
    clean = joined.split("#")[0]
    if not clean or clean.endswith("/robots.txt"):
        return None
    return clean


async def crawl_links(
    client: httpx.AsyncClient,
    start_url: str,
    allowed_host: str,
    max_depth: int,
    max_pages: int,
) -> list[str]:
    """BFS on same host; depth 0 = only start page."""
    seen: set[str] = set()
    out: list[str] = []
    queue: deque[tuple[str, int]] = deque([(start_url, 0)])

    while queue and len(out) < max_pages:
        url, depth = queue.popleft()
        if url in seen:
            continue
        seen.add(url)
        try:
            r = await client.get(url, follow_redirects=True)
            if r.status_code != 200:
                continue
            ct = (r.headers.get("content-type") or "").lower()
            if "html" not in ct and "xml" not in ct:
                continue
            out.append(str(r.url))
            if depth >= max_depth:
                continue
            soup = BeautifulSoup(r.text, "lxml")
            for a in soup.find_all("a", href=True):
                nxt = _normalize_link(str(r.url), a["href"], allowed_host)
                if nxt and nxt not in seen:
                    queue.append((nxt, depth + 1))
        except Exception:
            continue
    return out


async def discover_sitemap_urls(base_url: str, max_urls: int = 5000) -> tuple[str, list[str]]:
    """Returns (normalized_base, list of page urls)."""
    base_norm, host = assert_public_http_url(base_url)
    sitemap_guesses = [
        urljoin(base_norm, "/sitemap.xml"),
        urljoin(base_norm, "/sitemap_index.xml"),
    ]
    headers = {"User-Agent": USER_AGENT}
    async with httpx.AsyncClient(
        headers=headers, timeout=30.0, follow_redirects=True, verify=SSL_VERIFY
    ) as client:
        urls: list[str] = []
        for sm in sitemap_guesses:
            try:
                urls = await collect_sitemap_urls(client, sm, host, max_urls)
                if urls:
                    break
            except Exception:
                continue
        if not urls:
            # Fallback: crawl homepage only for links (depth 1)
            urls = await crawl_links(client, base_norm, host, max_depth=1, max_pages=min(200, max_urls))
        # dedupe preserve order
        seen: set[str] = set()
        deduped: list[str] = []
        for u in urls:
            if u not in seen:
                seen.add(u)
                deduped.append(u)
        return base_norm, deduped[:max_urls]


async def discover_crawl_only(base_url: str, max_depth: int, max_pages: int) -> tuple[str, list[str]]:
    base_norm, host = assert_public_http_url(base_url)
    headers = {"User-Agent": USER_AGENT}
    async with httpx.AsyncClient(
        headers=headers, timeout=30.0, follow_redirects=True, verify=SSL_VERIFY
    ) as client:
        urls = await crawl_links(client, base_norm, host, max_depth=max_depth, max_pages=max_pages)
        return base_norm, urls
