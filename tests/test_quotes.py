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
    result = gateway.fetch_spot_price("AAPL")

    assert result["ticker"] == "AAPL"
    assert result["currency"] == "USD"
    assert result["source"] == "yfinance_gateway"


def test_yfinance_gateway_exchange_rate():
    gateway = YFinanceGateway()
    rate = gateway.fetch_exchange_rate("USD", "BRL")
    assert rate == 5.50

    rate_same = gateway.fetch_exchange_rate("BRL", "BRL")
    assert rate_same == 1.0


def test_yfinance_gateway_dividends():
    gateway = YFinanceGateway()
    result = gateway.fetch_dividends("HGLG11")

    assert result["ticker"] == "HGLG11"
    assert result["dividend_yield_ttm"] > 0
    assert result["annual_payout_brl"] > 0
    assert result["monthly_payout_brl"] == round(result["annual_payout_brl"] / 12, 2)
