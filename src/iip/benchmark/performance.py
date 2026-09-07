"""Performance and benchmark comparison calculations."""

from __future__ import annotations

from iip.validation_engine.returns import simple_return

from .models import BenchmarkSeries, RelativePerformance


def series_return(series: BenchmarkSeries) -> float:
    if len(series.points) < 2:
        return 0.0
    return simple_return(series.points[0].value, series.points[-1].value)


def compare(
    ticker: str,
    asset_series: BenchmarkSeries,
    benchmark_series: BenchmarkSeries,
) -> RelativePerformance:
    asset_return = series_return(asset_series)
    benchmark_return = series_return(benchmark_series)
    return RelativePerformance(
        ticker=ticker.upper(),
        benchmark=benchmark_series.name,
        asset_return=asset_return,
        benchmark_return=benchmark_return,
        excess_return=round(asset_return - benchmark_return, 12),
    )
