"""Scenario report."""

from __future__ import annotations

from dataclasses import dataclass

from .decision_stability import StabilityResult


@dataclass(frozen=True)
class ScenarioReport:
    as_of: str
    stability: tuple[StabilityResult, ...]

    @property
    def stable_count(self) -> int:
        return sum(item.stable for item in self.stability)

    @property
    def changed_count(self) -> int:
        return sum(item.action_changed for item in self.stability)
