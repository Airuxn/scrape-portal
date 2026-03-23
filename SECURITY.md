# Security Policy

## Reporting a Vulnerability

If you discover a security issue, please **do not** open a public GitHub issue.

Contact the maintainer privately via GitHub Security Advisories or direct message.

## Security Model

Scrape Portal is a **public scraping tool** intended for authorized use only:

- No authentication is built in — anyone who can reach the deployment can call `/api/discover` and `/api/scrape`.
- **App-wide rate limiting** applies to all traffic (not per IP): shared request budget and concurrent job cap (`rate_limit.py`).
- SSRF protections block private IPs, localhost, and cloud metadata endpoints; redirects are validated on every hop (`ssrf.py`, `safe_http.py`).
- URL path filtering excludes admin, news indexes, and similar paths (`url_scope.py`).
- `robots.txt` is checked before scraping.

## Before Deploying Publicly

1. Set `SCRAPE_PORTAL_ALLOWED_ORIGINS` to your domain(s) if you need cross-origin access (defaults to same-origin only).
2. Tune `SCRAPE_PORTAL_RATE_LIMIT`, `SCRAPE_PORTAL_RATE_WINDOW`, and `SCRAPE_PORTAL_MAX_CONCURRENT` for your hosting budget.
3. Use only on sites you are **allowed** to scrape (terms, contract, law).
4. Never commit `.env` files or deployment secrets.

## Rate limiting (global)

| Variable | Default | Description |
|----------|---------|-------------|
| `SCRAPE_PORTAL_RATE_LIMIT` | `30` | Max requests per window for the **entire app** (all users share one bucket per instance) |
| `SCRAPE_PORTAL_RATE_WINDOW` | `60` | Window length in seconds |
| `SCRAPE_PORTAL_MAX_CONCURRENT` | `2` | Max simultaneous discover/scrape jobs app-wide |

On serverless hosts each instance has its own counters; for a single global limit across all instances use edge/KV rate limiting in front of the app.

## Abuse Prevention

Third parties could still use a public deployment as an open scrape proxy within the configured limits. Lower the limits or add deployment protection (Vercel authentication, private deployment) if that is a concern.
