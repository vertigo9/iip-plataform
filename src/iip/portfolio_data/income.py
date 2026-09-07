"""Income/proventos normalization."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IncomeEvent:
    ticker: str
    kind: str
    amount_per_unit: float
    ex_date: str | None = None
    payment_date: str | None = None


def annualized_income(events: tuple[IncomeEvent, ...], periods: int = 12) -> float:
    if periods <= 0:
        raise ValueError("periods must be positive")
    return round(sum(max(0.0, e.amount_per_unit) for e in events) * periods, 12)
