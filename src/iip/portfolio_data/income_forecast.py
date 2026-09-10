"""Income/proventos forecasting.

Simple moving-average projection over an official monthly distribution
series (e.g. the "R$/cota" series a fund manager publishes). Chosen
over a linear-trend regression deliberately: with as few as ~12 monthly
points, a fitted trend implies more precision than the sample supports,
and the vault's own distribution notes already warn against filling
gaps or projecting without documental basis. A moving average is
honest about what it is — a plain average of the last N observations —
and the output always declares which periods and how many of them went
into it.

Uses the standard-library ``statistics`` module, matching the existing
convention in ``iip.adaptive.anomaly`` and
``iip.benchmark.risk_adjusted`` — no numpy/pandas/scipy dependency
exists anywhere in this codebase (confirmed by audit), so this module
does not introduce one.

Deliberately not built on ``IncomeEvent`` (``iip.portfolio_data.income``):
that model represents discrete income events with a ``kind`` and
optional dates, suited to per-payment records. An official monthly
series from a management report is a different shape — one amount per
calendar month, no per-event metadata — so it gets its own minimal
``MonthlyDistribution`` pair here rather than overloading
``IncomeEvent`` with fields it doesn't need.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean


@dataclass(frozen=True)
class MonthlyDistribution:
    period: str  # "YYYY-MM"
    amount_per_unit: float


@dataclass(frozen=True)
class IncomeForecast:
    ticker: str
    method: str
    window: int
    sample_size: int
    periods_used: tuple[str, ...]
    projected_amount_per_unit: float


def forecast_next_distribution(
    ticker: str,
    history: tuple[MonthlyDistribution, ...],
    *,
    window: int = 3,
) -> IncomeForecast:
    """Project the next month's distribution as the average of the last
    ``window`` known months.

    If fewer than ``window`` months are available, uses whatever is
    available and reports the true ``sample_size`` — it never pretends
    to have averaged over ``window`` months when it did not.
    """

    if window <= 0:
        raise ValueError("window must be positive")
    if not history:
        raise ValueError("history must not be empty")

    ordered = tuple(sorted(history, key=lambda item: item.period))
    seen_periods = [item.period for item in ordered]
    if len(seen_periods) != len(set(seen_periods)):
        raise ValueError("history contains duplicate periods")

    sample = ordered[-window:]
    projected = round(mean(item.amount_per_unit for item in sample), 12)

    return IncomeForecast(
        ticker=ticker.strip().upper(),
        method=f"moving_average_{window}m",
        window=window,
        sample_size=len(sample),
        periods_used=tuple(item.period for item in sample),
        projected_amount_per_unit=projected,
    )
