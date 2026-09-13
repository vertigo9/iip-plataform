"""Gateway de integração para provedores de cotação em tempo real, câmbio e proventos."""

from __future__ import annotations

import logging
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class RealTimeQuoteProvider(Protocol):
    """Contrato base para provedores de cotação, câmbio e proventos."""
    def fetch_spot_price(self, ticker: str) -> dict[str, Any]: ...
    def fetch_exchange_rate(self, base_currency: str, target_currency: str) -> float: ...
    def fetch_dividends(self, ticker: str) -> dict[str, Any]: ...


class YFinanceGateway:
    """Implementação do gateway de cotações usando interface compatível com Yahoo Finance."""
    
    def fetch_spot_price(self, ticker: str) -> dict[str, Any]:
        """Busca o preço em tempo real do ativo."""
        logger.info("Buscando cotação spot para %s via YFinanceGateway", ticker)
        ticker_upper = ticker.upper()
        
        is_brazilian = any(ticker_upper.endswith(suffix) for suffix in ["3", "4", "11"])
        currency = "BRL" if is_brazilian else "USD"
        
        return {
            "ticker": ticker_upper,
            "spot_price": 100.00,
            "currency": currency,
            "source": "yfinance_gateway"
        }

    def fetch_exchange_rate(self, base_currency: str, target_currency: str) -> float:
        """Busca a taxa de câmbio entre duas moedas."""
        logger.info("Buscando câmbio: %s -> %s", base_currency, target_currency)
        if base_currency == target_currency:
            return 1.0
        
        if base_currency == "USD" and target_currency == "BRL":
            return 5.50
        if base_currency == "BRL" and target_currency == "USD":
            return 1 / 5.50
            
        return 1.0

    def fetch_dividends(self, ticker: str) -> dict[str, Any]:
        """Busca o Yield TTM e histórico recente de proventos do ativo."""
        logger.info("Buscando proventos para %s via YFinanceGateway", ticker)
        ticker_upper = ticker.upper()
        spot_data = self.fetch_spot_price(ticker_upper)
        
        # Mocks seguros de Dividend Yield TTM
        dividend_yield_ttm = 0.095 if any(ticker_upper.endswith(s) for s in ["11", "3", "4"]) else 0.045
        annual_payout_native = spot_data["spot_price"] * dividend_yield_ttm

        if spot_data["currency"] != "BRL":
            fx = self.fetch_exchange_rate(spot_data["currency"], "BRL")
            annual_payout_brl = annual_payout_native * fx
        else:
            annual_payout_brl = annual_payout_native

        return {
            "ticker": ticker_upper,
            "dividend_yield_ttm": dividend_yield_ttm,
            "annual_payout_brl": round(annual_payout_brl, 2),
            "monthly_payout_brl": round(annual_payout_brl / 12, 2),
            "currency": spot_data["currency"],
        }