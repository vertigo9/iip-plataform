"""Deterministic backtest engine."""

from __future__ import annotations

from dataclasses import dataclass

from .models import DecisionOutcome, HistoricalDecision
from .returns import ReturnPoint, max_drawdown


@dataclass(frozen=True)
class BacktestResult:
    outcomes: tuple[DecisionOutcome, ...]
    cumulative_return: float
    max_drawdown: float


def run(decisions: tuple[HistoricalDecision, ...]) -> BacktestResult:
    outcomes = tuple(
        DecisionOutcome(
            ticker=d.ticker,
            action=d.action,
            score=d.score,
            realized_return=d.realized_return or 0.0,
            realized_income=d.realized_income or 0.0,
        )
        for d in decisions
        if d.realized_return is not None
    )

    points = tuple(
        ReturnPoint(str(i), 100.0 * (1.0 + outcome.realized_return))
        for i, outcome in enumerate(outcomes, start=1)
    )
    cumulative = (points[-1].value / points[0].value) - 1.0 if points else 0.0
    return BacktestResult(
        outcomes=outcomes,
        cumulative_return=cumulative,
        max_drawdown=max_drawdown(points),
    )
