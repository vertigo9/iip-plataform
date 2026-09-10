"""Opportunity ranking for portfolio decisions.

Pure ranking utility: ``Opportunity`` here holds a score computed
elsewhere (it does not compute one), and ``rank_opportunities`` only
sorts by that pre-given score. This is not a duplicate of the
Opportunity Score formula in ``iip.portfolio_decision.opportunity`` —
that module computes the score; this one just orders whatever score it
is handed.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Opportunity:
    ticker: str
    score: float
    rationale: str


def rank_opportunities(items: tuple[Opportunity, ...]) -> tuple[Opportunity, ...]:
    return tuple(sorted(items, key=lambda item: (-item.score, item.ticker)))
