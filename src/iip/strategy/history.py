"""Strategy history and action-change tracking."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DecisionPoint:
    as_of: str
    ticker: str
    action: str
    priority_score: float


def action_changed(previous: DecisionPoint | None, current: DecisionPoint) -> bool:
    if previous is None:
        return True
    return previous.action.upper() != current.action.upper() or round(
        previous.priority_score, 12
    ) != round(current.priority_score, 12)
