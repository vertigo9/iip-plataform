"""XP Asset's fund documents via the MZIQ platform (see ``iip.sources.mziq`` for the
generic request/response shapes) -- the same lightweight, HTTP-only approach as
``iip.sources.btg_mziq`` and ``iip.sources.hsi_mziq``.

Confirmed live (19/09/2026) for XPML11 (XP Malls). Unlike BTG and HSI, the fund's own
page (https://xpasset.com.br/fundos/xp-malls) answers a plain GET with HTTP 403, so
the MZIQ config could not be read from its HTML, and no attempt was made to get
around that. Instead:
  - the company id is the one in the public CDN addresses of the fund's own
    management reports (``filemanager-cdn.mziq.com/published/<company id>/...``); the
    file names carry XPML11's CNPJ (``28757546000100``) and the documents are titled
    "XP Malls FII";
  - the category internal name was found by probing the public API with the names the
    other managers use: ``relatorios_gerenciais`` (the same as BTG's) lists the
    monthly reports back to 2024; ``relatorio-gerencial``, ``relatorio_gerencial``,
    ``relatorios-gerenciais``, ``relatorio``, ``relatorios`` and ``gerencial`` return
    nothing. Other categories of this company were not looked for, so only the
    verified one is listed.

Scope, as for the other MZIQ modules: DOCUMENT retrieval.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class XpMziqFund:
    ticker: str
    company_id: str
    category_internal_names: tuple[str, ...]


XP_MZIQ_FUNDS: dict[str, XpMziqFund] = {
    "XPML11": XpMziqFund(
        ticker="XPML11",
        company_id="8071264f-09a1-481e-9c5e-25e5b370cd63",
        category_internal_names=("relatorios_gerenciais",),
    ),
}


def fund_for_ticker(ticker: str) -> XpMziqFund | None:
    return XP_MZIQ_FUNDS.get(ticker.strip().upper())


def build_years_target(ticker: str):
    from .mziq import build_years_target as _build_years_target

    fund = fund_for_ticker(ticker)
    if fund is None:
        raise ValueError(f"no MZIQ config registered for ticker {ticker!r}")
    return _build_years_target(fund.company_id, fund.category_internal_names)


def build_documents_target(ticker: str, year: int):
    from .mziq import build_documents_target as _build_documents_target

    fund = fund_for_ticker(ticker)
    if fund is None:
        raise ValueError(f"no MZIQ config registered for ticker {ticker!r}")
    return _build_documents_target(fund.company_id, year, fund.category_internal_names)
