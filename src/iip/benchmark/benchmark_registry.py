"""Explicit benchmark registry."""

from __future__ import annotations

from dataclasses import dataclass

from .models import BenchmarkType


@dataclass(frozen=True)
class BenchmarkDefinition:
    name: str
    benchmark_type: BenchmarkType
    currency: str
    source: str


DEFAULT_BENCHMARKS = (
    BenchmarkDefinition("CDI", BenchmarkType.CDI, "BRL", "explicit-input"),
    BenchmarkDefinition("SELIC", BenchmarkType.SELIC, "BRL", "explicit-input"),
    BenchmarkDefinition("IPCA", BenchmarkType.IPCA, "BRL", "explicit-input"),
    BenchmarkDefinition("IBOVESPA", BenchmarkType.IBOVESPA, "BRL", "explicit-input"),
    BenchmarkDefinition("IFIX", BenchmarkType.IFIX, "BRL", "explicit-input"),
    BenchmarkDefinition("S&P500", BenchmarkType.SP500, "USD", "explicit-input"),
)


def get_benchmark(name: str) -> BenchmarkDefinition | None:
    target = name.casefold()
    return next(
        (item for item in DEFAULT_BENCHMARKS if item.name.casefold() == target),
        None,
    )
