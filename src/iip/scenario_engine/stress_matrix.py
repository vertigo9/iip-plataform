"""Scenario stress matrix."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StressPoint:
    ticker: str
    scenario: str
    score: float
    risk: float


def rank(
    points: tuple[StressPoint, ...],
) -> tuple[StressPoint, ...]:
    return tuple(
        sorted(
            points,
            key=lambda item: (
                -item.score,
                item.risk,
                item.ticker.upper(),
                item.scenario,
            ),
        )
    )
