"""Tests for SSRF protections (ssrf.py)."""
from __future__ import annotations

import socket
from unittest.mock import MagicMock

import pytest

from ssrf import (
    _is_bad_ip,
    assert_public_http_url,
    resolve_hostname,
    same_site,
)


@pytest.mark.parametrize(
    "ip,expected",
    [
        ("8.8.8.8", False),
        ("1.2.3.4", False),
        ("127.0.0.1", True),
        ("192.168.1.1", True),
        ("10.0.0.1", True),
        ("169.254.1.1", True),
        ("169.254.169.254", True),
        ("224.0.0.1", True),
        ("240.0.0.0", True),
        ("::1", True),
        ("fe80::1", True),
        # IPv4-mapped private addresses are still blocked via ipv4_mapped.is_private.
        ("::ffff:192.168.1.1", True),
    ],
)
def test_is_bad_ip(ip, expected):
    assert _is_bad_ip(ip) is expected


@pytest.mark.parametrize(
    "ip,expected",
    [
        ("", True),  # invalid
        ("not-an-ip", True),
    ],
)
def test_is_bad_ip_invalid(ip, expected):
    assert _is_bad_ip(ip) is expected


def test_resolve_hostname_calls_getaddrinfo(monkeypatch):
    def fake(host, port, *args, **kwargs):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("9.9.9.9", 0)),
        ]

    monkeypatch.setattr("ssrf.socket.getaddrinfo", fake)
    assert resolve_hostname("example.com") == ["9.9.9.9"]


def test_resolve_hostname_returns_empty_on_error(monkeypatch):
    monkeypatch.setattr("ssrf.socket.getaddrinfo", MagicMock(side_effect=OSError("no dns")))
    assert resolve_hostname("example.com") == []


@pytest.mark.parametrize(
    "url,message",
    [
        ("file:///etc/passwd", "http"),
        ("ftp://example.com/", "http"),
        ("http://localhost/", "toegestaan"),
        ("http://127.0.0.1/", "toegestaan"),
        ("http://metadata.google.internal/", "toegestaan"),
        ("http://192.168.1.1/", "Privé"),
        ("http://10.0.0.1/", "Privé"),
    ],
)
def test_assert_public_http_url_rejects_bad_hosts(url, message):
    with pytest.raises(ValueError, match=message):
        assert_public_http_url(url)


def test_assert_public_http_url_normalizes(monkeypatch):
    def fake(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("8.8.8.8", 0))]

    monkeypatch.setattr("ssrf.socket.getaddrinfo", fake)
    url, host = assert_public_http_url("https://Example.com/path#frag")
    assert host == "example.com"
    assert url == "https://example.com/path"
    assert "#" not in url


def test_assert_public_http_url_rejects_unresolvable(monkeypatch):
    monkeypatch.setattr("ssrf.socket.getaddrinfo", MagicMock(side_effect=OSError("no dns")))
    with pytest.raises(ValueError, match="DNS"):
        assert_public_http_url("https://does-not-resolve.example/")


def test_assert_public_http_url_rejects_metadata_ip(monkeypatch):
    def fake(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("169.254.169.254", 0))]

    monkeypatch.setattr("ssrf.socket.getaddrinfo", fake)
    with pytest.raises(ValueError, match="niet-publiek"):
        assert_public_http_url("https://metadata.example/")


@pytest.mark.parametrize(
    "url,allowed,expected",
    [
        ("https://www.foo.com/x", "foo.com", True),
        ("https://foo.com/", "www.foo.com", True),
        ("https://sub.foo.com/", "foo.com", True),
        ("https://bar.com/", "foo.com", False),
        ("https://foo.com.evil.com/", "foo.com", False),
        ("https://foo.com", "", False),
    ],
)
def test_same_site(url, allowed, expected):
    assert same_site(url, allowed) is expected
