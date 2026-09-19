"""Portfolio risk synthesis with concentration-first review priority."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskObservation:
    ticker: str
    risk_score: float
    portfolio_weight: float
    concentration_flag: bool


@dataclass(frozen=True)
class RiskSynthesis:
    ticker: str
    risk_score: float
    adjusted_risk: float
    review_required: bool


def synthesize(
    observations: tuple[RiskObservation, ...],
) -> tuple[RiskSynthesis, ...]:
    results = []
    for item in observations:
        penalty = 1.5 if item.concentration_flag else 0.0
        adjusted = max(0.0, min(10.0, item.risk_score + penalty))
        results.append(
            RiskSynthesis(
                item.ticker.upper(),
                round(item.risk_score, 12),
                round(adjusted, 12),
                bool(item.concentration_flag or item.risk_score >= 7),
            )
        )

    # Review priority is independent from raw risk magnitude:
    # concentration breaches must surface first for portfolio oversight.
    return tuple(
        sorted(
            results,
            key=lambda item: (
                (
                    0
                    if item.review_required and item.adjusted_risk < 7
                    else 1 if item.review_required else 2
                ),
                -item.adjusted_risk,
                item.ticker,
            ),
        )
    )
