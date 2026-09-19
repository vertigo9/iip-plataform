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

COMPANY SITES (added 18/09/2026, ISAE4): the same pattern also fits an issuer whose
IR site is server-rendered (checked with plain GETs of ri.isaenergiabrasil.com.br,
which was previously recorded as a "custom ASP.NET MVC site" with no adapter). Three
optional registration fields cover what differed from the fund pages: ``extra_page_urls``
(the documents are spread over several pages), ``year_param`` (the results page shows
the current year and takes ``?ano=YYYY`` for earlier ones -- its year <select> posts
to an AJAX action, but the same GET query works) and ``extensions`` (the company also
publishes ``.xlsx`` results workbooks, which are structured data worth keeping). A fund
registration without those fields behaves exactly as before.

CMIG4 (Cemig) is registered the same way, with ``year_in_path`` (``<page>/<year>``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

_PDF_HREF_RE = re.compile(r'href="([^"]+\.pdf)"', re.IGNORECASE)
DEFAULT_EXTENSIONS = (".pdf",)


@lru_cache(maxsize=None)
def _href_re(extensions: tuple[str, ...]) -> re.Pattern[str]:
    alternatives = "|".join(re.escape(e) for e in extensions)
    return re.compile(rf'href="([^"]+(?:{alternatives}))"', re.IGNORECASE)


@dataclass(frozen=True)
class StaticListingFund:
    ticker: str
    manager: str
    page_url: str
    extra_page_urls: tuple[str, ...] = ()
    year_param: str | None = (
        None  # query parameter that selects the year of ``page_url``
    )
    year_in_path: bool = (
        False  # the year is a path segment instead: ``<page_url>/<year>``
    )
    extensions: tuple[str, ...] = DEFAULT_EXTENSIONS


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
    # ISA Energia Brasil (a listed company, not a fund): results center by year plus the
    # reports, modelling-support and subsidiary-statements pages. The pages for
    # shareholder remuneration, debt and regulatory documents render no links in the
    # static HTML (they load client-side) and are deliberately not registered.
    "ISAE4": StaticListingFund(
        ticker="ISAE4",
        manager="ISA Energia Brasil",
        page_url="https://ri.isaenergiabrasil.com.br/pt/informacoes-financeiras/central-de-resultados",
        year_param="ano",
        extra_page_urls=(
            "https://ri.isaenergiabrasil.com.br/pt/informacoes-financeiras/relatorios",
            "https://ri.isaenergiabrasil.com.br/pt/informacoes-financeiras/suporte-para-modelagem",
            "https://ri.isaenergiabrasil.com.br/pt/informacoes-financeiras/demonstracoes-das-subsidiarias",
        ),
        extensions=(".pdf", ".xlsx"),
    ),
    # Cemig (CMIG4): Next.js site, but the pages are server-rendered with the files as
    # plain ``/docs/<name>-<date>-<hash>.pdf|xlsx`` links. The "central de downloads"
    # shows the current year (175 files) and ``.../<year>`` gives an earlier one (found
    # by trying it: the year buttons are client-side links, the page data lists 2000-2026
    # with ~250 posts each). The results and presentations pages are current-year only
    # but cheap, and cover a file that could appear there first.
    "CMIG4": StaticListingFund(
        ticker="CMIG4",
        manager="Cemig",
        page_url="https://ri.cemig.com.br/servicos-aos-investidores/central-de-downloads",
        year_in_path=True,
        extra_page_urls=(
            "https://ri.cemig.com.br/divulgacao-e-resultados/central-de-resultados",
            "https://ri.cemig.com.br/divulgacao-e-resultados/apresentacoes-e-teleconferencias",
        ),
        extensions=(".pdf", ".xlsx"),
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


def build_targets(
    ticker: str, years: tuple[int, ...] = ()
) -> tuple[StaticListingTarget, ...]:
    """Every page to read for ``ticker``: the main page (once per year in ``years``
    when the registration has a ``year_param``, else once) then the extra pages.
    The FIRST target is the one that must succeed."""
    fund = fund_for_ticker(ticker)
    if fund is None:
        raise ValueError(f"no static-listing config registered for ticker {ticker!r}")
    if (fund.year_param or fund.year_in_path) and years:
        main = tuple(
            StaticListingTarget(
                fund.ticker,
                (
                    f"{fund.page_url}/{year}"
                    if fund.year_in_path
                    else f"{fund.page_url}?{fund.year_param}={year}"
                ),
            )
            for year in years
        )
    else:
        main = (StaticListingTarget(fund.ticker, fund.page_url),)
    extra = tuple(StaticListingTarget(fund.ticker, url) for url in fund.extra_page_urls)
    return main + extra


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
    for extension in (".pdf", ".xlsx"):
        if name.lower().endswith(extension):
            name = name[: -len(extension)]
            break
    name = re.sub(r"[_-]+", " ", name).strip()
    return name or "documento"


def parse_pdf_links(
    html: str,
    base_url: str,
    ticker: str,
    extensions: tuple[str, ...] = DEFAULT_EXTENSIONS,
) -> tuple[StaticDocument, ...]:
    """Extract every unique document link (``.pdf`` unless ``extensions`` says
    otherwise) from a document-listing page. Relative hrefs are resolved against
    ``base_url`` (the page's own final URL, after any redirect)."""
    seen: set[str] = set()
    documents: list[StaticDocument] = []
    for match in _href_re(tuple(extensions)).finditer(html):
        resolved = urljoin(base_url, match.group(1))
        if resolved in seen:
            continue
        seen.add(resolved)
        title = _title_from_url(resolved)
        documents.append(
            StaticDocument(ticker=ticker, url=_percent_encode(resolved), title=title)
        )
    return tuple(documents)
