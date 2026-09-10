"""MZIQ (MZ Group) investor-relations document catalog — shared platform.

MZIQ is investor-relations infrastructure used by many Brazilian public
companies (confirmed: dozens of companies' document download links
share the same api.mziq.com host, found independently via web search).
Each company gets its own WordPress site (e.g. ri.abcbrasil.com.br)
built on this platform, identified by a UUID ("company_id"), with its
own set of document categories (e.g.
"central-resultados-earnings-release") — but the underlying API is
shared infrastructure, confirmed live against ABC Brasil's (ABCB4) IR
site: https://ri.abcbrasil.com.br/resultados/central-de-resultados/.

This is the same general approach already used by
``iip.harvest.patria`` for a single company (Patria/PCIP11), which
reverse-engineers this exact endpoint shape
(``/filter/categories/year/meta``) live per-site via Playwright. This
module generalizes it: given a company_id and its category internal
names (config the caller supplies, the same way xp_asset.py needs a
per-fund AssetRef), it builds the same two request bodies for ANY
company on the MZIQ platform, without needing a browser — because the
API accepts direct POST requests, confirmed live (no auth, no
Cloudflare, unlike FNET).

Two endpoints, both POST with a JSON body, verified against a real
captured response (not assumed):
  - ``POST /filemanager/company/{company_id}/categoryInternalName/document/language/years``
    body: ``{"categoryInternalNames": [...], "language_code": "pt_BR"}``
    response: ``{"success": true, "data": [2026, 2025, ...]}``
  - ``POST /filemanager/company/{company_id}/filter/categories/year/meta``
    body: ``{"year": "2026", "categories": [...], "language": "pt_BR", "published": true}``
    response: ``{"success": true, "data": {"document_metas": [...]}}``

Each ``document_meta`` item's download URL is in ``file_url`` for most
document types, but some (confirmed: video/audio conference recordings)
have ``file_url: null`` and use ``link_url`` instead — this module
checks both, in that order, never assuming ``file_url`` alone is
enough (a real gap found in the actual captured response, not
speculation).

The actual per-file download (``file_url``/``link_url``, hosted at
``api.mziq.com/mzfilemanager/v2/d/{company_id}/{file_id}?origin=2``)
is a plain unauthenticated GET, confirmed live: fetching one such URL
returned the raw PDF directly.

Same request/response split as the other sources: this module builds
the request (URL + JSON body) and parses the response; it performs no
HTTP request itself (see ``.mziq_harvester`` for the transport).
"""

from __future__ import annotations

import json
from dataclasses import dataclass

BASE_URL = "https://apicatalog.mziq.com/filemanager/company"


@dataclass(frozen=True)
class MziqTarget:
    url: str
    body: dict


@dataclass(frozen=True)
class MziqDocument:
    id: str
    company_id: str
    file_name_original: str | None
    file_title: str | None
    url: str | None
    file_size: int | None
    file_date: str | None
    file_quarter: int | None
    file_year: int | None
    category: str | None
    is_published: bool | None


def build_years_target(
    company_id: str,
    category_internal_names: tuple[str, ...],
    *,
    language_code: str = "pt_BR",
) -> MziqTarget:
    """Build the request for the list of years that have published
    documents in the given categories."""

    if not company_id:
        raise ValueError("company_id must not be empty")
    if not category_internal_names:
        raise ValueError("category_internal_names must not be empty")

    url = f"{BASE_URL}/{company_id}/categoryInternalName/document/language/years"
    body = {
        "categoryInternalNames": list(category_internal_names),
        "language_code": language_code,
    }
    return MziqTarget(url=url, body=body)


def build_documents_target(
    company_id: str,
    year: int,
    category_internal_names: tuple[str, ...],
    *,
    language: str = "pt_BR",
    published: bool = True,
) -> MziqTarget:
    """Build the request for documents in the given categories/year."""

    if not company_id:
        raise ValueError("company_id must not be empty")
    if not category_internal_names:
        raise ValueError("category_internal_names must not be empty")

    url = f"{BASE_URL}/{company_id}/filter/categories/year/meta"
    body = {
        "year": str(year),
        "categories": list(category_internal_names),
        "language": language,
        "published": published,
    }
    return MziqTarget(url=url, body=body)


def _as_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_years_response(body: bytes) -> tuple[int, ...]:
    raw = json.loads(body.decode("utf-8"))
    if not raw.get("success"):
        return ()
    return tuple(raw.get("data", []))


def parse_documents_response(body: bytes) -> tuple[MziqDocument, ...]:
    raw = json.loads(body.decode("utf-8"))
    if not raw.get("success"):
        return ()

    metas = raw.get("data", {}).get("document_metas", [])
    documents = []
    for item in metas:
        # file_url is null for some document types (e.g. video/audio
        # conference recordings, confirmed live) — link_url carries the
        # URL instead in that case.
        url = item.get("file_url") or item.get("link_url") or item.get("permalink")
        documents.append(
            MziqDocument(
                id=str(item.get("id", "")),
                company_id=str(item.get("company_id", "")),
                file_name_original=item.get("file_name_original"),
                file_title=item.get("file_title"),
                url=url,
                file_size=_as_int(item.get("file_size")),
                file_date=item.get("file_date"),
                file_quarter=item.get("file_quarter"),
                file_year=item.get("file_year"),
                category=item.get("internal_name"),
                is_published=item.get("is_published"),
            )
        )
    return tuple(documents)
