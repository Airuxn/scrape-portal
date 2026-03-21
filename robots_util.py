"""Fetch and apply robots.txt using stdlib RobotFileParser."""
from __future__ import annotations

from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser


USER_AGENT = "ScrapePortal/1.0 (+public research; respects robots.txt)"


def robots_url_for_base(base: str) -> str:
    p = urlparse(base)
    base = f"{p.scheme}://{p.netloc}"
    return urljoin(base, "/robots.txt")


def build_parser(base_url: str) -> RobotFileParser:
    rp = RobotFileParser()
    rp.set_url(robots_url_for_base(base_url))
    rp.read()
    return rp


def can_fetch(rp: RobotFileParser | None, url: str) -> bool:
    if rp is None:
        return True
    try:
        return rp.can_fetch(USER_AGENT, url)
    except Exception:
        return False
