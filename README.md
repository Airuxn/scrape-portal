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

**Do not** combine `builds` and `functions` in `vercel.json` — Vercel rejects that ([conflicting configuration](https://vercel.com/docs/errors/error-list#conflicting-functions-and-builds-configuration)). This repo uses **`rewrites` only** (see `vercel.json`).

**Python `api/index.py`:** exports **`app`** (ASGI via Mangum).

**Note:** Local runs use a normal server; Vercel runs **one Python serverless bundle** via `api/index.py` + Mangum. If the build fails, it’s usually `pip install`, Python version, or routing — fix using the log line.

5. **Limits:** each **`POST /api/scrape`** is **one** serverless invocation with your project **Function max duration** (e.g. 300s). Very large selections are split in the browser into several requests (`SCRAPE_BATCH_SIZE` in `static/app.js`, default **50**) so each invocation finishes in time. If a batch still times out, lower that constant or raise duration in **Settings → Functions** (within your plan’s max).

## License

Use only on sites you are allowed to scrape.
