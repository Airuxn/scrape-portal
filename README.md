# Scrape Portal (Scrape Portal)

**Scrape Portal** is a small web app that helps you **collect public page text** from a website you’re allowed to access. You give a **start URL**, it **finds candidate pages** (sitemap and/or crawl), **filters** noisy paths, respects **`robots.txt`**, and **downloads** selected pages into a **JSON** file (title + extracted plain text per URL).

---

## What it does

1. **Discover** — Walks the site in a controlled way and builds a list of URLs on the **same host** as your start URL. It prefers **sitemaps** when they exist; otherwise it can **crawl** links up to a chosen depth.
2. **Filter & dedupe** — Applies **path rules** so the list fits “customer-facing” content (not admin, news indexes, generic job boards, etc.—with tunable behaviour for known site patterns). **Multilingual duplicates** (e.g. `/nl/…`, `/en/…`, same listing or same query identity) are collapsed to **one URL** when the heuristics match.
3. **Robots check** — Each candidate is marked **selectable** only if **`robots.txt`** allows fetching that URL and it stays on the **same origin** as the start URL.
4. **Export** — For URLs you select, it **GETs** each page (with retries on temporary errors), checks **HTML**, strips boilerplate, and streams **newline-delimited JSON** progress until a final JSON document is assembled for download. Requests can be **throttled** (pause between pages) to reduce rate limits.

The UI is aimed at **open, public pages** (no logins, no internal networks). Anything that isn’t public HTML or that robots disallow is skipped or reported as an error for that row.

---

## How discovery works

| Mode | Behaviour |
|------|------------|
| **Auto (recommended)** | Tries **`/sitemap.xml`** (and index sitemaps) and collects URLs until a **global cap** (up to 5000). **Does not** use the “max pages” number from *More options* when the sitemap succeeds. If almost no URLs come from sitemaps (**&lt; 3**), it falls back to a **crawl** using **depth** and **max pages** from *More options*. |
| **Sitemap** | Same sitemap logic, but the **max pages** value caps how many URLs are kept. |
| **Crawl** | Breadth-first crawl from the start URL, same host only, using **crawl depth** and **max pages** from *More options*. |

After discovery, URLs are **path-filtered**, **language-deduped**, then checked against **robots.txt** for selection.

---

## How export works

- Only URLs on the **same host** as the **base URL** from discovery are fetched.
- The server re-checks **robots.txt** and path rules before each GET.
- Responses must be **HTML**; main text is extracted (title + body text).
- A configurable delay **`SCRAPE_PORTAL_DELAY`** (seconds between pages, default **2**) reduces the chance of **HTTP 429** or throttling; set to **0** to disable pauses (faster, riskier on strict sites).
- Large exports may be **split into batches** in the browser so each server request stays within time limits (implementation detail of the hosted deployment).

---

## Language deduplication (multilingual sites)

If the same logical page appears under different language prefixes (`/nl/`, `/en/`, …) or with translated slugs but a **stable query** (office ID, numeric IDs, etc.), the app tries to keep **one** URL per group, preferring **NL → EN → FR → DE** when multiple variants are present. Heuristics are **conservative** (wrong merges are avoided where possible; some duplicates may remain on unusual URL shapes).

---

## License / use

Use only on sites and data you’re **allowed** to scrape (terms, contract, law).
