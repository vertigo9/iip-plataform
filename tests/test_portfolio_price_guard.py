"""A batch must not persist an analysis when a market-data provider that WAS
configured failed to deliver the price (the bolsai daily-quota incident)."""

import json
from datetime import date
from typing import ClassVar

import pytest

from iip.portfolio.batch_analyze import analyze_portfolio
from iip.portfolio.batch_value import value_portfolio
from iip.portfolio.refresh import missing_required_market_data, refresh_portfolio
from iip.portfolio.registry import PortfolioAsset
from iip.sources.tesouro_direto import NtnbRate

RATE = NtnbRate(reference_date=date(2026, 9, 17), maturity=date(2060, 8, 15), real_yield=0.073)


# --- the guard itself ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("template_type", "kwargs"),
    [
        ("fii", {"bolsai_api_key": "k", "brapi_token": None}),
        ("equity", {"bolsai_api_key": "k", "brapi_token": None}),
        ("equity", {"bolsai_api_key": None, "brapi_token": "t"}),
        ("etf", {"bolsai_api_key": None, "brapi_token": "t"}),
        ("fiagro", {"bolsai_api_key": None, "brapi_token": "t"}),
    ],
)
def test_a_missing_price_with_the_provider_configured_is_a_failed_fetch(template_type, kwargs):
    reason = missing_required_market_data(template_type, {"price": None}, **kwargs)

    assert reason is not None
    assert "preço indisponível" in reason and "nada gravado" in reason
    assert len(reason) < 80  # survives the batch tables' 80-char column


@pytest.mark.parametrize("template_type", ["fii", "equity", "etf", "fiagro"])
def test_a_present_price_is_fine(template_type):
    assert missing_required_market_data(
        template_type, {"price": 10.0}, bolsai_api_key="k", brapi_token="t"
    ) is None


@pytest.mark.parametrize("template_type", ["fii", "equity", "etf", "fiagro"])
def test_running_offline_on_purpose_is_never_flagged(template_type):
    assert missing_required_market_data(
        template_type, {"price": None}, bolsai_api_key=None, brapi_token=None
    ) is None


def test_the_provider_that_matters_is_the_one_for_the_class():
    # only a brapi token configured: a FII (bolsai class) has no credential to fail
    assert missing_required_market_data(
        "fii", {"price": None}, bolsai_api_key=None, brapi_token="t"
    ) is None
    # only a bolsai key configured: an ETF (brapi class) likewise
    assert missing_required_market_data(
        "etf", {"price": None}, bolsai_api_key="k", brapi_token=None
    ) is None


@pytest.mark.parametrize("template_type", ["fixed_income", None, "unknown"])
def test_classes_with_no_price_in_their_template_are_never_flagged(template_type):
    assert missing_required_market_data(
        template_type, {"price": None}, bolsai_api_key="k", brapi_token="t"
    ) is None


# --- refresh ---------------------------------------------------------------------------


def _fii(ticker="BTLG11"):
    return PortfolioAsset(
        ticker, "fund", subtype="FII", structure="Tijolo", segment="Logístico",
        cnpj="00.000.000/0000-00",
    )


def _fetcher(price):
    def fetch(symbol, cnpj, ano, bolsai_api_key):
        return {"price": price, "financials": {}}, type("R", (), {"fetched_fields": (), "warnings": ()})()

    return fetch


def test_refresh_reports_an_error_and_writes_no_snapshot_when_the_price_is_missing(tmp_path):
    result = refresh_portfolio(
        tmp_path, bolsai_api_key="k", brapi_token=None, ano=2026, mes=8,
        positions=(_fii(),), fetch_fii=_fetcher(None),
    )

    assert [o.status for o in result.outcomes] == ["erro"]
    assert "preço indisponível" in result.outcomes[0].detail
    assert not list(tmp_path.rglob("BTLG11.json"))


def test_refresh_still_writes_the_snapshot_when_the_price_is_there(tmp_path):
    result = refresh_portfolio(
        tmp_path, bolsai_api_key="k", brapi_token=None, ano=2026, mes=8,
        positions=(_fii(),), fetch_fii=_fetcher(99.78),
    )

    assert [o.status for o in result.outcomes] == ["ok"]
    written = next(tmp_path.rglob("BTLG11.json"))
    assert json.loads(written.read_text(encoding="utf-8"))["price"] == 99.78


def test_refresh_offline_on_purpose_keeps_writing_snapshots_without_price(tmp_path):
    result = refresh_portfolio(
        tmp_path, bolsai_api_key=None, brapi_token=None, ano=2026, mes=8,
        positions=(_fii(),), fetch_fii=_fetcher(None),
    )

    assert [o.status for o in result.outcomes] == ["ok"]


def test_a_failed_position_does_not_stop_the_rest_of_the_refresh(tmp_path):
    def fetch(symbol, cnpj, ano, bolsai_api_key):
        price = None if symbol == "BAD11" else 10.0
        return {"price": price, "financials": {}}, type("R", (), {"fetched_fields": (), "warnings": ()})()

    result = refresh_portfolio(
        tmp_path, bolsai_api_key="k", brapi_token=None, ano=2026, mes=8,
        positions=(_fii("BAD11"), _fii("GOOD11")), fetch_fii=fetch,
    )

    assert {o.ticker: o.status for o in result.outcomes} == {"BAD11": "erro", "GOOD11": "ok"}


# --- analyze ---------------------------------------------------------------------------


class _Bridge:
    persisted: ClassVar[list] = []

    def __init__(self, vault):
        pass

    def sync_analysis_projection(self, report, ticker, analyzer_type):
        _Bridge.persisted.append(ticker)
        return type("P", (), {"status": type("S", (), {"value": "ok"})(), "path": "x"})()


def _analyze(price):
    _Bridge.persisted = []
    from iip.portfolio.batch_analyze import _BatchDeps

    result = analyze_portfolio(
        bolsai_api_key="k", brapi_token=None, vault_path="/vault", ano=2026, mes=8,
        positions=(_fii(),),
        deps=_BatchDeps(fetch_fii=_fetcher(price), knowledge_bridge_cls=_Bridge),
    )
    return result


def test_analyze_does_not_persist_an_analysis_built_without_a_price():
    result = _analyze(None)

    assert [o.status for o in result.outcomes] == ["erro"]
    assert "preço indisponível" in result.outcomes[0].detail
    assert _Bridge.persisted == []  # nothing written to the vault


def test_analyze_persists_when_the_price_is_there():
    result = _analyze(99.78)

    assert [o.status for o in result.outcomes] == ["ok"]
    assert _Bridge.persisted == ["BTLG11"]


# --- value -----------------------------------------------------------------------------


def _value(price):
    fetch = _fetcher(price)
    return value_portfolio(
        bolsai_api_key="k", brapi_token=None, positions=(_fii(),), fetch_fii=fetch,
        fetch_rate=lambda: RATE, ano=2026,
    )


def test_value_reports_an_error_instead_of_a_valuation_without_a_price():
    result = _value(None)

    assert [o.status for o in result.outcomes] == ["erro"]
    assert "preço indisponível" in result.outcomes[0].detail
