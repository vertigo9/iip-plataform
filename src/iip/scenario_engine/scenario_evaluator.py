"""Deterministic scenario evaluation."""

from __future__ import annotations

from .models import Scenario, ScenarioScore


def evaluate(
    scenario: Scenario,
    evaluator,
    threshold: float = 5.0,
) -> ScenarioScore:
    score = round(float(evaluator(scenario)), 12)
    return ScenarioScore(scenario.name, score, score >= threshold)


def evaluate_many(
    scenarios: tuple[Scenario, ...],
    evaluator,
    threshold: float = 5.0,
) -> tuple[ScenarioScore, ...]:
    return tuple(evaluate(scenario, evaluator, threshold) for scenario in scenarios)
