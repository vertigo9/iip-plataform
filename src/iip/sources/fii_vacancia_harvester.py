"""HTTP transport for ``iip.sources.fii_vacancia``: acha o relatório mais recente
da gestora, baixa o PDF e lê a vacância (ver o docstring do módulo puro)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from io import BytesIO
from urllib.request import Request, urlopen

from .fii_vacancia import (
    VacanciaReading,
    latest_hedge_url,
    latest_knri_url,
    latest_rbva_url,
    latest_trx_url,
    profile_for_ticker,
)


@dataclass(frozen=True)
class FetchedVacancia:
    ticker: str
    source_url: str
    reading: VacanciaReading | None


class FiiVacanciaHTTPHarvester:
    def __init__(
        self,
        opener: Callable[..., object] | None = None,
        *,
        timeout: float = 60.0,
        user_agent: str = "IIP-D-OBSIDIAN/1.0",
    ) -> None:
        self._opener = opener or urlopen
        self.timeout = timeout
        self.user_agent = user_agent

    def _download(self, url: str) -> bytes:
        request = Request(url, headers={"User-Agent": self.user_agent}, method="GET")
        response = self._opener(request, timeout=self.timeout)
        return response.read()

    def _latest_url(self, ticker: str) -> str | None:
        from . import btg_mziq
        from .static_pdf_listing_harvester import StaticPdfListingHTTPHarvester

        if btg_mziq.fund_for_ticker(ticker) is not None:
            return self._latest_btg_url(ticker)
        documents = StaticPdfListingHTTPHarvester(
            self._opener, timeout=self.timeout, user_agent=self.user_agent
        ).collect(ticker)
        urls = [document.url for document in documents]
        if ticker == "TRXF11":
            return latest_trx_url(urls)
        if ticker == "HGBS11":
            return latest_hedge_url(urls)
        if ticker == "RBVA11":
            return latest_rbva_url(urls)
        if ticker == "KNRI11":
            return latest_knri_url(urls)
        return None

    def _latest_btg_url(self, ticker: str) -> str | None:
        from .btg_mziq import build_documents_target, build_years_target
        from .mziq_harvester import MziqHTTPHarvester

        mziq = MziqHTTPHarvester(
            self._opener, timeout=self.timeout, user_agent=self.user_agent
        )
        # do ano mais recente para trás: o primeiro com relatório gerencial publicado
        for year in sorted(mziq.fetch_years(build_years_target(ticker)), reverse=True):
            reports = [
                d
                for d in mziq.fetch_documents(build_documents_target(ticker, year))
                if d.category == "relatorios_gerenciais" and d.is_published and d.url
            ]
            if reports:
                return max(reports, key=lambda d: d.file_date or "").url
        return None

    def fetch(self, ticker: str) -> FetchedVacancia | None:
        """``None`` quando o ticker não tem perfil ou nenhum relatório foi achado;
        ``reading=None`` quando o PDF veio mas o layout não casou."""
        from pypdf import PdfReader

        ticker = ticker.strip().upper()
        profile = profile_for_ticker(ticker)
        if profile is None:
            return None
        url = self._latest_url(ticker)
        if url is None:
            return None
        reader = PdfReader(BytesIO(self._download(url)))
        text = "\n".join(
            page.extract_text() or "" for page in reader.pages[: profile.max_pages]
        )
        return FetchedVacancia(ticker, url, profile.parser(text))
