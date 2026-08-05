# Scrape Portal

> ⚠️ **UNDER CONSTRUCTION** ⚠️  
> This application is currently under active development. Some features may be incomplete or subject to change. Use at your own discretion.

**Scrape Portal** is a small web app that helps you **collect public page text** from a website you're allowed to access. You give a **start URL**, it **finds candidate pages** (sitemap and/or crawl), **filters** noisy paths, respects **`robots.txt`**, and **downloads** selected pages into a **JSON** file (title + extracted plain text per URL).

---

## What it does

1. **Discover** — Walks the site in a controlled way and builds a list of URLs on the **same host** as your start URL. It prefers **sitemaps** when they exist; otherwise it can **crawl** links up to a chosen depth.
2. **Filter & dedupe** — Applies **path rules** so the list fits customer-facing content (not admin, news indexes, generic job boards, etc.). **Multilingual duplicates** (e.g. `/nl/…`, `/en/…`, same listing or same query identity) are collapsed to **one URL** when the heuristics match.
3. **Robots check** — Each candidate is marked **selectable** only if **`robots.txt`** allows fetching that URL and it stays on the **same origin** as the start URL.
4. **Export** — For URLs you select, it **GETs** each page (with retries on temporary errors), checks **HTML**, strips boilerplate, and streams **newline-delimited JSON** progress until a final JSON document is assembled for download.

The UI is aimed at **open, public pages** (no logins, no internal networks). Anything that isn't public HTML or that robots disallow is skipped or reported as an error for that row.

---

## How discovery works

| Mode | Behaviour |
|------|------------|
| **Auto (recommended)** | Tries **`/sitemap.xml`** (and index sitemaps) and collects URLs until a **global cap** (up to 5000). If almost no URLs come from sitemaps (**&lt; 3**), it falls back to a **crawl** using **depth** and **max pages** from *More options*. |
| **Sitemap** | Same sitemap logic, but the **max pages** value caps how many URLs are kept. |
| **Crawl** | Breadth-first crawl from the start URL, same host only, using **crawl depth** and **max pages** from *More options*. |

---

## How export works

- Only URLs on the **same host** as the **base URL** from discovery are fetched.
- The server re-checks **robots.txt** and path rules before each GET.
- **`SCRAPE_PORTAL_CONCURRENCY`** (default **4**): parallel page fetches during export.
- **`SCRAPE_PORTAL_DELAY`**: optional pause after each page to reduce **HTTP 429**.
- Large exports may be **split into batches** in the browser for hosted deployments with time limits.

---

## Environment variables

| Variable | Description |
|----------|-------------|
| `SCRAPE_PORTAL_CONCURRENCY` | Parallel scrape workers (default `4`) |
| `SCRAPE_PORTAL_DELAY` | Seconds to wait after each page (default `0`) |
| `SCRAPE_PORTAL_DAILY_WEBSITES` | Max distinct websites per UTC day, app-wide (default `20`) |
| `UPSTASH_REDIS_REST_URL` / `KV_REST_API_URL` | Redis REST endpoint for a **shared** daily quota (required on Vercel for a real global limit) |
| `UPSTASH_REDIS_REST_TOKEN` / `KV_REST_API_TOKEN` | Token for the Redis REST endpoint |

---

See [SECURITY.md](SECURITY.md) for the security model and deployment guidance.

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

- [FastAPI](https://fastapi.tiangolo.com/) and [httpx](https://www.python-httpx.org/) for the API and HTTP stack
- [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/) for HTML parsing
- [Vercel](https://vercel.com/) for serverless hosting

---

## 📞 Support

For support and questions:

- Create an issue on GitHub
- Security: see [SECURITY.md](SECURITY.md)

---

**⭐ If this project helped you, please give it a star!**
