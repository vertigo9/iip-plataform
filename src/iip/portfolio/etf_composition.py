"""Composição da carteira de um ETF de renda fixa para o vault: busca na CDA e texto da
seção ``IIP:portfolio_composition`` da nota "Carteira e Crédito".

Só descreve o que a CDA mostra (ver ``iip.sources.cvm_cda_etf``); nenhum número aqui entra
em score ou valuation.
"""

from __future__ import annotations

import datetime as _dt

from iip.sources.cvm_cda import recent_months
from iip.sources.cvm_cda_etf import (
    CdaEtfPortfolio,
    bond_weights,
    bonds_coverage,
    share_maturing_after_years,
    weighted_average_maturity_years,
)
from iip.sources.cvm_cda_harvester import CvmCdaHTTPHarvester, FetchedEtfCda, fetch_etf

LONG_DATED_YEARS = 10


def default_fetch_etf_cda(cnpj: str) -> FetchedEtfCda:
    # data de calendário (quais meses tentar), não timestamp
    months = recent_months(_dt.date.today())  # noqa: DTZ011
    return fetch_etf(CvmCdaHTTPHarvester(), cnpj, months=months)


def render_composition(portfolio: CdaEtfPortfolio, source_url: str) -> str:
    wam = weighted_average_maturity_years(portfolio)
    long_dated = share_maturing_after_years(portfolio, LONG_DATED_YEARS)
    lines = [
        f"Carteira em {portfolio.reference_date:%d/%m/%Y} (CDA da CVM, competência "
        f"{portfolio.month}): patrimônio líquido de R$ {portfolio.net_assets / 1e6:,.1f} mi, "
        f"{len(portfolio.bonds)} títulos públicos = "
        f"{bonds_coverage(portfolio):.1%} do patrimônio.",
        "",
        "| Vencimento | Peso |",
        "|---|---:|",
    ]
    lines += [
        f"| {maturity:%d/%m/%Y} | {weight:.2%} |"
        for maturity, weight in bond_weights(portfolio)
    ]
    lines.append("")
    if wam is not None:
        lines.append(
            f"Prazo médio ponderado até o vencimento: {wam:.1f} anos (não é duration)."
        )
    lines.append(
        f"Vencendo em mais de {LONG_DATED_YEARS} anos: {long_dated:.1%} do patrimônio."
    )
    lines += [
        "",
        "O tipo de cada título não vem na CDA (só vencimento e valor de mercado). A "
        "composição é do fim do mês, com ~3 semanas de defasagem, e não muda o score nem o "
        f"valuation. Fonte: {source_url}",
    ]
    return "\n".join(lines)
