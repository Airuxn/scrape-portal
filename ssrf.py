"""Block SSRF: private IPs, localhost, link-local, metadata endpoints."""
from __future__ import annotations

import ipaddress
import re
import socket
from urllib.parse import urlparse

# Hostnames that should never be crawled
_BLOCKED_HOSTS = frozenset(
    {
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        "::1",
        "metadata.google.internal",
        "metadata",
    }
)

_METADATA_HOST = re.compile(r"^169\.254\.169\.254$", re.I)


def _is_bad_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return True
    if addr.version == 4:
        if _METADATA_HOST.match(str(addr)):
            return True
    return bool(
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or (addr.version == 6 and addr.ipv4_mapped and addr.ipv4_mapped.is_private)
    )


def resolve_hostname(hostname: str) -> list[str]:
    """Return IPv4/IPv6 strings for hostname."""
    ips: list[str] = []
    try:
        for fam, _, _, _, sockaddr in socket.getaddrinfo(hostname, None):
            if fam == socket.AF_INET:
                ips.append(sockaddr[0])
            elif fam == socket.AF_INET6:
                ips.append(sockaddr[0])
    except OSError:
        return []
    return ips


def assert_public_http_url(url: str) -> tuple[str, str]:
    """
    Validate URL for crawling. Returns (normalized_url, hostname).
    Raises ValueError on invalid or unsafe URL.
    """
    from urllib.parse import urlunparse

    p = urlparse(url.strip())
    if p.scheme not in ("http", "https"):
        raise ValueError("Alleen http(s)-URL's zijn toegestaan.")
    if not p.netloc:
        raise ValueError("Ongeldige URL.")
    host = p.hostname
    if not host:
        raise ValueError("Ongeldige host.")
    host_l = host.lower()
    if host_l in _BLOCKED_HOSTS or host_l.endswith(".localhost"):
        raise ValueError("Deze host is niet toegestaan.")
    if host_l.startswith("127.") or host_l.startswith("10.") or host_l.startswith("192.168."):
        raise ValueError("Privé- of lokale adressen zijn niet toegestaan.")

    ips = resolve_hostname(host)
    if not ips:
        raise ValueError("Host kan niet worden opgelost (DNS).")
    for ip in ips:
        if _is_bad_ip(ip):
            raise ValueError("Deze host wijst naar een niet-publiek netwerk.")

    # Normalize: strip fragment, no credentials in output
    clean = urlunparse(
        (
            p.scheme,
            p.netloc.lower().split("@")[-1],
            p.path or "/",
            p.params,
            p.query,
            "",
        )
    )
    return clean, host_l


def _host_key(hostname: str) -> str:
    h = hostname.lower()
    return h[4:] if h.startswith("www.") else h


def same_site(url: str, allowed_host: str) -> bool:
    """Same registrable host; treats www. and apex as equivalent."""
    p = urlparse(url)
    h = (p.hostname or "").lower()
    a = allowed_host.lower()
    if not h or not a:
        return False
    if _host_key(h) == _host_key(a):
        return True
    return h.endswith("." + _host_key(a))
