"""Investor-relations document API for the "Solutions IR" platform
(api.solutions-ir.com) -- a shared third-party IR infrastructure used
by (at least) BTCI11 and, per a prior session's investigation,
formerly-MZIQ-hosted CSUD3 after its Dec/2024 IR site relaunch (see
``iip.sources.equity_mziq`` module docstring).

Confirmed live (18/09/2026) for BTCI11 -- this was the closing piece
of a session-long gap: BTCI11's own IR page
(btgpactual.com/asset-management/fundos/fundos-listados/BTCI11) is a
client-rendered Astro app with no MZIQ signature anywhere, and a
Playwright headless browser was actively blocked by the site's WAF
(``net::ERR_HTTP2_PROTOCOL_ERROR``, then a hard timeout with HTTP/2
disabled) -- the opposite of every other discovery in this project,
where Playwright was the fallback for a static-HTML dead end. What
worked instead: the page's own static HTML embeds an ``astro-island``
element with a literal ``props`` attribute containing
``apiBaseUrl``/``siteId`` in plain JSON (no execution needed), and its
referenced JS *component* bundle (fetched with a second plain GET, not
run) contained ``apiFundId``/``apiFundTicker``/``apiFundCnpj`` as
literal default parameter values. The actual REST endpoint path
(``/v2/asset/{fund_id}/documents/{cnpj}``) was found the same way, by
grep'ing the (much larger) vendor JS bundle those components import
from for a template literal built from ``this.apiBaseUrl`` -- static
analysis of shipped JS source, not runtime interception.

The endpoint returns ALL of a fund's documents in one response (no
pagination, no years/categories API calls needed, unlike MZIQ) --
confirmed live: 803 documents across 17 categories for BTCI11,
grouped by ``nome_tipo``/``sigla`` (e.g. "RELATORIO MENSAL",
"INFORMATIVO MENSAL", "ATAS DE ASSEMBLEIAS E CONVOCACOES"). Some
categories ("INFORMATIVO MENSAL"/"INFORME MENSAL") likely overlap with
CVM's own structured Informe Mensal data the same way Pátria's
"informe_contabil_mensal" MZIQ category did -- this module still lists
them as documents (real IR evidence), it just never extracts NAV from
them, same policy as every other document-only provider here.

COMPANY SITES (added 18/09/2026, CSUD3): the same platform also serves listed
companies, through a different endpoint shape found the same way (static reading
of the IR site's own JS bundles, ``ri.csu.com.br``): the page's Astro island
embeds ``apiBaseUrl``/``siteId`` and the bundle's file client calls
``GET {apiBaseUrl}/v2/files/{siteId}?language=pt&date=YYYY-01-02`` (public, no
auth). Unlike the fund endpoint it returns ONE YEAR per call -- a
``{years, categoriesTitle, categories: {key: [documents]}}`` object, the year
chosen by ``date`` (the ``year`` parameter the client also builds is ignored:
checked live, it always returns the current year; ``/period`` caps a range at
365 days). Each document carries ``id``/``title``/``url``/``refDate``/
``deliveryDate``. Register a company with ``site_id`` instead of
``fund_id``/``cnpj``; ``build_site_targets`` builds one target per year.
"""

from __future__ import annotations

from dataclasses import dataclass

BASE_URL = "https://api.solutions-ir.com"


@dataclass(frozen=True)
class SolutionsIrCompany:
    ticker: str
    fund_id: str = ""  # fund-shaped endpoint (BTCI11)
    cnpj: str = ""
    api_base_url: str = BASE_URL
    site_id: str = ""  # company-shaped endpoint (CSUD3): the IR site's id

    @property
    def is_site(self) -> bool:
        return bool(self.site_id)


SOLUTIONS_IR_COMPANIES: dict[str, SolutionsIrCompany] = {
    "BTCI11": SolutionsIrCompany(
        ticker="BTCI11",
        fund_id="296809",
        cnpj="09552812000114",
    ),
    # CSU Digital: ri.csu.com.br (Astro, Solutions IR). siteId read from the page's own
    # astro-island props; verified live (73 documents for 2026, 78 for 2025).
    "CSUD3": SolutionsIrCompany(
        ticker="CSUD3",
        site_id="cda8bfad-7383-4b57-bede-6ce1af8a28ba",
    ),
}


