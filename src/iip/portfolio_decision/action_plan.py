"""Portfolio action plan prioritization."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ActionPlanItem:
    ticker: str
    action: str
    priority: float
    rationale: str


def prioritize(items: tuple[ActionPlanItem, ...]) -> tuple[ActionPlanItem, ...]:
    return tuple(
        sorted(
            items,
            key=lambda item: (-item.priority, item.ticker),
        )
    )
