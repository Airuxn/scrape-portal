# Security Policy

## Reporting a Vulnerability

If you discover a security issue, please **do not** open a public GitHub issue.

Contact the maintainer privately via GitHub Security Advisories or direct message.

## Security Model

Scrape Portal is a **public scraping tool** intended for authorized use only:

- No authentication is built in — anyone who can reach the deployment can call `/api/discover` and `/api/scrape`.
- **Daily website quota** applies app-wide: max distinct websites per UTC day (`SCRAPE_PORTAL_DAILY_WEBSITES`, default `20`). Re-scraping the same site the same day does not use an extra slot.
- SSRF protections block private IPs, localhost, and cloud metadata endpoints; redirects are validated on every hop (`ssrf.py`, `safe_http.py`).
- URL path filtering excludes admin, news indexes, and similar paths (`url_scope.py`).
- `robots.txt` is checked before scraping.

## Before Deploying Publicly

1. Set `SCRAPE_PORTAL_DAILY_WEBSITES` if you need a different daily cap (default `20` unique sites per UTC day).
2. Use only on sites you are **allowed** to scrape (terms, contract, law).
3. Never commit `.env` files or deployment secrets.
4. For a **global** daily limit on serverless (Vercel), connect **Vercel KV** or **Upstash Redis** and set `KV_REST_API_URL` + `KV_REST_API_TOKEN` (or the `UPSTASH_REDIS_REST_*` equivalents). Without this, each server instance keeps its own in-memory counter and the limit can appear to reset between requests or browsers.

## Daily website quota

| Variable | Default | Description |
|----------|---------|-------------|
| `SCRAPE_PORTAL_DAILY_WEBSITES` | `20` | Max **distinct** websites per UTC calendar day for the entire app (all users share one counter per serverless instance) |

The same website (e.g. `www.example.be` and `example.be`) can be discovered and scraped again the same day without using another slot. Export batches for one site never consume extra slots.

On serverless hosts the in-memory fallback resets on cold starts and differs per warm instance — **not** per browser, but switching tabs or retrying can hit another instance so the limit looks broken. Use Vercel KV / Upstash (`KV_REST_API_*` or `UPSTASH_REDIS_REST_*`) for one shared counter.

## Abuse Prevention

Third parties could still use a public deployment as an open scrape proxy within the daily quota. Lower `SCRAPE_PORTAL_DAILY_WEBSITES` or add deployment protection (Vercel authentication, private deployment) if that is a concern.
