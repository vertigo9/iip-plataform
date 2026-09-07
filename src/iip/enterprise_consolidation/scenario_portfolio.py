"""Enterprise portfolio scenario aggregation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PortfolioScenarioPoint:
    portfolio_id: str
    scenario: str
    score: float


def rank(
    points: tuple[PortfolioScenarioPoint, ...],
) -> tuple[PortfolioScenarioPoint, ...]:
    return tuple(
        sorted(
            points,
            key=lambda item: (-item.score, item.portfolio_id, item.scenario),
        )
    )
