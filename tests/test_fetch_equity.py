import pytest

from iip.cli.fetch_template import fetch_equity_template_live
from iip.sources.b3_bolsai import BolsaiFundamentals
from iip.sources.b3_bolsai_harvester import BolsaiHTTPHarvester, FetchedFundamentals
from iip.sources.b3_brapi import BrapiQuote
from iip.sources.b3_brapi_harvester import BrapiHTTPHarvester, FetchedQuotes
from iip.sources.cvm_dfp_harvester import CvmDfpHTTPHarvester
from tests.test_cvm_dfp import BANK_CNPJ, HOLDING_CNPJ, NON_FINANCIAL_CNPJ, make_zip

CNPJ = NON_FINANCIAL_CNPJ  # ABCB4's real registry CNPJ is the "bank" fixture;
# most tests below use the non-financial fixture company since it has a
# complete real-looking dataset (equity/net_income/revenue/ebit/invested_capital).


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


def _mock_dfp_with_fixture(monkeypatch):
    def fake_fetch(self, target):
        import iip.sources.cvm_dfp_harvester as mod

        body = make_zip()
        return mod.FetchedDfpYear(
            target=target,
            status_code=200,
            bpa_con=mod.parse_bpa_con(body),
            bpa_ind=mod.parse_bpa_ind(body),
            bpp_con=mod.parse_bpp_con(body),
            bpp_ind=mod.parse_bpp_ind(body),
            dre_con=mod.parse_dre_con(body),
            dre_ind=mod.parse_dre_ind(body),
        )

    monkeypatch.setattr(CvmDfpHTTPHarvester, "fetch", fake_fetch)


def test_fetch_equity_fills_price_market_cap_dividend_yield(monkeypatch):
    def fake_fetch(self, target):
        return FetchedFundamentals(
            target=target, status_code=200, fundamentals=make_bolsai_fundamentals()
        )

    monkeypatch.setattr(BolsaiHTTPHarvester, "fetch", fake_fetch)
    _mock_dfp_with_fixture(monkeypatch)

    template, resultado = fetch_equity_template_live(
        "PETR4", "00.000.000/0000-00", 2025, "fake-key", None
    )

    assert "price" in resultado.fetched_fields
    assert "market_cap" in resultado.fetched_fields
    assert "dividend_yield" in resultado.fetched_fields
    assert template["price"] == 48.42
    assert template["market_cap"] == 315_000_000_000.0
    assert template["financials"]["dividend_yield"] == 12.5


def test_fetch_equity_fills_real_dfp_fundamentals_for_non_financial_company(monkeypatch):
    def fake_bolsai(self, target):
        raise RuntimeError("no bolsai in this test")

    monkeypatch.setattr(BolsaiHTTPHarvester, "fetch", fake_bolsai)
    _mock_dfp_with_fixture(monkeypatch)

    template, resultado = fetch_equity_template_live(
        "KLBN4", NON_FINANCIAL_CNPJ, 2025, "fake-key", None
    )

    fin = template["financials"]
    assert fin["equity"] == 14401101.0
    assert fin["net_income"] == 1678211.0
    assert fin["revenue"] == 20697507.0
    assert fin["ebit"] == 4480349.0
    assert fin["invested_capital"] == 14401101.0 + 40628278.0
    for field in ("equity", "net_income", "revenue", "ebit", "invested_capital"):
        assert field in resultado.fetched_fields


def test_fetch_equity_leaves_ebit_and_invested_capital_at_default_for_bank(monkeypatch):
    def fake_bolsai(self, target):
        raise RuntimeError("no bolsai in this test")

    monkeypatch.setattr(BolsaiHTTPHarvester, "fetch", fake_bolsai)
    _mock_dfp_with_fixture(monkeypatch)

    template, resultado = fetch_equity_template_live(
        "ABCB4", BANK_CNPJ, 2025, "fake-key", None
    )

    fin = template["financials"]
    assert fin["equity"] == 6758948.0
    assert fin["net_income"] == 1002000.0
    assert "ebit" not in resultado.fetched_fields
    assert "invested_capital" not in resultado.fetched_fields
    assert any("EBIT não encontrado" in w for w in resultado.warnings)


