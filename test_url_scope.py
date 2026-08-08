"""Tests for URL path filtering (url_scope.py)."""
from __future__ import annotations

import pytest

from url_scope import (
    filter_urls_for_scraping,
    is_customer_facing_url,
    path_segments,
    url_allowed_for_scraping,
)


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://x.be/", []),
        ("https://x.be/a/b/", ["a", "b"]),
        ("https://x.be//a//b//", ["a", "b"]),
    ],
)
def test_path_segments(url, expected):
    assert path_segments(url) == expected


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://x.be/", True),
        ("https://x.be/over-ons", True),
        ("https://x.be/stages", True),  # in allow-extended set
        ("https://x.be/nieuws/item", False),
        ("https://x.be/wp-admin/", False),
        ("https://x.be/jobs", False),
        ("https://x.be/vacatures", False),
    ],
)
def test_is_customer_facing_url(url, expected):
    assert is_customer_facing_url(url) is expected


def test_url_allowed_for_scraping_returns_reason():
    ok, reason = url_allowed_for_scraping("https://x.be/contact", "x.be")
    assert ok is True
    assert reason == ""

    ok, reason = url_allowed_for_scraping("https://x.be/nieuws", "x.be")
    assert ok is False
    assert "uitgesloten" in reason


def test_filter_urls_for_scraping_preserves_order_and_hostname():
    urls = [
        "https://x.be/nieuws",
        "https://x.be/contact",
        "https://x.be/stages",
        "https://x.be/admin/login",
    ]
    filtered = filter_urls_for_scraping("anything.example", urls)
    assert filtered == ["https://x.be/contact", "https://x.be/stages"]
