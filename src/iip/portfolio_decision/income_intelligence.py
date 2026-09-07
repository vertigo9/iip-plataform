"""Portfolio income intelligence."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IncomeObservation:
    ticker: str
    annual_income: float
    weight: float
    income_growth: float = 0.0


@dataclass(frozen=True)
class IncomeSummary:
    ticker: str
    annual_income: float
    income_share: float
    growth: float


def summarize(
    observations: tuple[IncomeObservation, ...],
) -> tuple[IncomeSummary, ...]:
    total = sum(max(0.0, x.annual_income) for x in observations)
    if total <= 0:
        return tuple(
            IncomeSummary(x.ticker.upper(), 0.0, 0.0, x.income_growth)
            for x in observations
        )
    return tuple(
        IncomeSummary(
            x.ticker.upper(),
            round(max(0.0, x.annual_income), 12),
            round(max(0.0, x.annual_income) / total, 12),
            round(x.income_growth, 12),
        )
        for x in sorted(
            observations,
            key=lambda item: (-item.annual_income, item.ticker),
        )
    )
