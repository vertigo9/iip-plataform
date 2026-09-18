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
"""

from __future__ import annotations

from dataclasses import dataclass

BASE_URL = "https://api.solutions-ir.com"


@dataclass(frozen=True)
class SolutionsIrCompany:
    ticker: str
    fund_id: str
    cnpj: str
    api_base_url: str = BASE_URL


SOLUTIONS_IR_COMPANIES: dict[str, SolutionsIrCompany] = {
    "BTCI11": SolutionsIrCompany(
        ticker="BTCI11",
        fund_id="296809",
        cnpj="09552812000114",
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


def build_documents_target(ticker: str) -> SolutionsIrTarget:
    company = company_for_ticker(ticker)
    if company is None:
        raise ValueError(f"no Solutions IR config registered for ticker {ticker!r}")
    normalized_cnpj = "".join(ch for ch in company.cnpj if ch.isdigit())
    url = f"{company.api_base_url}/v2/asset/{company.fund_id}/documents/{normalized_cnpj}"
    return SolutionsIrTarget(ticker=company.ticker, url=url)


def _as_int_year(value: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def parse_documents_response(body: bytes, ticker: str) -> tuple[SolutionsIrDocument, ...]:
    import json

    payload = json.loads(body.decode("utf-8"))
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
                        title=item.get("nome") or item.get("data_descricao") or "documento",
                        url=url,
                    )
                )
    documents.sort(key=lambda d: (_as_int_year(d.year), d.category_sigla), reverse=True)
    return tuple(documents)
