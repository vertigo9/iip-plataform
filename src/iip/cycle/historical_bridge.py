"""Historical decision-cycle bridge."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HistoricalPoint:
    cycle_id: str
    ticker: str
    score: float
    action: str


def detect_action_change(
    previous: HistoricalPoint | None, current: HistoricalPoint
) -> bool:
    if previous is None:
        return True
    return previous.action != current.action or previous.score != current.score
