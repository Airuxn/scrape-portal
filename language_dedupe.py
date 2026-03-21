"""
Groepeer URL’s die dezelfde pagina in een andere taal zijn (pad /nl/… vs /fr/… of ?lang=).

1) Bestandsnaam-ID: …-formentor-1083.htm → zelfde object over talen heen.

2) Vertaalde slug + dezelfde “resource”-query: bv. /de/ferienvermietung?office_id=12345 en
   /en/holiday-rental?office_id=12345 — geen vaste lijst met één parameternaam: we groeperen
   op de volledige query (zonder taal-keys) wanneer:
   - het pad na de taal “shallow” is (≤ 2 segmenten, geen listing-ID in bestandsnaam), en
   - de query minstens één parameter heeft die op een stabiele bron-ID lijkt
     (naam zoals *_id, chk_*, office, branch, … of waarde 3+ cijfers, UUID, …),
     en we paginatie-only params (page, sort, …) negeren.

Geen enkele heuristiek is 100% foutloos voor elk domein: we zijn conservatief (liever een
dubbele laten staan dan twee verschillende pagina’s samenvoegen). Uitzonderlijke CMS-namen
kun je later uitbreiden via _STABLE_PARAM_NAME_RE / _PAGINATION_KEYS.

Behoud één URL per groep: voorkeur NL, dan EN, FR, DE (zie _PREF).
"""
from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from urllib.parse import ParseResult, parse_qsl, urlencode, urlparse, urlunparse

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

# Alleen sorteren/filteren — geen bron-identiteit.
_PAGINATION_KEYS = frozenset(
    {
        "page",
        "p",
        "pg",
        "offset",
        "limit",
        "sort",
        "order",
        "dir",
        "orderby",
        "view",
        "tab",
        "mode",
        "layout",
        "cursor",
    }
)

# Parameternamen die vaak een kantoor/object/lijst-ID dragen (geen volledige CMS-dekking).
_STABLE_PARAM_NAME_RE = re.compile(
    r"^(chk_.+|.+_id|id|ref|reference|office|branch|venue|store|agency|site|unit|"
    r"location|listing|object|property|bureau|kantoor|magasin|filiale|filial|station|"
    r"depot|standort|objectid|itemid|propertyid|listingid|agencyid|storeid|officeid|"
    r"chkoffice|chk_office|office_id|branch_id|location_id)$",
    re.IGNORECASE,
)

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

# Lagere score = hogere voorkeur (nl > en > fr > de; daarna overige talen).
_PREF: dict[str, int] = {"nl": 0, "en": 1, "fr": 2, "de": 3, "it": 4, "es": 5}


def _path_segments(path: str) -> list[str]:
    return [s for s in (path or "").split("/") if s]


def _non_lang_query_pairs(p: ParseResult) -> list[tuple[str, str]]:
    return [
        (k, v)
        for k, v in parse_qsl(p.query, keep_blank_values=True)
        if k.lower() not in _LANG_QUERY_KEYS
    ]


def _identity_candidate_pairs(pairs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    return [(k, v) for k, v in pairs if k.lower() not in _PAGINATION_KEYS and v != ""]


def _pair_looks_like_resource_identity(key: str, value: str) -> bool:
    kl = key.lower()
    if _STABLE_PARAM_NAME_RE.match(kl):
        return True
    if re.fullmatch(r"\d{3,}", value.strip()):
        return True
    if _UUID_RE.match(value.strip()):
        return True
    return False


def _query_looks_like_resource_identity(pairs: list[tuple[str, str]]) -> bool:
    """Minstens één niet-paginatie parameter die op een stabiele ID wijst."""
    cands = _identity_candidate_pairs(pairs)
    if not cands:
        return False
    return any(_pair_looks_like_resource_identity(k, v) for k, v in cands)


def _cross_lang_query_key(
    p: ParseResult, scheme: str, netloc: str, path_after_lang: str
) -> str | None:
    """
    Zelfde logische pagina over /nl|fr|de|en/… met verschillende slug: groepeer op
    genormaliseerde query wanneer het pad ondiep is en de query een resource-ID lijkt.
    """
    if _listing_id_from_path_no_lang(path_after_lang):
        return None
    rest_segs = _path_segments(path_after_lang)
    if len(rest_segs) > 2:
        return None

    pairs = _non_lang_query_pairs(p)
    if not pairs:
        return None
    if not _query_looks_like_resource_identity(pairs):
        return None

    pairs_sorted = sorted(pairs, key=lambda kv: (kv[0].lower(), kv[0], kv[1]))
    qs = urlencode(pairs_sorted)
    digest = hashlib.sha256(qs.encode("utf-8")).hexdigest()[:40]
    return urlunparse((scheme, netloc, f"/__qstable__/{digest}", "", "", ""))


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
    scheme = p.scheme or "https"
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
                key = urlunparse((scheme, netloc, f"/__listing__/{lid}", "", query, ""))
                return key, lang
        qid = _cross_lang_query_key(p, scheme, netloc, path)
        if qid:
            return qid, lang
    else:
        q_pairs = parse_qsl(p.query, keep_blank_values=True)
        for k, v in q_pairs:
            if k.lower() in _LANG_QUERY_KEYS and v:
                lang = _normalize_lang_code(v)
                break
        qid = _cross_lang_query_key(p, scheme, netloc, path)
        if qid:
            return qid, lang

    q_kept = [
        (k, v)
        for k, v in parse_qsl(p.query, keep_blank_values=True)
        if k.lower() not in _LANG_QUERY_KEYS
    ]
    q_kept.sort()
    query = urlencode(q_kept)
    key = urlunparse((scheme, netloc, path or "/", p.params, query, ""))
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
