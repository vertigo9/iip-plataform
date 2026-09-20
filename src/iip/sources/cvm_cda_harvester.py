"""HTTP transport for ``iip.sources.cvm_cda``: baixa o zip da CDA do mês e lê o fundo."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .cvm_cda import CdaError, CdaPortfolio, build_url, parse_cda_zip
from .cvm_cda_etf import CdaEtfPortfolio, parse_cda_etf_zip


@dataclass(frozen=True)
class FetchedCda:
    portfolio: CdaPortfolio
    url: str


class CvmCdaHTTPHarvester:
    def __init__(
        self,
        opener: Callable[..., object] | None = None,
        *,
        timeout: float = 180.0,
        user_agent: str = "IIP-D-OBSIDIAN/1.0",
    ) -> None:
        self._opener = opener or urlopen
        self.timeout = timeout
        self.user_agent = user_agent

    def _download(self, url: str) -> bytes | None:
        """``None`` para um mês ainda não publicado (404); qualquer outra falha propaga."""
        request = Request(url, headers={"User-Agent": self.user_agent}, method="GET")
        try:
            response = self._opener(request, timeout=self.timeout)
        except HTTPError as exc:
            if exc.code == 404:
                return None
            raise
        return response.read()

    def fetch(self, cnpj: str, *, months: Iterable[str]) -> FetchedCda:
        """A carteira do fundo no primeiro mês de ``months`` (do mais novo para o mais
        velho) em que a CDA foi publicada E o fundo aparece. ``CdaError`` se nenhum serve.
        """
        tried = []
        for month in months:
            url = build_url(month)
            body = self._download(url)
            if body is None:
                tried.append(f"{month} (não publicado)")
                continue
            portfolio = parse_cda_zip(body, cnpj, month)
            if portfolio is None:
                tried.append(f"{month} (fundo ausente)")
                continue
            return FetchedCda(portfolio, url)
        raise CdaError(
            f"sem CDA utilizável para o CNPJ {cnpj}: "
            + (", ".join(tried) or "nenhum mês")
        )


@dataclass(frozen=True)
class FetchedEtfCda:
    portfolio: CdaEtfPortfolio
    url: str


def fetch_etf(
    harvester: CvmCdaHTTPHarvester, cnpj: str, *, months: Iterable[str]
) -> FetchedEtfCda:
    """Como ``CvmCdaHTTPHarvester.fetch``, para um ETF de renda fixa (arquivo
    ``cda_fie``): a carteira no primeiro mês publicado em que o fundo aparece."""
    tried = []
    for month in months:
        url = build_url(month)
        body = harvester._download(url)
        if body is None:
            tried.append(f"{month} (não publicado)")
            continue
        portfolio = parse_cda_etf_zip(body, cnpj, month)
        if portfolio is None:
            tried.append(f"{month} (fundo ausente)")
            continue
        return FetchedEtfCda(portfolio, url)
    raise CdaError(
        f"sem CDA de ETF utilizável para o CNPJ {cnpj}: "
        + (", ".join(tried) or "nenhum mês")
    )
