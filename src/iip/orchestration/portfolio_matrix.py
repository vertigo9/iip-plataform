"""Portfolio decision matrix by class/segment/risk."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MatrixEntry:
    ticker: str
    asset_class: str
    segment: str | None
    risk: str
    score: float
    action: str


def sort_matrix(entries: tuple[MatrixEntry, ...]) -> tuple[MatrixEntry, ...]:
    return tuple(
        sorted(
            entries,
            key=lambda item: (-item.score, item.risk, item.ticker),
        )
    )
