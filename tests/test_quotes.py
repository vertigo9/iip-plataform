"""Testes unitários para o gateway de cotações em tempo real."""

from iip.data.quotes import YFinanceGateway


def test_yfinance_gateway_spot_price_brl():
    gateway = YFinanceGateway()
    result = gateway.fetch_spot_price("PETR4")
    
    assert result["ticker"] == "PETR4"
    assert result["currency"] == "BRL"
    assert result["spot_price"] > 0


def test_yfinance_gateway_spot_price_usd():
    gateway = YFinanceGateway()
    result = gateway.fetch_spot_price("AAPL") # Stock Internacional
    
    assert result["ticker"] == "AAPL"
    assert result["currency"] == "USD"
    assert result["source"] == "yfinance_gateway"