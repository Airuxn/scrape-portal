"""Shared test fixtures."""
from __future__ import annotations

import socket

import pytest


@pytest.fixture(autouse=True)
def _stub_dns(monkeypatch):
    """Avoid real DNS lookups during tests."""

    def _fake_getaddrinfo(host, port, *args, **kwargs):
        return [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                ("1.2.3.4", 0),
            )
        ]

    monkeypatch.setattr("ssrf.socket.getaddrinfo", _fake_getaddrinfo)
