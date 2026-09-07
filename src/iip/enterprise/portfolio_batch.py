"""Enterprise-scale portfolio batching and partitioning."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class PortfolioPartition:
    index: int
    tickers: tuple[str, ...]


def partition(tickers: Iterable[str], size: int = 10) -> tuple[PortfolioPartition, ...]:
    if size <= 0:
        raise ValueError("size must be positive")
    values = [ticker.upper() for ticker in tickers]
    return tuple(
        PortfolioPartition(
            index=i,
            tickers=tuple(values[i : i + size]),
        )
        for i in range(0, len(values), size)
    )
