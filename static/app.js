const $ = (s, el = document) => el.querySelector(s);

// Gelijk aan server MAX_SCRAPE_BATCH (grote exports zoals large exports)
const MAX_SCRAPE = 5000;

/**
 * Vercel beëindigt elke serverless-invocation na maxDuration (host maxDuration).
 * Eén lange /api/scrape-stream raakt die limiet → timeout in logs, geen `done` in de stream.
 * Kleinere batches = meerdere korte invocations; totale export blijft één JSON-download.
 */
const SCRAPE_BATCH_SIZE = 50;

function chunkArray(arr, size) {
  const out = [];
  for (let i = 0; i < arr.length; i += size) {
    out.push(arr.slice(i, i + size));
  }
  return out;
}

/** bv. https://www.ieper.be/ → ieper_data.json */
function exportJsonFilenameFromUrl(urlStr) {
  try {
    const url = new URL(/^https?:\/\//i.test(urlStr) ? urlStr : `https://${urlStr}`);
    let host = url.hostname.toLowerCase();
    if (host.startsWith("www.")) host = host.slice(4);
    const first = host.split(".")[0] || "website";
    const slug = first.replace(/[^a-z0-9_-]/gi, "").replace(/^-+|-+$/g, "") || "website";
    return `${slug}_data.json`;
  } catch {
    return "website_data.json";
  }
}

async function parseJsonOrThrow(r) {
  const text = await r.text();
  try {
    return text ? JSON.parse(text) : {};
  } catch {
    throw new Error(text.slice(0, 200) || r.statusText);
  }
}

function formatApiError(data, fallback) {
  const d = data?.detail;
  if (typeof d === "string") return new Error(d);
  if (Array.isArray(d) && d[0]?.msg) return new Error(d.map((x) => x.msg).join("; "));
  return new Error(fallback || "Fout");
}

/** Accepts "example.be" or "https://www.example.be" — browser url input does not. */
function normalizeWebsiteInput(raw) {
  let s = String(raw || "").trim();
  if (!s) throw new Error("Vul een website in.");
  if (!/^https?:\/\//i.test(s)) {
    s = `https://${s}`;
  }
  let u;
  try {
    u = new URL(s);
  } catch {
    throw new Error("Dat lijkt geen geldige website. Controleer de spelling.");
  }
  if (u.protocol !== "http:" && u.protocol !== "https:") {
    throw new Error("Alleen http(s)-adressen zijn toegestaan.");
  }
  if (!u.hostname) {
    throw new Error("Vul een geldig domein in (bv. www.voorbeeld.be).");
  }
  return u.href;
}

/** @returns {() => void} stop timer + clear loading UI */
function startLoadingStatus(el, line1, detailLine) {
  const detail =
    detailLine ||
    "Bij grote sites kan dit even duren; dit tabblad open laten.";
  el.classList.remove("error");
  el.classList.add("status-loading");
  let sec = 0;
  const render = () => {
    el.innerHTML =
      '<span class="spinner" aria-hidden="true"></span><span>Nog bezig: ' +
      line1 +
      " <strong>" +
      sec +
      " s</strong>. " +
      detail +
      "</span>";
    sec += 1;
  };
  render();
  const id = setInterval(render, 1000);
  return () => {
    clearInterval(id);
    el.classList.remove("status-loading");
    el.innerHTML = "";
  };
}

function setFormBusy(form, busy) {
  if (!form) return;
  form.setAttribute("aria-busy", busy ? "true" : "false");
}

async function discover(ev) {
  ev.preventDefault();
  const form = $("#form-discover");
  const fd = new FormData(form);
  let urlNorm;
  try {
    urlNorm = normalizeWebsiteInput(fd.get("url"));
    form.querySelector('[name="url"]').value = urlNorm;
  } catch (e) {
    const status = $("#discover-status");
    status.textContent = e.message || String(e);
    status.classList.add("error");
    return;
  }
  const body = {
    url: urlNorm,
    mode: fd.get("mode"),
    crawl_depth: Number(fd.get("crawl_depth")),
    crawl_max_pages: Number(fd.get("crawl_max_pages")),
  };
  const status = $("#discover-status");
  $("#btn-discover").disabled = true;
  const stopLoad = startLoadingStatus(
    status,
    "sitemap/crawl ophalen en robots-filter",
    "Geen aparte controle meer per URL in de lijst — dat voorkomt blokkades. Grote sitemaps kunnen lang downloaden."
  );
  setFormBusy(form, true);

  try {
    const r = await fetch("/api/discover", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await parseJsonOrThrow(r);
    if (!r.ok) throw formatApiError(data, r.statusText);
    stopLoad();
    renderRows(data);
    $("#base-url").value = data.base_url;
    $("#step-pick").classList.remove("hidden");
    status.textContent = `Klaar: ${data.count} URL’s gecontroleerd.`;
    status.classList.remove("error");
  } catch (e) {
    stopLoad();
    status.textContent = e.message || String(e);
    status.classList.add("error");
  } finally {
    $("#btn-discover").disabled = false;
    setFormBusy(form, false);
  }
}

function renderRows(data) {
  const tb = $("#url-rows");
  tb.innerHTML = "";
  let selectable = 0;
  for (const row of data.urls) {
    const tr = document.createElement("tr");
    const can = row.selectable === true;
    if (can) selectable++;

    const td0 = document.createElement("td");
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.className = "pick";
    cb.disabled = !can;
    cb.dataset.url = row.url;
    td0.appendChild(cb);

    const td1 = document.createElement("td");
    td1.className = "url-cell";
    td1.textContent = row.url;

    const td2 = document.createElement("td");
    td2.className = `reason ${can ? "ok" : "bad"}`;
    td2.textContent = row.reason;

    tr.appendChild(td0);
    tr.appendChild(td1);
    tr.appendChild(td2);
    tb.appendChild(tr);
  }
  $("#count-label").textContent = `${selectable} van ${data.urls.length} kiesbaar`;
  updateScrapeButton();
}

function selectedUrls() {
  const out = [];
  for (const cb of document.querySelectorAll(".pick:checked")) {
    out.push(cb.dataset.url);
  }
  return out;
}

function updateScrapeButton() {
  const n = selectedUrls().length;
  const btn = $("#btn-scrape");
  btn.disabled = n === 0 || n > MAX_SCRAPE;
  btn.textContent =
    n === 0
      ? "JSON downloaden"
      : n > MAX_SCRAPE
        ? `Max. ${MAX_SCRAPE} pagina’s`
        : `JSON downloaden (${n})`;
}

$("#form-discover").addEventListener("submit", discover);

$("#btn-sel-all").addEventListener("click", () => {
  for (const cb of document.querySelectorAll(".pick:not(:disabled)")) {
    cb.checked = true;
  }
  updateScrapeButton();
});

$("#btn-sel-none").addEventListener("click", () => {
  for (const cb of document.querySelectorAll(".pick")) cb.checked = false;
  updateScrapeButton();
});

document.addEventListener("change", (e) => {
  if (e.target.classList.contains("pick")) updateScrapeButton();
});

async function readNdjsonLines(response, onObject) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const lines = buf.split("\n");
    buf = lines.pop() || "";
    for (const line of lines) {
      const t = line.trim();
      if (!t) continue;
      onObject(JSON.parse(t));
    }
  }
  if (buf.trim()) {
    onObject(JSON.parse(buf.trim()));
  }
}

