"""Extract visible text from HTML (public pages only)."""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from robots_util import USER_AGENT


def extract_text(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "nav", "footer", "header"]):
        tag.decompose()
    main = soup.find("main") or soup.find("article") or soup.find("body")
    if not main:
        title = (soup.title.string or "").strip() if soup.title else ""
        return "", title
    text = main.get_text(separator="\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    h1 = main.find("h1")
    if h1 and h1.get_text(strip=True):
        title = h1.get_text(strip=True)
    return text, title
