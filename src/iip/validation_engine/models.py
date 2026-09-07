"""Historical validation models for IIP decisions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class MarketRegime(StrEnum):
    EXPANSION = "expansion"
    NORMAL = "normal"
    STRESS = "stress"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class HistoricalDecision:
    date: str
    ticker: str
    score: float
    action: str
    realized_return: float | None = None
    realized_income: float | None = None
    regime: MarketRegime = MarketRegime.UNKNOWN


@dataclass(frozen=True)
class DecisionOutcome:
    ticker: str
    action: str
    score: float
    realized_return: float
    realized_income: float


@dataclass(frozen=True)
class ValidationSummary:
    observations: int
    hit_rate: float
    average_return: float
    average_income: float
    max_drawdown: float
    stress_hit_rate: float
