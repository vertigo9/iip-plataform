"""Opportunity radar combining decision signals and allocation gaps.

Legacy/local formula, scoped to this portfolio-intelligence view only.
Not used by any other module (confirmed via audit — only this module's
own __init__.py re-export and its own test import it). Its
``opportunity_score`` weighting (``score * (1 + gap)``) is locked in by
``tests/test_portfolio_intelligence_50001_60000.py`` and must not
change. Note this formula has no upper clamp on the output — unlike the
canonical one, ``opportunity_score`` can exceed 10 when ``gap`` is high.

For any new Opportunity Score work, use
``iip.portfolio_decision.opportunity.build`` instead — that is the
canonical implementation (also weighs income need, output bounded, and
is the one wired into the persistence layer in
``iip.decision.persistence``). Do not unify this module's formula with
the canonical one: the two produce different numbers for the same
inputs, and this module's numbers are covered by an existing passing
test.
"""

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
