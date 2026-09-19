"""HSI Gestora de Fundos Imobiliários' investor-relations documents via the MZIQ
platform (see ``iip.sources.mziq`` for the generic request/response shapes) --
the same lightweight, HTTP-only approach as ``iip.sources.btg_mziq``.

Confirmed live (19/09/2026) for HSML11 (HSI Malls). Like BTLG11's, the MZIQ config
is plainly embedded in the fund's own static page, no browser needed:
  - the company id sits in a literal ``var fmId = '<uuid>'`` assignment on
    https://hsml.hsifii.com/informacoes-aos-investidores/relatorios/ (the page also
    sets ``var fmName = 'HSI RI'`` and ``var fmBase =
    'https://api.mziq.com/mzfilemanager'``);
  - the category internal names are in ``categories.push({... internal_name: ...})``
    calls on the same page. Note HSI writes them with hyphens
    (``relatorio-gerencial``), where BTG uses underscores (``relatorios_gerenciais``).

The company id was checked against the API: it lists the monthly management
reports back to 2019, and the CNPJ in each file name (``32892018000131``) is
HSML11's.

Scope, as for the other MZIQ modules: DOCUMENT retrieval. The fundamentals
spreadsheet HSI publishes (category ``central-fundamentos-planilhas``) is listed
here but not parsed.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HsiMziqFund:
    ticker: str
    company_id: str
    category_internal_names: tuple[str, ...]


HSI_MZIQ_FUNDS: dict[str, HsiMziqFund] = {
    "HSML11": HsiMziqFund(
        ticker="HSML11",
        company_id="1bea7b91-2f45-4c39-99ab-5856eff6841b",
        category_internal_names=(
            "relatorio-gerencial",
            "tabela-rentabilidade",
            "xml-5.0",
            "central-fundamentos-planilhas",
        ),
    ),
}


def fund_for_ticker(ticker: str) -> HsiMziqFund | None:
    return HSI_MZIQ_FUNDS.get(ticker.strip().upper())


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
