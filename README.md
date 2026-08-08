# Scrape Portal

Small web app to **collect public page text** from sites you're allowed to access. Give a **start URL** — it discovers candidate pages (sitemap and/or crawl), filters noisy paths, respects **`robots.txt`**, and exports selected pages as **JSON** (title + plain text per URL).

**Status:** stable · **Project age:** started March 2026 · **Stack:** FastAPI · Python 3.12+ · [MIT](LICENSE)

[![CI](https://github.com/Airuxn/scrape-portal/actions/workflows/ci.yml/badge.svg)](https://github.com/Airuxn/scrape-portal/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/Airuxn/scrape-portal/branch/main/graph/badge.svg)](https://codecov.io/gh/Airuxn/scrape-portal)
[![License](https://img.shields.io/github/license/Airuxn/scrape-portal)](LICENSE)

**Quality:** CI (Ruff, pip-audit, full unit-test suite) · Codecov · CodeQL · Dependabot · Vercel waits for CI + CodeQL before production and preview deploys

---

## Quick start

```bash
git clone https://github.com/Airuxn/scrape-portal.git
cd scrape-portal
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`. For Vercel, set Redis env vars (see below). Vercel waits for GitHub **CI + CodeQL** to pass before building production or preview deploys (`ignoreCommand` in `vercel.json`) — no extra GitHub secrets needed.

---

## What it does

1. **Discover** — Same-host URL list via sitemap (preferred) or controlled crawl.
2. **Filter & dedupe** — Path rules drop admin/news noise; multilingual duplicates collapse when heuristics match.
3. **Robots check** — URLs are selectable only if `robots.txt` allows fetch and origin matches the start URL.
4. **Export** — GET each selected page, strip boilerplate, stream NDJSON progress, assemble final JSON download.

Aimed at **open, public HTML** — no logins, no internal networks. Non-HTML or disallowed URLs are skipped or reported per row.

---

## Discovery modes

| Mode | Behaviour |
|------|------------|
| **Auto (recommended)** | Tries `/sitemap.xml` (and indexes) up to 5000 URLs; if fewer than 3 from sitemaps, falls back to crawl using *More options* depth/max. |
| **Sitemap** | Same sitemap logic; **max pages** caps the list. |
| **Crawl** | Breadth-first from start URL, same host only. |

---

## Export behaviour

- Same-host enforcement on every fetch; robots and path rules re-checked per URL.
- `SCRAPE_PORTAL_CONCURRENCY` (default **4**) — parallel workers.
- `SCRAPE_PORTAL_DELAY` — optional pause after each page (reduces HTTP 429).
- Large exports may batch in the browser on hosted deployments with time limits.

---

## Testing strategy

The test suite is split into three layers:

1. **Unit tests** — pure functions and small modules (`url_scope`, `robots_util`, `ssrf`, `safe_http`, `http_config`, `language_dedupe`, `discovery` helpers, `rate_limit`, `quota_store`, and `main` utilities). They use `unittest.mock` and `httpx.MockTransport` so they never touch the live internet.
2. **Integration tests** — FastAPI routes (`test_api.py`, `test_integration.py`) with mocked discovery and HTTP fetches to verify request/response shape, quota state, and same-host enforcement without real outbound requests.
3. **Manual / real-HTTP checks** — end-to-end scraping against live or responder-style sites. These validate real sitemap parsing, robots.txt fetching, and rate-limit behaviour from the serverless runtime. They are not part of the CI coverage number because they require a live HTTP target.

Codecov covers the unit-testable code: SSRF checks, safe redirect handling, rate limiting, quota, URL scope, discovery helpers, robots.txt helpers, and FastAPI route shape. Static UI assets (`public/**`) and the thin Vercel serverless entry point (`api/index.py`) are excluded from the coverage target because they are better validated by deploy smoke tests and manual UI review.

---

## What makes this different

- **Safety first, by default:** every URL is re-checked against SSRF rules, same-host enforcement, and `robots.txt` on every HTTP hop, not just at discovery time.
- **Shared daily quota:** one app-wide limit on distinct websites per UTC day, backed by Upstash/Vercel KV in production and falling back to memory locally.
- **Multilingual deduplication:** heuristic grouping of translated pages (`/nl/...`, `/fr/...`, `?lang=...`) so exports do not contain duplicate content across language variants.
- **Deployment-aware CI:** Vercel waits for GitHub CI and CodeQL before building production or preview deploys, without needing extra GitHub secrets.

---

## Lessons learned

- **Coverage is a signal, not a guarantee.** A high coverage number for SSRF and rate-limit logic is meaningful, but real scraping confidence still requires live HTTP tests because sitemap shapes, robots.txt quirks, and CDN behaviour vary across sites.
- **Mock at the transport layer.** Testing `httpx` with `MockTransport` keeps the redirect and error-handling paths realistic without relying on external network availability.
- **Stub DNS in tests.** `assert_public_http_url` resolves hostnames before checking IPs; a shared DNS stub removes flakiness from CI and local runs while still exercising the resolution code path.
- **Keep the serverless entry point thin.** `api/index.py` only adjusts `sys.path` and re-exports the app; it is not worth unit-testing but is critical to deploy correctly.

---

## Environment variables

| Variable | Description |
|----------|-------------|
| `SCRAPE_PORTAL_CONCURRENCY` | Parallel scrape workers (default `4`) |
| `SCRAPE_PORTAL_DELAY` | Seconds after each page (default `0`) |
| `SCRAPE_PORTAL_DAILY_WEBSITES` | Max distinct websites per UTC day (default `20`) |
| `UPSTASH_REDIS_REST_URL` / `KV_REST_API_URL` | Redis REST endpoint for shared daily quota (required on Vercel) |
| `UPSTASH_REDIS_REST_TOKEN` / `KV_REST_API_TOKEN` | Token for Redis REST |

---

## Security

No authentication on public deployments — SSRF protections and robots enforcement limit abuse. Use only on sites and data you're **allowed** to scrape (terms, contract, law).

See [SECURITY.md](SECURITY.md) for the security model, daily quota, and reporting.

---

## Repository layout

| Path | Description |
|------|-------------|
| `main.py` | FastAPI app + static UI |
| `discovery.py` | Sitemap and crawl discovery |
| `scraper.py` | HTML fetch and text extraction |
| `ssrf.py` / `safe_http.py` | SSRF-safe HTTP client |
| `rate_limit.py` / `quota_store.py` | Daily website quota |
| `test_*.py` | Unit and integration tests (CI) |

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Commit changes: `git commit -am 'Add feature'`
4. Push to branch: `git push origin feature-name`
5. Submit a Pull Request

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

Use only on sites and data you're **allowed** to scrape (terms, contract, law).

---

## 🙏 Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/) and [httpx](https://www.python-httpx.org/) — API and HTTP stack
- [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/) — HTML parsing
- [Vercel](https://vercel.com/) — serverless hosting

---

## 📞 Support

For support and questions:

- Create an issue on [GitHub](https://github.com/Airuxn/scrape-portal/issues)
- Security: see [SECURITY.md](SECURITY.md)

---

**⭐ If this project helped you, please give it a star!**
