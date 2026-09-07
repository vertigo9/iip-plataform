"""Opportunity ranking for portfolio decisions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Opportunity:
    ticker: str
    score: float
    rationale: str


def rank_opportunities(items: tuple[Opportunity, ...]) -> tuple[Opportunity, ...]:
    return tuple(sorted(items, key=lambda item: (-item.score, item.ticker)))
