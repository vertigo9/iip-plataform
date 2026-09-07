"""Opportunity radar combining decision signals and allocation gaps."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OpportunityPoint:
    ticker: str
    decision_score: float
    allocation_gap: float
    opportunity_score: float


def build(
    ticker: str,
    decision_score: float,
    allocation_gap: float,
) -> OpportunityPoint:
    score = max(0.0, min(10.0, float(decision_score)))
    gap = max(0.0, min(1.0, float(allocation_gap)))
    return OpportunityPoint(
        ticker.upper(),
        score,
        gap,
        round(score * (1 + gap), 12),
    )
