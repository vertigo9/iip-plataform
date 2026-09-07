"""Portfolio strategy and allocation contracts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StrategyInput:
    ticker: str
    score: float
    confidence: float
    income_yield: float
    margin_of_safety: float
    risk_score: float
    current_weight: float
    target_weight: float


@dataclass(frozen=True)
class StrategySignal:
    ticker: str
    quality_score: float
    income_score: float
    valuation_score: float
    risk_score: float
    allocation_gap: float


@dataclass(frozen=True)
class StrategyDecision:
    ticker: str
    priority_score: float
    action: str
    rationale: tuple[str, ...]