def test_fetch_equity_treats_zeroed_holding_revenue_as_unavailable(monkeypatch):
    def fake_bolsai(self, target):
        raise RuntimeError("no bolsai in this test")

    monkeypatch.setattr(BolsaiHTTPHarvester, "fetch", fake_bolsai)
    _mock_dfp_with_fixture(monkeypatch)

    template, resultado = fetch_equity_template_live(
        "BBSE3", HOLDING_CNPJ, 2025, "fake-key", None
    )

    fin = template["financials"]
    assert fin["net_income"] == 9017329.0
    assert "revenue" not in resultado.fetched_fields
    assert any("Receita" in w and "zerada" in w for w in resultado.warnings)


def test_fetch_equity_fills_debt_to_equity_from_standard_dfp_lines(monkeypatch):
    def fake_bolsai(self, target):
        raise RuntimeError("no bolsai in this test")

    monkeypatch.setattr(BolsaiHTTPHarvester, "fetch", fake_bolsai)
    _mock_dfp_with_fixture(monkeypatch)

    template, resultado = fetch_equity_template_live(
        "KLBN4", NON_FINANCIAL_CNPJ, 2025, "fake-key", None
    )
    assert "debt_to_equity" in resultado.fetched_fields
    assert template["financials"]["debt_to_equity"] == pytest.approx(
        36721042 / 14401101, abs=1e-4
    )


def test_fetch_equity_never_reports_zero_debt_total_as_debt_to_equity(monkeypatch):
    from tests.test_cvm_dfp import ZERO_DEBT_CNPJ

    def fake_bolsai(self, target):
        raise RuntimeError("no bolsai in this test")

    monkeypatch.setattr(BolsaiHTTPHarvester, "fetch", fake_bolsai)
    _mock_dfp_with_fixture(monkeypatch)

    _template, resultado = fetch_equity_template_live(
        "ALOS3", ZERO_DEBT_CNPJ, 2025, "fake-key", None
    )
    assert "debt_to_equity" not in resultado.fetched_fields
    assert any("debt_to_equity" in w for w in resultado.warnings)


def test_fetch_equity_computes_real_3y_cagr_from_two_distinct_dfp_years(monkeypatch):
    def fake_bolsai(self, target):
        raise RuntimeError("no bolsai in this test")

    def fake_dfp(self, target):
        import iip.sources.cvm_dfp_harvester as mod

        body = make_zip()  # PENÚLTIMO rows encode the "3 years ago" case
        return mod.FetchedDfpYear(
            target=target,
            status_code=200,
            bpa_con=mod.parse_bpa_con(body),
            bpa_ind=mod.parse_bpa_ind(body),
            bpp_con=mod.parse_bpp_con(body),
            bpp_ind=mod.parse_bpp_ind(body),
            dre_con=mod.parse_dre_con(body),
            dre_ind=mod.parse_dre_ind(body),
        )

    monkeypatch.setattr(BolsaiHTTPHarvester, "fetch", fake_bolsai)
    monkeypatch.setattr(CvmDfpHTTPHarvester, "fetch", fake_dfp)

    # Fixture only encodes one real "ÚLTIMO" snapshot per CNPJ -- both the
    # ano=2025 and ano_base=2022 fetches return the identical fixture data,
    # so growth comes out to 0% (same values both times). That's still a
    # real exercise of the CAGR wiring end-to-end (two separate DFP fetches,
    # two extract_fundamentals calls, a real division) -- not the "no data"
    # path (which leaves the field absent, not present-with-zero).
    _template, resultado = fetch_equity_template_live(
        "KLBN4", NON_FINANCIAL_CNPJ, 2025, "fake-key", None
    )
    for field in ("revenue_growth_3y", "earnings_growth_3y", "book_value_growth_3y"):
        assert field in resultado.fetched_fields
    fin = _template["financials"]
    assert fin["revenue_growth_3y"] == 0.0
    assert fin["earnings_growth_3y"] == 0.0
    assert fin["book_value_growth_3y"] == 0.0
    assert any("Crescimento 3y" in w for w in resultado.warnings)


