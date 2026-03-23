"""HTTP GET with manual redirect following and SSRF checks on every hop."""
from __future__ import annotations

from urllib.parse import urljoin

import httpx

from ssrf import assert_public_http_url

MAX_REDIRECTS = 8
_REDIRECT_CODES = frozenset({301, 302, 303, 307, 308})


async def safe_get(
    client: httpx.AsyncClient,
    url: str,
    *,
    max_redirects: int = MAX_REDIRECTS,
    **kwargs,
) -> httpx.Response:
    """
    GET without httpx auto-redirects; validates each URL before requesting.
    """
    current = url.strip()
    response: httpx.Response | None = None

    for _ in range(max_redirects + 1):
        assert_public_http_url(current)
        response = await client.get(current, follow_redirects=False, **kwargs)
        if response.status_code not in _REDIRECT_CODES:
            return response
        location = response.headers.get("location")
        if not location:
            return response
        current = urljoin(str(response.url), location)

    raise ValueError("Te veel redirects.")