$("#btn-scrape").addEventListener("click", async () => {
  const urls = selectedUrls();
  if (urls.length === 0 || urls.length > MAX_SCRAPE) return;
  const base = $("#base-url").value;
  const st = $("#scrape-status");
  const logEl = $("#scrape-log");
  $("#btn-scrape").disabled = true;
  logEl.hidden = false;
  logEl.innerHTML = "";
  st.textContent = "";
  st.classList.remove("error");

  try {
    const batches = chunkArray(urls, SCRAPE_BATCH_SIZE);
    const allPages = [];
    let baseUrlOut = base;

    logEl.appendChild(
      document.createTextNode(
        `→ ${urls.length} pagina’s${batches.length > 1 ? ` (${batches.length} × max ${SCRAPE_BATCH_SIZE} i.p.v. Vercel time-out)` : ""}\n`
      )
    );

    let cumulativeBefore = 0;
    for (const batch of batches) {
      const r = await fetch("/api/scrape", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/x-ndjson",
        },
        body: JSON.stringify({ base_url: base, urls: batch }),
      });
      if (!r.ok) {
        const data = await parseJsonOrThrow(r);
        throw formatApiError(data, r.statusText);
      }

      let batchDone = null;
      await readNdjsonLines(r, (msg) => {
        if (msg.type === "progress") {
          const ok = !msg.result.error;
          const line = document.createElement("div");
          const tag = ok ? "OK " : "FAIL ";
          const span = document.createElement("span");
          span.className = ok ? "ok" : "fail";
          span.textContent = tag;
          line.appendChild(span);
          const globalIndex = cumulativeBefore + msg.index;
          line.appendChild(
            document.createTextNode(
              `${globalIndex}/${urls.length} ${msg.url}${ok ? "" : " — " + msg.result.error}`
            )
          );
          logEl.appendChild(line);
          logEl.scrollTop = logEl.scrollHeight;
        }
        if (msg.type === "done") {
          batchDone = msg;
        }
      });

      if (!batchDone) {
        throw new Error(
          "Onvolledige stream van server (time-out?). Verlaag SCRAPE_BATCH_SIZE in app.js."
        );
      }

      allPages.push(...batchDone.pages);
      baseUrlOut = batchDone.base_url;
      cumulativeBefore += batch.length;
    }

    const blob = new Blob(
      [
        JSON.stringify(
          {
            base_url: baseUrlOut,
            pages: allPages,
          },
          null,
          2
        ),
      ],
      { type: "application/json" }
    );
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = exportJsonFilenameFromUrl(baseUrlOut);
    a.click();
    URL.revokeObjectURL(a.href);
    st.textContent = `Klaar: download gestart (${allPages.length} regels in JSON).`;
  } catch (e) {
    st.textContent = e.message || String(e);
    st.classList.add("error");
  } finally {
    $("#btn-scrape").disabled = false;
    updateScrapeButton();
  }
});