def test_fetch_equity_continues_when_dfp_fetch_fails(monkeypatch):
    def fake_bolsai(self, target):
        return FetchedFundamentals(
            target=target, status_code=200, fundamentals=make_bolsai_fundamentals()
        )

    def failing_dfp(self, target):
        raise RuntimeError("simulated CVM outage")

    monkeypatch.setattr(BolsaiHTTPHarvester, "fetch", fake_bolsai)
    monkeypatch.setattr(CvmDfpHTTPHarvester, "fetch", failing_dfp)

    template, resultado = fetch_equity_template_live(
        "PETR4", "00.000.000/0000-00", 2025, "fake-key", None
    )

    assert template["price"] == 48.42  # bolsai path unaffected by DFP failure
    assert any("não consegui buscar DFP" in w for w in resultado.warnings)
    for field in ("equity", "net_income", "revenue", "ebit"):
        assert field not in resultado.fetched_fields


def test_fetch_equity_warns_about_remaining_qualitative_defaults(monkeypatch):
    def fake_bolsai(self, target):
        return FetchedFundamentals(
            target=target, status_code=200, fundamentals=make_bolsai_fundamentals()
        )

    monkeypatch.setattr(BolsaiHTTPHarvester, "fetch", fake_bolsai)
    _mock_dfp_with_fixture(monkeypatch)

    _, resultado = fetch_equity_template_live(
        "PETR4", "00.000.000/0000-00", 2025, "fake-key", None
    )
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
    _mock_dfp_with_fixture(monkeypatch)

    template, resultado = fetch_equity_template_live(
        "PETR4", "00.000.000/0000-00", 2025, None, "fake-token"
    )

    assert "price" in resultado.fetched_fields
    assert template["price"] == 48.42
    assert template["market_cap"] is None
    assert template["financials"]["dividend_yield"] == 0


def test_fetch_equity_warns_when_no_price_credentials_at_all(monkeypatch):
    _mock_dfp_with_fixture(monkeypatch)

    template, resultado = fetch_equity_template_live(
        "PETR4", "00.000.000/0000-00", 2025, None, None
    )

    assert template["price"] is None
    assert any("Nem IIP_BOLSAI_API_KEY" in w for w in resultado.warnings)


def test_fetch_equity_continues_when_bolsai_fetch_fails(monkeypatch):
    def failing_fetch(self, target):
        raise RuntimeError("simulated outage")

    monkeypatch.setattr(BolsaiHTTPHarvester, "fetch", failing_fetch)
    _mock_dfp_with_fixture(monkeypatch)

    template, resultado = fetch_equity_template_live(
        "PETR4", "00.000.000/0000-00", 2025, "fake-key", None
    )

    assert template["price"] is None
    assert any("não consegui buscar fundamentos" in w for w in resultado.warnings)


def test_fetch_equity_continues_when_brapi_fetch_fails(monkeypatch):
    def failing_fetch(self, target):
        raise RuntimeError("simulated outage")

    monkeypatch.setattr(BrapiHTTPHarvester, "fetch", failing_fetch)
    _mock_dfp_with_fixture(monkeypatch)

    template, resultado = fetch_equity_template_live(
        "PETR4", "00.000.000/0000-00", 2025, None, "fake-token"
    )

    assert template["price"] is None
    assert any("não consegui buscar preço via brapi" in w for w in resultado.warnings)
