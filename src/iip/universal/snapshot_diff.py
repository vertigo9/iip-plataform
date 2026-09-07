"""Portfolio snapshot change detection with deterministic precision."""

from __future__ import annotations

from dataclasses import dataclass

from .portfolio_state import PortfolioState


@dataclass(frozen=True)
class SnapshotChange:
    ticker: str
    previous_weight: float | None
    current_weight: float | None
    change: float | None


def diff(
    previous: PortfolioState | None, current: PortfolioState
) -> tuple[SnapshotChange, ...]:
    old = {p.ticker: p.weight for p in previous.positions} if previous else {}
    new = {p.ticker: p.weight for p in current.positions}
    tickers = sorted(set(old) | set(new))

    result = []
    for ticker in tickers:
        previous_weight = old.get(ticker)
        current_weight = new.get(ticker)
        if previous_weight is None and current_weight is None:
            change = None
        else:
            change = round(
                (current_weight or 0.0) - (previous_weight or 0.0),
                12,
            )
        result.append(
            SnapshotChange(
                ticker=ticker,
                previous_weight=previous_weight,
                current_weight=current_weight,
                change=change,
            )
        )
    return tuple(result)
