"""Deterministic rebalancing needs, prioritizing increases before reductions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RebalanceNeed:
    ticker: str
    current_weight: float
    target_weight: float

    @property
    def delta(self) -> float:
        return round(self.target_weight - self.current_weight, 12)


def compute_needs(
    current: tuple[tuple[str, float], ...],
    targets: tuple[tuple[str, float], ...],
) -> tuple[RebalanceNeed, ...]:
    cur = dict(current)
    tgt = dict(targets)
    needs = [
        RebalanceNeed(
            ticker,
            cur.get(ticker, 0.0),
            tgt.get(ticker, 0.0),
        )
        for ticker in sorted(set(cur) | set(tgt))
    ]

    # Operational ordering:
    # 1) underweight / positive delta first;
    # 2) reductions / negative delta after;
    # 3) deterministic ticker tie-break.
    return tuple(
        sorted(
            needs,
            key=lambda item: (
                0 if item.delta > 0 else 1 if item.delta < 0 else 2,
                -item.delta if item.delta > 0 else item.delta,
                item.ticker,
            ),
        )
    )