@dataclass(frozen=True)
class SolutionsIrTarget:
    ticker: str
    url: str


@dataclass(frozen=True)
class SolutionsIrDocument:
    ticker: str
    category_sigla: str
    category_name: str
    year: str
    date: str
    title: str
    url: str


def company_for_ticker(ticker: str) -> SolutionsIrCompany | None:
    return SOLUTIONS_IR_COMPANIES.get(ticker.strip().upper())


def build_site_targets(
    ticker: str, years: tuple[int, ...], language: str = "pt"
) -> tuple[SolutionsIrTarget, ...]:
    """One request per calendar year for a company-shaped registration."""
    company = company_for_ticker(ticker)
    if company is None:
        raise ValueError(f"no Solutions IR config registered for ticker {ticker!r}")
    if not company.is_site:
        raise ValueError(
            f"{ticker!r} is registered with the fund endpoint, not a site id"
        )
    return tuple(
        SolutionsIrTarget(
            ticker=company.ticker,
            url=(
                f"{company.api_base_url}/v2/files/{company.site_id}"
                f"?language={language}&date={year}-01-02"
            ),
        )
        for year in years
    )


def build_documents_target(ticker: str) -> SolutionsIrTarget:
    company = company_for_ticker(ticker)
    if company is None:
        raise ValueError(f"no Solutions IR config registered for ticker {ticker!r}")
    if company.is_site:
        raise ValueError(
            f"{ticker!r} is a company site: use build_site_targets (one request per year)"
        )
    normalized_cnpj = "".join(ch for ch in company.cnpj if ch.isdigit())
    url = (
        f"{company.api_base_url}/v2/asset/{company.fund_id}/documents/{normalized_cnpj}"
    )
    return SolutionsIrTarget(ticker=company.ticker, url=url)


def _as_int_year(value: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _parse_site_response(payload: dict, ticker: str) -> tuple[SolutionsIrDocument, ...]:
    titles = payload.get("categoriesTitle") or {}
    documents: list[SolutionsIrDocument] = []
    for key, items in (payload.get("categories") or {}).items():
        for item in items or []:
            url = item.get("url")
            if not url:
                continue
            ref = item.get("refDate") or ""
            delivered = item.get("deliveryDate") or ""
            documents.append(
                SolutionsIrDocument(
                    ticker=ticker,
                    category_sigla=key,
                    category_name=(titles.get(key) or key).strip(),
                    year=(ref or delivered)[:4],
                    date=(delivered or ref)[:10],
                    title=(
                        item.get("title") or item.get("name") or "documento"
                    ).strip(),
                    url=url,
                )
            )
    documents.sort(
        key=lambda d: (_as_int_year(d.year), d.date, d.category_sigla), reverse=True
    )
    return tuple(documents)


def parse_documents_response(
    body: bytes, ticker: str
) -> tuple[SolutionsIrDocument, ...]:
    import json

    payload = json.loads(body.decode("utf-8"))
    if isinstance(payload.get("categories"), dict):
        return _parse_site_response(payload, ticker)
    documents: list[SolutionsIrDocument] = []
    for group in payload.get("files", []):
        sigla = group.get("sigla") or ""
        nome_tipo = group.get("nome_tipo") or ""
        for year_entry in group.get("ano_historico", []):
            year = year_entry.get("ano") or ""
            for item in year_entry.get("historico", []):
                url = item.get("link")
                if not url:
                    continue
                documents.append(
                    SolutionsIrDocument(
                        ticker=ticker,
                        category_sigla=sigla,
                        category_name=nome_tipo,
                        year=year,
                        date=item.get("data_descricao") or item.get("date") or "",
                        title=item.get("nome")
                        or item.get("data_descricao")
                        or "documento",
                        url=url,
                    )
                )
    documents.sort(key=lambda d: (_as_int_year(d.year), d.category_sigla), reverse=True)
    return tuple(documents)
