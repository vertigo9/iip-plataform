"""Stable decision query facade."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DecisionView:
    ticker: str
    action: str
    score: float
    confidence: float
    rationale: tuple[str, ...]


def view(
    ticker: str,
    action: str,
    score: float,
    confidence: float,
    rationale: tuple[str, ...] = (),
) -> DecisionView:
    return DecisionView(
        ticker.upper(),
        action.upper(),
        max(0.0, min(10.0, float(score))),
        max(0.0, min(1.0, float(confidence))),
        tuple(dict.fromkeys(rationale)),
    )
