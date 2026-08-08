"""Tests for multilingual URL deduplication (language_dedupe.py)."""
from __future__ import annotations

from urllib.parse import urlparse

from language_dedupe import (
    _canonical_and_lang,
    _cross_lang_query_key,
    _listing_id_from_path_no_lang,
    _normalize_lang_code,
    _pair_looks_like_resource_identity,
    _query_looks_like_resource_identity,
    dedupe_urls_by_language,
)


def test_listing_id_from_path_no_lang():
    assert _listing_id_from_path_no_lang("/vakantieverhuur/formentor-1083.htm") == "1083"
    assert _listing_id_from_path_no_lang("/holiday-rental/formentor-1083.html") == "1083"
    assert _listing_id_from_path_no_lang("/no-id/") is None
    assert _listing_id_from_path_no_lang("/short-12") is None


def test_normalize_lang_code():
    assert _normalize_lang_code("nl") == "nl"
    assert _normalize_lang_code("NL-BE") == "nl-be"
    assert _normalize_lang_code("en-US") == "en"
    # Any two-letter alpha code is accepted as a base language.
    assert _normalize_lang_code("xx") == "xx"
    assert _normalize_lang_code("") is None
    assert _normalize_lang_code("abc") is None


def test_pair_looks_like_resource_identity():
    assert _pair_looks_like_resource_identity("office_id", "123") is True
    assert _pair_looks_like_resource_identity("page", "3") is False
    assert _pair_looks_like_resource_identity("foo", "123456") is True
    assert _pair_looks_like_resource_identity("foo", "abc") is False


def test_query_looks_like_resource_identity():
    assert _query_looks_like_resource_identity([("office_id", "123")]) is True
    assert _query_looks_like_resource_identity([("page", "2")]) is False
    assert _query_looks_like_resource_identity([("page", "2"), ("office_id", "123")]) is True


def test_cross_lang_query_key_groups_shallow_resource_queries():
    url = "https://example.com/de/ferienvermietung?office_id=12345&page=2"
    key = _cross_lang_query_key(urlparse(url), "https", "example.com", "/de/ferienvermietung")
    assert key is not None
    assert key.startswith("https://example.com/__qstable__/")


def test_cross_lang_query_key_returns_none_for_deep_paths():
    url = "https://example.com/de/very/deep/path?office_id=123"
    key = _cross_lang_query_key(urlparse(url), "https", "example.com", "/de/very/deep/path")
    assert key is None


def test_canonical_and_lang_for_language_path_prefix():
    key, lang = _canonical_and_lang("https://example.com/nl/over-ons")
    assert lang == "nl"
    assert "/nl/" not in key


def test_canonical_and_lang_for_query_language():
    key, lang = _canonical_and_lang("https://example.com/over-ons?lang=fr")
    assert lang == "fr"
    assert "lang=fr" not in key


def test_canonical_and_lang_for_listing_id():
    urls = [
        "https://example.com/nl/vakantieverhuur/formentor-1083.htm",
        "https://example.com/de/ferienvermietung/formentor-1083.htm",
    ]
    keys = [_canonical_and_lang(u)[0] for u in urls]
    assert keys[0] == keys[1]


def test_dedupe_urls_by_language_prefers_nl_then_en():
    # Same object reference in the URL filename groups these variants.
    urls = [
        "https://example.com/en/item-1083.htm",
        "https://example.com/nl/item-1083.htm",
        "https://example.com/fr/item-1083.htm",
    ]
    result = dedupe_urls_by_language(urls)
    assert result == ["https://example.com/nl/item-1083.htm"]


def test_dedupe_urls_by_language_preserves_first_key_order():
    # The first canonical key occurrence drives order; language preference picks the variant.
    urls = [
        "https://example.com/nl/page-a",
        "https://example.com/en/page-b",
        "https://example.com/fr/page-a",
    ]
    result = dedupe_urls_by_language(urls)
    assert result == ["https://example.com/nl/page-a", "https://example.com/en/page-b"]


def test_dedupe_urls_by_language_keeps_unique_urls():
    urls = ["https://example.com/a", "https://example.com/b", "https://example.com/c"]
    assert dedupe_urls_by_language(urls) == urls


def test_dedupe_urls_by_language_empty():
    assert dedupe_urls_by_language([]) == []
