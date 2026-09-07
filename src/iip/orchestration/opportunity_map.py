"""Opportunity map separating intrinsic score from allocation need."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OpportunityPoint:
    ticker: str
    intrinsic_score: float
    allocation_need: float
    combined_score: float


def build_point(
    ticker: str,
    intrinsic_score: float,
    allocation_need: float,
) -> OpportunityPoint:
    intrinsic = max(0.0, min(10.0, float(intrinsic_score)))
    need = max(0.0, min(1.0, float(allocation_need)))
    return OpportunityPoint(
        ticker.upper(),
        intrinsic,
        need,
        round(intrinsic * (0.5 + 0.5 * need), 12),
    )
