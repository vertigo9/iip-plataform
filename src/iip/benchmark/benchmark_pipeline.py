"""Integrated benchmark/observability pipeline."""

from __future__ import annotations

from dataclasses import dataclass

from .dashboard import DashboardSnapshot, build
from .drawdown import DrawdownDiagnostic, worst_drawdown
from .models import BenchmarkSeries, RelativePerformance
from .performance import compare


@dataclass(frozen=True)
class BenchmarkPipelineResult:
    relative: RelativePerformance
    drawdown: DrawdownDiagnostic
    dashboard: DashboardSnapshot


def run(
    ticker: str,
    asset_series: BenchmarkSeries,
    benchmark_series: BenchmarkSeries,
    asset_values: tuple[float, ...],
    alerts: int = 0,
    as_of: str = "",
) -> BenchmarkPipelineResult:
    relative = compare(ticker, asset_series, benchmark_series)
    drawdown = worst_drawdown(asset_values)
    dashboard = build(
        as_of,
        relative.asset_return,
        relative.benchmark_return,
        drawdown.drawdown,
        alerts,
    )
    return BenchmarkPipelineResult(relative, drawdown, dashboard)
