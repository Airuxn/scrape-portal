# Scrape Portal

FastAPI **Scrape Portal**: discover URLs (sitemap/crawl), filter paths, respect `robots.txt`, export page text as JSON.

## Local run

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8765
```

Optional: `SCRAPE_PORTAL_DELAY` — seconds between GETs during export (default `2`).

## Deploy on Vercel

1. Push this repo to GitHub.
2. In [Vercel](https://vercel.com), **Import** the repository (Python detected via `api/index.py` + `vercel.json`).
3. **Limits:** serverless functions have a **max duration** (Hobby: 10s; Pro: up to 60s with `maxDuration` in `vercel.json`). Large sitemap discovery and long JSON exports may **time out** on Vercel — for heavy use, run on a VPS, [Railway](https://railway.app), or [Render](https://render.com) with a normal long-lived process.

## License

Use only on sites you are allowed to scrape.
