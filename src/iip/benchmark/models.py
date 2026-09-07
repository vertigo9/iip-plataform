"""Advanced benchmark and observability models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class BenchmarkType(StrEnum):
    CDI = "CDI"
    SELIC = "SELIC"
    IPCA = "IPCA"
    IBOVESPA = "IBOVESPA"
    IFIX = "IFIX"
    SP500 = "S&P500"
    CUSTOM = "CUSTOM"


@dataclass(frozen=True)
class BenchmarkPoint:
    date: str
    value: float


@dataclass(frozen=True)
class BenchmarkSeries:
    name: str
    benchmark_type: BenchmarkType
    points: tuple[BenchmarkPoint, ...]


@dataclass(frozen=True)
class RelativePerformance:
    ticker: str
    benchmark: str
    asset_return: float
    benchmark_return: float
    excess_return: float
