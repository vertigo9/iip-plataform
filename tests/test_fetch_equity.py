from iip.cli.fetch_template import fetch_equity_template_live
from iip.sources.b3_bolsai import BolsaiFundamentals
from iip.sources.b3_bolsai_harvester import BolsaiHTTPHarvester, FetchedFundamentals
from iip.sources.b3_brapi import BrapiQuote
from iip.sources.b3_brapi_harvester import BrapiHTTPHarvester, FetchedQuotes


def make_bolsai_fundamentals(**overrides):
    defaults = {
        "ticker": "PETR4",
        "close_price": 48.42,
        "market_cap": 315_000_000_000.0,
        "pl": 4.59,
        "pvp": 1.2,
        "ev_ebitda": 5.1,
        "roe": 0.35,
        "roic": 0.18,
        "net_margin": 0.15,
        "gross_margin": 0.30,
        "dividend_yield": 12.5,
        "net_debt_ebitda": 1.8,
        "lpa": 5.2,
        "vpa": 8.1,
        "ebitda": 90_000_000_000.0,
    }
    defaults.update(overrides)
    return BolsaiFundamentals(**defaults)


def test_fetch_equity_fills_only_price_market_cap_dividend_yield(monkeypatch):
    def fake_fetch(self, target):
        return FetchedFundamentals(
            target=target, status_code=200, fundamentals=make_bolsai_fundamentals()
        )

    monkeypatch.setattr(BolsaiHTTPHarvester, "fetch", fake_fetch)

    template, resultado = fetch_equity_template_live("PETR4", "fake-key", None)

    assert set(resultado.fetched_fields) == {"price", "market_cap", "dividend_yield"}
    assert template["price"] == 48.42
    assert template["market_cap"] == 315_000_000_000.0
    assert template["financials"]["dividend_yield"] == 12.5


def test_fetch_equity_never_fills_ratio_derived_fields(monkeypatch):
    def fake_fetch(self, target):
        return FetchedFundamentals(
            target=target, status_code=200, fundamentals=make_bolsai_fundamentals()
        )

    monkeypatch.setattr(BolsaiHTTPHarvester, "fetch", fake_fetch)

    _template, resultado = fetch_equity_template_live("PETR4", "fake-key", None)

    # revenue/net_income/equity/invested_capital/ebit are raw absolute
    # figures bolsai doesn't provide -- must stay at analyzer defaults,
    # never be guessed from bolsai's ratios (roe, roic, margins).
    for field in ("revenue", "net_income", "ebit", "equity", "invested_capital"):
        assert field not in resultado.fetched_fields


def test_fetch_equity_warns_about_the_scope_limitation(monkeypatch):
    def fake_fetch(self, target):
        return FetchedFundamentals(
            target=target, status_code=200, fundamentals=make_bolsai_fundamentals()
        )

    monkeypatch.setattr(BolsaiHTTPHarvester, "fetch", fake_fetch)

    _, resultado = fetch_equity_template_live("PETR4", "fake-key", None)
    assert any("valores-padrão do analisador" in w for w in resultado.warnings)


def test_fetch_equity_falls_back_to_brapi_price_only_without_bolsai_key(monkeypatch):
    def fake_fetch(self, target):
        return FetchedQuotes(
            target=target,
            status_code=200,
            quotes=(
                BrapiQuote(
                    symbol="PETR4",
                    short_name="PETROBRAS PN",
                    currency="BRL",
                    regular_market_price=48.42,
                    regular_market_change_percent=1.2,
                ),
            ),
        )

    monkeypatch.setattr(BrapiHTTPHarvester, "fetch", fake_fetch)

    template, resultado = fetch_equity_template_live("PETR4", None, "fake-token")

    assert resultado.fetched_fields == ("price",)
    assert template["price"] == 48.42
    assert template["market_cap"] is None
    assert template["financials"]["dividend_yield"] == 0


def test_fetch_equity_warns_when_no_credentials_at_all():
    template, resultado = fetch_equity_template_live("PETR4", None, None)

    assert template["price"] is None
    assert resultado.fetched_fields == ()
    assert any("Nem IIP_BOLSAI_API_KEY" in w for w in resultado.warnings)


def test_fetch_equity_continues_when_bolsai_fetch_fails(monkeypatch):
    def failing_fetch(self, target):
        raise RuntimeError("simulated outage")

    monkeypatch.setattr(BolsaiHTTPHarvester, "fetch", failing_fetch)

    template, resultado = fetch_equity_template_live("PETR4", "fake-key", None)

    assert template["price"] is None
    assert any("não consegui buscar fundamentos" in w for w in resultado.warnings)


def test_fetch_equity_continues_when_brapi_fetch_fails(monkeypatch):
    def failing_fetch(self, target):
        raise RuntimeError("simulated outage")

    monkeypatch.setattr(BrapiHTTPHarvester, "fetch", failing_fetch)

    template, resultado = fetch_equity_template_live("PETR4", None, "fake-token")

    assert template["price"] is None
    assert any("não consegui buscar preço via brapi" in w for w in resultado.warnings)
