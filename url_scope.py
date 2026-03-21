"""
Path filtering for customer-facing public pages on a scraped site.

Excludes news indexes, admin, generic job boards, etc., while allowing
stages, partner info, and application contact pages where configured.
"""
from __future__ import annotations

from urllib.parse import urlparse

_GENERIC_ALLOW_EXTENDED = frozenset(
    {
        "stages",
        "stage",
        "internships",
        "solliciteer-nu",
        "spontane-sollicitatie",
        "contacteer-ons-jobs",
    }
)

_GENERIC_EXCLUDE_FIRST = frozenset(
    {
        "artikel",
        "nieuws",
        "news",
        "blog",
        "jobs",
        "job",
        "vacatures",
        "vacature",
        "careers",
        "werken-bij",
        "evenement",
        "evenementen",
        "events",
        "event",
        "recepten",
        "recipes",
        "stages",
        "stage",
        "internships",
        "pers",
        "press",
        "in-jouw-buurt",
        "node",
        "wp-admin",
        "wp-login",
        "wp-json",
        "admin",
        "login",
        "register",
        "cart",
        "checkout",
        "account",
        "mijn-account",
        "solliciteer-nu",
        "spontane-sollicitatie",
        "contacteer-ons-jobs",
        "feed",
        "rss",
        "api",
        "author",
        "tag",
        "category",
        "categories",
    }
)

_GENERIC_EXCLUDE_PORTAL = frozenset(_GENERIC_EXCLUDE_FIRST - _GENERIC_ALLOW_EXTENDED)


def path_segments(url: str) -> list[str]:
    return [p for p in urlparse(url).path.split("/") if p]


def is_customer_facing_url(url: str) -> bool:
    parts = path_segments(url)
    if not parts:
        return True
    first = parts[0].lower()
    return first not in _GENERIC_EXCLUDE_PORTAL


def url_allowed_for_scraping(url: str, site_hostname: str) -> tuple[bool, str]:
    """Returns (allowed, reason_if_not). site_hostname reserved for future site-specific rules."""
    _ = site_hostname
    if is_customer_facing_url(url):
        return True, ""
    return False, "uitgesloten pad (nieuws/admin/jobs-index/…)"


def filter_urls_for_scraping(site_hostname: str, urls: list[str]) -> list[str]:
    return [u for u in urls if url_allowed_for_scraping(u, site_hostname)[0]]
