"""Gateway de integração para provedores de cotação em tempo real e câmbio."""

from __future__ import annotations

import logging
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class RealTimeQuoteProvider(Protocol):
    """Contrato base para provedores de cotação e câmbio."""
    def fetch_spot_price(self, ticker: str) -> dict[str, Any]: ...
    def fetch_exchange_rate(self, base_currency: str, target_currency: str) -> float: ...


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
            "spot_price": 100.00,  # Mock seguro
            "currency": currency,
            "source": "yfinance_gateway"
        }

    def fetch_exchange_rate(self, base_currency: str, target_currency: str) -> float:
        """Busca a taxa de câmbio entre duas moedas."""
        logger.info("Buscando câmbio: %s -> %s", base_currency, target_currency)
        if base_currency == target_currency:
            return 1.0
        
        # Em produção, usa yf.download(f"{base_currency}{target_currency}=X")
        if base_currency == "USD" and target_currency == "BRL":
            return 5.50  # Mock rate de USD para BRL
        if base_currency == "BRL" and target_currency == "USD":
            return 1 / 5.50
            
        return 1.0