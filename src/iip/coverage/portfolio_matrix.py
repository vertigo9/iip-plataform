"""Portfolio matrix consolidation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MatrixPoint:
    ticker: str
    score: float
    risk: float
    allocation_gap: float
    action: str


def rank(points: tuple[MatrixPoint, ...]) -> tuple[MatrixPoint, ...]:
    return tuple(
        sorted(
            points,
            key=lambda x: (
                -x.score,
                x.risk,
                -x.allocation_gap,
                x.ticker.upper(),
            ),
        )
    )
