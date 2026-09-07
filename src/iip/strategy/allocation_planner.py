"""Contribution and rebalancing planning without order execution."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AllocationNeed:
    ticker: str
    gap: float
    action: str


def plan(
    current: tuple[tuple[str, float], ...],
    target: tuple[tuple[str, float], ...],
    *,
    threshold: float = 0.01,
) -> tuple[AllocationNeed, ...]:
    cur = dict(current)
    tgt = dict(target)
    result = []
    for ticker in sorted(set(cur) | set(tgt)):
        gap = round(tgt.get(ticker, 0.0) - cur.get(ticker, 0.0), 12)
        if gap >= threshold:
            action = "AUMENTAR"
        elif gap <= -threshold:
            action = "REDUZIR"
        else:
            action = "MANTER"
        result.append(AllocationNeed(ticker.upper(), gap, action))
    return tuple(
        sorted(
            result,
            key=lambda x: (
                0 if x.action == "AUMENTAR" else 1 if x.action == "REDUZIR" else 2,
                -abs(x.gap),
                x.ticker,
            ),
        )
    )
