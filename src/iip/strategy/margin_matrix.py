"""Valuation / margin-of-safety matrix."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MarginPoint:
    ticker: str
    margin_of_safety: float
    valuation_method: str
    confidence: float


def rank(points: tuple[MarginPoint, ...]) -> tuple[MarginPoint, ...]:
    return tuple(
        sorted(
            points,
            key=lambda x: (-x.margin_of_safety, -x.confidence, x.ticker),
        )
    )
