"""Transporte de ``iip.sources.fii_distribution_reports``: acha o relatório mais recente da
gestora (a mesma busca que ``FiiVacanciaHTTPHarvester`` faz para a ocupação), baixa o PDF e
lê a distribuição por cota declarada. Para HGCR11 e PCIP11 lê a planilha de fundamentos da
Pátria (``rendimento_cota``)."""

from __future__ import annotations

from io import BytesIO

from .fii_distribution_reports import DeclaredDistribution, read_declared, supports
from .fii_vacancia_harvester import FiiVacanciaHTTPHarvester

# a planilha de crédito da Pátria traz o rendimento por cota do último mês
PATRIA_SHEET_TICKERS = frozenset({"HGCR11", "PCIP11"})
_MAX_PAGES = 12


class FiiDistributionHTTPHarvester(FiiVacanciaHTTPHarvester):
    def fetch_distribution(self, ticker: str) -> DeclaredDistribution | None:
        """``None`` se o fundo não tem leitor, nenhum relatório foi achado ou o texto não
        casa com o layout esperado."""
        from pypdf import PdfReader

        ticker = ticker.strip().upper()
        if not supports(ticker):
            return None
        url = self._latest_url(ticker)
        if url is None:
            return None
        reader = PdfReader(BytesIO(self._download(url)))
        text = "\n".join(
            page.extract_text() or "" for page in reader.pages[:_MAX_PAGES]
        )
        return read_declared(ticker, text, url)

    def fetch_patria_sheet(self, ticker: str) -> DeclaredDistribution | None:
        from .patria_planilha_fundamentos_harvester import (
            PatriaPlanilhaFundamentosHTTPHarvester,
        )

        ticker = ticker.strip().upper()
        if ticker not in PATRIA_SHEET_TICKERS:
            return None
        result = PatriaPlanilhaFundamentosHTTPHarvester().fetch(ticker)
        credit = result.credito
        if credit is None or not credit.rendimento_cota or credit.rendimento_cota <= 0:
            return None
        return DeclaredDistribution(
            ticker,
            credit.rendimento_cota,
            "planilha de fundamentos da Pátria",
            f"rendimento por cota do último mês na planilha "
            f"(competência {credit.competencia})",
            competencia=(f"{credit.competencia:%Y-%m}" if credit.competencia else None),
        )
