"""TLS verification: env SSL_CERT_FILE, then system CA bundle (Linux), then certifi."""
from __future__ import annotations

import os
from pathlib import Path

_SYSTEM_CA = Path("/etc/ssl/certs/ca-certificates.crt")


def _ssl_verify_path() -> bool | str:
    env = os.environ.get("SSL_CERT_FILE", "").strip()
    if env and Path(env).is_file():
        return env
    if _SYSTEM_CA.is_file():
        return str(_SYSTEM_CA)
    try:
        import certifi

        return certifi.where()
    except ImportError:
        return True


SSL_VERIFY = _ssl_verify_path()
