"""Allocation bridge using explicit existing contribution decisions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AllocationCandidate:
    ticker: str
    score: float
    weight: float


def eligible_candidates(
    observations,
    *,
    min_score: float = 8.0,
    max_weight: float = 0.30,
) -> tuple[AllocationCandidate, ...]:
    candidates = [
        AllocationCandidate(item.ticker, item.score, item.weight)
        for item in observations
        if item.action in {"APORTAR", "COMPRAR"}
        and item.score is not None
        and item.score >= min_score
        and item.weight < max_weight
    ]
    return tuple(sorted(candidates, key=lambda x: (-x.score, x.ticker)))
