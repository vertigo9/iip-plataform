"""Multi-portfolio and scenario evaluation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class Scenario:
    name: str
    parameters: tuple[tuple[str, float], ...]


@dataclass(frozen=True)
class ScenarioResult:
    name: str
    score: float


def evaluate(
    scenarios: tuple[Scenario, ...],
    evaluator: Callable[[Scenario], float],
) -> tuple[ScenarioResult, ...]:
    return tuple(
        ScenarioResult(
            scenario.name,
            round(float(evaluator(scenario)), 12),
        )
        for scenario in scenarios
    )
