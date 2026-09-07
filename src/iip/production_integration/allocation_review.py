"""Human-review allocation gate."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AllocationReview:
    ticker: str
    suggested_action: str
    estimated_weight: float
    manual_review_required: bool
    reason: str


def build(
    ticker: str,
    suggested_action: str,
    estimated_weight: float,
    *,
    concentration_breach: bool = False,
    high_risk: bool = False,
) -> AllocationReview:
    if concentration_breach:
        reason = "concentration"
    elif high_risk:
        reason = "risk"
    else:
        reason = "standard"

    return AllocationReview(
        ticker.upper(),
        suggested_action.upper(),
        max(0.0, min(1.0, estimated_weight)),
        concentration_breach or high_risk,
        reason,
    )
