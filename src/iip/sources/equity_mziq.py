"""Equity investor-relations documents via the MZIQ platform (see
``iip.sources.mziq`` for the generic request/response shapes) -- same
lightweight, HTTP-only approach as ``iip.sources.patria_mziq``/
``btg_mziq``, applied to the portfolio's equity registry positions.

ABCB4 (Banco ABC Brasil) confirmed live (18/09/2026, re-verified from
an earlier session's saved reconnaissance at
``mziq_reconhecimento/https_ri_abcbrasil_com_br_resultados_central_de_resultados/``)
-- its ``company_id``/categories were captured from real MZIQ API
traffic on https://ri.abcbrasil.com.br/resultados/central-de-resultados/.
This is also the concrete example ``iip.sources.mziq``'s own module
docstring already referenced as "confirmed live against ABC Brasil's
IR site" before any per-company config existed anywhere in the
codebase -- this module is that config, finally registered.

Other portfolio equities (BBSE3, ISAE4, CXSE3, CPFE3, CMIG4, SAUD3,
ALOS3, CSUD3, VBBR3, KLBN4, FESA4, LEVE3, PASS3) have not been
confirmed as MZIQ-hosted yet -- not included here rather than guessed.
Unlike the FII managers, most large-cap Brazilian public companies use
one of several other IR platforms (not just MZIQ), so this module
covering more than ABCB4 is not a given the way BTLG11 or the 7
static-listing FII managers were.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EquityMziqCompany:
    ticker: str
    company_id: str
    category_internal_names: tuple[str, ...]


EQUITY_MZIQ_COMPANIES: dict[str, EquityMziqCompany] = {
    "ABCB4": EquityMziqCompany(
        ticker="ABCB4",
        company_id="6298ef6f-2b75-43f8-b2ab-99e3fe33e809",
        category_internal_names=(
            "central-resultados-earnings-release",
            "central-resultados-dfp",
            "central-resultados-itr",
            "central-resultados-df-prudencial",
            "central-resultados-df",
            "central-resultados-apresentacao",
            "central-resultados-fact-sheet",
            "central-resultados-teleconferencia-slides",
            "central-resultados-teleconferencia",
            "central-resultados-transcricao",
            "central-resultados-series-historicas",
        ),
    ),
}


def company_for_ticker(ticker: str) -> EquityMziqCompany | None:
    return EQUITY_MZIQ_COMPANIES.get(ticker.strip().upper())


# Alias matching the fund_for_ticker/build_years_target/build_documents_target
# interface iip.cli.main._collect_mziq_manager_documents expects from any
# manager-specific MZIQ config module (see patria_mziq.py/btg_mziq.py) --
# "company" is the more accurate name for an equity issuer, but the shared
# CLI helper is generic across FII managers and equity issuers alike.
fund_for_ticker = company_for_ticker


def build_years_target(ticker: str):
    from .mziq import build_years_target as _build_years_target

    company = company_for_ticker(ticker)
    if company is None:
        raise ValueError(f"no MZIQ config registered for ticker {ticker!r}")
    return _build_years_target(company.company_id, company.category_internal_names)


def build_documents_target(ticker: str, year: int):
    from .mziq import build_documents_target as _build_documents_target

    company = company_for_ticker(ticker)
    if company is None:
        raise ValueError(f"no MZIQ config registered for ticker {ticker!r}")
    return _build_documents_target(
        company.company_id, year, company.category_internal_names
    )
