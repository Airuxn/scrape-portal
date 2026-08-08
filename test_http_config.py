"""Tests for TLS CA bundle selection (http_config.py)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from http_config import _ssl_verify_path


def test_ssl_verify_path_prefers_env_file(monkeypatch, tmp_path):
    cert = tmp_path / "custom.pem"
    cert.write_text("cert")
    monkeypatch.setenv("SSL_CERT_FILE", str(cert))
    assert _ssl_verify_path() == str(cert)


def test_ssl_verify_path_falls_back_to_system_ca(monkeypatch):
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    with patch.object(Path, "is_file", lambda self: str(self) == "/etc/ssl/certs/ca-certificates.crt"):
        assert _ssl_verify_path() == "/etc/ssl/certs/ca-certificates.crt"


def test_ssl_verify_path_falls_back_to_certifi(monkeypatch):
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    with patch.object(Path, "is_file", lambda self: False):
        result = _ssl_verify_path()
    assert isinstance(result, str)
    assert "certifi" in result.lower()


def test_ssl_verify_path_returns_true_when_certifi_missing(monkeypatch):
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    with patch.object(Path, "is_file", lambda self: False):
        with patch.dict("sys.modules", {"certifi": None}):
            assert _ssl_verify_path() is True
