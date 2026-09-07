"""Historical decision validation summary."""

from __future__ import annotations

from .backtest import run
from .hit_rate import hit_rate, regime_hit_rate
from .models import HistoricalDecision, MarketRegime, ValidationSummary


def summarize(decisions: tuple[HistoricalDecision, ...]) -> ValidationSummary:
    result = run(decisions)
    evaluated = result.outcomes

    avg_return = (
        sum(item.realized_return for item in evaluated) / len(evaluated)
        if evaluated
        else 0.0
    )
    avg_income = (
        sum(item.realized_income for item in evaluated) / len(evaluated)
        if evaluated
        else 0.0
    )

    return ValidationSummary(
        observations=len(evaluated),
        hit_rate=hit_rate(decisions),
        average_return=avg_return,
        average_income=avg_income,
        max_drawdown=result.max_drawdown,
        stress_hit_rate=regime_hit_rate(decisions, MarketRegime.STRESS),
    )
