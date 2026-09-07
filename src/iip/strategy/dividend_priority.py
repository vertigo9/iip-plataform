"""Dividend priority ranking."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DividendCandidate:
    ticker: str
    yield_on_price: float
    sustainability: float
    growth: float
    weight: float


def rank(candidates: tuple[DividendCandidate, ...]) -> tuple[DividendCandidate, ...]:
    return tuple(
        sorted(
            candidates,
            key=lambda x: (
                -(x.yield_on_price * 0.45 + x.sustainability * 0.35 + x.growth * 0.20),
                x.ticker,
            ),
        )
    )
