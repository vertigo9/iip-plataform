"""Generic document source for FII managers whose investor-relations
site lists every report as a plain ``<a href="....pdf">`` directly in
the page's static HTML -- no JS-rendered API needed at all (unlike
``iip.sources.mziq``/``patria_mziq``/``btg_mziq``, which need a POST
call to an API that only exists after JS runs).

Confirmed live (18/09/2026) for the 7 registry positions below --
every one of the remaining managers without any adapter turned out to
use this same simple pattern (mostly plain WordPress media uploads),
found by fetching each fund's own page with a plain HTTP GET and
regex-matching ``.pdf`` hrefs, no browser needed even for discovery.
Several of the registry's own ``source_url`` values were stale/broken
placeholders (KNRI11, RBVA11 -- confirmed 404 live) and had to be
re-found via web search; the corrected URLs are what's registered
here, not the registry's.

Deliberately does NOT parse any document for NAV/cota patrimonial --
these are all FII subtype with a verified CNPJ, so CVM's own
structured data (``iip.sources.cvm_fii``) already covers that. This
is for document retrieval only, same scope note as ``patria_mziq``.

Title is derived from the PDF's own filename (already descriptive on
every site checked, e.g. "TRXF11-Relatorio-Gerencial-Agosto-2026.pdf"),
not from surrounding link text -- link text varies too much per site
to parse reliably, while the filename is uniform to extract.
``discovered_year`` is deliberately never inferred from the URL/title
either (date formats vary per site, several ambiguous) -- evidence
falls back to its ingestion date instead of guessing the document's
real one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

_PDF_HREF_RE = re.compile(r'href="([^"]+\.pdf)"', re.IGNORECASE)


@dataclass(frozen=True)
class StaticListingFund:
    ticker: str
    manager: str
    page_url: str


STATIC_PDF_LISTING_FUNDS: dict[str, StaticListingFund] = {
    "TRXF11": StaticListingFund(
        ticker="TRXF11",
        manager="TRX",
        page_url="https://trxf11.com.br/relatorios-gerenciais-2",
    ),
    "VGIP11": StaticListingFund(
        ticker="VGIP11",
        manager="Valora Invest",
        page_url="https://valorainvest.com.br/fundo/vgip11",
    ),
    "CPTI11": StaticListingFund(
        ticker="CPTI11",
        manager="Capitânia",
        page_url="https://capitaniainfra.com.br/cpti11",
    ),
    "MANA11": StaticListingFund(
        ticker="MANA11",
        manager="Manati/ICM",
        # registry's source_url (manaticm.com/fundo/mana11) 404s live --
        # this one confirmed working (18/09/2026), found via web search.
        page_url="https://manaticm.com/fundo-manati/mana11-manati-hedge-fund-fii/",
    ),
    "RBVA11": StaticListingFund(
        ticker="RBVA11",
        manager="Rio Bravo",
        # registry's source_url (riobravo.com.br/rbva11) 404s live --
        # this one confirmed working (18/09/2026), found via web search.
        page_url="https://www.riobravo.com.br/fundos/fii-rio-bravo-renda-varejo/",
    ),
    "HGBS11": StaticListingFund(
        ticker="HGBS11",
        manager="Hedge Investments",
        page_url="https://hedgeinvest.com.br/fundos/hgbs",
    ),
    "KNRI11": StaticListingFund(
        ticker="KNRI11",
        manager="Kinea",
        # registry's source_url had a literal "..." placeholder --
        # this one confirmed working (18/09/2026), found via web search.
        page_url="https://www.kinea.com.br/fundos/fundo-imobiliario-kinea-renda-knri11/",
    ),
}


@dataclass(frozen=True)
class StaticListingTarget:
    ticker: str
    url: str


@dataclass(frozen=True)
class StaticDocument:
    ticker: str
    url: str
    title: str


def fund_for_ticker(ticker: str) -> StaticListingFund | None:
    return STATIC_PDF_LISTING_FUNDS.get(ticker.strip().upper())


def build_target(ticker: str) -> StaticListingTarget:
    fund = fund_for_ticker(ticker)
    if fund is None:
        raise ValueError(f"no static-listing config registered for ticker {ticker!r}")
    return StaticListingTarget(ticker=fund.ticker, url=fund.page_url)


def _percent_encode(url: str) -> str:
    """Percent-encode a URL's path/query so it's safe to put on an HTTP
    request line. Confirmed live (18/09/2026): a handful of hrefs on
    HGBS11's own listing page contain raw, un-escaped non-ASCII
    characters (e.g. "...Praça_da_Moça...pdf") -- urllib can't put
    those on the request line as-is (UnicodeEncodeError), even though
    the underlying text decoded correctly from the page's own UTF-8.
    ``safe="/%"``/``safe="=&%"`` leaves already-percent-encoded
    sequences (and separators) alone rather than double-encoding them.
    """
    parts = urlsplit(url)
    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            quote(parts.path, safe="/%"),
            quote(parts.query, safe="=&%"),
            parts.fragment,
        )
    )


def _title_from_url(url: str) -> str:
    name = url.split("?", 1)[0].rsplit("/", 1)[-1]
    if name.lower().endswith(".pdf"):
        name = name[: -len(".pdf")]
    name = re.sub(r"[_-]+", " ", name).strip()
    return name or "documento"


def parse_pdf_links(html: str, base_url: str, ticker: str) -> tuple[StaticDocument, ...]:
    """Extract every unique ``.pdf`` link from a fund's document-listing
    page. Relative hrefs are resolved against ``base_url`` (the page's
    own final URL, after any redirect)."""
    seen: set[str] = set()
    documents: list[StaticDocument] = []
    for match in _PDF_HREF_RE.finditer(html):
        resolved = urljoin(base_url, match.group(1))
        if resolved in seen:
            continue
        seen.add(resolved)
        title = _title_from_url(resolved)
        documents.append(
            StaticDocument(ticker=ticker, url=_percent_encode(resolved), title=title)
        )
    return tuple(documents)
