"""Portfolio alerts from explicit rules."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PortfolioAlert:
    ticker: str
    alert_type: str
    severity: str
    detail: str


def yield_alert(
    ticker: str,
    current_yield: float,
    reference_yield: float,
) -> PortfolioAlert | None:
    if reference_yield <= 0:
        return None

    change = (current_yield / reference_yield) - 1.0

    # Severity bands:
    # <= -25% : high
    # <= -10% : medium
    # otherwise: no alert
    if change <= -0.25:
        return PortfolioAlert(ticker, "yield_drop", "high", f"change={change:.2%}")
    if change <= -0.10:
        return PortfolioAlert(ticker, "yield_drop", "medium", f"change={change:.2%}")
    return None
