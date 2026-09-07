"""Income bridge for the portfolio decision cycle."""

from __future__ import annotations


def normalize_income(amount: float | None) -> float:
    if amount is None:
        return 0.0
    if amount < 0:
        raise ValueError("income must be non-negative")
    return round(float(amount), 12)
