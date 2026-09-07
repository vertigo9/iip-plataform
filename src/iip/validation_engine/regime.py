"""Market-regime classification from explicit observations."""

from __future__ import annotations

from dataclasses import dataclass

from .models import MarketRegime


@dataclass(frozen=True)
class RegimeObservation:
    date: str
    benchmark_return: float
    volatility: float


def classify(observation: RegimeObservation) -> MarketRegime:
    if observation.benchmark_return <= -0.10 or observation.volatility >= 0.30:
        return MarketRegime.STRESS
    if observation.benchmark_return >= 0.10 and observation.volatility < 0.20:
        return MarketRegime.EXPANSION
    if observation.benchmark_return == 0 and observation.volatility == 0:
        return MarketRegime.UNKNOWN
    return MarketRegime.NORMAL
