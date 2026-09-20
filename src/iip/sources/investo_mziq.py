"""Investo ETF documents (regulamento, índice, tributação, fatores de
risco, comunicados, "as cotas") via the MZIQ platform -- the same
lightweight, HTTP-only approach as ``iip.sources.btg_mziq``, applied to
the Investo Trend Fixed Income ETFs.

Confirmed live (20/09/2026) for LFTB11 only: the ``documentos`` section of
https://www.investoetf.com/etf/lftb11 is an MZIQ file manager whose
``company_id`` and category internal names (all prefixed ``LFTB11_``) sit
in the page itself. This is for DOCUMENT retrieval; the ETF's NAV, cost,
tracking and flows come from ``iip.sources.investo_etf``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InvestoMziqFund:
    ticker: str
    company_id: str
    category_internal_names: tuple[str, ...]


INVESTO_MZIQ_FUNDS: dict[str, InvestoMziqFund] = {
    "LFTB11": InvestoMziqFund(
        ticker="LFTB11",
        company_id="02c0bf8f-2988-419f-9a6f-4e116a4bf822",
        category_internal_names=(
            "LFTB11_Instrumento",
            "LFTB11_Comunicado",
            "LFTB11_O_indice",
            "LFTB11_Regulamento",
            "LFTB11_Tributacao",
            "LFTB11_Fatores_de_risco",
            "LFTB11_As_cotas",
        ),
    ),
}


def fund_for_ticker(ticker: str) -> InvestoMziqFund | None:
    return INVESTO_MZIQ_FUNDS.get(ticker.strip().upper())


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
