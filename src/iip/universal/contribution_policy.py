"""Portfolio contribution allocation policy."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ContributionRule:
    minimum_score: float
    minimum_confidence: float
    max_position_weight: float


@dataclass(frozen=True)
class ContributionDecision:
    ticker: str
    eligible: bool
    reason: str


def evaluate(
    ticker: str,
    score: float,
    confidence: float,
    current_weight: float,
    rule: ContributionRule,
) -> ContributionDecision:
    if score < rule.minimum_score:
        return ContributionDecision(ticker, False, "score_below_minimum")
    if confidence < rule.minimum_confidence:
        return ContributionDecision(ticker, False, "confidence_below_minimum")
    if current_weight >= rule.max_position_weight:
        return ContributionDecision(ticker, False, "position_above_limit")
    return ContributionDecision(ticker, True, "eligible")
