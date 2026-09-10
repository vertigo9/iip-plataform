"""Opportunity map separating intrinsic score from allocation need.

Legacy/local formula, scoped to this orchestration view only. Not used
by any other module (confirmed via audit — only this module's own
__init__.py re-export and its own test import it). Its
``combined_score`` weighting (50% intrinsic / 50% allocation need) is
locked in by ``tests/test_orchestration_16001_22000.py`` and must not
change.

For any new Opportunity Score work, use
``iip.portfolio_decision.opportunity.build`` instead — that is the
canonical implementation (also weighs income need, and is the one wired
into the persistence layer in ``iip.decision.persistence``). Do not
unify this module's formula with the canonical one: the two produce
different numbers for the same inputs, and this module's numbers are
covered by an existing passing test.
"""

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
