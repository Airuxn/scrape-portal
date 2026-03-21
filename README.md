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

1. Push this repo to GitHub (`main`).
2. In [Vercel](https://vercel.com) → **Add New** → **Project** → **Import** this repo.
3. **Settings → General → Root Directory:** leave empty (`.`).
4. Open **Deployments** after a push. If the latest row is **red**, open it and read **Build Logs** / **Function Logs** — that message is why deploy “doesn’t work” (local `uvicorn` does not run that step).

**Do not** combine `builds` and `functions` in `vercel.json` — Vercel rejects that ([conflicting configuration](https://vercel.com/docs/errors/error-list#conflicting-functions-and-builds-configuration)). This repo uses only `functions` + `rewrites`.

**Python `api/index.py`:** exports **`app`** (ASGI via Mangum). We **do not** set `memory` / `maxDuration` in `vercel.json`: Vercel’s `functions` glob often fails with “unmatched pattern” for Python because validation runs before functions are registered. Set **Function max duration** in the Vercel project **Settings → Functions** if you need longer than 10s (Hobby) or 60s (Pro).

**Note:** Local runs use a normal server; Vercel runs **one Python serverless bundle** via `api/index.py` + Mangum. If the build fails, it’s usually `pip install`, Python version, or routing — fix using the log line.

5. **Limits:** long sitemap runs / big exports may **time out** (see `maxDuration` in `vercel.json`). For heavy use, use Railway/Render/VPS with `uvicorn`.

## License

Use only on sites you are allowed to scrape.
