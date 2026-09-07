"""Benchmark comparison contracts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BenchmarkComparison:
    ticker: str
    asset_return: float
    benchmark_return: float

    @property
    def excess_return(self) -> float:
        return round(self.asset_return - self.benchmark_return, 12)
