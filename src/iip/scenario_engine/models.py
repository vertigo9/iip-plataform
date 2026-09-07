"""Scenario and validation contracts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Scenario:
    name: str
    parameters: tuple[tuple[str, float], ...]


@dataclass(frozen=True)
class ScenarioScore:
    scenario: str
    score: float
    passed: bool


@dataclass(frozen=True)
class DecisionScenario:
    ticker: str
    baseline_action: str
    stressed_action: str
    baseline_score: float
    stressed_score: float


@dataclass(frozen=True)
class StabilityResult:
    ticker: str
    stable: bool
    action_changed: bool
    score_delta: float
