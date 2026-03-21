"""
Groepeer URL’s die dezelfde pagina in een andere taal zijn (pad /nl/… vs /fr/… of ?lang=).

Sites zoals  gebruiken per taal andere mappen/bestandsnamen (nl/vakantieverhuur/… vs
de/ferienvermietung/…); dan groeperen we op het referentie-getal in de bestandsnaam
(bv. …-formentor-1083.htm → 1083).

Behoud één URL per groep: voorkeur NL, dan EN, daarna FR, DE, …
"""
from __future__ import annotations

import re
from collections import defaultdict
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

# Eerste pad-segment dat we als taalcode beschouwen (meertalige sites / CMS).
_LANG_PATH_PREFIXES = frozenset(
    {
        "nl",
        "fr",
        "de",
        "en",
        "it",
        "es",
        "nl-be",
        "fr-be",
        "de-be",
        "en-be",
        "be-nl",
        "be-fr",
        "be-de",
        "be-en",
    }
)

_LANG_QUERY_KEYS = frozenset({"lang", "language", "locale", "lng", "lc", "langcode"})

# Lagere score = hogere voorkeur (NL eerst, dan EN).
_PREF: dict[str, int] = {"nl": 0, "en": 1, "fr": 2, "de": 3, "it": 4, "es": 5}


def _listing_id_from_path_no_lang(path: str) -> str | None:
    """
    Zelfde object, andere taal: pad verschilt (nl/vakantieverhuur/... vs de/ferienvermietung/...),
    maar de bestandsnaam eindigt op hetzelfde referentie-getal (bv. ...-formentor-1083.htm).
    """
    segments = [s for s in path.split("/") if s]
    if len(segments) < 2:
        return None
    last = segments[-1]
    if "." not in last:
        return None
    stem = last.rsplit(".", 1)[0].lower()
    m = re.search(r"-(\d{3,})$", stem)
    if not m:
        return None
    return m.group(1)


def _normalize_lang_code(raw: str | None) -> str | None:
    if not raw:
        return None
    s = raw.strip().lower()
    if not s:
        return None
    if s in _LANG_PATH_PREFIXES:
        return s
    # nl-be, en-us, …
    base = s.split("-")[0]
    if len(base) == 2 and base.isalpha():
        return base
    return None


def _canonical_and_lang(url: str) -> tuple[str, str | None]:
    """(sleutel voor groepering, taalcode of None)."""
    p = urlparse(url)
    netloc = (p.netloc or "").lower()
    segments = [s for s in (p.path or "").split("/") if s]
    lang: str | None = None
    path = p.path or "/"

    if segments and segments[0].lower() in _LANG_PATH_PREFIXES:
        lang = segments[0].lower()
        rest = segments[1:]
        path = "/" + "/".join(rest) if rest else "/"
        # Zelfde pand, andere taal-paden (bv. example-site): groepeer op ID in bestandsnaam.
        if len(rest) >= 2:
            lid = _listing_id_from_path_no_lang(path)
            if lid:
                q_kept = [
                    (k, v)
                    for k, v in parse_qsl(p.query, keep_blank_values=True)
                    if k.lower() not in _LANG_QUERY_KEYS
                ]
                q_kept.sort()
                query = urlencode(q_kept)
                key = urlunparse((p.scheme, netloc, f"/__listing__/{lid}", "", query, ""))
                return key, lang
    else:
        q_pairs = parse_qsl(p.query, keep_blank_values=True)
        for k, v in q_pairs:
            if k.lower() in _LANG_QUERY_KEYS and v:
                lang = _normalize_lang_code(v)
                break

    q_kept = [
        (k, v)
        for k, v in parse_qsl(p.query, keep_blank_values=True)
        if k.lower() not in _LANG_QUERY_KEYS
    ]
    q_kept.sort()
    query = urlencode(q_kept)
    key = urlunparse((p.scheme, netloc, path or "/", p.params, query, ""))
    return key, lang


def _score(url: str) -> tuple[int, str]:
    _, lang = _canonical_and_lang(url)
    pref = _PREF.get(lang or "", 50)
    return (pref, url)


def dedupe_urls_by_language(urls: list[str]) -> list[str]:
    """
    Per canonieke pagina één URL: voorkeur NL, dan EN, daarna FR/DE/…
    Volgorde volgt de eerste keer dat een canonieke sleutel voorkomt in `urls`.
    """
    if not urls:
        return []

    groups: dict[str, list[str]] = defaultdict(list)
    for u in urls:
        key, _ = _canonical_and_lang(u)
        groups[key].append(u)

    out: list[str] = []
    seen: set[str] = set()
    for u in urls:
        key, _ = _canonical_and_lang(u)
        if key in seen:
            continue
        seen.add(key)
        variants = groups[key]
        chosen = min(variants, key=_score)
        out.append(chosen)
    return out
