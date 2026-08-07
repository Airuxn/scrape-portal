"""Security and URL policy tests (SSRF blocks, scrape path filters)."""
from __future__ import annotations

import pytest

from ssrf import assert_public_http_url, same_site
from url_scope import filter_urls_for_scraping, is_customer_facing_url, path_segments


def test_rejects_localhost():
    with pytest.raises(ValueError, match="niet toegestaan"):
        assert_public_http_url("http://localhost/")


def test_rejects_private_ip_literal():
    with pytest.raises(ValueError, match="Privé"):
        assert_public_http_url("http://192.168.1.1/")


def test_rejects_non_http_scheme():
    with pytest.raises(ValueError, match="http"):
        assert_public_http_url("file:///etc/passwd")


def test_accepts_resolvable_public_host():
    url, host = assert_public_http_url("https://example.com/path?q=1")
    assert host == "example.com"
    assert url == "https://example.com/path?q=1"


def test_same_site_treats_www_as_equivalent():
    assert same_site("https://www.foo.com/x", "foo.com")
    assert same_site("https://foo.com", "www.foo.com")
    assert not same_site("https://bar.com", "foo.com")


def test_path_segments():
    assert path_segments("https://x.be/a/b/") == ["a", "b"]


def test_customer_facing_excludes_news_and_admin():
    assert not is_customer_facing_url("https://x.be/nieuws/foo")
    assert not is_customer_facing_url("https://x.be/wp-admin/")
    assert is_customer_facing_url("https://x.be/over-ons")


def test_filter_urls_for_scraping():
    urls = ["https://x.be/nieuws", "https://x.be/contact", "https://x.be/stages"]
    filtered = filter_urls_for_scraping("x.be", urls)
    assert "https://x.be/nieuws" not in filtered
    assert "https://x.be/contact" in filtered
    assert "https://x.be/stages" in filtered
