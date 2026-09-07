"""Portfolio-wide scenario aggregation."""

from __future__ import annotations

from dataclasses import dataclass

from .models import ScenarioScore


@dataclass(frozen=True)
class PortfolioScenario:
    name: str
    scores: tuple[ScenarioScore, ...]


@dataclass(frozen=True)
class PortfolioScenarioResult:
    name: str
    average_score: float
    pass_rate: float


def summarize(
    scenario: PortfolioScenario,
) -> PortfolioScenarioResult:
    total = len(scenario.scores)
    if total == 0:
        return PortfolioScenarioResult(scenario.name, 0.0, 0.0)
    average = sum(item.score for item in scenario.scores) / total
    passed = sum(item.passed for item in scenario.scores)
    return PortfolioScenarioResult(
        scenario.name,
        round(average, 12),
        round(passed / total, 12),
    )
