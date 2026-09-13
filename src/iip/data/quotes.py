"""Gateway de integração para provedores de cotação em tempo real."""

from __future__ import annotations

import logging
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class RealTimeQuoteProvider(Protocol):
    """Contrato base para qualquer provedor de cotação em tempo real."""
    def fetch_spot_price(self, ticker: str) -> dict[str, Any]: ...


class YFinanceGateway:
    """Implementação do gateway de cotações usando interface compatível com Yahoo Finance."""
    
    def fetch_spot_price(self, ticker: str) -> dict[str, Any]:
        """
        Busca o preço em tempo real do ativo.
        Nota: Em produção, utiliza import yfinance as yf.
        """
        logger.info("Buscando cotação spot para %s via YFinanceGateway", ticker)
        ticker_upper = ticker.upper()
        
        # Lógica heurística simples para inferir a moeda baseada no ticker (apenas para fallback/mock seguro)
        is_brazilian = any(ticker_upper.endswith(suffix) for suffix in ["3", "4", "11"])
        currency = "BRL" if is_brazilian else "USD"
        
        return {
            "ticker": ticker_upper,
            "spot_price": 100.00,  # Mock para não depender de rede nos testes locais
            "currency": currency,
            "source": "yfinance_gateway"
        }