"""
Public web UI: discover URLs on a site (sitemap / crawl), respect robots.txt,
only allow scraping pages that return OK for anonymous GET and are allowed by robots.
"""
from __future__ import annotations

import asyncio
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Literal

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from url_scope import filter_urls_for_scraping, url_allowed_for_scraping
from discovery import discover_crawl_only, discover_sitemap_urls
from language_dedupe import dedupe_urls_by_language
from http_config import SSL_VERIFY
from robots_util import USER_AGENT, build_parser, can_fetch
from scraper import extract_text
from safe_http import safe_get
from rate_limit import RateLimitExceeded, reserve_website_slot
from ssrf import assert_public_http_url, same_site

app = FastAPI(title="Scrape Portal", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_executor = ThreadPoolExecutor(max_workers=4)

MAX_LIST_URLS = 5000
# Large exports: same order of magnitude as a full sitemap run.
MAX_SCRAPE_BATCH = 5000
MAX_BODY = 2_000_000
FETCH_RETRIES = 8
# Na elke geëmitteerde pagina (optioneel). Met parallelle downloads is dit minder zwaar dan vroeger.
# SCRAPE_PORTAL_CONCURRENCY: gelijktijdige GETs (default 4). Zet op 1 voor strikt sequentieel.
SCRAPE_DELAY_SECONDS = float(os.environ.get("SCRAPE_PORTAL_DELAY", "0"))
SCRAPE_CONCURRENCY = max(1, int(os.environ.get("SCRAPE_PORTAL_CONCURRENCY", "4")))


def _backoff_seconds(attempt: int, transient_http: bool) -> float:
    return min(120.0, 2.0**attempt + (5.0 if transient_http else 2.0))


class DiscoverIn(BaseModel):
    url: str = Field(..., description="Start-URL (homepage of site)")
    mode: Literal["auto", "sitemap", "crawl"] = "auto"
    crawl_depth: int = Field(2, ge=0, le=4)
    crawl_max_pages: int = Field(400, ge=10, le=5000)


class ScrapeIn(BaseModel):
    base_url: str
    urls: list[str] = Field(..., max_length=MAX_SCRAPE_BATCH)


def _robots_sync(base: str) -> Any:
    try:
        return build_parser(base)
    except Exception:
        return None


async def check_urls_with_robots(base_url: str, urls: list[str]) -> list[dict[str, Any]]:
    """
    Bepaal kiesbare URL’s alleen via zelfde host + robots.txt.
    Geen massale HEAD-requests (die gaven HTTP 429 op grote sites).
    Of een pagina echt publiek HTML is, zie je bij de export (GET + inhoud).
    """
    from urllib.parse import urlparse as up

    try:
        base_norm, _ = assert_public_http_url(base_url)
    except ValueError as e:
        raise HTTPException(400, str(e))

    allowed_host = (up(base_norm).hostname or "").lower()

    loop = asyncio.get_event_loop()
    rp = await loop.run_in_executor(_executor, _robots_sync, base_norm)

    out: list[dict[str, Any]] = []
    for u in urls:
        if not same_site(u, allowed_host):
            out.append(
                {
                    "url": u,
                    "selectable": False,
                    "reason": "andere host dan start-URL",
                }
            )
        elif not can_fetch(rp, u):
            out.append(
                {
                    "url": u,
                    "selectable": False,
                    "reason": "geblokkeerd door robots.txt",
                }
            )
        else:
            out.append(
                {
                    "url": u,
                    "selectable": True,
                    "reason": "ok (robots.txt staat toe)",
                }
            )
    return out


@app.post("/api/discover")
async def api_discover(body: DiscoverIn):
    try:
        base_input, _ = assert_public_http_url(body.url)
    except ValueError as e:
        raise HTTPException(400, str(e))

    try:
        used, limit = await reserve_website_slot(base_input)
    except RateLimitExceeded as e:
        headers = {}
        if e.retry_after_seconds is not None:
            headers["Retry-After"] = str(e.retry_after_seconds)
        raise HTTPException(429, e.detail, headers=headers)

    try:
        if body.mode == "crawl":
            base, urls = await discover_crawl_only(
                body.url, max_depth=body.crawl_depth, max_pages=min(body.crawl_max_pages, MAX_LIST_URLS)
            )
        elif body.mode == "sitemap":
            base, urls = await discover_sitemap_urls(body.url, max_urls=min(body.crawl_max_pages, MAX_LIST_URLS))
        else:
            base, urls = await discover_sitemap_urls(body.url, max_urls=MAX_LIST_URLS)
            if len(urls) < 3:
                base, urls = await discover_crawl_only(
                    body.url, max_depth=body.crawl_depth, max_pages=min(body.crawl_max_pages, MAX_LIST_URLS)
                )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(502, f"Ontdekken mislukt: {e!s}")

    from urllib.parse import urlparse as up

    site_host = up(base).hostname or ""
    urls = filter_urls_for_scraping(site_host, urls[:MAX_LIST_URLS])
    urls = dedupe_urls_by_language(urls)
    checked = await check_urls_with_robots(base, urls)
    return {
        "base_url": base,
        "count": len(checked),
        "urls": checked,
        "daily_websites_used": used,
        "daily_websites_limit": limit,
    }


@app.post("/api/scrape")
async def api_scrape(body: ScrapeIn):
    from urllib.parse import urlparse as up

    try:
        base_norm, _host = assert_public_http_url(body.base_url)
    except ValueError as e:
        raise HTTPException(400, str(e))

    try:
        await reserve_website_slot(base_norm)
    except RateLimitExceeded as e:
        headers = {}
        if e.retry_after_seconds is not None:
            headers["Retry-After"] = str(e.retry_after_seconds)
        raise HTTPException(429, e.detail, headers=headers)

    allowed_host = (up(base_norm).hostname or "").lower()
    urls = dedupe_urls_by_language(body.urls[:MAX_SCRAPE_BATCH])

    async def ndjson_stream():
        loop = asyncio.get_event_loop()
        rp = await loop.run_in_executor(_executor, _robots_sync, base_norm)
        out: list[dict[str, Any]] = []
        total = len(urls)
        yield (
            json.dumps(
                {
                    "type": "start",
                    "total": total,
                    "delay_seconds": SCRAPE_DELAY_SECONDS,
                    "concurrency": SCRAPE_CONCURRENCY,
                },
                ensure_ascii=False,
            )
            + "\n"
        ).encode("utf-8")

        http_headers = {"User-Agent": USER_AGENT}
        fetch_sem = asyncio.Semaphore(SCRAPE_CONCURRENCY)

        async def fetch_row(index: int, url: str) -> tuple[int, dict[str, Any]]:
            """1-based index; row is the same shape as before."""
            row: dict[str, Any]
            if not same_site(url, allowed_host):
                return index, {"url": url, "error": "andere host"}
            ok_scope, scope_reason = url_allowed_for_scraping(url, allowed_host)
            if not ok_scope:
                return index, {"url": url, "error": scope_reason}
            if not can_fetch(rp, url):
                return index, {"url": url, "error": "robots.txt staat dit niet toe"}
            async with fetch_sem:
                try:
                    r = None
                    for attempt in range(FETCH_RETRIES):
                        r = await safe_get(client, url)
                        if r.status_code in (429, 502, 503, 504) and attempt < FETCH_RETRIES - 1:
                            await asyncio.sleep(_backoff_seconds(attempt, True))
                            continue
                        break
                    assert r is not None
                    if r.status_code in (401, 403):
                        row = {"url": url, "error": "geen openbare toegang"}
                    else:
                        r.raise_for_status()
                        if len(r.content) > MAX_BODY:
                            row = {"url": url, "error": "pagina te groot"}
                        else:
                            ct = (r.headers.get("content-type") or "").lower()
                            if "html" not in ct:
                                row = {"url": url, "error": "geen HTML"}
                            else:
                                text, title = extract_text(r.text)
                                row = {
                                    "url": str(r.url),
                                    "title": title,
                                    "text": text,
                                }
                except Exception as e:
                    row = {"url": url, "error": str(e)[:200]}
            return index, row

        async with httpx.AsyncClient(
            headers=http_headers, timeout=45.0, follow_redirects=False, verify=SSL_VERIFY
        ) as client:
            if total == 0:
                pass
            else:
                tasks = {
                    asyncio.create_task(fetch_row(i + 1, url)): i + 1
                    for i, url in enumerate(urls)
                }
                buffer: dict[int, dict[str, Any]] = {}
                next_emit = 1
                pending = set(tasks.keys())

                while pending:
                    done, _ = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                    for task in done:
                        idx, row = await task
                        buffer[idx] = row
                        pending.discard(task)
                    while next_emit in buffer:
                        row = buffer.pop(next_emit)
                        out.append(row)
                        prog = {
                            "type": "progress",
                            "index": next_emit,
                            "total": total,
                            "url": urls[next_emit - 1],
                            "result": row,
                        }
                        yield (json.dumps(prog, ensure_ascii=False) + "\n").encode("utf-8")
                        if SCRAPE_DELAY_SECONDS > 0:
                            await asyncio.sleep(SCRAPE_DELAY_SECONDS)
                        next_emit += 1

        done = {"type": "done", "base_url": base_norm, "pages": out}
        yield (json.dumps(done, ensure_ascii=False) + "\n").encode("utf-8")

    return StreamingResponse(
        ndjson_stream(),
        media_type="application/x-ndjson; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


_BASE = Path(__file__).resolve().parent
_public_dir = _BASE / "public"
_static_dir = _public_dir / "static"

if _static_dir.is_dir():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


@app.get("/")
async def index():
    return FileResponse(_public_dir / "index.html")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    # Browsers vragen dit standaard aan; zonder route krijg je een 404 in de serverlog.
    return Response(status_code=204)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8765, reload=True)
