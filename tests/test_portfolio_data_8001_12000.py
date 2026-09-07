from iip.portfolio_data.benchmark import BenchmarkComparison
from iip.portfolio_data.currency import normalize_currency_weight
from iip.portfolio_data.data_quality import validate_weight
from iip.portfolio_data.income import IncomeEvent, annualized_income
from iip.portfolio_data.market_data import normalize_quote
from iip.portfolio_data.portfolio_data_pipeline import AssetDataBundle, to_report
from iip.portfolio_data.portfolio_report import PortfolioReport, PortfolioRow
from iip.portfolio_data.refresh import RefreshTask, prioritize
from iip.portfolio_data.valuation import ValuationMethod, build_snapshot
from iip.portfolio_data.yield_metrics import yield_on_cost, yield_on_price


def test_market_quote_normalization():
    q = normalize_quote("cpfe3", 42.5, "brl", "2026-08-29")
    assert q.ticker == "CPFE3"
    assert q.currency == "BRL"


def test_income_annualization():
    events = (
        IncomeEvent("HGRU11", "dividend", 0.10),
        IncomeEvent("HGRU11", "dividend", 0.10),
    )
    assert annualized_income(events) == 2.4


def test_class_aware_valuation():
    snapshot = build_snapshot("cpfe3", ValuationMethod.DCF, 50, 40)
    assert snapshot.margin_of_safety == 0.25


def test_yield_metrics():
    assert yield_on_price(6, 40) == 0.15
    assert yield_on_cost(6, 30) == 0.20


def test_currency():
    assert normalize_currency_weight("usd", 0.25).currency == "USD"


def test_benchmark_excess_return():
    comparison = BenchmarkComparison("SCHD", 0.12, 0.08)
    assert comparison.excess_return == 0.04


def test_portfolio_report_totals():
    report = PortfolioReport(
        "2026-08-29",
        (
            PortfolioRow("HGRU11", "fund", 100, 0.5, 12, 0.12, 8, "APORTAR"),
            PortfolioRow("CPFE3", "equity", 100, 0.5, 8, 0.08, 7, "MANTER"),
        ),
    )
    assert report.total_value == 200
    assert report.total_income == 20


def test_data_quality():
    assert validate_weight(0.25).valid
    assert not validate_weight(1.2).valid


def test_refresh_priority():
    result = prioritize(
        (
            RefreshTask("B", "b3", 2),
            RefreshTask("A", "xp", 1),
        )
    )
    assert tuple(item.ticker for item in result) == ("A", "B")


def test_portfolio_data_pipeline():
    quote = normalize_quote("XPML11", 100, "BRL", "2026-08-29")
    bundle = AssetDataBundle(
        "XPML11",
        quote,
        (IncomeEvent("XPML11", "dividend", 0.80),),
        build_snapshot("XPML11", ValuationMethod.YIELD, 110, 100),
        score=8.5,
        action="APORTAR",
    )
    report = to_report("2026-08-29", (bundle,))
    assert report.rows[0].ticker == "XPML11"
    assert report.rows[0].yield_on_price == 0.096
    assert report.rows[0].score == 8.5
