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
4. For strict global limits across all serverless instances, add Vercel KV or edge rate limiting in front of the app.

## Daily website quota

| Variable | Default | Description |
|----------|---------|-------------|
| `SCRAPE_PORTAL_DAILY_WEBSITES` | `20` | Max **distinct** websites per UTC calendar day for the entire app (all users share one counter per serverless instance) |

The same website (e.g. `www.example.be` and `example.be`) can be discovered and scraped again the same day without using another slot. Export batches for one site never consume extra slots.

On serverless hosts each warm instance keeps its own counter; for one hard global cap across all instances use edge/KV rate limiting in front of the app.

## Abuse Prevention

Third parties could still use a public deployment as an open scrape proxy within the daily quota. Lower `SCRAPE_PORTAL_DAILY_WEBSITES` or add deployment protection (Vercel authentication, private deployment) if that is a concern.
