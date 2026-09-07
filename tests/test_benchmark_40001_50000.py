from iip.benchmark.alerting import threshold_alert
from iip.benchmark.attribution import attribute
from iip.benchmark.benchmark_pipeline import run
from iip.benchmark.benchmark_registry import get_benchmark
from iip.benchmark.dashboard import build
from iip.benchmark.drawdown import worst_drawdown
from iip.benchmark.models import BenchmarkPoint, BenchmarkSeries, BenchmarkType
from iip.benchmark.monitoring import ObservationCounter
from iip.benchmark.performance import compare, series_return
from iip.benchmark.risk_adjusted import sharpe_like, volatility


def make_series():
    return (
        BenchmarkPoint("2026-01", 100),
        BenchmarkPoint("2026-06", 110),
    )


def test_series_return():
    series = BenchmarkSeries("Asset", BenchmarkType.CUSTOM, make_series())
    assert series_return(series) == 0.10


def test_relative_performance():
    asset = BenchmarkSeries("CPFE3", BenchmarkType.CUSTOM, make_series())
    bench = BenchmarkSeries(
        "IBOVESPA",
        BenchmarkType.IBOVESPA,
        (BenchmarkPoint("2026-01", 100), BenchmarkPoint("2026-06", 105)),
    )
    result = compare("cpfe3", asset, bench)
    assert result.ticker == "CPFE3"
    assert result.excess_return == 0.05


def test_risk_adjusted():
    returns = (0.01, 0.02, 0.00)
    assert volatility(returns) > 0
    assert sharpe_like(returns) > 0


def test_benchmark_registry():
    assert get_benchmark("cdi").benchmark_type == BenchmarkType.CDI
    assert get_benchmark("unknown") is None


def test_attribution():
    result = attribute(
        (("Renda Urbana", 0.20, 0.10), ("Renda Urbana", 0.10, 0.05)),
        "segment",
    )
    assert result[0].value == "Renda Urbana"
    assert result[0].contribution == 0.025


def test_drawdown():
    result = worst_drawdown((100, 120, 90, 110))
    assert result.drawdown == 0.25
    assert result.peak_value == 120
    assert result.trough_value == 90


def test_monitoring():
    counter = ObservationCounter()
    counter.record(success=True)
    counter.record(success=False, stale=True)
    assert counter.observations == 2
    assert counter.success_rate == 0.5
    assert counter.stale_rate == 0.5


def test_alerting():
    assert threshold_alert("latency", 2.0, 1.0).severity == "high"
    assert threshold_alert("latency", 1.1, 1.0).severity == "medium"
    assert threshold_alert("latency", 0.5, 1.0) is None


def test_dashboard():
    snapshot = build("2026-08-29", 0.12, 0.08, 0.10, 2)
    assert snapshot.excess_return == 0.04
    assert snapshot.alerts == 2


def test_benchmark_pipeline():
    asset = BenchmarkSeries("CPFE3", BenchmarkType.CUSTOM, make_series())
    bench = BenchmarkSeries(
        "IBOVESPA",
        BenchmarkType.IBOVESPA,
        (BenchmarkPoint("2026-01", 100), BenchmarkPoint("2026-06", 105)),
    )
    result = run("CPFE3", asset, bench, (100, 120, 90), alerts=1, as_of="2026-08-29")
    assert result.relative.excess_return == 0.05
    assert result.drawdown.drawdown == 0.25
    assert result.dashboard.alerts == 1
