"""HTTP transport for ``iip.sources.investo_etf``: dois GETs públicos, sem login, a
ficha do produto e o histórico de cotas do ETF (ver o docstring do módulo puro)."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from urllib.request import Request, urlopen

from .investo_etf import (
    InvestoEtfError,
    InvestoNavPoint,
    InvestoProduct,
    InvestoReturns,
    history_url,
    parse_history,
    parse_product,
    parse_returns,
    product_url,
    returns_url,
    same_cnpj,
    supports,
)


@dataclass(frozen=True)
class FetchedInvestoEtf:
    ticker: str
    product: InvestoProduct
    points: tuple[InvestoNavPoint, ...]

    @property
    def latest(self) -> InvestoNavPoint:
        return self.points[-1]


class InvestoEtfHTTPHarvester:
    def __init__(
        self,
        opener: Callable[..., object] | None = None,
        *,
        timeout: float = 30.0,
        user_agent: str = "IIP-D-OBSIDIAN/1.0",
    ) -> None:
        self._opener = opener or urlopen
        self.timeout = timeout
        self.user_agent = user_agent

    def _get_json(self, url: str) -> object:
        request = Request(
            url,
            headers={"User-Agent": self.user_agent, "Accept": "application/json"},
            method="GET",
        )
        response = self._opener(request, timeout=self.timeout)
        return json.loads(response.read().decode("utf-8"))

    def fetch(
        self, ticker: str, *, expected_cnpj: str | None = None
    ) -> FetchedInvestoEtf:
        """Levanta ``InvestoEtfError`` se o ticker não foi verificado, se a ficha ou o
        histórico não vêm no formato esperado, ou se o CNPJ da ficha não é o
        ``expected_cnpj`` (a cota de outro fundo jamais é devolvida)."""
        ticker = ticker.strip().upper()
        if not supports(ticker):
            raise InvestoEtfError(f"{ticker} não é um ETF verificado nesta fonte")
        product = parse_product(self._get_json(product_url(ticker)))
        if product is None:
            raise InvestoEtfError(f"ficha de {ticker} fora do formato esperado")
        if product.ticker != ticker:
            raise InvestoEtfError(
                f"a ficha pedida para {ticker} é a de {product.ticker}"
            )
        if expected_cnpj is not None and not same_cnpj(product.cnpj, expected_cnpj):
            raise InvestoEtfError(
                f"CNPJ da ficha ({product.cnpj}) difere do esperado ({expected_cnpj})"
            )
        points = parse_history(self._get_json(history_url(ticker)))
        if not points:
            raise InvestoEtfError(f"histórico de cotas de {ticker} vazio ou ilegível")
        return FetchedInvestoEtf(ticker, product, points)

    def fetch_returns(self, ticker: str) -> InvestoReturns:
        """A rentabilidade oficial (tabela por período e série diária ETF x índice).
        Levanta ``InvestoEtfError`` se o ticker não foi verificado ou a resposta não é a
        do fundo pedido. Separado do ``fetch``: o NAV do valuation não depende dela."""
        ticker = ticker.strip().upper()
        if not supports(ticker):
            raise InvestoEtfError(f"{ticker} não é um ETF verificado nesta fonte")
        returns = parse_returns(self._get_json(returns_url(ticker)))
        if returns is None:
            raise InvestoEtfError(f"rentabilidade de {ticker} fora do formato esperado")
        if returns.ticker != ticker:
            raise InvestoEtfError(
                f"a rentabilidade pedida para {ticker} é a de {returns.ticker or '?'}"
            )
        return returns
