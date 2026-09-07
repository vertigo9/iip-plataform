"""Executive strategy report."""

from __future__ import annotations

from dataclasses import dataclass

from .allocation_planner import AllocationNeed
from .income_plan import IncomePlan
from .models import StrategyDecision


@dataclass(frozen=True)
class StrategyReport:
    as_of: str
    decisions: tuple[StrategyDecision, ...]
    income_plan: IncomePlan
    allocation_needs: tuple[AllocationNeed, ...]

    @property
    def contribution_candidates(self) -> tuple[StrategyDecision, ...]:
        return tuple(item for item in self.decisions if item.action == "APORTAR")
